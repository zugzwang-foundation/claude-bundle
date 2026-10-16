# Licences: every model and package Bundle depends on

Status: DRAFT — research note, 2026-10-16.

## The question

D12 says: datasets CC BY 4.0, like the docs; model weights Apache-2.0, so base models must be Apache-2.0 or MIT. Relay rule 8 adds: every model we train from, ship or generate data with, and every package we depend on, must allow that, and gated models are skipped. This note checks, against sources opened on 16 October 2026, the licence of every model named across the six research tracks (base encoders, teachers, comparators, datasets) and every package the pipeline and the website pin, and asks three things of each: what the licence is (exact SPDX name where one exists), whether it restricts outputs or training on outputs, and whether it is compatible with code under Apache-2.0, data under CC BY 4.0 and weights under Apache-2.0. It also says where the other tracks' licence claims were loose. Nothing here is from memory; where a thing was not opened today it says "unknown".

## Findings

### How each line was checked

- Models: the Hugging Face Hub API `https://huggingface.co/api/models/<id>` for `gated` (`false`, `auto` or `manual`), `cardData.license`, the `license:` tag and `createdAt`; where the card links a LICENSE file it was read raw [1–3]. Datasets: the same at `/api/datasets/<id>` [4].
- Python packages: PyPI's JSON API for the exact pinned version in `pipeline/pyproject.toml` (W3), reading `license_expression`, `license`, the licence classifier and the upload date [5]. npm packages: the registry document for the exact version pinned in `web/package.json` (W5) [6]. Repositories and fonts: the GitHub API `license.spdx_id` and the raw LICENSE or OFL.txt [7–9].
- Licence texts read today: Gemma Terms of Use [10], the Gemma 4 licence page [11] and Gemma Prohibited Use Policy [12], Llama 4 Community License [13], LFM Open License v1.0 [14], NVIDIA Nemotron Open Model License [15], the NGC vLLM container page [16], Anthropic's Commercial Terms [17], the SIL Open Font License 1.1 as shipped in google/fonts [9], PyTorch's LICENSE [18], gpt-oss's LICENSE and USAGE_POLICY [19].

### What the licence classes mean for Bundle

- **Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, 0BSD, Zlib, BSL-1.0, PSF-2.0**: permissive, no clause about outputs or about training on outputs. All are fine as dependencies of Apache-2.0 code. Apache-2.0 or MIT weights can be fine-tuned and the result released under Apache-2.0 if the upstream LICENSE and notice travel with it. (A BSD-3-Clause base would be fine too; none is in play.)
- **"MIT OR Apache-2.0"** (Biome, uv): the user picks either; fine.
- **OFL-1.1** (both fonts): font software "can be bundled, embedded" and redistributed with any software, cannot be "sold by itself", and the OFL text must accompany the files; Reserved Font Names bind only if declared, and neither font declares one [9]. Fonts are assets under their own licence, not Apache-2.0 code; the repository must say so.
- **CC BY 4.0** (Nemotron-Personas): attribution in the dataset card; compatible with Bundle's CC BY 4.0 data.
- **Excluders**: CC BY-NC and CC BY-NC-SA (non-commercial); the Gemma Terms of Use, whose "Model Derivatives" include models made from Gemma's outputs through distillation or "synthetic data Outputs by Gemma for training", with use restrictions that must pass through and a right for Google to restrict usage remotely [10]; the Llama 4 Community License, which requires a model trained on Llama outputs to carry "Llama" at the start of its name, to display "Built with Llama", and to pass through the Acceptable Use Policy, plus the 700 million monthly-active-users clause [13]; the LFM Open License v1.0, which bars commercial use by entities with annual revenue of US$10 million or more [14]; the NVIDIA Nemotron Open Model License, which allows commercial use and claims no ownership of outputs but is its own licence with a notice obligation, so it fails D12 as a base [15]; repositories with no licence at all; gated repositories; and hosted services whose terms forbid training on outputs (Anthropic: customers may not use the Services "to train competing AI models" [17]).

### The tables

