# web/ — the demo website

Status: version 1 of the story runs end to end (BDL-3, W5): welcome → quiz → history → chat → months pass → challenge → reveal → continue, with the sorter in a Web Worker and the tech view behind its own switch. The contracts below are final unless a relay reopens them. Final check on 2026-10-16 at 19:22 IST: `typecheck`, `lint` (106 files), `test` (107 of 107), `build` and `e2e` (10 of 10: the story and the accessibility walk, phone and desktop, light and dark) were all green on the reviewed code.

Vite + React + TypeScript, plain CSS with design tokens, Biome, Vitest, Playwright. The sorter runs a small open model in a Web Worker with Transformers.js (WebGPU where available, WASM otherwise). No cookies, no analytics, no `localStorage`/`sessionStorage`; the only third-party requests are the model download from huggingface.co (and its `*.hf.co` download host).

## How to run

1. Node 24.21.0 (`.node-version` at the repository root; `fnm use`). `node --version` must print `v24.21.0`.
2. `npm install` (lockfile), then `npx playwright install chromium` once for the end-to-end tests.
3. `npm run dev` for the dev server, or `npm run build && npm run preview` for the production build on http://localhost:4173.

| command | what it does |
|---|---|
| `npm run dev` | Vite dev server (copies the ONNX runtime wasm files to `public/ort/` first) |
| `npm run build` | `precompute` + `typecheck` + `vite build` → `dist/` |
| `npm run build:web` | `vite build` alone; succeeds without `src/generated/library-embeddings.json` |
| `npm run preview` | serves `dist/` on port 4173 |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` / `npm run format` | Biome check / write |
| `npm test` | Vitest: rules, scoring, bundler, assembly, continuation, quiz, screens' pure helpers, flow reducer |
| `npm run e2e` | builds, then Playwright drives the whole story at 390×844 (`phone`) and 1440×900 (`desktop`), light and dark; the model is downloaded from huggingface.co in the test browser. Screenshots of every step go to `test-results/screens/`, or to `$BDL_SCREENS_DIR`, named `<project>-<theme>-<nn>-<step>.png`; measured budgets go to `test-results/budgets/<project>-<theme>.json` |
| `npm run precompute` | embeds every library chat with the manifest's model and writes `src/generated/library-embeddings.json` (skips when nothing changed) |

The page opened with `?test` in the URL exposes two hooks for the Playwright run and nothing else: the challenge heading carries `data-target-title`, and `window.__bundleStats` holds the sort's timings once the switch has been flipped (`src/testing.ts`). Visitors never pass that flag.

## Budgets (measured 2026-10-16 on this Mac, final check at 19:22 IST: `npm run build`, then `gzip -c | wc -c` over `dist/`, then `npm run e2e` in headless Chromium; the build figures are decimal KB and MB as Vite prints them, the model figures are MB of 1,048,576 bytes as the worker counts them)

| item | measured | budget | within? |
|---|---|---|---|
| main JavaScript `dist/assets/index-*.js` (React, the app, and the twelve library files inlined by the eager glob, about 85 KB gzip of content) | 517.1 KB raw, **173.6 KB gzip** (Vite's own estimate prints 175.2 KB) | 200 KB gzip before the model | yes |
| sorter worker `dist/assets/worker-*.js` (Transformers.js + onnxruntime-web glue; its own chunk, loaded when the quiz starts) | 542.6 KB raw, **154.9 KB gzip** | — (see note) | main + worker = 328.5 KB gzip, over if both count |
| tech view `dist/assets/TechPanel-*.js` (lazy; only when that switch is on) | 21.6 KB raw, 7.5 KB gzip | — | — |
| CSS (`index-*.css` + `TechPanel-*.css`) | 45.6 KB raw, 9.2 KB gzip | — | — |
| precomputed library embeddings `dist/assets/library-embeddings-*.json` (a static JSON asset, fetched once when the switch is flipped; not a script; 360 library chats) | 1.16 MB raw, 354.8 KB gzip | — | — |
| ONNX runtime wasm `public/ort/ort-wasm-simd-threaded.asyncify.wasm` (fetched once when the worker starts, before the model) | 26.9 MB raw, 6.7 MB gzip | not in the relay; reported | — |
| model download (`Xenova/all-MiniLM-L6-v2`, q8: `onnx/model_quantized.onnx` 22,972,370 B + `tokenizer.json` + `config.json` + `tokenizer_config.json`), as the worker totals the files it fetched (23,685,047 B); the sum of the three 200 responses that carried a Content-Length was 21.91 MB (`tokenizer.json`, 0.68 MB, came without one); hosts seen: `huggingface.co` and `us.aws.cdn.hf.co` | **22.59 MB** | 40 MB | yes |
| time per decision (scoring + rules, `BundlingResult.steps[].ms`, 171–174 decisions per run, ranges over the four runs; Chromium's timer resolves to 0.1 ms) | **median 0.10 ms**, mean 0.09–0.11 ms, p95 0.20 ms, max 0.30–0.80 ms | 50 ms | yes, every decision |
| all of a run's decisions added up (`decisionMs`) | 15.9–18.8 ms | — | — |
| embedding the visitor's three own chats live in the worker (`embedMs`; every library chat, including the ones that arrive while the months pass, uses its precomputed vector) | 67–79 ms per run | — | — |
| model load to ready (download, compile, first run) | 8.4–14.0 s | — | — |
| device in the test browser | WASM: headless Chromium hands out no WebGPU adapter (see decision 9); the WebGPU path is untested in this run | — | — |
| what the untrained baseline with the default calibration made of the 135 history chats plus the visitor's own and the later ones | 20–27 bundles, 73–87 loose chats; the challenge target was bundled in 1 of the 4 walks (phone, dark) and left loose in the other 3 (see decision 10) | — | — |

Note on the JavaScript budget. The relay's figure is "JavaScript under 200 KB gzipped, before the model". The main bundle (everything a visitor runs before flipping the switch, including the library content) is 173.6 KB. The worker chunk is the Transformers.js runtime and the ONNX glue; it is JavaScript too, it starts downloading with the quiz, and it is 154.9 KB on its own, so main + worker is 328.5 KB. Two ways down if the sum is what counts: serve the twelve library files as a fetched JSON asset instead of an eager import (about −85 KB from main, but `getLibrary()` would stop being synchronous, which the W5 contract fixes), and import `AutoTokenizer`/`AutoModel` instead of `pipeline` in the worker (untested saving). Both are open points for the close-out.

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
| @axe-core/playwright | 4.13.0 | 2026-08-11 |
| @huggingface/transformers | 4.3.0 | 2026-09-16 |

Notes. The relay's draft contract said Transformers.js "v3.x"; the current major is 4 (4.0.0 shipped 2026-03-30, last 3.x was 3.8.1 on 2025-12-02), it exports `pipeline` and `env` unchanged and loads the q8 model in Node and in Chromium, so 4.3.0 is pinned. jsdom is not installed: the unit tests are pure (`environment: node`). Transformers 4.3.0 brings onnxruntime-web 1.31.0-dev.20260914 (its own pin).

## Fonts (self-hosted, SIL Open Font License 1.1; checked 2026-10-16)

| file | source | sha256 |
|---|---|---|
| `public/fonts/BricolageGrotesque-Variable.woff2` (204,636 B) | https://github.com/ateliertriay/bricolage, `fonts/webfonts/BricolageGrotesque[opsz,wdth,wght].woff2` at `main` (commit 84745e5, 2023-07-19); renamed to avoid brackets in URLs | b51a8ebd…f1a8e |
| `public/fonts/AtkinsonHyperlegible-{Regular,Bold,Italic,BoldItalic}.woff2` (23–25 KB each) | https://github.com/googlefonts/atkinson-hyperlegible, `fonts/webfonts/` at `main` (commit 1cb3116, 2021-04-30) | 2df4ba17…, da8fce41…, 60bedf09…, f27e9514… |
| `public/fonts/OFL-BricolageGrotesque.txt`, `public/fonts/OFL-AtkinsonHyperlegible.txt` | each repository's `OFL.txt` | — |

`src/styles/tokens.css` declares the `@font-face` rules with system fallbacks (`sans-serif` last).

## Model and licence (checked 2026-10-16)

- `src/sorter/model-manifest.json`: `Xenova/all-MiniLM-L6-v2`, source `hub`, dtype `q8`.
- https://huggingface.co/Xenova/all-MiniLM-L6-v2 states `License: apache-2.0`; quantised from `sentence-transformers/all-MiniLM-L6-v2`.
- https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 states `License: apache-2.0`; 384-dimensional embeddings, inputs truncated at 256 word pieces.
- Node check (`pipeline('feature-extraction', …, {dtype:'q8'})`): dims `[2, 384]`; cosine("how do I train for a half marathon", "best running plan for a 21k race") = 0.49; an unrelated sentence scored 0.18. Files land in `node_modules/@huggingface/transformers/.cache/`.
- Both conditions hold (under 40 MB, Apache-2.0), so the manifest stays on all-MiniLM-L6-v2; `Xenova/bge-small-en-v1.5` (MIT) is the fallback if either changes.
- When `source` is `local`, the worker and the precompute script read the model from `public/models/<id>/` (`env.allowLocalModels = true`, `env.allowRemoteModels = false`).

## Privacy and third-party requests

- Transformers.js points onnxruntime-web at a jsdelivr CDN for its wasm files by default. `scripts/copy-ort.mjs` copies the two files the installed onnxruntime-web bundle names into `public/ort/` (gitignored) and the worker sets `env.backends.onnx.wasm.wasmPaths` to `/ort/` in the build and to `/node_modules/onnxruntime-web/dist/` under the dev server (decision 11). Either way the files come from this origin.
- Vite also emits a copy of the wasm under `dist/assets/` because onnxruntime-web references it with `new URL(…, import.meta.url)`; the `dropDuplicateOrtWasm` plugin in `vite.config.ts` removes that unused duplicate.
- The Playwright flow lets requests through only to this origin and to `(huggingface|hf)\.co`; every other host is aborted and recorded, and the test asserts that list is empty. In the run of 2026-10-16 the hosts seen were `localhost`, `huggingface.co` and `us.aws.cdn.hf.co`.
- Nothing a visitor picks or types is sent anywhere: the quiz, the history, the typed text and the sort all live in the tab. The `?test` hooks only read state back into the test runner.
- Transformers.js keeps the downloaded model files in the browser's Cache Storage (`caches`, key `transformers-cache`; its default when the API exists) so a return visit skips the 22 MB download. That is the HTTP-cache family, not `localStorage`/`sessionStorage`, and the files are identical for every visitor; the tech view's Privacy panel says so. Nothing else is stored.

## Contracts in code

- `src/config.ts`: `APP_NAME` (the only place the product name is written), `FOOTER_TEXT`, `JS_BUDGET_KB`, `MODEL_BUDGET_MB`, `DECISION_BUDGET_MS`.
- `src/styles/tokens.css`: the relay's token table (light default, dark via `html[data-theme="dark"]` plus a `prefers-color-scheme` fallback), bundle colours, radii, spacing, type scale, fonts, reduced motion.
- `src/content/types.ts`, `src/content/library/index.ts` (`getLibrary()`, eager glob over `./*.json` minus the schema, works with zero files), `src/content/assemble.ts` (`assemble(interests, seed, {now, library?})`, mulberry32, 100–150 chats over 274 days ending at `now`, threads in order with at least a day between chats), `src/content/quiz.ts` (seven questions, twelve types), `src/content/continuation.ts` (`pickContinuation`, `fillContinuation`/`fillContinuationParts`, `bundleChatIdsFor`, `tidyDropped`), `src/content/fixtures/sample.json` (tests only; its `interest` is `sample`, outside the schema's enum on purpose so it can never be mistaken for library content).
- `src/sorter/`: `scoring.ts` (cosine over L2-normalised vectors, normalised mean for bundles, constant `noneScore`, softmax over `scores / temperature`), `rules.ts` (`decide`: argmax over candidates, file ≥ 0.85, suggest ≥ 0.55, else leave), `bundler.ts` (date-ordered simulation with per-chat placements, steps and timings), `worker.ts` + `client.ts` (messages: load → progress/ready, embed → embedded), `embeddings.ts` (fetches the generated vectors as a JSON asset; `null` when absent), `text.ts` (`chatText` = title + newline + question; also imported by the precompute script so both sides embed the same words), `calibration.json`, `model-manifest.json`.
- `src/state/flow.ts`: reducer, `FlowProvider`, `useFlow`; steps in `src/state/steps.ts`; `useSorter.ts` subscribes to the worker client.
- Screens in `src/screens/<Name>.tsx` + `.css`, each with its pure helpers unit-tested next to it; `Continue.tsx`'s `planContinuation` fills the thread's continuation from the chats actually in the found chat's bundle (thread chats first, then the bundle's other members, dropped and tidied otherwise; the found chat never names itself) and `components/ContinuationReply.tsx` marks each filled title. Shared UI in `src/components/`; `src/tech/TechPanel.tsx` is a lazy chunk rendered when `techView` is on.
- `src/testing.ts`: the `?test` hooks described under How to run.
- `scripts/precompute-embeddings.mjs` rounds vectors to 5 decimals (JSON size; cosine error below 1e-4) and stores a content hash to skip unchanged runs. With zero library files it writes an empty embeddings file. `scripts/validate-library.mjs` and `src/content/library/library.schema.json` belong to the library workstream (W4) and are excluded from Biome here.

## Contrast (WCAG 2.x ratios computed from the tokens, 2026-10-16)

| pair | light | dark |
|---|---|---|
| ink on paper / surface | 14.8 / 16.3 | 15.4 / 14.0 |
| muted on paper / surface | 5.7 / 6.3 | 8.0 / 7.3 |
| accent-ink on paper / accent-soft | 9.0 / 8.3 | 11.2 / 9.0 |
| on-accent text on accent (buttons) | 6.0 | 7.2 |
| bundle colours as text on surface | teal 4.3, blue 4.9, saffron 3.0, rose 4.9, plum 5.9, grey 3.1 | all ≥ 5.7 |

So in light mode the bundle colours are fills, borders and large text only; labels use ink or muted.

Non-text contrast: `--line` (1.4:1 on paper and on surface, both themes) is a divider and the border of controls that their text identifies (buttons, switches, pills). The two text inputs, whose border is what identifies them, use `--line-strong`: #7b8597 in light (3.4:1 on paper, 3.7:1 on surface) and #66718a in dark (3.8:1 on paper, 3.5:1 on surface). Focus rings are `--accent` (5.5:1 or better on every background).

## Accessibility (reviewed 2026-10-16)

- Focus: every step hands focus to its `h1` on arrival (`App.tsx`) and scrolls to the top, so keyboard and screen-reader users land on the new content rather than on `<body>`. Scroll regions take keyboard focus: the sidebars, the reveal's long list, the chat transcript once it has messages.
- Targets on phones and touch screens (`(width < 48rem), (pointer: coarse)`): at least 44 CSS px in both directions for the step dots, the header switches, the drawer toggle and its Close, the chat chips, the bundle rows, the tech view's Show all, and the skip link when it appears.
- Live regions announce state changes only: the sorter's four coarse states (quiz line and tech view), the debounced match count, the challenge and reveal status lines (including when Give up and Skip the hunt appear), the months summary. Both timers are `role="timer"`.
- Reduced motion: durations go to 0 ms, animations to 0.01 ms (so `animationend` still fires for the challenge's shake) and transitions to 0 s. At 0.01 ms, with `transition-property` defaulting to `all`, every property change on every element became a micro-transition and a theme flip lagged about 200 ms in Chromium (57 transitions in flight).
- `e2e/a11y.spec.ts` walks welcome to reveal (before the switch, so without the model) in both themes on both viewports with reduced motion on, from the keyboard where it matters: the skip link is the first Tab stop, arrows and digits drive the quiz, Enter activates every button, Escape closes the drawer and returns focus. At each step it runs axe-core (WCAG 2.0, 2.1 and 2.2, A and AA) and expects zero violations, checks one `h1` and no skipped heading level, the focused heading, and on the phone the 44 px targets. 4 of 4 passed on 2026-10-16 (5.2–5.7 s each in the final check). The bundled reveal and the continue step need the model and were reviewed by hand.

## Decisions taken here (open points for the close-out)

1. Transformers.js 4.3.0 instead of a 3.x pin (see Pinned versions).
2. TypeScript 7.0.2 (the native compiler) for `tsc --noEmit`; it type-checks this project without issues.
3. The ONNX wasm is self-hosted by a copy script rather than imported, so the site never calls a CDN.
4. The main bundle is 173.6 KB gzip, within the 200 KB budget; main + worker is 328.5 KB (see the note under Budgets).
5. Biome 2.5 migrated `rules.recommended: true` to `rules.preset`; it is set to `"recommended"` (the migration wrote `"none"`, which would have disabled every rule).
6. The precomputed embeddings are a fetched JSON asset (355 KB gzip), not a script, so they stay out of the JavaScript figure and are only fetched when the switch is flipped.
7. The e2e run uses `?test` hooks (target title, timings) rather than scraping; they are inert without the flag.
8. The library validator and schema from W4 are excluded from Biome rather than reformatted in this branch.
9. The worker asks for a WebGPU adapter before choosing WebGPU: headless and some mobile browsers expose `navigator.gpu` with no adapter, and Transformers.js 4.3 chains every session creation on one promise (`webInitChain` in `src/backends/onnx.js`) that never recovers from a rejection, so a failed WebGPU attempt cannot be retried on WASM in the same worker. If WebGPU still fails, the client terminates the worker and loads again in a fresh one with `device: "wasm"`.
10. With the untrained baseline encoder and the default calibration (`temperature` 0.05, `noneScore` 0.30, file ≥ 0.85, suggest ≥ 0.55) the sorter leaves most chats loose. A Node run of the exact browser maths over three assembled histories (seeds 11, 23, 37; 144, 133 and 165 chats) gave 51 file, 81 suggest and 310 leave decisions, 16–21 bundles and 72–98 loose chats each, and 7 of the visitor's 9 own chats left loose: every loose chat is a softmax candidate, so the probability mass spreads out as the history grows. That is what the calibration step (W6) is for; the maths and the defaults are the relay's contract and were not changed here. The continue step handles a loose target (it says the sorter left the chat alone), and the Playwright flow asserts a `<mark>` in the continuation only when the target was bundled, recording `targetBundled` in `test-results/budgets/`. In the final check the target was bundled in 1 of the 4 walks and left loose in 3.
11. In `npm run dev` the worker points the ONNX runtime at `/node_modules/onnxruntime-web/dist/` instead of `/ort/`: Vite's dev server refuses a dynamic `import()` of a file under `public/`, which left the sorter dead in dev ("Failed to fetch dynamically imported module …asyncify.mjs"). The production bundle is unchanged (the branch is compiled out); checked in headless Chromium against the dev server: ready on WASM in 8.8 s, no console errors.
12. The accessibility review added `--line-strong`, the 44 px targets, the focus hand-off per step, `transition-duration: 0s` under reduced motion and `e2e/a11y.spec.ts`; `@axe-core/playwright` 4.13.0 is the one new (dev) dependency.
