// Copies the ONNX Runtime wasm files that Transformers.js needs into public/ort/,
// so the site serves them itself instead of loading them from a CDN.
// Idempotent; runs before dev and build (see package.json).
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "node_modules", "onnxruntime-web", "dist");
const out = join(root, "public", "ort");

// Transformers.js (browser build) imports onnxruntime-web/webgpu; find the files it names.
const bundle = readFileSync(join(dist, "ort.webgpu.bundle.min.mjs"), "utf8");
const wanted = new Set(bundle.match(/ort-wasm-simd-threaded[a-z.]*\.(?:mjs|wasm)/g) ?? []);
if (wanted.size === 0) {
  console.error("copy-ort: no wasm file names found in onnxruntime-web; check the version");
  process.exit(1);
}

mkdirSync(out, { recursive: true });
for (const name of readdirSync(dist)) {
  if (!wanted.has(name)) continue;
  const from = join(dist, name);
  const to = join(out, name);
  if (existsSync(to) && statSync(to).size === statSync(from).size) continue;
  copyFileSync(from, to);
  console.log(`copy-ort: ${name} (${(statSync(from).size / 1_048_576).toFixed(1)} MB)`);
}
