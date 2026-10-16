// W6 parity: embed the 32 parity texts with Transformers.js in Node and time single decisions.
//
// Run from the web worktree so that "@huggingface/transformers" resolves from its node_modules
// (the pipeline worktree has none); the script is fed on stdin so no file is copied there:
//
//   cd <checkout>/web && \
//   PARITY_PIPELINE_DIR=<checkout>/pipeline node --input-type=module < <checkout>/pipeline/scripts/w6_parity_node.mjs
//
// Environment: PARITY_PIPELINE_DIR (the pipeline/ directory; required unless the three path
// knobs below are all set), and optionally PARITY_TEXTS, PARITY_MODELS_DIR (parent of the export
// directory), PARITY_MODEL_ID (the export directory's name), PARITY_OUT_DIR, PARITY_DTYPES (comma list).
// Writes <out>/parity-node-<dtype>.json per dtype (vectors, token ids, timings) and
// <out>/parity-node-errors.json when a dtype fails to load.
import { readFileSync, writeFileSync } from "node:fs";
import { performance } from "node:perf_hooks";
import { env, pipeline } from "@huggingface/transformers";

const PIPE = process.env.PARITY_PIPELINE_DIR;
if (!PIPE && !(process.env.PARITY_TEXTS && process.env.PARITY_MODELS_DIR && process.env.PARITY_OUT_DIR)) {
  console.error("set PARITY_PIPELINE_DIR to the pipeline/ directory (or PARITY_TEXTS, PARITY_MODELS_DIR and PARITY_OUT_DIR)");
  process.exit(2);
}
const textsPath = process.env.PARITY_TEXTS ?? `${PIPE}/data/runs/parity-texts.json`;
const modelsDir = process.env.PARITY_MODELS_DIR ?? `${PIPE}/data/models`;
const modelId = process.env.PARITY_MODEL_ID ?? "student-v0-onnx";
const outDir = process.env.PARITY_OUT_DIR ?? `${PIPE}/data/runs`;
const dtypes = (process.env.PARITY_DTYPES ?? "q8,fp32").split(",");
const TIMED = 40;

env.allowLocalModels = true;
env.allowRemoteModels = false;
env.localModelPath = modelsDir;

const texts = JSON.parse(readFileSync(textsPath, "utf8")).texts;
const pkg = (p) => JSON.parse(readFileSync(`node_modules/${p}/package.json`, "utf8")).version;
const versions = {
  node: process.version,
  "@huggingface/transformers": pkg("@huggingface/transformers"),
  "onnxruntime-node": pkg("onnxruntime-node"),
  "onnxruntime-common": pkg("onnxruntime-common"),
};
console.log("versions", JSON.stringify(versions));
console.log(`texts ${texts.length} from ${textsPath}`);
console.log(`localModelPath ${env.localModelPath}, model id ${modelId}, dtypes ${dtypes.join(",")}`);

const stats = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  const q = (p) => s[Math.min(s.length - 1, Math.floor(p * (s.length - 1) + 0.5))];
  return {
    n: s.length,
    min: s[0],
    median: s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2,
    p90: q(0.9),
    max: s[s.length - 1],
    mean: s.reduce((a, b) => a + b, 0) / s.length,
  };
};
const round = (x) => Math.round(x * 1000) / 1000;
const errors = [];

for (const dtype of dtypes) {
  console.log(`\n== dtype ${dtype} ==`);
  const t0 = performance.now();
  let extractor;
  try {
    extractor = await pipeline("feature-extraction", modelId, { dtype, device: "cpu" });
  } catch (e) {
    const rec = { dtype, error: String(e?.message ?? e), stack: String(e?.stack ?? "").split("\n").slice(0, 6) };
    console.log("LOAD FAILED:", rec.error);
    errors.push(rec);
    continue;
  }
  const loadMs = performance.now() - t0;
  const rss = process.memoryUsage().rss;

  let sessionInfo = null;
  try {
    const s = extractor.model?.sessions?.model;
    sessionInfo = {
      inputNames: s?.inputNames ?? null,
      outputNames: s?.outputNames ?? null,
      config: s?.config ?? null,
      modelType: extractor.model?.config?.model_type ?? null,
    };
  } catch {
    sessionInfo = null;
  }

  const tok = extractor.tokenizer(texts, { padding: true, truncation: true });
  const tokenIds = tok.input_ids
    .tolist()
    .map((row, i) => row.map(Number).filter((_, j) => Number(tok.attention_mask.tolist()[i][j]) === 1));
  const paddedLen = tok.input_ids.dims[1];

  const tb = performance.now();
  const out = await extractor(texts, { pooling: "mean", normalize: true });
  const batchMs = performance.now() - tb;
  const dim = out.dims[1];
  const vectorsBatch = out.tolist();

  const vectorsSingle = [];
  const singleMs = [];
  for (const t of texts) {
    const s = performance.now();
    const o = await extractor([t], { pooling: "mean", normalize: true });
    singleMs.push(performance.now() - s);
    vectorsSingle.push(o.tolist()[0]);
  }

  const timed = [];
  for (let i = 0; i < TIMED; i++) {
    const s = performance.now();
    await extractor([texts[i % texts.length]], { pooling: "mean", normalize: true });
    timed.push(performance.now() - s);
  }

  const result = {
    dtype,
    modelId,
    localModelPath: modelsDir,
    device: "cpu",
    fileLoaded: `${modelId}/onnx/model${dtype === "fp32" ? "" : dtype === "q8" ? "_quantized" : `_${dtype}`}.onnx`,
    versions,
    sessionInfo,
    n: texts.length,
    dim,
    paddedLen,
    tokenIds,
    loadMs: round(loadMs),
    rssMBAfterLoad: round(rss / 1e6),
    batch32Ms: round(batchMs),
    singleMs: singleMs.map(round),
    timed40Ms: timed.map(round),
    timed40Stats: Object.fromEntries(Object.entries(stats(timed)).map(([k, v]) => [k, round(v)])),
    vectorsBatch,
    vectorsSingle,
  };
  writeFileSync(`${outDir}/parity-node-${dtype}.json`, `${JSON.stringify(result)}\n`);
  console.log(`load ${result.loadMs} ms, rss ${result.rssMBAfterLoad} MB, dim ${dim}, padded length ${paddedLen}`);
  console.log(`batch of 32: ${result.batch32Ms} ms; first single ${round(singleMs[0])} ms`);
  console.log(`40 single decisions (ms): ${JSON.stringify(result.timed40Stats)}`);
  console.log(`session: ${JSON.stringify(sessionInfo)}`);
  console.log(`wrote ${outDir}/parity-node-${dtype}.json`);
  try {
    await extractor.dispose?.();
  } catch {
    // nothing to free
  }
}

if (errors.length) {
  writeFileSync(`${outDir}/parity-node-errors.json`, `${JSON.stringify(errors, null, 1)}\n`);
  console.log(`\n${errors.length} dtype(s) failed; see ${outDir}/parity-node-errors.json`);
}
