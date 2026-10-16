# web/ — the demo website

Status: DRAFT scaffold (BDL-3, W5). Every screen is a clickable stub; the contracts below are final unless a relay reopens them.

Vite + React + TypeScript, plain CSS with design tokens, Biome, Vitest, Playwright. The sorter runs a small open model in a Web Worker with Transformers.js (WebGPU where available, WASM otherwise). No cookies, no analytics, no `localStorage`/`sessionStorage`; the only third-party requests are the model download from huggingface.co (and its `*.hf.co` download host).

## Commands

| command | what it does |
|---|---|
| `npm run dev` | Vite dev server (copies the ONNX runtime wasm files to `public/ort/` first) |
| `npm run build` | `precompute` + `typecheck` + `vite build` |
| `npm run build:web` | `vite build` alone; succeeds without `src/generated/library-embeddings.json` |
| `npm run preview` | serves `dist/` on port 4173 |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` / `npm run format` | Biome check / write |
| `npm test` | Vitest: rules, scoring, bundler, assembly, flow reducer |
| `npm run e2e` | builds, then Playwright at 390×844 (`phone`) and 1440×900 (`desktop`); screenshots of every step in light and dark go to `test-results/screens/`, or to `$BDL_SCREENS_DIR` |
| `npm run precompute` | embeds every library chat with the manifest's model and writes `src/generated/library-embeddings.json` (skips when nothing changed) |

Runtime: Node 24.21.0 (`.node-version` at the repository root). Install with `npm install` (lockfile) and `npx playwright install chromium` once.

## Pinned versions (checked with `npm view <pkg> time` on 2026-10-16; each at least 14 days old)

| package | version | released |
|---|---|---|
| vite | 8.3.2 | 2026-10-01 |
| react, react-dom | 19.3.0 | 2026-09-09 |
| typescript | 7.0.2 | 2026-07-08 |
| @types/react, @types/react-dom | 19.3.0 | 2026-09-09 |
| @vitejs/plugin-react | 6.1.1 | 2026-08-28 |
| @biomejs/biome | 2.5.15 | 2026-09-30 |
| vitest | 5.0.3 | 2026-09-30 |
| @playwright/test | 1.63.0 | 2026-09-04 |
| @huggingface/transformers | 4.3.0 | 2026-09-16 |

Notes. The relay's draft contract said Transformers.js "v3.x"; the current major is 4 (4.0.0 shipped 2026-03-30, last 3.x was 3.8.1 on 2025-12-02), it exports `pipeline` and `env` unchanged and loads the q8 model in Node and in Chromium, so 4.3.0 is pinned. jsdom is not installed: the unit tests are pure (`environment: node`). Transformers 4.3.0 brings onnxruntime-web 1.31.0-dev.20260914 (its own pin).

## Fonts (self-hosted, SIL Open Font License 1.1; checked 2026-10-16)

| file | source | sha256 |
|---|---|---|
| `public/fonts/BricolageGrotesque-Variable.woff2` (204,636 B) | https://github.com/ateliertriay/bricolage, `fonts/webfonts/BricolageGrotesque[opsz,wdth,wght].woff2` at `main` (commit 84745e5, 2023-07-19); renamed to avoid brackets in URLs | b51a8ebd…f1a8e |
| `public/fonts/AtkinsonHyperlegible-{Regular,Bold,Italic,BoldItalic}.woff2` (23–25 KB each) | https://github.com/googlefonts/atkinson-hyperlegible, `fonts/webfonts/` at `main` (commit 1cb3116, 2021-04-30) | 2df4ba17…, da8fce41…, 60bedf09…, f27e9514… |
| `public/fonts/OFL-BricolageGrotesque.txt`, `public/fonts/OFL-AtkinsonHyperlegible.txt` | each repository's `OFL.txt` | — |

`src/styles/tokens.css` declares the `@font-face` rules with system fallbacks (`sans-serif` last).

## Budgets (measured 2026-10-16 on this Mac; `npm run build:web`, gzip -c | wc -c)

| item | measured | budget |
|---|---|---|
| main JavaScript `dist/assets/index-*.js` | 232.8 KB raw, **71.6 KB gzip** | 200 KB gzip |
| sorter worker `dist/assets/worker-*.js` (Transformers.js + onnxruntime-web glue, loaded when the quiz starts) | 542.5 KB raw, **154.8 KB gzip** | counted separately; main + worker = 226.4 KB gzip |
| CSS | 8.2 KB raw, 2.5 KB gzip | — |
| ONNX runtime wasm `public/ort/ort-wasm-simd-threaded.asyncify.wasm` (fetched once, before the model) | 26.9 MB raw, 6.8 MB gzip (Vite's figure; served compressed by the host) | not in the relay; reported |
| model download, measured in Chromium (`Xenova/all-MiniLM-L6-v2`, q8) | **22.6 MB** = `onnx/model_quantized.onnx` 21.91 MB + `tokenizer.json` 0.68 MB + two small JSON files | 40 MB |
| model load to ready, headless Chromium, WebGPU, warm network | 6.7 s | — |
| per-decision time | not yet measured (the bundler records `ms` per decision; the reveal screen will report it) | 50 ms |

Open point: the worker chunk alone is under 200 KB but main + worker is 226 KB gzip. If the relay's budget means all JavaScript, the options are lazy-loading only the glue the chosen device needs or trimming Transformers.js imports.

## Model and licence (checked 2026-10-16)

- `src/sorter/model-manifest.json`: `Xenova/all-MiniLM-L6-v2`, source `hub`, dtype `q8`.
- https://huggingface.co/Xenova/all-MiniLM-L6-v2 states `License: apache-2.0`; quantised from `sentence-transformers/all-MiniLM-L6-v2`.
- https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 states `License: apache-2.0`; 384-dimensional embeddings, inputs truncated at 256 word pieces.
- Node check (`pipeline('feature-extraction', …, {dtype:'q8'})`): dims `[2, 384]`; cosine("how do I train for a half marathon", "best running plan for a 21k race") = 0.49; an unrelated sentence scored 0.18. Files land in `node_modules/@huggingface/transformers/.cache/`.
- Both conditions hold (under 40 MB, Apache-2.0), so the manifest stays on all-MiniLM-L6-v2; `Xenova/bge-small-en-v1.5` (MIT) is the fallback if either changes.
- When `source` is `local`, the worker and the precompute script read the model from `public/models/<id>/` (`env.allowLocalModels = true`, `env.allowRemoteModels = false`).

## Privacy and third-party requests

- Transformers.js points onnxruntime-web at a jsdelivr CDN for its wasm files by default. `scripts/copy-ort.mjs` copies the two files the installed onnxruntime-web bundle names into `public/ort/` (gitignored) and the worker sets `env.backends.onnx.wasm.wasmPaths` to `/ort/`. Verified in Chromium: requests went only to `localhost`, `huggingface.co` and `us.aws.cdn.hf.co`.
- Vite also emits a copy of the wasm under `dist/assets/` because onnxruntime-web references it with `new URL(…, import.meta.url)`; the `dropDuplicateOrtWasm` plugin in `vite.config.ts` removes that unused duplicate.
- The Playwright flow test aborts every request that leaves the origin and asserts the hosts match `(huggingface|hf)\.co`.

## Contracts in code

- `src/config.ts`: `APP_NAME` (the only place the product name is written), `FOOTER_TEXT`, `JS_BUDGET_KB`, `MODEL_BUDGET_MB`, `DECISION_BUDGET_MS`.
- `src/styles/tokens.css`: the relay's token table (light default, dark via `html[data-theme="dark"]` plus a `prefers-color-scheme` fallback), bundle colours, radii, spacing, type scale, fonts, reduced motion.
- `src/content/types.ts`, `src/content/library/index.ts` (`getLibrary()`, glob over `./*.json` minus the schema, works with zero files), `src/content/assemble.ts` (`assemble(interests, seed, {now, library?})`, mulberry32, 100–150 chats over 274 days ending at `now`, threads in order with at least a day between chats), `src/content/fixtures/sample.json` (tests only; its `interest` is `sample`, outside the schema's enum on purpose so it can never be mistaken for library content).
- `src/sorter/`: `scoring.ts` (cosine over L2-normalised vectors, normalised mean for bundles, constant `noneScore`, softmax over `scores / temperature`), `rules.ts` (`decide`: argmax over candidates, file ≥ 0.85, suggest ≥ 0.55, else leave), `bundler.ts` (date-ordered simulation with per-chat placements, steps and timings), `worker.ts` + `client.ts` (messages: load → progress/ready, embed → embedded), `embeddings.ts` (lazy loader for the generated vectors; `null` when absent), `text.ts` (`chatText` = title + newline + question; also imported by the precompute script so both sides embed the same words), `calibration.json`, `model-manifest.json`.
- `src/state/flow.ts`: reducer, `FlowProvider`, `useFlow`; steps in `src/state/steps.ts`.
- Screens in `src/screens/<Name>.tsx` + `.css`; shared UI in `src/components/`; `src/tech/TechPanel.tsx` renders when `techView` is on.
- `scripts/precompute-embeddings.mjs` rounds vectors to 5 decimals (JSON size; cosine error below 1e-4) and stores a content hash to skip unchanged runs. With zero library files it writes an empty vectors object.

## Contrast (WCAG 2.x ratios computed from the tokens, 2026-10-16)

| pair | light | dark |
|---|---|---|
| ink on paper / surface | 14.8 / 16.3 | 15.4 / 14.0 |
| muted on paper / surface | 5.7 / 6.3 | 8.0 / 7.3 |
| accent-ink on paper / accent-soft | 9.0 / 8.3 | 11.2 / 9.0 |
| on-accent text on accent (buttons) | 6.0 | 7.2 |
| bundle colours as text on surface | teal 4.3, blue 4.9, saffron 3.0, rose 4.9, plum 5.9, grey 3.1 | all ≥ 5.7 |

So in light mode the bundle colours are fills, borders and large text only; labels use ink or muted.

## Decisions taken in this scaffold (open points for the close-out)

1. Transformers.js 4.3.0 instead of a 3.x pin (see Pinned versions).
2. TypeScript 7.0.2 (the native compiler) for `tsc --noEmit`; it type-checks this project without issues.
3. The ONNX wasm is self-hosted by a copy script rather than imported, so the site never calls a CDN.
4. `main + worker` JavaScript is 226 KB gzip against a 200 KB budget if both count; the main bundle alone is 72 KB.
5. Biome 2.5 migrated `rules.recommended: true` to `rules.preset`; it is set to `"recommended"` (the migration wrote `"none"`, which would have disabled every rule).