Columns: name; what it is; licence (SPDX where one exists); restriction on outputs or training (yes/no/unknown); compatible with code Apache-2.0 / data CC BY 4.0 / weights Apache-2.0 (yes/no; "n/a" where the question has no meaning, e.g. a package's weights); source; date checked. For packages, the weights column means "may sit in the training or export toolchain without reaching the weights' licence".

**Table 1. Base encoders (student candidates).**

| Name | What it is | Licence | Restricts outputs or training | Code / data / weights | Source | Checked |
|---|---|---|---|---|---|---|
| sentence-transformers/all-MiniLM-L6-v2 | 22.7M English sentence encoder; the pipeline's encoder (`config.py`) and V0 base; fine-tuned from nreimers/MiniLM-L6-H384-uncased | Apache-2.0; `gated: false` | no | yes / yes / yes | [1a] card line 5 | 16 Oct 2026 |
| Xenova/all-MiniLM-L6-v2 | Transformers.js ONNX mirror; the id in `web/src/sorter/model-manifest.json` | Apache-2.0 (tag); `gated: false` | no | yes / yes / yes | [1b] | 16 Oct 2026 |
| mixedbread-ai/mxbai-embed-xsmall-v1 | 24.1M, built on all-MiniLM-L6-v2, 4,096-token context; challenger encoder | Apache-2.0; `gated: false` | no | yes / yes / yes | [1c] card line 1658 | 16 Oct 2026 |
| Snowflake/snowflake-arctic-embed-xs | 22M retrieval encoder | Apache-2.0 per the card text ("licensed under the Apache-2"); no `license` field in Hub metadata | no | yes / yes / yes | [1d] | 16 Oct 2026 |
| BAAI/bge-small-en-v1.5 | 33.4M, 12 layers | MIT; `gated: false` | no | yes / yes / yes | [1e] | 16 Oct 2026 |
| thenlper/gte-small | 33.4M | MIT; `gated: false` | no | yes / yes / yes | [1f] | 16 Oct 2026 |
| cross-encoder/ms-marco-MiniLM-L6-v2 | 22.7M cross-encoder; V1 reranker at most | Apache-2.0; `gated: false` | no | yes / yes / yes | [1g] | 16 Oct 2026 |
| ibm-granite/granite-embedding-30m-english | 30M, no quantised file | Apache-2.0; `gated: false` | no | yes / yes / yes | [1h] | 16 Oct 2026 |
| minishlab/potion-base-8M | 7.56M static (model2vec) fallback | MIT; `gated: false` | no | yes / yes / yes | [1i] | 16 Oct 2026 |
| sentence-transformers/static-similarity-mrl-multilingual-v1 | static multilingual; V1 experiment | Apache-2.0; `gated: false` | no | yes / yes / yes | [1j] | 16 Oct 2026 |
| sentence-transformers/all-mpnet-base-v2 | 0.1B; DSTC11 baseline reference, not shipped | Apache-2.0; `gated: false` | no | yes / yes / yes | [1k] | 16 Oct 2026 |
| intfloat/multilingual-e5-small | 118 MB int8, over budget | MIT; `gated: false` | no | yes / yes / yes (size excludes it) | [1l] | 16 Oct 2026 |
| nomic-ai/nomic-embed-text-v1.5 | 137 MB int8, over budget | Apache-2.0; `gated: false` | no | yes / yes / yes (size excludes it) | [1m] | 16 Oct 2026 |
| google/embeddinggemma-2 | 270M text encoder; over budget; possible V1 embedding teacher | Apache-2.0; `gated: false`; created 14 Sep 2026 | no. Note: EmbeddingGemma (v1) is listed under the Gemma Terms [10] and is excluded | yes / yes / yes | [1n] | 16 Oct 2026 |
| jinaai/jina-embeddings-v5-text-small | 677M | CC-BY-NC-4.0 | yes (non-commercial) | no / no / no | [1o] | 16 Oct 2026 |
| hotchpotch/bekko-system-one-v0-400m | 17M–400M encoders, 29 MB browser build | none: no licence field or tag; card says the licence is to be finalised (R1) | unknown | no / no / no | [1p] | 16 Oct 2026 |

**Table 2. Teachers.**

| Name | What it is | Licence | Restricts outputs or training | Code / data / weights | Source | Checked |
|---|---|---|---|---|---|---|
| Qwen/Qwen3.6-35B-A3B | 35B/3B MoE; Spark teacher (R3 pick) | Apache-2.0; LICENSE is the unmodified Apache text; `gated: false` | no | yes / yes / yes | [2a] | 16 Oct 2026 |
| nvidia/Qwen3.6-35B-A3B-NVFP4 | NVFP4 checkpoint of the above | Apache-2.0; `gated: false` | no | yes / yes / yes | [2b] | 16 Oct 2026 |
| Qwen/Qwen3-30B-A3B-Instruct-2507 | fallback A | Apache-2.0; `gated: false` | no | yes / yes / yes | [2c] | 16 Oct 2026 |
| Qwen/Qwen3-4B-Instruct-2507 | Mac toy teacher | Apache-2.0; LICENSE is the Apache text; `gated: false` | no | yes / yes / yes | [2d] | 16 Oct 2026 |
| unsloth/Qwen3-4B-Instruct-2507-GGUF | Q4_K_M file W3 actually serves | Apache-2.0 tag, linking Qwen's LICENSE; `gated: false` | no | yes / yes / yes | [2e] | 16 Oct 2026 |
| openai/gpt-oss-120b (and 20b) | fallback B | Apache-2.0 (LICENSE is the Apache text) plus a one-sentence USAGE_POLICY: comply with applicable law; `gated: false` | no | yes / yes / yes | [2f] [19] | 16 Oct 2026 |
| google/gemma-4-26B-A4B-it, gemma-4-31B-it | second teacher (one person in five); Strands' teacher | Apache-2.0: the licence page carries the unmodified Apache text and the card says "apache-2.0"; `gated: false` | no, in the licence. Google's site also links a Prohibited Use Policy (21 Feb 2024) written for "Gemma or Model Derivatives" under the Gemma Terms; the Apache text does not incorporate it | yes / yes / yes, with that caveat | [2g] [11] [12] | 16 Oct 2026 |
| zai-org/GLM-4.7-Flash | 31B/3B MoE; third voice | MIT; `gated: false` | no | yes / yes / yes | [2h] | 16 Oct 2026 |
| google/gemma-3-27b-it | the relay's "Gemma 3 (note its terms)" | Gemma Terms of Use (tag `gemma`); `gated: manual` | yes: a student trained on its outputs is a Model Derivative; use restrictions pass through; remote restriction | no / no / no | [2i] [10] | 16 Oct 2026 |
| meta-llama/Llama-4-Scout-17B-16E-Instruct | Llama family | Llama 4 Community License (tag `other`, name `llama4`); `gated: manual` | yes: "Llama" name prefix, "Built with Llama", 700M MAU, AUP pass-through | no / no / no | [2j] [13] | 16 Oct 2026 |
| nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | 30B/3.5B hybrid MoE | NVIDIA Nemotron Open Model License, 15 Dec 2025 (tag `other`); `gated: false` | outputs: no (NVIDIA claims no ownership); derivatives must carry an NVIDIA licence notice | n/a / yes / no (not Apache-2.0 or MIT) | [2k] [15] | 16 Oct 2026 |

**Table 3. Comparators and hosted services.**

| Name | What it is | Licence | Restricts outputs or training | Code / data / weights | Source | Checked |
|---|---|---|---|---|---|---|
| Cloudflare/clef-flash | 9B decision model on Qwen/Qwen3.5-9B (Apache-2.0); D11 comparator | Apache-2.0; card: released under Apache-2.0 "following the base model"; `gated: false` | no | yes / yes / yes | [3a] [3b] | 16 Oct 2026 |
| Cloudflare/clef | 27B on Qwen3.8-27B (Apache-2.0) | Apache-2.0; `gated: false` | no | yes / yes / yes | [3c] [3d] | 16 Oct 2026 |
| StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 | 1.9B on Qwen/Qwen3.5-2B-Base (Apache-2.0); trained on Gemma-4-31B-it outputs; per-source licence list in `training/sources.md` | Apache-2.0; `gated: false` | no | yes / yes / yes | [3e] [3f] | 16 Oct 2026 |
| perplexity-ai/pplx-decider-v1.1-27b | 26B on Qwen3.8-27B | Apache-2.0; `gated: false` | no | yes / yes / yes | [3g] | 16 Oct 2026 |
| vllm-sr/d3-flash, vllm-sr/d3-mini | 8.4B and 4B | Apache-2.0; `gated: false` | no | yes / yes / yes | [3h] | 16 Oct 2026 |
| h2oai/h2o-lightning-4b | 4.7B | Apache-2.0; `gated: false` | no | yes / yes / yes | [3i] | 16 Oct 2026 |
| convaiinnovations/laya | 322M–421M encoders | Apache-2.0; `gated: false` | no | yes / yes / yes | [3j] | 16 Oct 2026 |
| LiquidAI/d1-3B, d1-omni-600M | 3.1B and 587M decision models on LFM2.5 | LFM Open License v1.0 (tag `other`, name `lfm1.0`); not gated | yes: no commercial use at or above US$10M annual revenue | no / no / no | [3k] [14] | 16 Oct 2026 |
| Claude Haiku 5.5 (Anthropic API) | hosted LLM; D11 weekly comparator, with approval | Anthropic Commercial Terms, 17 Jun 2025; no weights | yes: may not use the Services "to train competing AI models" | n/a / no (its outputs can never be lessons, labels or exam items) / n/a | [17] | 16 Oct 2026 |
| Jev, OpenAI Decisions API, Microsoft-Decision-1 | hosted only, no weights (R1) | proprietary | unknown | no (nothing to download) | decision-models.md | 16 Oct 2026 |

**Table 4. Datasets and reference corpora.**

| Name | What it is | Licence | Restricts outputs or training | Code / data / weights | Source | Checked |
|---|---|---|---|---|---|---|
| nvidia/Nemotron-Personas-USA, -India | persona seeds (R3 recipe step 1) | CC-BY-4.0 (card section "License/Terms of Use"); `gated: false`; made with gpt-oss-120b | attribution only | n/a / yes / n/a | [4a] | 16 Oct 2026 |
| proj-persona/PersonaHub | personas | CC-BY-NC-SA-4.0 | yes (non-commercial, share-alike) | n/a / no / n/a | [4b] | 16 Oct 2026 |
| lmsys/lmsys-chat-1m | real chats | own agreement; `gated: auto`; no licence tag | yes | n/a / no / n/a (D3 excludes real chats anyway) | [4c] | 16 Oct 2026 |
| allenai/WildChat-1M | real chats | ODC-BY on the Hub card (tag `odc-by`); the arXiv abstract names AI2 ImpACT licences | unclear: two statements | n/a / no (D3) / n/a | [4d] | 16 Oct 2026 |
| snap-research/locomo | memory benchmark | CC BY-NC 4.0 (repository LICENSE.txt) | yes | n/a / no / n/a | [4e] | 16 Oct 2026 |
| CLINC150 (clinc/oos-eval), Banking77 (PolyAI) | metric patterns only, never data | CC BY 3.0 and CC BY 4.0 per R5's reading of the LICENSE files today; GitHub API shows no SPDX id | no | not used as data | prior-art.md [59][60] | 16 Oct 2026 |

**Table 5. Python packages, pinned in `pipeline/pyproject.toml` (version, PyPI upload date).**

| Name | What it is | Licence | Restricts outputs or training | Code / data / weights | Source | Checked |
|---|---|---|---|---|---|---|
| torch 2.14.1 (30 Sep 2026) | training and ONNX export | BSD-3-Clause (LICENSE file); PyPI expression "Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT" for bundled parts | no | yes / n/a / yes | [5] [18] | 16 Oct 2026 |
| sentence-transformers 6.1.0 (18 Sep 2026) | encoder loading, MNRL training | Apache-2.0 | no | yes / n/a / yes | [5] [7a] | 16 Oct 2026 |
| transformers 5.18.0 (30 Sep 2026) | model classes | Apache-2.0 (free text "Apache 2.0 License") | no | yes / n/a / yes | [5] | 16 Oct 2026 |
| tokenizers 0.23.2 (3 Sep 2026) | tokeniser | Apache-2.0 (classifier only) | no | yes / n/a / yes | [5] | 16 Oct 2026 |
| onnx 1.23.1 (29 Sep 2026) | ONNX graph | Apache-2.0 | no | yes / n/a / yes | [5] [7b] | 16 Oct 2026 |
| onnxruntime 1.30.0 (10 Sep 2026) | quantise_dynamic, checks | MIT | no | yes / n/a / yes | [5] [7c] | 16 Oct 2026 |
| optimum-onnx 0.1.0 (23 Dec 2025) | named by the relay; dropped by W3 (pins transformers<4.58) | Apache-2.0 | no | yes / n/a / yes | [5] [7d] | 16 Oct 2026 |
| optimum 2.3.0 (4 Aug 2026) | not used | Apache-2.0 (free text "Apache") | no | yes / n/a / yes | [5] | 16 Oct 2026 |
| pydantic 2.13.5 (28 Aug 2026) | schemas | MIT | no | yes / n/a / n/a | [5] | 16 Oct 2026 |
| httpx 0.28.1 (6 Dec 2024) | teacher client | BSD-3-Clause | no | yes / n/a / n/a | [5] | 16 Oct 2026 |
| numpy 2.5.3 (6 Sep 2026) | maths | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | no | yes / n/a / yes | [5] | 16 Oct 2026 |
| scikit-learn 1.9.1 (10 Sep 2026) | GroupShuffleSplit, calibration | BSD-3-Clause | no | yes / n/a / yes | [5] | 16 Oct 2026 |
| ruff 0.16.10 (1 Oct 2026) | lint, dev only | MIT | no | yes / n/a / n/a | [5] | 16 Oct 2026 |
| pytest 9.1.1 (19 Jun 2026) | tests, dev only | MIT | no | yes / n/a / n/a | [5] | 16 Oct 2026 |
| uv 0.13.1 (14 Oct 2026; `uv_build>=0.13.1` in pyproject) | package manager and build backend | MIT OR Apache-2.0 (both LICENSE files in the repo) | no | yes / n/a / n/a | [5] [7e] | 16 Oct 2026 |
| vllm 0.31.0 latest (5 Oct 2026); 0.30.0 is the 14-day pin | Spark serving (BDL-4) | Apache-2.0 | no | yes / n/a / n/a | [5] [7f] | 16 Oct 2026 |
| datasketch 2.0.0 (5 Jul 2026) | MinHash dedupe, candidate | MIT | no | yes / n/a / n/a | [5] | 16 Oct 2026 |
| text-dedup 0.4.1 (28 Dec 2025) | dedupe, candidate | Apache-2.0 (repository LICENSE); PyPI metadata has no licence field | no | yes / n/a / n/a | [5] [7g] | 16 Oct 2026 |
| model2vec 0.10.0 (11 Oct 2026) | static-model path | MIT | no | yes / n/a / yes | [5] | 16 Oct 2026 |
| setfit 1.2.0 (4 Sep 2026) | recipe reference | Apache-2.0 | no | yes / n/a / yes | [5] | 16 Oct 2026 |
| mapie 1.5.0 (5 Aug 2026) | conformal sets, V1 | BSD-3-Clause | no | yes / n/a / yes | [5] | 16 Oct 2026 |
| huggingface-hub 2.2.0 | transitive | Apache-2.0 | no | yes / n/a / n/a | [5] | 16 Oct 2026 |
| CPython 3.14 | runtime | PSF-2.0 ("Python Software Foundation License Version 2") | no | yes / n/a / n/a | [8a] | 16 Oct 2026 |

**Table 6. npm packages, pinned in `web/package.json`.**

| Name | What it is | Licence | Restricts outputs or training | Code / data / weights | Source | Checked |
|---|---|---|---|---|---|---|
| @huggingface/transformers 4.3.0 | in-browser inference | Apache-2.0 | no | yes / n/a / n/a | [6] [7h] | 16 Oct 2026 |
| onnxruntime-web 1.31.0-dev.20260914-8d85527a0 (the exact build 4.3.0 depends on; latest stable 1.30.0) | WASM runtime; binaries self-hosted in `web/public/ort/` | MIT | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| onnxruntime-node 1.30.0 (dependency of 4.3.0) | Node-side inference for the precompute script | MIT | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| react 19.3.0, react-dom 19.3.0 | UI | MIT | no | yes / n/a / n/a | [6] [7i] | 16 Oct 2026 |
| vite 8.3.2 | build | MIT | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| @vitejs/plugin-react 6.1.1 | build | MIT | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| typescript 7.0.2 | compiler | Apache-2.0 | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| @biomejs/biome 2.5.15 | lint and format | MIT OR Apache-2.0 | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| vitest 5.0.3 | unit tests | MIT | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| @playwright/test 1.63.0 | end-to-end tests, OG image | Apache-2.0 | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| @types/react, @types/react-dom 19.3.0; @types/node | types | MIT | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| sharp 0.35.x (transitive of transformers.js) | image codec | Apache-2.0 | no | yes / n/a / n/a | [6] | 16 Oct 2026 |
| Node.js 24.21.0 | runtime | MIT (LICENSE header; bundled deps carry their own) | no | yes / n/a / n/a | [8b] | 16 Oct 2026 |

**Table 7. Tools, containers and fonts.**

| Name | What it is | Licence | Restricts outputs or training | Code / data / weights | Source | Checked |
|---|---|---|---|---|---|---|
| llama.cpp (llama-server 0.5.0, W3's Mac teacher server) | GGUF serving | MIT | no | yes / n/a / n/a | [7j] | 16 Oct 2026 |
| Ollama | convenience runtime, not for bulk | MIT | no | yes / n/a / n/a | [7k] | 16 Oct 2026 |
| nvcr.io/nvidia/vllm container (26.05-py3; latest 26.09-py3) | Spark serving image | NVIDIA End User License Agreement plus Product-Specific Terms for AI Products; not open | unknown (tool run on our machine; nothing shipped) | n/a | [16] | 16 Oct 2026 |
| NVIDIA/dgx-spark-playbooks | recipes | Apache-2.0 | no | yes / n/a / n/a | [7l] | 16 Oct 2026 |
| Tailscale client | remote access | BSD-3-Clause | no | n/a | [7m] | 16 Oct 2026 |
| Bricolage Grotesque (variable woff2 from ateliertriay/bricolage) | display font, self-hosted in `web/public/fonts/` with `OFL-BricolageGrotesque.txt` | OFL-1.1; "Copyright 2022 The Bricolage Grotesque Project Authors"; no Reserved Font Name | may be bundled and embedded; not sold alone; keep the OFL text | yes as an asset under its own licence | [9a] [7n] | 16 Oct 2026 |
| Atkinson Hyperlegible (googlefonts/atkinson-hyperlegible, 2021) | body font, self-hosted with `OFL-AtkinsonHyperlegible.txt` | OFL-1.1; "Copyright 2020 Braille Institute of America, Inc."; no Reserved Font Name | same | yes as an asset | [9b] [7o] | 16 Oct 2026 |
| Atkinson Hyperlegible Next (google/fonts, added 7 Jan 2025) | newer family, not used | OFL-1.1 | same | yes if ever swapped in | [9c] | 16 Oct 2026 |

## Options compared

| Policy option for D12 and rule 8 | What it would allow | What it costs | Verdict |
|---|---|---|---|
| A. D12 as written: bases Apache-2.0 or MIT; packages any OSI-permissive, no copyleft | every model and package the tracks recommend | nothing: all pass | **Keep** |
| B. Read "Apache-2.0 or MIT" literally for packages too | would wrongly exclude torch, httpx, numpy, scikit-learn, mapie (BSD-3-Clause), Biome and uv (dual) | the whole toolchain | Reject; write "permissive" for packages |
| C. Admit Nemotron Open Model License models as teachers | one more fast MoE teacher | a third licence to track and an NVIDIA notice in the dataset card | Not needed; Qwen and Gemma 4 suffice |
| D. Admit Gemma 4 as a second teacher | model variety (R3's one-in-five) | the prohibited-use policy question on Google's site, even though the Apache text does not incorporate it | Yes, secondary only; say so in the dataset card |
| E. Admit Gemma Terms, Llama or LFM1.0 models | more teachers and comparators | pass-through naming, use restrictions or a revenue cap on the student | **Reject** |
| F. Use Claude Haiku 5.5 as a labeller or teacher | cheap labels | Anthropic's terms forbid training competing models on outputs | Reject; comparator only (D11) |
| G. Cite a mirror repository (Xenova, onnx-community) as the licence source | convenience | mirrors sometimes carry no licence tag (Xenova/bge-small-en-v1.5) | Reject; cite the base repository and ship our own export with its LICENSE |

## Recommendation

1. **Base encoder.** `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0, not gated) with `mixedbread-ai/mxbai-embed-xsmall-v1` (Apache-2.0) as challenger; `BAAI/bge-small-en-v1.5` and `thenlper/gte-small` (MIT) and `minishlab/potion-base-8M` (MIT) are licence-clean alternatives. Ship Bundle's own ONNX export under `web/public/models/<id>/` with a `LICENSE` (Apache-2.0) and a `NOTICE` naming the base model, its repository and licence; do not depend on a mirror's tag.
2. **Teachers.** Qwen3.6-35B-A3B via `nvidia/Qwen3.6-35B-A3B-NVFP4` (Apache-2.0) first; Qwen3-30B-A3B-Instruct-2507 and gpt-oss-120b (both Apache-2.0) as fallbacks; Gemma 4 26B-A4B-it (Apache-2.0) secondary; on the Mac, Qwen3-4B-Instruct-2507 as the unsloth GGUF (Apache-2.0 tag, Qwen's Apache LICENSE). GLM-4.7-Flash (MIT) is a clean third voice. The dataset card names every teacher and its licence and credits NVIDIA for Nemotron-Personas (CC BY 4.0).
3. **Comparators.** Clef-flash, Clef, pplx-decider v1.1, Strands Decider 2B, d3-flash and d3-mini, H2O-Lightning-4B and Laya are all Apache-2.0 and `gated: false`, and so may also label ambiguous teacher output on the Spark. Liquid d1 is out (LFM1.0). Haiku 5.5 is a scoreboard comparator only, with approval, and its outputs are never stored as data.
4. **Packages.** Everything pinned by W3 and W5 is Apache-2.0, MIT, BSD-3-Clause, dual MIT/Apache-2.0 or PSF-2.0; nothing copyleft. Three to tidy: pin `text-dedup` to a git tag (no PyPI licence metadata) or use `datasketch`; note that `uv_build>=0.13.1` points at a release two days old; add `onnxruntime`'s MIT LICENSE next to the self-hosted WASM binaries in `web/public/ort/`, since MIT requires the notice to travel with the binary.
5. **Fonts.** Keep both OFL.txt files beside the woff2 files (W5 has done this) and state in `web/README.md` and the site's licence page that the fonts are OFL-1.1, not Apache-2.0.
6. **Repository.** A top-level `LICENSE` (Apache-2.0) for code, `LICENSE-docs` (CC BY 4.0) for docs and datasets, and a `THIRD_PARTY_NOTICES.md` listing the base encoder, the fonts, the ONNX Runtime binaries and the teachers used for each data release. Add "no gated model, ever" to the pipeline's model-download step as a check on the Hub API's `gated` field.

## What doesn't work, or would change the plan

1. **Gemma 3 is out twice, not "note its terms".** `google/gemma-3-27b-it` is `gated: manual` and under the Gemma Terms of Use, whose Model Derivatives clause names synthetic-data training. The relay's candidate list should read "Gemma 3 excluded; Gemma 4 Apache-2.0". EmbeddingGemma v1 is on the same Terms page; EmbeddingGemma 2 is Apache-2.0.
2. **Gemma 4 is Apache-2.0, with a loose end R3 did not mention.** Google's Gemma 4 licence page shows the unmodified Apache text, and the Hub card says `apache-2.0`, but the same site links a Prohibited Use Policy dated 21 February 2024 that speaks of "Gemma or Model Derivatives". Apache-2.0 has no mechanism to bind a separate policy, so it does not restrict Bundle; it is still the one teacher a careful reader could question. Keep Gemma 4 secondary and record the reasoning.
3. **D12's "Apache-2.0 or MIT" is right for base weights and wrong as a package rule.** torch, httpx, numpy, scikit-learn and mapie are BSD-3-Clause; Biome and uv are "MIT OR Apache-2.0"; CPython is PSF-2.0. Relay rule 8 says "must allow that", which they do. If anyone reads D12 literally for packages, half the toolchain fails; the decision should say "permissive, no copyleft" for packages.
4. **Hub metadata is not a licence.** Snowflake's arctic-embed-xs has no `license` field though its card says Apache-2; the Xenova bge-small and paraphrase-multilingual conversions carry none (R4); Bekko carries none. Only a LICENSE file or a card sentence counts, and only from the base repository.
5. **Anthropic's terms close a door D11 left ajar.** "To train competing AI models" is forbidden, so Haiku 5.5 can never be a labeller, a tie-breaker or a source of exam items. Write that into the exam runner's rules, not only into DECISIONS.md.
6. **The NGC vLLM container is not open software.** It is under NVIDIA's EULA and AI product terms. It is a tool run on our own box, which is fine, but the site and README must not claim the whole stack is open-licensed; upstream `vllm/vllm-openai` (Apache-2.0) is the open alternative R6 already names.
7. **Nemotron is a teacher in principle, not a base.** NVIDIA claims no ownership of outputs, so Nemotron-written chats could be CC BY 4.0, but the weights are under NVIDIA's own licence and a notice obligation; R3's choice to skip it stands.
8. **Freshness and licence are separate checks.** uv 0.13.1 (14 Oct 2026) and @huggingface/transformers 4.3.1 (6 Oct) are licence-clean but inside the 14-day rule; W3's build backend bound and W5's typescript 7.0.2 (8 Jul, fine) show the two rules need separate lines in the pin table.
9. **Unknowns, on purpose.** The terms of Jev, OpenAI's Decisions API and Microsoft-Decision-1 (hosted, not used); whether Google regards its prohibited-use policy as a condition of Gemma 4 (the licence page is silent); CLINC150 and Banking77 LICENSE files were read by R5 today, not reopened here.

## Sources

1. Hugging Face Hub API, `https://huggingface.co/api/models/<id>`, fields `gated`, `cardData.license`, `license_name`, `license_link`, `tags`, `createdAt` (checked 16 Oct 2026), for:
   - 1a https://huggingface.co/api/models/sentence-transformers/all-MiniLM-L6-v2 and https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/raw/main/README.md
   - 1b https://huggingface.co/api/models/Xenova/all-MiniLM-L6-v2
   - 1c https://huggingface.co/api/models/mixedbread-ai/mxbai-embed-xsmall-v1 and https://huggingface.co/mixedbread-ai/mxbai-embed-xsmall-v1/raw/main/README.md
   - 1d https://huggingface.co/api/models/Snowflake/snowflake-arctic-embed-xs and https://huggingface.co/Snowflake/snowflake-arctic-embed-xs
   - 1e https://huggingface.co/api/models/BAAI/bge-small-en-v1.5
   - 1f https://huggingface.co/api/models/thenlper/gte-small
   - 1g https://huggingface.co/api/models/cross-encoder/ms-marco-MiniLM-L6-v2
   - 1h https://huggingface.co/api/models/ibm-granite/granite-embedding-30m-english
   - 1i https://huggingface.co/api/models/minishlab/potion-base-8M
   - 1j https://huggingface.co/api/models/sentence-transformers/static-similarity-mrl-multilingual-v1
   - 1k https://huggingface.co/api/models/sentence-transformers/all-mpnet-base-v2
   - 1l https://huggingface.co/api/models/intfloat/multilingual-e5-small
   - 1m https://huggingface.co/api/models/nomic-ai/nomic-embed-text-v1.5
   - 1n https://huggingface.co/api/models/google/embeddinggemma-2
   - 1o https://huggingface.co/api/models/jinaai/jina-embeddings-v5-text-small
   - 1p https://huggingface.co/api/models/hotchpotch/bekko-system-one-v0-400m
2. Teachers, same endpoint (checked 16 Oct 2026):
   - 2a https://huggingface.co/api/models/Qwen/Qwen3.6-35B-A3B and https://huggingface.co/Qwen/Qwen3.6-35B-A3B/raw/main/LICENSE
   - 2b https://huggingface.co/api/models/nvidia/Qwen3.6-35B-A3B-NVFP4
   - 2c https://huggingface.co/api/models/Qwen/Qwen3-30B-A3B-Instruct-2507
   - 2d https://huggingface.co/api/models/Qwen/Qwen3-4B-Instruct-2507 and https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/raw/main/LICENSE
   - 2e https://huggingface.co/api/models/unsloth/Qwen3-4B-Instruct-2507-GGUF
   - 2f https://huggingface.co/api/models/openai/gpt-oss-120b
   - 2g https://huggingface.co/api/models/google/gemma-4-26B-A4B-it , https://huggingface.co/api/models/google/gemma-4-31B-it and https://huggingface.co/google/gemma-4-26B-A4B-it
   - 2h https://huggingface.co/api/models/zai-org/GLM-4.7-Flash
   - 2i https://huggingface.co/api/models/google/gemma-3-27b-it
   - 2j https://huggingface.co/api/models/meta-llama/Llama-4-Scout-17B-16E-Instruct
   - 2k https://huggingface.co/api/models/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16
3. Comparators, same endpoint (checked 16 Oct 2026):
   - 3a https://huggingface.co/api/models/Cloudflare/clef-flash and https://huggingface.co/Cloudflare/clef-flash
   - 3b https://huggingface.co/api/models/Qwen/Qwen3.5-9B
   - 3c https://huggingface.co/api/models/Cloudflare/clef
   - 3d https://huggingface.co/api/models/Qwen/Qwen3.8-27B
   - 3e https://huggingface.co/api/models/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 and https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610
   - 3f https://huggingface.co/api/models/Qwen/Qwen3.5-2B-Base
   - 3g https://huggingface.co/api/models/perplexity-ai/pplx-decider-v1.1-27b
   - 3h https://huggingface.co/api/models/vllm-sr/d3-flash and https://huggingface.co/api/models/vllm-sr/d3-mini
   - 3i https://huggingface.co/api/models/h2oai/h2o-lightning-4b
   - 3j https://huggingface.co/api/models/convaiinnovations/laya
   - 3k https://huggingface.co/LiquidAI/d1-3B and https://huggingface.co/api/models/LiquidAI/LFM2.5-VL-3B
4. Datasets, `https://huggingface.co/api/datasets/<id>` (checked 16 Oct 2026):
   - 4a https://huggingface.co/api/datasets/nvidia/Nemotron-Personas-USA , https://huggingface.co/api/datasets/nvidia/Nemotron-Personas-India and https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA/raw/main/README.md
   - 4b https://huggingface.co/api/datasets/proj-persona/PersonaHub
   - 4c https://huggingface.co/api/datasets/lmsys/lmsys-chat-1m
   - 4d https://huggingface.co/api/datasets/allenai/WildChat-1M and https://arxiv.org/abs/2405.01470
   - 4e https://raw.githubusercontent.com/snap-research/locomo/main/LICENSE.txt
5. PyPI JSON API, `https://pypi.org/pypi/<package>/<version>/json`, for torch 2.14.1, sentence-transformers 6.1.0, transformers 5.18.0, tokenizers 0.23.2, onnx 1.23.1, onnxruntime 1.30.0, optimum-onnx 0.1.0, optimum 2.3.0, pydantic 2.13.5, httpx 0.28.1, numpy 2.5.3, scikit-learn 1.9.1, ruff 0.16.10, pytest 9.1.1, uv 0.13.1, vllm 0.31.0, datasketch 2.0.0, text-dedup 0.4.1, model2vec 0.10.0, setfit 1.2.0, mapie 1.5.0, huggingface-hub 2.2.0 (checked 16 Oct 2026)
6. npm registry, `https://registry.npmjs.org/<package>/<version>`, for @huggingface/transformers 4.3.0 (dependencies field), onnxruntime-web 1.31.0-dev.20260914-8d85527a0 and 1.30.0, onnxruntime-node 1.30.0, react 19.3.0, react-dom 19.3.0, vite 8.3.2, @vitejs/plugin-react 6.1.1, typescript 7.0.2, @biomejs/biome 2.5.15, vitest 5.0.3, @playwright/test 1.63.0, @types/react 19.3.0, @types/react-dom 19.3.0, @types/node, sharp (checked 16 Oct 2026)
7. GitHub API `https://api.github.com/repos/<owner>/<repo>`, field `license.spdx_id` (checked 16 Oct 2026): 7a huggingface/sentence-transformers (Apache-2.0) and https://raw.githubusercontent.com/huggingface/sentence-transformers/master/LICENSE ; 7b onnx/onnx ; 7c microsoft/onnxruntime ; 7d huggingface/optimum-onnx ; 7e astral-sh/uv with https://raw.githubusercontent.com/astral-sh/uv/main/LICENSE-MIT and LICENSE-APACHE (both present) ; 7f vllm-project/vllm ; 7g ChenghaoMou/text-dedup and https://raw.githubusercontent.com/ChenghaoMou/text-dedup/main/LICENSE ; 7h huggingface/transformers.js ; 7i react/react (facebook/react redirects) ; 7j ggml-org/llama.cpp ; 7k ollama/ollama ; 7l NVIDIA/dgx-spark-playbooks ; 7m tailscale/tailscale ; 7n ateliertriay/bricolage (OFL-1.1) ; 7o googlefonts/atkinson-hyperlegible (OFL-1.1)
8. Runtimes: 8a https://raw.githubusercontent.com/python/cpython/main/LICENSE ("PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2") ; 8b https://raw.githubusercontent.com/nodejs/node/main/LICENSE (checked 16 Oct 2026)
9. Fonts as served by Google Fonts (checked 16 Oct 2026): 9a https://raw.githubusercontent.com/google/fonts/main/ofl/bricolagegrotesque/OFL.txt and METADATA.pb ; 9b https://raw.githubusercontent.com/google/fonts/main/ofl/atkinsonhyperlegible/OFL.txt and METADATA.pb ; 9c https://raw.githubusercontent.com/google/fonts/main/ofl/atkinsonhyperlegiblenext/OFL.txt and METADATA.pb ; the W5 copies are listed in `web/README.md` with source commits and hashes
10. Gemma Terms of Use, last modified 1 April 2026 — https://ai.google.dev/gemma/terms (checked 16 Oct 2026)
11. Gemma 4 licence page, unmodified Apache License 2.0 text, "Last updated 2026-04-01" — https://ai.google.dev/gemma/docs/gemma_4_license (checked 16 Oct 2026)
12. Gemma Prohibited Use Policy, 21 February 2024 — https://ai.google.dev/gemma/prohibited_use_policy (checked 16 Oct 2026)
13. Llama 4 Community License Agreement, 5 April 2025 — https://raw.githubusercontent.com/meta-llama/llama-models/main/models/llama4/LICENSE (checked 16 Oct 2026)
14. LFM Open License v1.0 — https://huggingface.co/LiquidAI/d1-3b/blob/main/LICENSE (checked 16 Oct 2026)
15. NVIDIA Nemotron Open Model License, 15 December 2025 — https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/ (checked 16 Oct 2026)
16. NGC catalogue, vLLM container (EULA and Product-Specific Terms for AI Products; latest tag 26.09-py3) — https://catalog.ngc.nvidia.com/orgs/nvidia/containers/vllm (checked 16 Oct 2026)
17. Anthropic Commercial Terms of Service, effective 17 June 2025, section D.4 — https://www.anthropic.com/legal/commercial-terms (checked 16 Oct 2026)
18. PyTorch LICENSE (BSD-3-Clause text) — https://raw.githubusercontent.com/pytorch/pytorch/main/LICENSE (checked 16 Oct 2026)
19. gpt-oss LICENSE and USAGE_POLICY — https://raw.githubusercontent.com/openai/gpt-oss/main/LICENSE and https://raw.githubusercontent.com/openai/gpt-oss/main/USAGE_POLICY (checked 16 Oct 2026)
20. Project files read: `pipeline/pyproject.toml` and `src/bundle_pipeline/config.py` (W3 worktree); `web/package.json`, `web/src/sorter/model-manifest.json`, `web/src/styles/tokens.css`, `web/public/fonts/`, `web/README.md` (W5 worktree); the six track files in `docs/research/` (16 Oct 2026)

## Verdict

**Usable as a base encoder under D12 (Apache-2.0 or MIT, not gated):** sentence-transformers/all-MiniLM-L6-v2 (pick), mixedbread-ai/mxbai-embed-xsmall-v1 (challenger), Snowflake/snowflake-arctic-embed-xs (cite the card sentence, not Hub metadata), BAAI/bge-small-en-v1.5, thenlper/gte-small, minishlab/potion-base-8M, sentence-transformers/static-similarity-mrl-multilingual-v1, ibm-granite/granite-embedding-30m-english, cross-encoder/ms-marco-MiniLM-L6-v2 and sentence-transformers/all-mpnet-base-v2. Licence-clean but over the 40 MB budget: intfloat/multilingual-e5-small, nomic-ai/nomic-embed-text-v1.5, google/embeddinggemma-2.

**Usable as a teacher (outputs free to train on and release under CC BY 4.0):** Qwen/Qwen3.6-35B-A3B and nvidia/Qwen3.6-35B-A3B-NVFP4, Qwen/Qwen3-30B-A3B-Instruct-2507, Qwen/Qwen3-4B-Instruct-2507 and its unsloth GGUF, openai/gpt-oss-120b and 20b, zai-org/GLM-4.7-Flash, and google/gemma-4-26B-A4B-it or gemma-4-31B-it as a secondary teacher with the prohibited-use note recorded.

**Usable as comparators or Spark-side labellers:** Cloudflare/clef-flash and clef, perplexity-ai/pplx-decider-v1.1-27b, StrandsAgents/strands-decider-2B-qwen3.5-v1-2610, vllm-sr/d3-flash and d3-mini, h2oai/h2o-lightning-4b, convaiinnovations/laya. Claude Haiku 5.5: comparator only, outputs never kept.

**Excluded:** Gemma 3 and every model on the Gemma Terms page including EmbeddingGemma v1 (Terms pass through to the student; `gated: manual`); Llama 3.x and 4 (naming and AUP pass-through; `gated: manual`); LiquidAI d1-3B and d1-omni-600M (LFM1.0 revenue cap); NVIDIA Nemotron 3 Nano as a base (NVIDIA's own licence); jinaai/jina-embeddings-v5-text-small (CC BY-NC 4.0); hotchpotch/bekko (no licence); Persona Hub (CC BY-NC-SA 4.0); LMSYS-Chat-1M (gated, own agreement) and LoCoMo (CC BY-NC 4.0); WildChat and ShareChat as data (D3, and WildChat's two licence statements); any mirror repository without a licence tag as the cited source; and any hosted model's outputs as training data where the provider's terms forbid it. Every model recommended in this note returns `gated: false` from the Hub API today.
