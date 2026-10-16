/** Messages between the sorter client and its Web Worker. */
export type Device = "webgpu" | "wasm";

export type WorkerRequest =
  /** Load the model. `device` forces a backend; otherwise WebGPU when an adapter is handed out, else WASM. */
  { type: "load"; device?: Device } | { type: "embed"; id: number; texts: string[] };

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
  /** `device` names the backend a failed load was trying; the client retries a WebGPU failure on WASM in a fresh worker. */
  | { type: "error"; id?: number; message: string; device?: Device };
