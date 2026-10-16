# Browser runtime and web stack

Status: DRAFT — research note, 2026-10-16.

Track R4 of BDL-3. Written from sources opened on 16 October 2026 and from measurements taken on this Mac the same day. Where nothing was checked, it says "unknown".

## The question

Four things the website workstream (W5) needs settled before it writes code:

1. What Transformers.js and ONNX Runtime Web are today: versions, WebGPU and WASM support on phones and desktops, the Web Worker pattern, caching, quantisation (dtype) choices, and how to load our own model from a static site.
2. Whether the relay's budgets are realistic for a 22–33M-parameter encoder at int8 on a mid-range phone: a download under 40 MB and under 50 ms per decision.
3. Which exact versions of Vite, React, TypeScript, Biome, Vitest and Playwright to pin, given the rule that releases should be at least 14 days old (published on or before 2 October 2026).
4. How to do social preview images for a static site.

## Findings

### Transformers.js and ONNX Runtime Web

**Versions.** `@huggingface/transformers` latest is 4.3.1, published 6 October 2026; 4.3.0 was published 16 September 2026; the first stable 4.0.0 was published 30 March 2026 after twelve `4.0.0-next` builds (next.0 to next.11) (npm registry, checked 16 Oct 2026 [1]). Hugging Face's "Transformers.js v4" post is dated 9 February 2026 and describes a WebGPU runtime rewritten in C++ with the ONNX Runtime team, bundles about 10% smaller on average (the default web export 53% smaller) and "~4x speedup" for BERT-style embedding models [3]. 4.3.0 "Enable[s] WebGPU for Safari 26 and above", upgrades ONNX Runtime and fixes duplicate model downloads when a progress callback is attached [4]. 4.3.1 only adds EmbeddingGemma 2 support [2]. Licence Apache-2.0 [1].

**ONNX Runtime Web is pinned for us.** Transformers.js 4.3.0 and 4.3.1 both depend on the exact dev build `onnxruntime-web@1.31.0-dev.20260914-8d85527a0` and on `onnxruntime-node@1.30.0` [1, 44]. The latest stable `onnxruntime-web` on npm is 1.30.0 (14 September 2026); ONNX Runtime 1.31.0 was tagged on GitHub on 9 October 2026 but is not npm's `latest` for the web package today [1, 14]. Licence MIT [1]. Conclusion: do not pin `onnxruntime-web` ourselves; it arrives with Transformers.js.

**The web build needs a bundler.** `dist/transformers.web.js` imports the bare specifiers `onnxruntime-web/webgpu` and `onnxruntime-common`; loaded straight into a page it fails with "Failed to resolve module specifier" (seen in Chrome today) [44]. Through Vite it works. The `./webgpu` export resolves to `ort.webgpu.bundle.min.mjs` (118 KB raw, 39 KB gzip, 34 KB brotli) [44].

