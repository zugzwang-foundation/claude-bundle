import { env, pipeline } from "@huggingface/transformers";
import type { Device, WorkerRequest, WorkerResponse } from "./messages";
import manifest from "./model-manifest.json";

type Dtype = "fp32" | "fp16" | "q8" | "int8" | "uint8" | "q4" | "bnb4" | "q4f16";

interface ProgressEvent {
  status: string;
  file?: string;
  loaded?: number;
  total?: number;
}

/** The subset of the worker scope we use; the DOM lib types `self` as a Window. */
interface WorkerScope {
  postMessage(message: WorkerResponse, transfer?: Transferable[]): void;
  addEventListener(type: "message", listener: (event: MessageEvent<WorkerRequest>) => void): void;
}

/** The one WebGPU call we make; the DOM lib does not type navigator.gpu. */
interface GpuNavigator {
  gpu?: { requestAdapter(): Promise<object | null> };
}

type Extractor = (
  texts: string[],
  options: { pooling: "mean"; normalize: boolean },
) => Promise<{ dims: number[]; data: ArrayLike<number> }>;

const scope = self as unknown as WorkerScope;
const base = import.meta.env.BASE_URL;

// The ONNX runtime's wasm files are served from this origin, never from a CDN:
// scripts/copy-ort.mjs puts them in public/ort/ for the build. The dev server
// refuses a dynamic import out of public/, so there they come straight from
// node_modules, which Vite serves and transforms like any other module.
if (env.backends.onnx.wasm) {
  env.backends.onnx.wasm.wasmPaths = import.meta.env.DEV
    ? `${base}node_modules/onnxruntime-web/dist/`
    : `${base}ort/`;
}

if (manifest.source === "local") {
  env.allowLocalModels = true;
  env.allowRemoteModels = false;
  env.localModelPath = `${base}models/`;
} else {
  env.allowLocalModels = false;
  env.allowRemoteModels = true;
}

let extractor: Extractor | null = null;
let loading: Promise<void> | null = null;
let attempted: Device | null = null;

function post(message: WorkerResponse, transfer?: Transferable[]): void {
  scope.postMessage(message, transfer);
}

/**
 * WebGPU only when the browser actually hands out an adapter. Headless and some
 * mobile browsers expose navigator.gpu with none, and a WebGPU session that
 * fails poisons every later session in this worker: Transformers.js chains
 * session creation on one promise that never recovers from a rejection. So the
 * choice is made up front, and a failure is retried by the client in a fresh
 * worker with `device: "wasm"` rather than here.
 */
async function pickDevice(forced?: Device): Promise<Device> {
  if (forced) return forced;
  const gpu = (navigator as unknown as GpuNavigator).gpu;
  if (!gpu) return "wasm";
  try {
    return (await gpu.requestAdapter()) ? "webgpu" : "wasm";
  } catch {
    return "wasm";
  }
}

async function createExtractor(device: Device, onProgress: (p: ProgressEvent) => void) {
  const result = await pipeline("feature-extraction", manifest.id, {
    dtype: manifest.dtype as Dtype,
    device,
    progress_callback: onProgress as never,
  });
  return result as unknown as Extractor;
}

async function load(forced?: Device): Promise<void> {
  const t0 = performance.now();
  const files = new Map<string, number>();
  const onProgress = (p: ProgressEvent) => {
    if (p.status === "progress" && p.file && p.total) {
      files.set(p.file, p.total);
      post({ type: "progress", loaded: p.loaded ?? 0, total: p.total, file: p.file });
    }
  };
  const device = await pickDevice(forced);
  attempted = device;
  extractor = await createExtractor(device, onProgress);
  let sizeBytes = 0;
  for (const total of files.values()) sizeBytes += total;
  post({ type: "ready", device, model: manifest.id, sizeBytes, loadMs: performance.now() - t0 });
}

/** Start the load, or join the one under way. A failed load is forgotten, so the next request tries again. */
function startLoad(forced?: Device): Promise<void> {
  if (!loading) {
    loading = load(forced).catch((error: unknown) => {
      loading = null;
      post({
        type: "error",
        message: error instanceof Error ? error.message : String(error),
        device: attempted ?? undefined,
      });
      throw error;
    });
    loading.catch(() => undefined);
  }
  return loading;
}

async function embed(id: number, texts: string[]): Promise<void> {
  await startLoad();
  if (!extractor) throw new Error("Model not loaded");
  const t0 = performance.now();
  const output = await extractor(texts, { pooling: "mean", normalize: true });
  const dim = output.dims[1] ?? 0;
  const data = Float32Array.from(output.data);
  const vectors = texts.map((_, i) => data.slice(i * dim, (i + 1) * dim));
  post(
    { type: "embedded", id, vectors, ms: performance.now() - t0 },
    vectors.map((v) => v.buffer),
  );
}

scope.addEventListener("message", (event) => {
  const message = event.data;
  if (message.type === "load") {
    // A failure is reported by startLoad itself.
    startLoad(message.device).catch(() => undefined);
    return;
  }
  if (message.type === "embed") {
    embed(message.id, message.texts).catch((error: unknown) => {
      post({
        type: "error",
        id: message.id,
        message: error instanceof Error ? error.message : String(error),
      });
    });
  }
});
