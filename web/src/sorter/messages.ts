/** Messages between the sorter client and its Web Worker. */
export type Device = "webgpu" | "wasm";

export type WorkerRequest = { type: "load" } | { type: "embed"; id: number; texts: string[] };

export interface ReadyInfo {
  device: Device;
  model: string;
  /** Bytes downloaded for the model and tokenizer files. */
  sizeBytes: number;
  loadMs: number;
}

export type WorkerResponse =
  | { type: "progress"; loaded: number; total: number; file: string }
  | ({ type: "ready" } & ReadyInfo)
  | { type: "embedded"; id: number; vectors: Float32Array[]; ms: number }
  | { type: "error"; id?: number; message: string };