**WASM binaries come from a CDN unless you say otherwise.** The bundle sets `wasmPaths` to `https://cdn.jsdelivr.net/npm/onnxruntime-web@<version>/dist/` when nothing is set, and picks `ort-wasm-simd-threaded.asyncify.{mjs,wasm}`; the plain `ort-wasm-simd-threaded.{mjs,wasm}` is used only on Safari below 26 without WebGPU [44]. The docs confirm the CDN default and `env.backends.onnx.wasm.wasmPaths` as the override [7]. Measured sizes of the pinned dev build (raw / gzip -9 / brotli -q11): asyncify 26.9 MB / 6.6 MB / 3.9 MB; plain 14.3 MB / 3.7 MB / 2.3 MB; jsep 28.4 MB / 6.6 MB / 3.8 MB; jspi 16.8 MB / 4.1 MB / 2.6 MB [44]. A Vite 8.3.3 production build emitted the asyncify `.wasm` into `dist/assets/` on its own (26,861 kB, gzip 6,763 kB in Vite's report), yet Transformers.js would still fetch the CDN copy unless `wasmPaths` points at our own origin [43]. The relay's rule "the only third-party request is the model download" therefore needs `wasmPaths` set; with the model self-hosted too, the site makes no third-party request at all.

**Devices and defaults.** In the browser the default device is `wasm`; `device: 'webgpu'` is accepted when `navigator.gpu` exists and `'auto'` tries WebGPU then WASM [44]. The default dtype is `q8` on `wasm` and `fp32` on everything else; `fp16` on WebGPU is only used when the adapter reports `shader-f16` [44]. Transformers.js forces `wasm.proxy = false` and sets `webgpu.powerPreference = 'high-performance'` [44]. ONNX Runtime Web enables its WebGPU execution provider through the `onnxruntime-web/webgpu` import and `executionProviders: ['webgpu']`, which Transformers.js does for us [11, 44]. The HF WebGPU guide warns that outside Chromium a model may fail on WebGPU even where it runs in WASM, and puts global WebGPU support at about 85% as of March 2026 [5].

**dtype names and file names** (verbatim from the shipped bundle [44], matching the dtype guide [6]): fp32 → `model.onnx`; fp16 → `model_fp16.onnx`; int8 → `model_int8.onnx`; uint8 → `model_uint8.onnx`; q8 → `model_quantized.onnx`; q4 → `model_q4.onnx`; q4f16 → `model_q4f16.onnx`; bnb4 → `model_bnb4.onnx`; plus q2, q1, q2f16, q1f16 (added in 4.1.0 [2]). Per-module dtype maps are supported, and `ModelRegistry.get_available_dtypes(id)` probes which files exist [6].

**Loading our own model from a static site** [7, 8]: `env.allowLocalModels` defaults to `false` in browsers, so set it to `true`; set `env.allowRemoteModels = false` so nothing ever goes to the Hub; `env.localModelPath` defaults to the `/models/` URL path. The expected layout is `<localModelPath>/<model-id>/config.json`, `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json` and `onnx/model_quantized.onnx` (for q8), which is exactly what the Hub repositories look like [21]. Vite serves `web/public/` at the site root, so `web/public/models/<id>/…` matches the default path, and `.gitignore` already excludes it.

**Caching** [8]: models are cached with the Cache API (`env.useBrowserCache`, default true) under the cache name `transformers-cache` (`env.cacheKey`); `env.useWasmCache` (default true) also caches the WASM binary and its `.mjs` factory; a `customCache` with `match`/`put` can replace it. 4.3.0 stopped writing non-HTTP(S) resources to the cache [4]. Measured today: the second load of MiniLM-L6 q8 on the same origin took 0.66 s against 16 s cold; a different port (origin) re-downloaded, because the cache is per origin [43].

**Web Worker pattern** [9, 28]: the HF React tutorial creates the worker with `new Worker(new URL('./worker.js', import.meta.url), { type: 'module' })`, keeps one pipeline in a singleton `getInstance(progress_callback)`, and posts status messages (`initiate`, `progress`, `done`, `ready`, `update`, `complete`) back with `self.postMessage`. Vite detects that exact constructor form statically and emits the worker as a separate chunk; `?worker` imports are the alternative [28]. ONNX Runtime's own `wasm.proxy` worker is disabled by Transformers.js and is incompatible with WebGPU anyway [12, 44].

**Threads.** ONNX Runtime Web picks `numThreads` as the smaller of half `navigator.hardwareConcurrency` and 4, and multi-threading needs `crossOriginIsolated`, i.e. COOP and COEP headers; otherwise it silently runs single-threaded [12]. Measured today: 4 threads cut MiniLM-L6 latency from 37 ms to 14 ms [43].

**Browser support, from primary sources.** WebGPU: Chrome and Edge 113+ on desktop [10]; Chrome for Android since 121 (18 January 2024) on Android 12+ with Qualcomm and ARM GPUs [17]; Safari 26.0 (15 September 2025) enabled by default on macOS, iOS, iPadOS and visionOS [15]; Firefox 141 on Windows (22 July 2025) [18] and 147 on Apple-silicon Macs (13 January 2026) [19]; Firefox on Linux and Android: not by default per caniuse [10], otherwise unknown. caniuse puts global WebGPU usage at 87.82% [10]; MDN still rates it "limited availability" and HTTPS-only [20]. ONNX Runtime Web's README table still marks WebGPU unsupported in Safari, which is older than Transformers.js 4.3.0's Safari 26 switch [13, 4]: treat Safari WebGPU as "try, then fall back". WASM runs in every browser in that table including iOS Safari and Android Chrome [13]; it needs SIMD, which Safari gained in 16.4 (March 2023) [16].

**Vite dev server.** A probe with Vite 8.3.3 pre-bundled `@huggingface/transformers` into `node_modules/.vite/deps/` without errors [43]; older advice to add `optimizeDeps.exclude` was not needed here, but W5 should confirm at runtime.

### Budgets: download and latency

**File sizes on the Hub today** (HF API byte counts, checked 16 Oct 2026). Sizes in this note are decimal megabytes (1 MB = 1,000,000 bytes), the unit the WASM and Vite figures below already use; the Hub's web pages show MiB, which read about 5% smaller.

| Repository | Licence (gated?) | int8 / q8 | fp16 | fp32 | tokenizer.json |
|---|---|---|---|---|---|
| Xenova/all-MiniLM-L6-v2 (base sentence-transformers/all-MiniLM-L6-v2) | apache-2.0 (not gated) | 23.0 / 23.0 MB | 45.3 MB | 90.4 MB | 0.71 MB [21] |
| Xenova/bge-small-en-v1.5 (base BAAI/bge-small-en-v1.5) | base is MIT (not gated); the conversion repo lists none | 33.8 / 34.0 MB | 66.7 MB | 133.1 MB | 0.71 MB [22] |
| onnx-community/all-MiniLM-L6-v2-ONNX | apache-2.0 | none published (fp32, fp16, q4, q4f16 only, each split into `.onnx` + `.onnx_data`) | 45.2 MB | 90.3 MB | unknown [23] |
| Xenova/paraphrase-multilingual-MiniLM-L12-v2 (base sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) | conversion repo lists none; base licence unknown (not gated) | 118.1 / 118.3 MB | 235.3 MB | 470.3 MB | unknown [24] |

Rule of thumb that the table confirms: int8 is about one byte per parameter, so a 22M-class encoder is about 23 MB and a 33M-class one about 34 MB; a 250k-token multilingual vocabulary pushes a "small" model past 100 MB.

**Download totals.** MiniLM-L6 class: 23.0 MB model + 0.7 MB tokenizer + 3.9–6.6 MB WASM runtime (brotli–gzip) + about 0.2 MB JS ≈ 28–31 MB. bge-small class: 33.8 + 0.7 + 3.9–6.6 + 0.2 ≈ 39–41 MB: over the line with gzip, under it by about 1 MB only if the host serves brotli. Whether Vercel serves brotli for static assets: unknown today (out of scope). For time: Ookla's global median mobile download was 61.52 Mbps in November 2024, with Myanmar lowest at 5.09 Mbps [42]; 31 MB takes about 4 s at the median, 25 s at 10 Mbps and 50 s at 5 Mbps. A six-to-eight-tap quiz runs 30–60 s, so the model finishes during the quiz on anything better than roughly 5 Mbps, provided loading starts on the first tap.

**Latency, measured today** [43]. Method: Vite 8.3.3 build of a page importing `@huggingface/transformers@4.3.0`, served from localhost (one origin plain, one with COOP/COEP), Chrome 155 on this Mac (Apple silicon, 10 cores), models fetched from the Hub, WASM self-hosted. One short chat title at a time, `pooling: 'mean'`, `normalize: true`; five warm-ups, then the median and p90 of 40 runs; then one batch of 10 and one of 32.

| Configuration | median ms | p90 ms | batch 10 ms | batch 32 ms |
|---|---|---|---|---|
| MiniLM-L6 q8, wasm, 1 thread | 37.1 | 45.4 | 382 | 1,017 |
| MiniLM-L6 q8, wasm, 4 threads (isolated origin) | 14.4 | 20.4 | 137 | 397 |
| MiniLM-L6 fp32, webgpu | 8.7 | 9.1 | 122 * | 31 |
| MiniLM-L6 q8, webgpu | 53.4 | 77.4 | 359 | 982 |
| MiniLM-L6 q8, wasm, 1 thread, CPU throttled 4× | 116.0 | 138.7 | 1,263 | 4,654 |
| MiniLM-L6 q8, wasm, 4 threads, CPU throttled 4× | 64.7 | 79.9 | 503 | 1,401 |
| bge-small q8, wasm, 1 thread | 71.2 | 88.6 | 755 | 2,386 |

\* first run of that batch shape, so it includes shader compilation.

What it says: on this Mac, "under 50 ms per decision" holds for a 6-layer 22M model in WASM even single-threaded, fails for q8 on WebGPU (quantised kernels are slower on the GPU than on the CPU), and fails for a 12-layer 33M model single-threaded. No phone was measured today; the 4× CPU throttle is only a stand-in for a mid-range phone and gives 65–116 ms per decision, so "well under a second" (the spec) is comfortable and "under 50 ms" is not. Xenova's public benchmark (8 March 2024, Chrome 122, Intel Mac) agrees on shape: MiniLM fp32 at sequence length 512 took 386 ms in WASM and 23.8 ms on WebGPU at batch 1, and WebGPU's lead grows with batch size [25]. Our texts are short, which is why WASM does well here.

A decision is one forward pass of the new chat plus dot products against stored candidate vectors when the student is a bi-encoder; a cross-encoder would need one pass per candidate and is not affordable on a phone at these numbers (R2's call). The demo's reveal sorts 100–150 chats: at phone-class 65–116 ms each that is 7–17 s single-threaded, so library embeddings must be precomputed at build (the relay already says so) and only the visitor's own typed chats embedded live.

A cheaper alternative exists for a no-training baseline: Model2Vec static embeddings (minishlab/potion-base-8M, MIT, 7.56M parameters) have ONNX weights that work with Transformers.js since October 2024 [26]; there is no transformer forward pass, so latency is negligible, at a quality cost. That belongs to R2, but it is the fallback if phones prove too slow.

### Static-site stack: versions on npm today

"Pin" is the newest release published on or before 2 October 2026 (14 days old) unless noted. All dates from the npm registry [1]; licences from `npm view … license` [1].

| Package | Latest (date) | Pin (date) | Licence | Notes |
|---|---|---|---|---|
| vite | 8.3.4 (8 Oct) | **8.3.3** (6 Oct, exception) or 8.3.2 (1 Oct) | MIT | On 6 Oct 2026 the project published 8.3.3, 8.2.4, 8.1.6, 7.3.7 and 6.4.4 within forty minutes, a coordinated patch across five lines [1]. The 8.3.3 changelog lists four fixes: a `launch-editor` update, a `fs.serve` check for `?vite-wasm-instance`, storing ids rather than URLs in `safeModulePaths`, and a `transformIndexHtml` filename fix; it does not label them security, but three touch dev-server file access [47]. Search results call them three dev-server advisories; the advisories themselves would not open today (NOT VERIFIED). For scale, the last Vite dev-server advisory that did open, CVE-2026-39363 (6 April 2026, high, arbitrary file read over the dev server's WebSocket), was patched in 8.0.5 [30]. Vite 8 (12 Mar 2026) is Rolldown and Oxc based; Node 20.19+ or 22.12+ [27]. |
| @vitejs/plugin-react | 6.1.2 (5 Oct) | 6.1.1 (28 Aug) | MIT | |
| react, react-dom | 19.3.1 (14 Oct) | 19.3.0 (9 Sep) | MIT | 19.3 adds `<ViewTransition>`, Fragment refs, `browser()` [31]. The 19.3.1 note lists one Server Components transport change [32]; a hosting provider's bulletin (14 Oct 2026) calls 19.3.1/19.2.9/19.1.10/19.0.9 security patches for a remote code execution in React Flight (Server Components) and a denial of service in Server Functions, with apps that use no server-side React unaffected by the latter [33]; react.dev has no post on it [34]. We have no server React, so 19.3.0 is fine. |
| @types/react, @types/react-dom | 19.3.0 (9 Sep) | 19.3.0 | MIT | |
| typescript | 7.0.2 (8 Jul) | **6.0.3** (16 Apr) | Apache-2.0 | TypeScript 7.0 (8 Jul 2026) is the native Go compiler; `tsc` now runs it; `strict`, `module: esnext`, `types: []` and `rootDir: ./` become defaults; no stable programmatic API until 7.1; `@typescript/typescript6` keeps the JS compiler [35]. Vite's own react-ts template pins `~6.0.2` today [29]. Start on 6.0.3; try 7.0.2 in a later session. |
| @biomejs/biome | 2.5.15 (30 Sep) | 2.5.15 | MIT OR Apache-2.0 | Weekly 2.5.x patches [36]. |
| vitest | 5.0.5 (15 Oct) | 5.0.3 (30 Sep) | MIT | Vitest 5 (3 Sep 2026) needs Vite ≥ 6.4 and Node ≥ 22.12; `clearMocks` defaults to true; locators strict; async assertions must be awaited [37]. |
| @playwright/test | 1.64.1 (14 Oct) | 1.63.0 (4 Sep) | Apache-2.0 | 1.64.0 is 7 Oct (9 days). 1.63 adds `locator.visible()`, test locks, `reducedMotion`/`contrast` options [38]. |
| @huggingface/transformers | 4.3.1 (6 Oct) | 4.3.0 (16 Sep) | Apache-2.0 | 4.3.1 only adds a model [2]. |
| @types/node | 26.6.5 (9 Oct); newest 24.x is 24.19.2 (9 Oct) | 24.19.1 (1 Oct) | MIT | Follow the pinned Node 24 line, not npm's `latest`. |

Node 24.21.0 (already pinned in `.node-version`) satisfies every requirement above. Vite's react-ts template now ships `oxlint` rather than ESLint [29]; that does not affect the relay's choice of Biome.

**Bundle size, measured with these versions** [43]: a module worker that imports `@huggingface/transformers` and nothing else builds to 541 KB raw, 154 KB gzip, 127 KB brotli; React 19.3.0 plus `react-dom/client` plus a one-button component builds to 219 KB raw, 67 KB gzip, 58 KB brotli. Together that is 221 KB gzip (185 KB brotli) before a line of our own code.

### Social preview images

- Open Graph (ogp.me): required `og:title`, `og:type`, `og:image`, `og:url`; recommended `og:description`, `og:site_name`; image sub-properties `og:image:type`, `og:image:width`, `og:image:height`, `og:image:alt`, and "if the page specifies an og:image it should specify og:image:alt" [39].
- Facebook: at least 1200 × 630, aspect as close to 1.91:1 as possible, under 8 MB; width and height tags let the crawler render without downloading first [40].
- X: `summary_large_image` cards are 2:1; 1200 × 600 recommended, minimum 144 × 144, maximum 4096 × 4096, under 5 MB; JPEG, PNG, WebP and GIF (first frame), converted to JPEG [41]. The official X developer pages returned 403 or 404 today, so this comes from a secondary source; the tag names `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image` are from the same source. unknown: whether X falls back to `og:` tags.
- One 1200 × 630 PNG serves both: X centre-crops to 2:1, which trims about 15 px top and bottom (my arithmetic), so keep text inside roughly 1080 × 560.
- Generating the PNG at build: (a) Playwright screenshot of an HTML card that uses the site's own CSS tokens and self-hosted fonts; Playwright is already a dev dependency (Apache-2.0) [38]. (b) `sharp` renders SVG to PNG, Node ≥ 20.9, Apache-2.0 [45], and is already installed as a dependency of `@huggingface/transformers` (`sharp ^0.35.4`) [44]; but text in SVG uses the build machine's fonts, so CI and the Mac can render differently. (c) `satori` + `@resvg/resvg-js`: both MPL-2.0; satori shipped 0.56.2 → 0.62.0 between 14 and 16 October 2026 [1, 46]; resvg-js's last stable is 2.6.2 from 26 March 2024 [1].
- The absolute `og:url` and `og:image` URLs need the public domain, which waits on the name (D13).

## Options compared

| Option | What it costs the visitor | Latency per decision (today's measurements) | Licence | Verdict |
|---|---|---|---|---|
| A. One int8 (q8) file, WASM everywhere, worker, self-hosted runtime | 28–31 MB for a 22M-class encoder; 39–41 MB for 33M-class (over 40 MB unless brotli) | Mac 37 ms (1 thread) / 14 ms (4 threads); throttled 4× 116 / 65 ms | Transformers.js Apache-2.0; ONNX Runtime Web MIT; model Apache-2.0 (Xenova/all-MiniLM-L6-v2, not gated) | **Recommend** |
| B. WebGPU with fp16 or fp32 file, WASM q8 as fallback | +45 MB (fp16) or +90 MB (fp32) for the 22M model, both over budget | Mac 8.7 ms fp32; q8 on WebGPU is slower than WASM (53 ms) | same | Desktop tech-view experiment only, not the shipping path |
| C. Static embeddings (Model2Vec potion-base-8M) as baseline | small (unknown exact size today) | negligible, no transformer pass | MIT (not gated) | R2 to judge quality; fallback if phones are too slow |
| D. Multilingual small encoder | 118 MB int8 for the smallest Xenova conversion found | unknown | conversion repo lists none | Not within 40 MB; English only for v0 |
| E. Cross-origin isolation (COOP/COEP) for 4 threads | none; needs response headers at the host | 2.6× faster in WASM | n/a | Worth it for the Mac demo; headers are a hosting matter, decide at deploy time |
| OG-1. Playwright screenshot at build, PNG committed | one static PNG | n/a | Apache-2.0 | **Recommend** |
| OG-2. sharp SVG → PNG | one static PNG | n/a | Apache-2.0 | Acceptable; font mismatch risk in CI |
| OG-3. satori + resvg | one static PNG | n/a | MPL-2.0 | Avoid for now; churn |
| TS-6. typescript 6.0.3 | n/a | n/a | Apache-2.0 | **Recommend** for W5 |
| TS-7. typescript 7.0.2 | n/a | 8–12× faster `tsc` claimed [35] | Apache-2.0 | Try in a later session |

## Recommendation

1. Ship one model file, `onnx/model_quantized.onnx` at int8 (or `model_int8.onnx` loaded with `dtype: 'int8'`), under `web/public/models/<id>/`, and run it with `device: 'wasm'` on every browser. Do not use WebGPU for the shipping path: with int8 weights it is slower than WASM, and the fp16/fp32 files that make WebGPU fast break the 40 MB budget. Keep a `?device=webgpu` switch in the tech view as an experiment.
2. In the worker, before anything else: `env.allowLocalModels = true; env.allowRemoteModels = false; env.localModelPath = '/models/'; env.backends.onnx.wasm.wasmPaths = '/ort/';` and copy `ort-wasm-simd-threaded.asyncify.mjs` and `.wasm` (plus the plain pair for Safari below 26) from `node_modules/onnxruntime-web/dist/` into `web/public/ort/` with a build script, so the site makes no third-party request at all. Cache the model and the WASM with the default Cache API behaviour; version the model folder name so a new release is a new cache entry.
3. Use the HF worker pattern: module worker created with `new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' })`, singleton pipeline, `progress_callback` forwarded as messages, request ids on every message. Start loading on the first quiz tap.
4. Prefer a 6-layer 22M-class encoder (MiniLM-L6 size) over a 12-layer 33M one for v0: it fits the download with margin (28–31 MB) and meets 50 ms on the Mac single-threaded; the 33M class fails the 50 ms line without threads and lands at 39–41 MB, over the 40 MB line unless the host serves brotli. This is input to R2 and W6, not a decision on model quality.
5. Budgets to measure and report: JavaScript as two numbers, UI bundle (React and app) and inference worker, in gzip and brotli; download as model + tokenizer + runtime; latency as median and p90 over 40 single decisions after warm-up, in Chrome on this Mac, plus the same page under 4× CPU throttling as the phone proxy until a real phone is measured.
6. Pin: vite 8.3.3, @vitejs/plugin-react 6.1.1, react and react-dom 19.3.0, @types/react and @types/react-dom 19.3.0, typescript 6.0.3, @biomejs/biome 2.5.15, vitest 5.0.3, @playwright/test 1.63.0, @huggingface/transformers 4.3.0, @types/node 24.19.1. Use exact versions, no ranges, and `npm ci` from the lockfile.
7. Social preview: a script `web/scripts/og-image.ts` renders `web/og/card.html` (site tokens, self-hosted fonts, 1200 × 630) with Playwright and writes `web/public/og.png`; commit the PNG; add `og:title`, `og:type=website`, `og:description`, `og:site_name`, `og:image`, `og:image:width=1200`, `og:image:height=630`, `og:image:alt`, `twitter:card=summary_large_image`, `twitter:title`, `twitter:description`, `twitter:image` to `index.html`; keep `og:url` and the absolute image URL in the one site config constant with a placeholder until the domain exists.
8. Licences of everything named above, all checked on npm or the Hub today: @huggingface/transformers Apache-2.0; onnxruntime-web MIT; vite, @vitejs/plugin-react, react, react-dom, @types/*, vitest MIT; typescript and @playwright/test Apache-2.0; @biomejs/biome MIT OR Apache-2.0; baseline model Xenova/all-MiniLM-L6-v2 apache-2.0 (base sentence-transformers/all-MiniLM-L6-v2), alternative BAAI/bge-small-en-v1.5 MIT, fallback minishlab/potion-base-8M MIT. None of the three models is gated. The paraphrase-multilingual conversion has no licence field and is not recommended.

## What doesn't work, or would change the plan

1. **The 200 KB JavaScript budget is already spent by the libraries.** Transformers.js plus the ONNX Runtime JS in the worker is 154 KB gzip; React plus react-dom is 67 KB gzip; that is 221 KB gzip (185 KB brotli) before our code. Either restate the budget as two numbers (UI bundle under 120 KB gzip, worker under 170 KB gzip) or accept about 300 KB gzip total. Dropping React for a smaller renderer would save about 60 KB but contradicts D8; not recommended today.
2. **"Uses WebGPU where available" is wrong for an int8 model.** Measured: q8 on WebGPU 53 ms versus 37 ms on single-thread WASM, and fp32/fp16 files that would make WebGPU fast are 90 MB and 45 MB. Change the relay to "WASM everywhere; WebGPU only as a tech-view experiment".
3. **"Under 50 ms per decision on this Mac" depends on the model's depth, not just its size.** MiniLM-L6 (6 layers) passes at 37 ms single-threaded; bge-small (12 layers, 33M) fails at 71 ms unless the page is cross-origin isolated (COOP and COEP headers), which is a hosting decision we have deferred. Phones are slower still: 65–116 ms under 4× throttling. Keep "well under a second on a phone" from the spec as the hard line and treat 50 ms as a Mac-only target.
4. **"Model download under 40 MB" must count the runtime.** The WASM binary is 3.9–6.6 MB compressed and the tokenizer 0.7 MB; a 33M-class int8 model then lands at 39–41 MB: over the line with gzip, under it by about 1 MB with brotli, with no room for a second file. A 22M-class model fits with 9–12 MB to spare.
5. **Transformers.js defaults break two relay rules unless overridden**: it fetches WASM from jsdelivr, and `allowLocalModels` is false in browsers. Both are one-line fixes, but the Playwright run should assert that no request leaves the origin.
6. **No sub-40 MB multilingual encoder was found** among the Hub conversions checked (118 MB int8 for the smallest). v0 is English-only; "multilingual reach" in R2 should be read with that in mind.
7. **No phone was measured today.** The throttled-Mac figures are a proxy. Add to "Needs Hrishikesh": open the demo on his phone and read the tech-view latency, and the W5 Playwright run should include a 4× CPU-throttled pass.
8. **The onnx-community MiniLM repository has no int8 file today**, although the current docs use it as the example for `get_available_dtypes` [6, 23]. Use the Xenova repository for the baseline or our own export (W6 already plans int8 export).
9. **The 14-day rule collides with a same-day patch wave for Vite.** Five release lines were patched on 6 October 2026 with fixes to dev-server file-access checks and `launch-editor` [47]; the advisories would not open, so "security" is unconfirmed. Pinning 8.3.3 at 10 days old is the sensible reading, since the fixes only touch the dev server and cost nothing in production; the strict reading is 8.3.2.
10. **TypeScript 7 changed `tsc` under our feet.** It is the default on npm since 8 July 2026 with different compiler defaults and no stable programmatic API until 7.1; Vite's own template stays on 6.0.x. Starting on 6.0.3 avoids a day of tooling surprises.
11. **The Cache API is per origin.** Every preview URL re-downloads the model; that is fine for visitors but makes "download finishes during the quiz" worth testing from a cold cache, not a warm one.
12. **Sources that would not open today**: X's card documentation (403/404), speedtest.net, SitePoint (402). Their facts above are marked secondary or unknown.

## Sources

1. npm registry, via `npm view <package> time dist-tags dependencies license` — https://registry.npmjs.org/ (checked 16 Oct 2026)
2. Transformers.js releases — https://github.com/huggingface/transformers.js/releases (checked 16 Oct 2026)
3. Transformers.js v4: Now Available on NPM — https://huggingface.co/blog/transformersjs-v4 (checked 16 Oct 2026)
4. Transformers.js 4.3.0 release notes — https://github.com/huggingface/transformers.js/releases/tag/4.3.0 (checked 16 Oct 2026)
5. Running models on WebGPU — https://huggingface.co/docs/transformers.js/guides/webgpu (checked 16 Oct 2026)
6. Using quantized models (dtypes) — https://huggingface.co/docs/transformers.js/guides/dtypes (checked 16 Oct 2026)
7. Use custom models — https://huggingface.co/docs/transformers.js/custom_usage (checked 16 Oct 2026)
8. env API reference — https://huggingface.co/docs/transformers.js/api/env (checked 16 Oct 2026)
9. Building a React application (worker pattern) — https://huggingface.co/docs/transformers.js/tutorials/react (checked 16 Oct 2026)
10. caniuse: WebGPU — https://caniuse.com/webgpu (checked 16 Oct 2026)
11. ONNX Runtime Web: WebGPU execution provider — https://onnxruntime.ai/docs/tutorials/web/ep-webgpu.html (checked 16 Oct 2026)
12. ONNX Runtime Web: env flags and session options — https://onnxruntime.ai/docs/tutorials/web/env-flags-and-session-options.html (checked 16 Oct 2026)
13. ONNX Runtime js/web README (support table) — https://github.com/microsoft/onnxruntime/blob/main/js/web/README.md (checked 16 Oct 2026)
14. ONNX Runtime releases (page and GitHub API `releases/latest`) — https://github.com/microsoft/onnxruntime/releases , https://api.github.com/repos/microsoft/onnxruntime/releases/latest (checked 16 Oct 2026)
15. WebKit Features in Safari 26.0 — https://webkit.org/blog/17333/webkit-features-in-safari-26-0/ (checked 16 Oct 2026)
16. WebKit Features in Safari 16.4 — https://webkit.org/blog/13966/webkit-features-in-safari-16-4/ (checked 16 Oct 2026)
17. What's New in WebGPU (Chrome 121) — https://developer.chrome.com/blog/new-in-webgpu-121 (checked 16 Oct 2026)
18. Firefox 141.0 release notes — https://www.firefox.com/en-US/firefox/141.0/releasenotes/ (checked 16 Oct 2026)
19. Firefox 147.0 release notes — https://www.firefox.com/en-US/firefox/147.0/releasenotes/ (checked 16 Oct 2026)
20. MDN: WebGPU API — https://developer.mozilla.org/en-US/docs/Web/API/WebGPU_API (checked 16 Oct 2026)
21. Xenova/all-MiniLM-L6-v2 model info and file trees — https://huggingface.co/api/models/Xenova/all-MiniLM-L6-v2 , https://huggingface.co/api/models/Xenova/all-MiniLM-L6-v2/tree/main , https://huggingface.co/api/models/Xenova/all-MiniLM-L6-v2/tree/main/onnx (checked 16 Oct 2026)
22. Xenova/bge-small-en-v1.5 info, root and onnx trees, and BAAI/bge-small-en-v1.5 licence — https://huggingface.co/api/models/Xenova/bge-small-en-v1.5 , https://huggingface.co/api/models/Xenova/bge-small-en-v1.5/tree/main , https://huggingface.co/api/models/Xenova/bge-small-en-v1.5/tree/main/onnx , https://huggingface.co/api/models/BAAI/bge-small-en-v1.5 (checked 16 Oct 2026)
23. onnx-community/all-MiniLM-L6-v2-ONNX info and onnx tree — https://huggingface.co/api/models/onnx-community/all-MiniLM-L6-v2-ONNX , https://huggingface.co/api/models/onnx-community/all-MiniLM-L6-v2-ONNX/tree/main/onnx (checked 16 Oct 2026)
24. Xenova/paraphrase-multilingual-MiniLM-L12-v2 info and onnx tree — https://huggingface.co/api/models/Xenova/paraphrase-multilingual-MiniLM-L12-v2 , https://huggingface.co/api/models/Xenova/paraphrase-multilingual-MiniLM-L12-v2/tree/main/onnx (checked 16 Oct 2026)
25. Transformers.js WebGPU embedding benchmark results — https://huggingface.co/spaces/Xenova/webgpu-embedding-benchmark/discussions/3 , https://huggingface.co/spaces/Xenova/webgpu-embedding-benchmark/discussions/4 (checked 16 Oct 2026)
26. minishlab/potion-base-8M model card, API info and the ONNX-weights discussion — https://huggingface.co/minishlab/potion-base-8M , https://huggingface.co/api/models/minishlab/potion-base-8M , https://huggingface.co/minishlab/potion-base-8M/discussions/1 (checked 16 Oct 2026)
27. Announcing Vite 8 — https://vite.dev/blog/announcing-vite8 (checked 16 Oct 2026)
28. Vite features: Web Workers, WebAssembly — https://vite.dev/guide/features (checked 16 Oct 2026)
29. create-vite template-react-ts package.json — https://raw.githubusercontent.com/vitejs/vite/main/packages/create-vite/template-react-ts/package.json (checked 16 Oct 2026)
30. GitHub advisory CVE-2026-39363 (an earlier Vite dev-server advisory, April 2026) — https://github.com/advisories/GHSA-p9ff-h696-f583 (checked 16 Oct 2026)
31. React v19.3.0 release — https://github.com/facebook/react/releases/tag/v19.3.0 (checked 16 Oct 2026)
32. React v19.3.1 release — https://github.com/facebook/react/releases/tag/v19.3.1 (checked 16 Oct 2026)
33. Pantheon: Next.js security release (secondary, on React 19.3.1 and siblings) — https://docs.pantheon.io/release-notes/2026/10/nextjs-security-release (checked 16 Oct 2026)
34. React blog index — https://react.dev/blog (checked 16 Oct 2026)
35. Announcing TypeScript 7.0 — https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/ (checked 16 Oct 2026)
36. Biome releases — https://github.com/biomejs/biome/releases (checked 16 Oct 2026)
37. Vitest 5 announcement — https://vitest.dev/blog/vitest-5 (checked 16 Oct 2026)
38. Playwright release notes — https://playwright.dev/docs/release-notes (checked 16 Oct 2026)
39. The Open Graph protocol — https://ogp.me/ (checked 16 Oct 2026)
40. Facebook sharing: images — https://developers.facebook.com/docs/sharing/webmasters/images/ (checked 16 Oct 2026)
41. OpenGraphPlus: X card images (secondary) — https://opengraphplus.com/consumers/twitter/images (checked 16 Oct 2026)
42. DataReportal, Digital 2025: accelerated access (Ookla data, Nov 2024) — https://datareportal.com/reports/digital-2025-sub-section-accelerated-access (checked 16 Oct 2026)
43. Local measurements, 16 Oct 2026: Vite 8.3.3 production build and dev-server probe with @huggingface/transformers 4.3.0 and react 19.3.0; latency bench in Chrome 155 on this Mac via the chrome-devtools MCP with CPU throttling. Scripts live in the session scratchpad, not in the repository; method described above.
44. Package contents inspected locally after `npm pack`: @huggingface/transformers 4.3.0 (`package.json`, `dist/transformers.web.js`), onnxruntime-web 1.30.0 and 1.31.0-dev.20260914-8d85527a0 (`package.json` exports, `dist/*.wasm`, `dist/*.mjs`); the four `.wasm` binaries of the dev build re-downloaded by the skeptic from https://cdn.jsdelivr.net/npm/onnxruntime-web@1.31.0-dev.20260914-8d85527a0/dist/ and re-measured (checked 16 Oct 2026)
45. sharp documentation — https://sharp.pixelplumbing.com/ (checked 16 Oct 2026)
46. satori releases — https://github.com/vercel/satori/releases (checked 16 Oct 2026)
47. Vite changelog (entries for 8.3.3 and 8.3.4) — https://raw.githubusercontent.com/vitejs/vite/main/packages/vite/CHANGELOG.md (checked 16 Oct 2026)

## Verification notes (skeptic)

Second pass on 16 Oct 2026, 12:20–13:00 UTC. Every version, date and licence in the stack table was re-read from the npm registry; the four Hub trees, the ORT WASM binaries, and sources 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36, 37, 38, 39, 40, 42, 45, 46 and 47 were reopened. The latency and bundle-size measurements [43] could not be repeated here and stand as the author's.

1. **Units fixed.** The model sizes were MiB labelled MB (22,972,370 bytes was written as 21.9 MB) while the WASM and Vite figures were decimal MB. Every model size, total and derived figure is now decimal MB from the Hub's byte counts. The effect is material: the bge-small class moves from "37–40 MB, on the line" to 39–41 MB, over the 40 MB budget unless brotli is served; the MiniLM class from 27–29 MB to 28–31 MB. The recommendation does not change; its margin shrinks from 11 MB to 9–12 MB.
2. **WASM sizes confirmed** by re-downloading the pinned dev build from jsdelivr: asyncify 26,861,777 bytes (gzip -9 6,596,823; brotli -q 11 3,883,805), plain 14,264,838 (3,661,630; 2,307,197), jsep 28,352,885, jspi 16,811,691. The bundle hard-codes `https://cdn.jsdelivr.net/npm/onnxruntime-web@${version}/dist/` as the default `wasmPaths`, selects the `.asyncify` binary, forces `powerPreference = "high-performance"` and checks `shader-f16` [44]; the custom-usage doc says the WASM path "Defaults to use a CDN" [7].
3. **Tokenizer sizes filled in**: 711,661 bytes (MiniLM) and 711,396 bytes (bge-small), both 0.71 MB; bge-small's was "unknown".
4. **onnx-community/all-MiniLM-L6-v2-ONNX** stores each dtype as `.onnx` plus an external `.onnx_data` file; the table now says so, since a self-hosted copy must ship both files.
5. **HF v4 post**: the "about 10%" bundle figure is the average across builds; the post also says the default web export is 53% smaller. Both are now stated.
6. **Counting**: there are twelve `4.0.0-next` builds on npm (next.0 to next.11), not eleven.
7. **@types/node**: npm's `latest` is 26.6.5 (9 Oct 2026); 24.19.2 is only the newest 24.x. The row now says so; the 24.19.1 pin stands because Node 24 is pinned.
8. **Quote length**: one WebGPU-guide quote ran to 16 words and is paraphrased. No other quote exceeds 15 words.
9. **Orphaned sources**: 11 (ORT WebGPU EP doc) and 30 (CVE-2026-39363) were listed but never cited; both were opened and now support a sentence each.
10. **Gating and licences**: Xenova/all-MiniLM-L6-v2, BAAI/bge-small-en-v1.5 and minishlab/potion-base-8M all report `gated: false` on the Hub API; licences apache-2.0, MIT and MIT. Added as recommendation 8. The Xenova bge-small and multilingual conversion repositories have no licence field of their own.
11. **Confirmed as written**: ONNX Runtime v1.31.0 published 2026-10-09T04:51Z (GitHub API) with no stable 1.31.0 for `onnxruntime-web` on npm; Transformers.js 4.3.0 release notes (Safari 26 WebGPU, ORT upgrade, duplicate-download fix, no cache writes for non-HTTP(S)); 4.1.0 added q1/q1f16/q2/q2f16; 4.3.1 adds only EmbeddingGemma 2; TypeScript 7.0 (8 Jul 2026, Go, new defaults, no API until 7.1, `@typescript/typescript6`, 8–12×); Vite 8 (12 Mar 2026, Rolldown and Oxc, Node 20.19+/22.12+); Vite 8.3.3 changelog's four fixes and 8.3.4 on 8 Oct; create-vite react-ts template at `typescript ~6.0.2` with oxlint; Vitest 5 (3 Sep 2026, Vite ≥ 6.4.0, Node ≥ 22.12.0, clearMocks true, strict locators, awaited assertions); React 19.3.0 (9 Sep 2026, ViewTransition, Fragment refs, `browser()`) and 19.3.1 (one RSC transport change); Playwright 1.63 features; Biome 2.5.15 on 30 Sep with weekly 2.5.x patches; Safari 26.0 (15 Sep 2025, WebGPU on four platforms) and 16.4 (27 Mar 2023, WASM SIMD); Chrome 121 (18 Jan 2024, Android 12+, Qualcomm and ARM); Firefox 141 (22 Jul 2025, Windows) and 147 (13 Jan 2026, Apple silicon); caniuse 87.82% and no default Firefox on Linux or Android; MDN "limited availability", secure context only; ORT README marks Safari WebGPU unsupported and WASM supported everywhere; ORT numThreads = min(half hardwareConcurrency, 4), needs crossOriginIsolated, proxy incompatible with WebGPU; HF env defaults (allowLocalModels false in browsers, `/models/`, `transformers-cache`, useWasmCache, customCache match/put); HF React tutorial worker constructor, singleton and six status strings; Vite's worker detection rule and `?worker`; the Xenova benchmark figures 386 ms / 23.8 ms (discussion 4; discussion 3 has 378 / 32.4 from a second run); potion-base-8M MIT, 7.56M parameters, ONNX weights working with Transformers.js since 31 Oct 2024; sharp Apache-2.0, Node ≥ 20.9.0; satori 0.56.2 → 0.62.0 between 14 and 16 Oct 2026 and resvg-js 2.6.2 from 26 Mar 2024, both MPL-2.0; ogp.me required properties and the og:image:alt rule; Facebook 1200 × 630, 1.91:1, 8 MB, width/height tags; Ookla 61.52 Mbps (Nov 2024) and Myanmar 5.09 Mbps via DataReportal.
12. **Still unverified**: the X card limits (secondary source only), whether the 6 Oct Vite patch wave was security-labelled, Vercel's brotli behaviour, and any phone measurement.
