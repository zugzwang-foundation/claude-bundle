import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

/**
 * onnxruntime-web refers to its wasm file through `new URL(..., import.meta.url)`,
 * so Vite emits a 26 MB copy under dist/assets. The worker sets `wasmPaths` to
 * /ort/ (filled by scripts/copy-ort.mjs), so that copy is never fetched; drop it.
 */
function dropDuplicateOrtWasm(): Plugin {
  return {
    name: "drop-duplicate-ort-wasm",
    generateBundle(_options, bundle) {
      for (const [fileName, output] of Object.entries(bundle)) {
        if (output.type === "asset" && /ort-wasm-simd-threaded.*\.wasm$/.test(fileName)) {
          delete bundle[fileName];
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), dropDuplicateOrtWasm()],
  worker: { format: "es" },
  build: { target: "es2022", sourcemap: false, chunkSizeWarningLimit: 600 },
  optimizeDeps: { exclude: ["@huggingface/transformers"] },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
