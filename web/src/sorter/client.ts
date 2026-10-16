import type { ReadyInfo, WorkerRequest, WorkerResponse } from "./messages";

export type SorterStatus = "idle" | "loading" | "ready" | "error";

export interface SorterProgress {
  loaded: number;
  total: number;
  /** 0 to 1 across every file seen so far. */
  fraction: number;
  file: string | null;
}

export interface SorterSnapshot {
  status: SorterStatus;
  progress: SorterProgress;
  ready: ReadyInfo | null;
  error: string | null;
  /** Milliseconds the worker spent on the latest embedding call. */
  lastEmbedMs: number | null;
}

interface Pending {
  resolve: (vectors: Float32Array[]) => void;
  reject: (error: Error) => void;
}

const INITIAL: SorterSnapshot = {
  status: "idle",
  progress: { loaded: 0, total: 0, fraction: 0, file: null },
  ready: null,
  error: null,
  lastEmbedMs: null,
};

/**
 * Talks to the sorter worker. `load()` is idempotent and can start early (the
 * quiz starts it); `embed()` waits for the model. The snapshot feeds React
 * through useSyncExternalStore (see src/state/useSorter.ts).
 */
export class SorterClient {
  private worker: Worker | null = null;
  private loadPromise: Promise<ReadyInfo> | null = null;
  private loadResolvers: { resolve: (info: ReadyInfo) => void; reject: (e: Error) => void } | null =
    null;
  private readonly pending = new Map<number, Pending>();
  private nextId = 1;
  private readonly files = new Map<string, { loaded: number; total: number }>();
  private readonly listeners = new Set<() => void>();
  private snapshot: SorterSnapshot = INITIAL;
  /** True once a failed WebGPU load has been retried on WASM in a fresh worker. */
  private retriedOnWasm = false;
  private readonly createWorker: () => Worker;

  constructor(createWorker?: () => Worker) {
    this.createWorker =
      createWorker ??
      (() => new Worker(new URL("./worker.ts", import.meta.url), { type: "module" }));
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getSnapshot = (): SorterSnapshot => this.snapshot;

  /** Start loading the model (once). Resolves when the worker is ready. */
  load(): Promise<ReadyInfo> {
    if (this.loadPromise && this.snapshot.status !== "error") return this.loadPromise;
    this.files.clear();
    this.retriedOnWasm = false;
    this.loadPromise = new Promise<ReadyInfo>((resolve, reject) => {
      this.loadResolvers = { resolve, reject };
    });
    // Callers may ignore the promise; keep an unhandled rejection from surfacing.
    this.loadPromise.catch(() => undefined);
    this.update({ status: "loading", error: null });
    this.send({ type: "load" });
    return this.loadPromise;
  }

  /** Embed texts in the worker; starts the load if needed. */
  async embed(texts: string[]): Promise<Float32Array[]> {
    if (texts.length === 0) return [];
    await this.load();
    const id = this.nextId;
    this.nextId += 1;
    return new Promise<Float32Array[]>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.send({ type: "embed", id, texts });
    });
  }

  /** Stop the worker and forget its state. */
  dispose(): void {
    this.worker?.terminate();
    this.worker = null;
    this.loadPromise = null;
    this.loadResolvers = null;
    for (const p of this.pending.values()) p.reject(new Error("Sorter disposed"));
    this.pending.clear();
    this.files.clear();
    this.update(INITIAL);
  }

  private send(message: WorkerRequest): void {
    if (!this.worker) {
      this.worker = this.createWorker();
      this.worker.addEventListener("message", (event: MessageEvent<WorkerResponse>) => {
        this.handle(event.data);
      });
      this.worker.addEventListener("error", (event: ErrorEvent) => {
        this.fail(event.message || "The sorter worker failed");
      });
    }
    this.worker.postMessage(message);
  }

  private handle(message: WorkerResponse): void {
    switch (message.type) {
      case "progress": {
        this.files.set(message.file, { loaded: message.loaded, total: message.total });
        let loaded = 0;
        let total = 0;
        for (const f of this.files.values()) {
          loaded += f.loaded;
          total += f.total;
        }
        this.update({
          progress: { loaded, total, fraction: total > 0 ? loaded / total : 0, file: message.file },
        });
        break;
      }
      case "ready": {
        const info: ReadyInfo = {
          device: message.device,
          model: message.model,
          sizeBytes: message.sizeBytes,
          loadMs: message.loadMs,
        };
        this.update({
          status: "ready",
          ready: info,
          progress: { ...this.snapshot.progress, fraction: 1 },
        });
        this.loadResolvers?.resolve(info);
        break;
      }
      case "embedded": {
        const pending = this.pending.get(message.id);
        this.pending.delete(message.id);
        this.update({ lastEmbedMs: message.ms });
        pending?.resolve(message.vectors);
        break;
      }
      case "error": {
        if (message.id !== undefined) {
          const pending = this.pending.get(message.id);
          this.pending.delete(message.id);
          pending?.reject(new Error(message.message));
        } else if (message.device === "webgpu" && !this.retriedOnWasm) {
          // A WebGPU session that fails poisons its worker (see worker.ts): start afresh on WASM.
          this.retriedOnWasm = true;
          this.restartWorker();
          this.send({ type: "load", device: "wasm" });
        } else {
          this.fail(message.message);
        }
        break;
      }
    }
  }

  private restartWorker(): void {
    this.worker?.terminate();
    this.worker = null;
    this.files.clear();
    for (const p of this.pending.values()) p.reject(new Error("Sorter restarted"));
    this.pending.clear();
    this.update({ progress: { loaded: 0, total: 0, fraction: 0, file: null } });
  }

  private fail(message: string): void {
    this.update({ status: "error", error: message });
    this.loadResolvers?.reject(new Error(message));
    for (const p of this.pending.values()) p.reject(new Error(message));
    this.pending.clear();
  }

  private update(patch: Partial<SorterSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...patch };
    for (const listener of this.listeners) listener();
  }
}

/** The app's single sorter. The worker is created on first use. */
export const sorter = new SorterClient();
