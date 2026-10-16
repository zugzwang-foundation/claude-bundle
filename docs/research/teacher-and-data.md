# Teacher model, serving on the Spark, and the data recipe

Status: DRAFT — research note, 2026-10-16.

## The question

Which open instruct model should write Bundle's invented people, lives and chats, so that the resulting dataset can be released under CC BY 4.0 and the student's weights under Apache-2.0 (D3, D12)? It must fit one DGX Spark (GB10, 128 GB unified memory), write well, and let us train on its outputs without conditions. Which serving stack should drive it over an OpenAI-compatible API (D9)? Which small teacher runs on the Mac today? And what practice keeps the synthetic data varied, deduplicated and honestly examined (D4, D7)?

Everything below comes from sources opened on 16 October 2026. Where nothing was checked the text says "unknown". The relay's plan is wrong in a few places; those are called out in the last two sections.

## Findings

### (a) Candidate teachers: licence, output terms, size, quality

A teacher only needs to (1) permit training a model on its outputs with no naming or licence pass-through, and (2) fit the Spark at a speed that finishes a run overnight. Apache-2.0 and MIT weights satisfy (1) outright. Two popular families do not.

**Licences that pass through to our model (excluded):**
- Llama 3.x/4: the Llama 4 Community License says that if you use Llama outputs to train a distributed model you must put "Llama" at the start of its name, display "Built with Llama", and the 700 million MAU clause applies [1] (checked 16 Oct 2026). Llama-4-Scout-17B-16E-Instruct is also gated on Hugging Face (legal name and date of birth required) [2]. Both facts rule it out under D12 and relay rule 8.
- Gemma 3 and earlier: the Gemma Terms of Use (version dated 1 April 2026) define "Model Derivatives" to include models created through transfer of "patterns of the weights, parameters, operations, or Output of Gemma", naming distillation and synthetic-data training; distribution of a Model Derivative must carry Google's use restrictions and Google reserves the right to restrict usage remotely [3]. The same page lists the versions it covers (Gemma 1–3 and their variants) and points to a separate licence for Gemma 4 [3]. A student trained on Gemma 3 chats would therefore not be Apache-2.0. Excluded.
- Gemma 4 is different: released 2 April 2026 under Apache-2.0 in E2B, E4B, 12B, 26B-A4B and 31B sizes with 256K context on the larger ones [4]; the 26B-A4B-it and 31B-it cards show licence Apache-2.0 and cite a July 2026 technical report [5][6], and the Hugging Face API reports `gated: false` for both and for E4B-it [79]. Gemma 4 is usable and not gated; Gemma 3 is not. The relay's "Gemma 3 (note its terms)" is a year out of date.

**Apache-2.0 or MIT, and fits one Spark:**

| Model | Licence | Size (total / active) | Checked quality signals | Notes |
|---|---|---|---|---|
| Qwen3.6-35B-A3B | Apache-2.0 | 35B / 3B MoE | SWE-bench Verified 73.4, MMLU-Pro 85.2 (card); writing benchmarks not on card | April 2026; text+image+video; vLLM ≥ 0.19.0, SGLang ≥ 0.5.10; MTP speculative decoding [7] |
| Qwen3.5-27B | Apache-2.0 | 27B dense | IFEval 95.0, IFBench 76.5 (card) | Feb 2026; thinking on by default, switchable [8] |
| Qwen3.5-35B-A3B | Apache-2.0 | 36B / 3B MoE | MMLU-Pro 85.3 (card); 201 languages | Feb 2026 [9] |
| Qwen3.5-122B-A10B | Apache-2.0 | 122B / 10B MoE | IFEval 93.4 (card) | Feb 2026; hybrid Gated DeltaNet + MoE [10] |
| Qwen3.8-27B | Apache-2.0 | 27B dense | IFBench 79.5 (card) | August 2026; non-thinking sampling T 0.7, top-p 0.8, top-k 20, presence penalty 1.5 [11] |
| Qwen3-30B-A3B-Instruct-2507 | Apache-2.0 | 30.5B / 3.3B MoE | Creative Writing 86.0, WritingBench 85.5, IFEval 84.7, Arena-Hard v2 69.0 (card) | Non-thinking only, no think blocks to strip; plain attention [12] |
| Qwen3-32B | Apache-2.0 | 32.8B dense | — | May 2025; thinking/non-thinking modes [13] |
| gpt-oss-120b / 20b | Apache-2.0 + a short usage policy | 117B / 5.1B and 21B / 3.6B MoE | Writing quality: unknown (no benchmark checked) | MXFP4 weights; 120b fits in 80 GB; must use the harmony chat format [14][15]. The USAGE_POLICY file asks for safe, lawful use and says nothing about training on outputs [16] |
| Gemma 4 26B-A4B-it / 31B-it | Apache-2.0 | 25.2B / 3.8B MoE; 30.7B dense | MMLU-Pro 82.6 / 85.2 (cards) | 256K context; 140+ languages; cards point to Google's safety guidance but no licence restriction [5][6] |
| GLM-4.7-Flash | MIT | 31B / 3B MoE | SWE-bench Verified 59.2, GPQA 75.2 (card) | Card cites the Aug 2025 GLM-4.5 report; the Hugging Face repo was created 19 Jan 2026 [17][79] |
| Mistral Small 3.2 24B Instruct 2506 | Apache-2.0 | 24B dense | Internal IF 84.78 %, Arena Hard v2 43.1, WildBench v2 65.33; 24 languages | ~55 GB in bf16; vLLM ≥ 0.9.1 [18] |
| Magistral-Small-2509 / Devstral-Small-2507 | Apache-2.0 | 24B | — | Reasoning and code variants of the same base [19][20]; not writers |
| Ministral 3 (3B, 8B, 14B) | Apache-2.0 | dense | Mistral's own claims only | 2 Dec 2025; Mistral Large 3 is 675B / 41B, too big [21] |
| Mistral Small 4 | Apache-2.0 | 119B / 6B MoE | Mistral says it matches gpt-oss-120b on three benchmarks | 16 Mar 2026; Mistral lists a minimum of 4× H100; fit on one Spark unknown [22] |
| Olmo 3.1 32B Instruct | Apache-2.0 | 32B dense | IFEval 88.8, AlpacaEval 2 LC 59.8 (card) | Dec 2025; Dolma 3 and Dolci data released; data cut-off Dec 2024 [23] |
| OLMo 2 0325 32B Instruct | Apache-2.0 | 32B dense | IFEval 85.6 (card) | Mar 2025; card notes some post-training data is subject to the Gemma Terms [24] |
| Granite 4.0 H-Small | Apache-2.0 | 32B / 9B hybrid Mamba-2 MoE | IFEval instruct-strict 89.87, average 87.55 (card); 12 languages | 2 Oct 2025; also Micro 3B, H-Micro 3B, H-Tiny 7B [25] |
| Phi-4 | MIT | 14B dense | MMLU 84.8 (card); English-focused, 16K context | Dec 2024 [26] |
| Phi-4-mini-instruct | MIT | 3.8B | 22 languages; 128K context; card warns of thin factual knowledge | Feb 2025 [27] |
| SmolLM3-3B | Apache-2.0 | 3B | IFEval 76.7 (card); 6 main languages | July 2025; post-trained on Qwen3-32B outputs [28][29] |
| Apertus-70B-Instruct-2509 | Apache-2.0 | 71B dense | Fully open data; 1,811 languages claimed | Sept 2025; dense 70B will be slow on the Spark [30] |
| Kolibri-1 | Apache-2.0 | 78B / 3.46B MoE | MMLU-Pro 80.0 (card) | 3 Oct 2026 (13 days old, inside the 14-day rule); German and English only; FP8 ~78 GB; needs Aleph Alpha's vLLM plugin [31] |
| Nemotron 3 Nano 30B-A3B | NVIDIA Nemotron Open Model License | 30B / 3.5B hybrid Mamba-2 MoE | Arena-Hard v2 67.7 (card) | 15 Dec 2025 [32]. Licence (15 Dec 2025): commercial use allowed, NVIDIA claims no ownership of outputs, attribution notice required; not Apache-2.0 or MIT [33] |

**Too big for one Spark** (NVIDIA says one unit runs "up to 200B parameters" [34]): GLM-4.6 at 357B (MIT) [35]; DeepSeek-V3.2 at 685B (MIT) [36]; Mistral Large 3 at 675B [21]; Reflection AI's Beam at 501B is also not downloadable yet [37]. Qwen3-Next-80B-A3B (Apache-2.0, not gated; the FP8 repo holds 81.3B stored parameters per the Hugging Face API, so roughly 80 GB — file size not verified) fits on paper, but a forum thread reports it failing to load in NVIDIA's vLLM image on the Spark (title and snippet only; the page was not opened) [38].

**Qwen2.5:** 7B through 32B are Apache-2.0, but the 3B and 72B carry the Qwen LICENSE AGREEMENT, which demands "Built with Qwen" attribution and a licence request above 100 million MAU [39]. Irrelevant now: every Qwen3.x checked is Apache-2.0.

**Toy teacher for the Mac today:** Qwen3-4B-Instruct-2507 is Apache-2.0, non-thinking only, with IFEval 83.4, WritingBench 83.4 and Creative Writing v3 83.5 on its card [40]. The MLX 4-bit conversion by mlx-community is 2.26 GB (converted with mlx-lm 0.26.2) [41]; the GGUF Q4_K_M from bartowski is 2.50 GB [42]. Alternatives under 5 GB at Q4: SmolLM3-3B (Apache-2.0), Phi-4-mini (MIT), Granite 4.0 Micro 3B (Apache-2.0), Gemma 4 E4B (Apache-2.0; mlx-lm support unknown).

### (b) Serving on the DGX Spark

Checked hardware: GB10 Grace Blackwell, 20-core Arm, 128 GB LPDDR5X at 273 GB/s, up to 1 PFLOP FP4, DGX OS, ConnectX-7 200 Gbps, 240 W supply [34]. A 64 GB OEM variant from Acer, ASUS, Dell, Gigabyte, HP and MSI ships from 23 October 2026 at $4,999; NVIDIA's post names llama.cpp, Ollama, vLLM and LM Studio as supported runtimes [43]. NVIDIA's playbooks repository (Apache-2.0) covers vLLM (single and cluster), SGLang, llama.cpp, Ollama with Open WebUI, TensorRT-LLM, NIM, speculative decoding, NVFP4, Unsloth, LLaMA Factory and NeMo [44][45].

The one number that matters for a data run is decode speed, and the Spark's 273 GB/s bus sets it. A dense 27B at NVFP4 (18.77 GB of weights) tops out near 273 ÷ 18.77 ≈ 14.5 tokens/s per stream; measured 12.3 tok/s on SGLang, 65 tok/s with DFlash2 speculative decoding (23 Aug 2026) [46]. MoE models with ~3B active decode several times faster:

| Stack | What NVIDIA documents | Community measurements on one Spark | JSON schema, seed, batching |
|---|---|---|---|
| vLLM | Container-based playbook, updated 14 Sept 2026; cluster mode for two Sparks [47] | NGC `nvcr.io/nvidia/vllm:26.04-py3` = vLLM 0.19.0 is the stable choice; upstream stable image "does not support GB10"; FP4 MoE needs `--moe-backend marlin`; page cache can trigger OOM; Qwen3.6-35B-A3B-NVFP4 ~102 tok/s single stream answer-only and ~125 with MTP-3 in thinking mode, Gemma-4-26B-A4B ~50, Gemma-4-31B dense ~6 (92 aggregate at 16 concurrent); the newer upstream track is `vllm/vllm-openai:cu130-nightly` (vLLM 0.23.x) (20 June 2026) [48]. NGC's catalog page lists 26.09-py3 as the latest tag (28 Sept 2026) and puts the container under NVIDIA's EULA and AI product terms, not an open licence [80]. Bare-metal `uv pip install vllm` gives 0.27.1 with torch 2.13 cu130 but a 425 s cold start while FlashInfer JIT-compiles for sm_121 (26 Aug 2026) [49] | `response_format` json_schema; backend `auto` by default; the old `guided_*` fields were removed in v0.12.0 in favour of `structured_outputs` [50]; continuous batching built in |
| SGLang | CUDA 13 container; examples gpt-oss, Qwen3 8B–32B, Nemotron; NVFP4 needs `--quantization modelopt_fp4` [51] | Qwen3.8-27B NVFP4 12.3 → 65 tok/s with DFlash2 [46] | `response_format` json_schema with xgrammar, outlines or llguidance [52] |
| llama.cpp | Build with `CMAKE_CUDA_ARCHITECTURES=121a-real`; example Qwen3.6-35B-A3B GGUF UD-Q4_K_XL ~30 GB; `/v1/chat/completions` [53] | gpt-oss-120b MXFP4: ~1,956 tok/s prompt, ~60 tok/s decode; Qwen3-Coder-30B-A3B Q8: ~44 tok/s decode (Oct 2025–Feb 2026) [54] | `response_format` json_schema, `seed`, `-np` parallel slots, continuous batching on by default [55] |
| Ollama | Open WebUI + Ollama container `ghcr.io/open-webui/open-webui:ollama`; examples gpt-oss 15 GB, qwen3.6 25 GB; 15–20 min [56] | unknown | JSON schema via `format`, and `response_format` on its OpenAI endpoint [57]; MIT [81] |
| TensorRT-LLM | Container v1.3.0rc13; NVFP4 first, FP8, BF16; Nemotron, Llama, Qwen, Phi, gpt-oss; OpenAI-compatible server on port 8355; 45–60 min; "not all model architectures are supported for NVFP4" [58] | unknown | unknown |

Caveat on the Qwen3.5/3.6/3.8 line: they use Gated DeltaNet linear-attention layers. A forum thread title reports Qwen3.5-35B going from 13 to 49 tok/s only after a native SM121 kernel build (title only; the page returned 403) [59], while the June 2026 vLLM playbook measured 102 tok/s with the NGC image [48]. Measure on day one before committing the overnight run.

### (c) Synthetic-data practice

- **Personas.** Persona Hub (Tencent) released 200k and 370M personas, but under CC BY-NC-SA 4.0 and "for research purposes only" [60][61]; it cannot seed a CC BY 4.0 dataset. NVIDIA's Nemotron-Personas datasets are CC BY 4.0: the USA set (6 million personas and 936M tokens per NVIDIA's blog of 28 Oct 2025, built with NeMo Data Designer, aligned to Census and BLS distributions [63]; the dataset card itself shows a 1M-row train split and the size class 1M–10M, so check which split you are sampling [62]) and the India set (3 million records in English, Devanagari Hindi and Latin Hindi) [64]. Paglieri et al. (Feb 2026) argue for persona generators that cover what is possible rather than what is probable, and evolve small generator functions with an LLM as mutation operator [65].
- **Difficulty control.** Evol-Instruct rewrites instructions step by step into harder ones [66]; Tag-Evol (ACL 2025 Findings) injects knowledge tags so the number and mix of tags sets difficulty in one shot, which is cheaper than iterating [67]. Magpie shows an aligned model will write realistic user turns when given only the chat-template prefix (4M instructions, 300k kept) [68]; useful for casually typed openers.
- **Sameness.** Verbalized Sampling (Oct 2025, revised July 2026) traces mode collapse to typicality bias in preference data and shows that asking for several candidates with probabilities raises diversity 1.6–2.1× over direct prompting, including for synthetic data [69]. Cosmopedia got under 1 % duplicates by multiplying topics by four audiences and three styles, and reports that most of the effort was prompt engineering [70].
- **Deduplication.** MinHash + LSH for near-lexical duplicates: datasketch is MIT [71]; text-dedup's defaults are 5-gram shingles, 240 permutations, threshold 0.7 (the repository is Apache-2.0 per its LICENSE file and the GitHub API; the PyPI metadata for 0.4.1 carries no licence field at all, so pin to a repository tag and record the licence from there) [72][82]. SemDeDup removes semantic duplicates by clustering embeddings and dropping pairs above a cosine threshold; it halved LAION with little loss [73].

### (d) Keeping the sealed exam honest

- Split by person: scikit-learn 1.9.1's GroupShuffleSplit (BSD-3-Clause) puts every member of a group on the same side of a split; its docs warn only that test sets from repeated splits may overlap, which does not matter with `n_splits=1`; a fixed integer `random_state` makes it reproducible [74].
- Contamination checks: Yang et al. (2023) show n-gram overlap misses paraphrased test items, and a 13B model reached GPT-4-level scores on contaminated benchmarks; they propose an LLM-based decontaminator [75]. Cosmopedia used 10-gram overlap then a SequenceMatcher ratio above 0.5 to discard matches [70]. A 2026 ICML position paper calls contamination "wide" and asks for contamination-resistant evaluation [76].
- Practice from a live benchmark: ARC Prize keeps a private set that is never sent to third-party APIs, signs zero-data-retention agreements with providers for the semi-private set, releases a new benchmark version roughly yearly, and watches the gap between semi-private and private scores to spot exposure or overfitting [77].

## Options compared

| Option for the Spark teacher | Licence fit | Fits 128 GB | Speed class | Writing evidence | Verdict |
|---|---|---|---|---|---|
| Qwen3.6-35B-A3B (NVFP4 or FP8) | Apache-2.0, not gated | yes, ~20–35 GB | fast MoE, ~102 tok/s answer-only, ~125 with MTP | indirect (family IFEval 93–95) | **Pick** |
| Qwen3-30B-A3B-Instruct-2507 | Apache-2.0 | yes | fast MoE, plain attention | best checked writing scores | **Fallback A** (if GDN kernels are slow) |
| gpt-oss-120b (MXFP4) | Apache-2.0 + light policy | yes, <80 GB | ~60 tok/s on llama.cpp | unknown | **Fallback B**; harmony format |
| Gemma 4 26B-A4B-it | Apache-2.0 | yes | ~50 tok/s | unknown | Good second teacher for variety |
| GLM-4.7-Flash | MIT | yes | fast MoE | unknown | Third voice if needed |
| Qwen3.5-27B / Qwen3.8-27B / Olmo 3.1 32B / Gemma 4 31B | Apache-2.0 | yes | dense, ~6–14 tok/s per stream | strongest IFEval (95.0) | Too slow for a 10M-token run unless batched hard |
| Nemotron 3 Nano | Nemotron licence | yes | fast | Arena-Hard 67.7 | Acceptable but adds a third licence to track; skip |
| Kolibri-1 | Apache-2.0 | FP8 78 GB | fast MoE | DE/EN only | Too new (13 days), plugin-bound; skip |
| Gemma 3, Llama 3.x/4 | pass-through terms | — | — | — | Excluded |
| GLM-4.6, DeepSeek-V3.2, Mistral Large 3, Beam | MIT/Apache | no | — | — | Excluded on size |

| Option for today's Mac toy | Licence | Size at Q4 | Server | Verdict |
|---|---|---|---|---|
| Qwen3-4B-Instruct-2507 | Apache-2.0 | 2.26 GB MLX, 2.50 GB GGUF | llama-server or mlx_lm.server | **Pick** |
| SmolLM3-3B | Apache-2.0 | ~2 GB (unknown exact) | same | Backup |
| Phi-4-mini-instruct | MIT | unknown | same | Backup; weaker writer per its own card |
| Gemma 4 E4B | Apache-2.0 | unknown | mlx-lm support unknown | Later |

## Recommendation

**Teacher:** Qwen3.6-35B-A3B (Apache-2.0, not gated [7][79]), served with vLLM (Apache-2.0 [83]) from NVIDIA's NGC `vllm:26.04-py3` container (vLLM 0.19.0, exactly the card's minimum), thinking disabled with `chat_template_kwargs: {"enable_thinking": false}` (the card says `/no_think` soft switches are not supported), `response_format` json_schema, and the card's own non-thinking sampling: temperature 0.7, top-p 0.8, top-k 20, presence penalty 1.5 [7]. Use the official `nvidia/Qwen3.6-35B-A3B-NVFP4` checkpoint (Apache-2.0, not gated, quantised with nvidia-modelopt v0.44.0, three safetensors shards; its card carries a DGX Spark section with `--moe-backend marlin --attention-backend flashinfer --kv-cache-dtype fp8` and an MTP speculative config) [84], and add `--language-model-only` to skip the vision encoder and free memory for KV cache [7]. The NGC container itself is under NVIDIA's EULA, not an open licence [80]; it is a tool run on our own machine, not a dependency we ship, but record it in licences.md, and the upstream `cu130-nightly` image is the fallback if that matters. First task on the Spark: a 10-minute throughput test at 16 concurrent requests; if aggregate decode is under 200 tok/s, switch to Fallback A (Qwen3-30B-A3B-Instruct-2507, plain attention, best checked writing numbers) or Fallback B (gpt-oss-120b on llama-server). Budget: 2,000 people × 60 chats at roughly 120 output tokens per chat is about 15M tokens, so 10 hours at 400 tok/s aggregate or 42 hours at 100 tok/s. Use a second teacher (Gemma 4 26B-A4B-it, Apache-2.0, not gated [5][79]) for one in five people so the student does not learn one model's tics.

**Toy teacher today:** Qwen3-4B-Instruct-2507 (Apache-2.0, not gated [40][79]) at Q4 behind llama.cpp's `llama-server` (MIT [83]) rather than `mlx_lm.server` (MIT [83]): llama-server documents json_schema, `seed` and `-np` parallel slots [55], while mlx-lm's server documents none of `seed`, JSON mode or `response_format` and warns it is not for production [78]. Both speak `/v1/chat/completions`, so the pipeline's client is unchanged. If llama.cpp is not installed, mlx-lm works with validation-and-retry instead of constrained output.

**Recipe:**
1. Seeds: sample personas from Nemotron-Personas (CC BY 4.0; credit NVIDIA in the dataset card), stratified by age, occupation and region, and translate each into a short "life sheet" the teacher expands. Add a small hand-written persona-generator function in the Paglieri et al. style for rare combinations.
2. Life: the teacher writes 3–6 bundles per person (name, why it matters, time span) plus 4–10 loose interests, as JSON under a schema.
3. Chats: assign each chat a difficulty tag from the relay's seven kinds by quota (for example 20 % overlaps, 15 % vague one-liners, 15 % belongs nowhere, 10 % long-gap follow-ups, 15 % typos and lower case, 10 % very short, 15 % opens a new thread), and have the teacher write to the tag. Ask for five candidate openers with verbalised probabilities and keep one at random, not the top one.
4. Validate: schema, tag rules (a "vague one-liner" has at most eight words; "belongs nowhere" must not share a noun with any bundle name), language, no real names or brands.
5. Dedup: exact hash → MinHash (datasketch, MIT, or text-dedup, Apache-2.0; 5-gram, 240 permutations, 0.7) → embedding near-duplicates (cosine ≥ 0.92 within a person, ≥ 0.95 across people, thresholds tuned on the toy run); keep the first.
6. Diversity report per run: mean pairwise cosine distance, unigram and bigram entropy, duplicate rate, tag mix, per-person vocabulary overlap. Fail the run if any falls below the previous run.
7. Split by person 80/10/10 with GroupShuffleSplit and a fixed seed; write SHA-256 of the canonical exam JSONL, the prompt version and the teacher's model hash into `scoreboard/runs/*.json`.
8. Sealed exam rules: the exam file is gitignored and encrypted at rest; no person and no model reads its rows; the exam runner prints aggregate metrics only; thresholds are set on practice, never on exam; the exam is regenerated with a new seed for each major version, keeping the old one to track the public-versus-sealed gap as ARC Prize does.
9. Decontaminate all three splits against the demo library: 10-gram overlap plus SequenceMatcher ratio over 0.5 (Cosmopedia) and embedding cosine ≥ 0.9 (because n-grams miss paraphrases); drop matches from the data, never from the library.

## What doesn't work, or would change the plan

1. **Gemma 3 is out, Gemma 4 is in.** The relay lists "Gemma 3 (note its terms)"; its terms make any model trained on its outputs a Model Derivative under Google's conditions. Gemma 4 (April 2026) is Apache-2.0 and is a fine second teacher.
2. **Llama is out twice over:** the naming clause for models trained on outputs, and gating.
3. **Persona Hub cannot be used:** CC BY-NC-SA 4.0 and research-only. Use Nemotron-Personas (CC BY 4.0) or our own generator.
4. **Dense teachers are slow on the Spark.** The 273 GB/s bus caps a 27B NVFP4 model near 14 tok/s per stream. The relay's overnight loop needs an MoE teacher with ~3B active parameters, or heavy batching, or speculative decoding.
5. **vLLM's stable upstream image does not support GB10.** The cu130 nightly does, and bare-metal pip wheels work after a ~7-minute FlashInfer JIT. Use the NGC container (or the nightly) rather than `uv pip install vllm`; R6's scripts/spark should pin `nvcr.io/nvidia/vllm:26.04-py3` and note that the container is under NVIDIA's EULA, not Apache-2.0, even though the vLLM inside is.
6. **mlx_lm.server cannot honour W3's "seeds" or constrained JSON** as documented; llama-server can. The relay's order "mlx-lm first, then Ollama or llama.cpp" should be reversed for this job.
7. **Qwen3.5/3.6/3.8 kernels on GB10 are a known risk** (Gated DeltaNet fallbacks). Keep Qwen3-30B-A3B-Instruct-2507 or gpt-oss-120b ready; both use plain attention.
8. **Writing-quality evidence is thin** for the newest models: the Qwen3.6 and Gemma 4 cards publish coding and knowledge scores, not WritingBench. A 50-person pilot judged by a second model, and by Hrishikesh reading 20 chats, should precede the full run.
9. **Model age.** Kolibri-1 (3 Oct 2026) and the 64 GB Spark (23 Oct 2026) are inside the relay's 14-day rule; Qwen3.8-27B (Aug 2026) and Qwen3.6-35B-A3B (Apr 2026) are not.
10. **Unknowns to settle on the Spark:** SGLang container tag, TensorRT-LLM support for Qwen3.6's architecture, the real memory and speed of the NVFP4 checkpoint with the vision encoder skipped, and whether Mistral Small 4 fits at NVFP4.
11. **Nemotron-Personas-USA is smaller on disk than the blog suggests.** The blog says 6 million personas; the Hugging Face card shows a 1M-row train split. One million is plenty for 2,000 people, but the dataset card, not the blog, is what we cite.

## Sources

1. https://raw.githubusercontent.com/meta-llama/llama-models/main/models/llama4/LICENSE (checked 16 Oct 2026)
2. https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct (checked 16 Oct 2026)
3. https://ai.google.dev/gemma/terms (checked 16 Oct 2026)
4. https://huggingface.co/blog/gemma4 (checked 16 Oct 2026)
5. https://huggingface.co/google/gemma-4-26B-A4B-it (checked 16 Oct 2026)
6. https://huggingface.co/google/gemma-4-31B-it (checked 16 Oct 2026)
7. https://huggingface.co/Qwen/Qwen3.6-35B-A3B (checked 16 Oct 2026)
8. https://huggingface.co/Qwen/Qwen3.5-27B (checked 16 Oct 2026)
9. https://huggingface.co/Qwen/Qwen3.5-35B-A3B (checked 16 Oct 2026)
10. https://huggingface.co/Qwen/Qwen3.5-122B-A10B (checked 16 Oct 2026)
11. https://huggingface.co/Qwen/Qwen3.8-27B (checked 16 Oct 2026)
12. https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507 (checked 16 Oct 2026)
13. https://huggingface.co/Qwen/Qwen3-32B (checked 16 Oct 2026)
14. https://huggingface.co/openai/gpt-oss-120b (checked 16 Oct 2026)
15. https://github.com/openai/gpt-oss (checked 16 Oct 2026)
16. https://raw.githubusercontent.com/openai/gpt-oss/main/USAGE_POLICY (checked 16 Oct 2026)
17. https://huggingface.co/zai-org/GLM-4.7-Flash (checked 16 Oct 2026)
18. https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506 (checked 16 Oct 2026)
19. https://huggingface.co/mistralai/Magistral-Small-2509 (listed in search results; checked 16 Oct 2026)
20. https://huggingface.co/mistralai/Devstral-Small-2507 (listed in search results; checked 16 Oct 2026)
21. https://mistral.ai/news/mistral-3/ (checked 16 Oct 2026)
22. https://mistral.ai/news/mistral-small-4 (checked 16 Oct 2026)
23. https://huggingface.co/allenai/Olmo-3.1-32B-Instruct (checked 16 Oct 2026)
24. https://huggingface.co/allenai/OLMo-2-0325-32B-Instruct (checked 16 Oct 2026)
25. https://huggingface.co/ibm-granite/granite-4.0-h-small (checked 16 Oct 2026)
26. https://huggingface.co/microsoft/phi-4 (checked 16 Oct 2026)
27. https://huggingface.co/microsoft/Phi-4-mini-instruct (checked 16 Oct 2026)
28. https://huggingface.co/HuggingFaceTB/SmolLM3-3B (checked 16 Oct 2026)
29. https://huggingface.co/blog/smollm3 (checked 16 Oct 2026)
30. https://huggingface.co/swiss-ai/Apertus-70B-Instruct-2509 (checked 16 Oct 2026)
31. https://huggingface.co/Aleph-Alpha/Kolibri-1 (checked 16 Oct 2026)
32. https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 (checked 16 Oct 2026)
33. https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/ (checked 16 Oct 2026)
34. https://www.nvidia.com/en-us/products/workstations/dgx-spark/ (checked 16 Oct 2026)
35. https://huggingface.co/zai-org/GLM-4.6 (checked 16 Oct 2026)
36. https://huggingface.co/deepseek-ai/DeepSeek-V3.2 (checked 16 Oct 2026)
37. https://www.marktechpost.com/2026/10/05/reflection-ai-introduces-beam-a-501b-open-weight-moe-model-with-23b-active-parameters-for-coding-and-agentic-workloads/ (search snippet; checked 16 Oct 2026)
38. https://forums.developer.nvidia.com/t/dgx-spark-qwen3-next-80b-proven-performance-but-missing-clear-path-to-nim-tensorrt-llm-web-uis/357820 (title and snippet only; checked 16 Oct 2026)
39. https://huggingface.co/Qwen/Qwen2.5-72B-Instruct/blob/main/LICENSE (checked 16 Oct 2026)
40. https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507 (checked 16 Oct 2026)
41. https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit (checked 16 Oct 2026)
42. https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF (checked 16 Oct 2026; Q4_K_M 2.50 GB, quantised with llama.cpp b6096)
43. https://blogs.nvidia.com/blog/local-ai-dgx-spark-64gb-sync/ (checked 16 Oct 2026)
44. https://github.com/NVIDIA/dgx-spark-playbooks (checked 16 Oct 2026)
45. https://build.nvidia.com/spark (checked 16 Oct 2026)
46. https://ai-muninn.com/en/blog/dgx-spark-bandwidth-ceiling-85-percent (checked 16 Oct 2026)
47. https://build.nvidia.com/spark/vllm/overview (checked 16 Oct 2026)
48. https://vlaicu.io/posts/dgx-vllm/ (checked 16 Oct 2026)
49. https://dev.to/conatusai/dgx-spark-gb10-bare-metal-vllm-the-install-that-works-two-landmines-measured-timings-32mp (checked 16 Oct 2026)
50. https://docs.vllm.ai/en/latest/features/structured_outputs/ (checked 16 Oct 2026)
51. https://build.nvidia.com/spark/sglang/overview (checked 16 Oct 2026)
52. https://docs.sglang.io/advanced_features/structured_outputs.html (checked 16 Oct 2026)
53. https://build.nvidia.com/spark/llama-cpp/overview (checked 16 Oct 2026)
54. https://github.com/ggml-org/llama.cpp/discussions/16578 (checked 16 Oct 2026)
55. https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md (checked 16 Oct 2026)
56. https://github.com/NVIDIA/dgx-spark-playbooks/blob/main/nvidia/open-webui/README.md (checked 16 Oct 2026)
57. https://docs.ollama.com/capabilities/structured-outputs (checked 16 Oct 2026)
58. https://build.nvidia.com/spark/trt-llm/overview (checked 16 Oct 2026)
59. https://forums.developer.nvidia.com/t/dgx-spark-13-49-tok-s-with-qwen3-5-35b-native-sm121-kernel-build-guide/365083 (title only, page returned 403; checked 16 Oct 2026)
60. https://arxiv.org/abs/2406.20094 (checked 16 Oct 2026)
61. https://github.com/tencent-ailab/persona-hub (checked 16 Oct 2026)
62. https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA (checked 16 Oct 2026)
63. https://huggingface.co/blog/nvidia/nemotron-personas-usa (checked 16 Oct 2026)
64. https://huggingface.co/datasets/nvidia/Nemotron-Personas-India (checked 16 Oct 2026)
65. https://arxiv.org/abs/2602.03545 (checked 16 Oct 2026)
66. https://arxiv.org/abs/2304.12244 (checked 16 Oct 2026)
67. https://arxiv.org/abs/2505.24165 (checked 16 Oct 2026)
68. https://arxiv.org/abs/2406.08464 (checked 16 Oct 2026)
69. https://arxiv.org/abs/2510.01171 (checked 16 Oct 2026)
70. https://huggingface.co/blog/cosmopedia (checked 16 Oct 2026)
71. https://github.com/ekzhu/datasketch (checked 16 Oct 2026)
72. https://github.com/ChenghaoMou/text-dedup (checked 16 Oct 2026)
73. https://arxiv.org/abs/2303.09540 (checked 16 Oct 2026)
74. https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html (checked 16 Oct 2026)
75. https://arxiv.org/abs/2311.04850 (checked 16 Oct 2026)
76. https://arxiv.org/abs/2605.19999 (checked 16 Oct 2026)
77. https://arcprize.org/policy (checked 16 Oct 2026)
78. https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md (checked 16 Oct 2026)
79. https://huggingface.co/api/models/google/gemma-4-26B-A4B-it and the same endpoint for google/gemma-4-31B-it, google/gemma-4-E4B-it, Qwen/Qwen3.6-35B-A3B, Qwen/Qwen3-30B-A3B-Instruct-2507, Qwen/Qwen3-4B-Instruct-2507, openai/gpt-oss-120b, zai-org/GLM-4.7-Flash, Qwen/Qwen3-Next-80B-A3B-Instruct-FP8 — `gated`, `license`, parameter count and creation date fields (checked 16 Oct 2026)
80. https://catalog.ngc.nvidia.com/orgs/nvidia/containers/vllm (checked 16 Oct 2026)
81. https://github.com/ollama/ollama (checked 16 Oct 2026)
82. https://pypi.org/pypi/text-dedup/json and https://api.github.com/repos/ChenghaoMou/text-dedup (checked 16 Oct 2026)
83. https://api.github.com/repos/<owner>/<repo> `license.spdx_id` for vllm-project/vllm (Apache-2.0), ggml-org/llama.cpp (MIT), ml-explore/mlx-lm (MIT), ekzhu/datasketch (MIT), scikit-learn/scikit-learn (BSD-3-Clause), sgl-project/sglang (Apache-2.0), mlc-ai/xgrammar (Apache-2.0), NVIDIA/dgx-spark-playbooks (Apache-2.0) (checked 16 Oct 2026)
84. https://huggingface.co/nvidia/Qwen3.6-35B-A3B-NVFP4 (checked 16 Oct 2026)

## Verification notes (skeptic)

Checked 16 October 2026 by opening the cited pages and the Hugging Face and GitHub APIs. Six sections present and in order; no change needed.

Spot-checks that held (licence, size, version or date read as stated): Qwen3.6-35B-A3B card (Apache-2.0, 35B/3B, April 2026, vLLM ≥ 0.19.0, SGLang ≥ 0.5.10, SWE-bench 73.4, MMLU-Pro 85.2) [7]; Gemma 4 blog date 2 April 2026 and Apache-2.0 [4]; Gemma Terms last modified 1 April 2026 and the Model Derivatives wording [3]; gemma-4-26B-A4B-it 25.2B/3.8B, 256K, MMLU-Pro 82.6 [5]; vlaicu.io NGC 26.04-py3 = vLLM 0.19.0, marlin flag, page-cache OOM [48]; Nemotron-Personas-USA CC BY 4.0 [62][63]; Persona Hub CC BY-NC-SA 4.0 and research-only [61]; Qwen3-30B-A3B-Instruct-2507 scores [12]; Qwen3-4B-Instruct-2507 scores and 2.26 GB MLX / 2.50 GB GGUF [40][41][42]; mlx-lm SERVER.md lists neither `seed` nor `response_format` [78]; llama-server json_schema, seed, `-np`, continuous batching default on [55]; GLM-4.7-Flash MIT [17]; Kolibri-1 3 Oct 2026, Apache-2.0, 78B/3.46B [31]; 64 GB Spark 23 Oct 2026, $4,999 [43]; Spark 273 GB/s, 128 GB, 200B [34]; text-dedup defaults [72]; scikit-learn 1.9.1 [74]; Llama 4 naming, "Built with Llama" and 700M MAU clauses [1]; gpt-oss sizes, MXFP4, harmony [14]; Qwen3.8-27B IFBench 79.5 and sampling [11]; ai-muninn 12.32 → 65.02 tok/s, 18.77 GB, 23 Aug 2026 [46]; Qwen3.5-27B IFEval 95.0 / IFBench 76.5 [8]; Nemotron licence 15 Dec 2025 terms [33]; Mistral Small 4 16 Mar 2026, 119B/6B, 4× H100 [22]; Olmo 3.1 scores [23]; Verbalized Sampling 1.6–2.1× and 15 July 2026 revision [69]; Cosmopedia under 1 %, 4 audiences × 3 styles, 10-gram + 0.5 [70]; Qwen2.5 licence clauses [39]; Tag-Evol ACL 2025 Findings [67]; Paglieri 3 Feb 2026 [65]; ICML 2026 position paper [76]; SemDeDup 50 % [73]; SmolLM3 and Qwen3-32B synthetic data [29]; Nemotron 3 Nano 15 Dec 2025, 30B/3.5B, Arena-Hard 67.7 [32]; Mistral Small 3.2 scores, ~55 GB, vLLM ≥ 0.9.1 [18]; Nemotron-Personas-India 3M rows, three scripts [64]; Granite 4.0 H-Small 2 Oct 2025, 32B/9B, 12 languages [25].

Gating: every model in the recommendation and both fallbacks returns `gated: false` from the Hugging Face API [79]; the NVIDIA NVFP4 checkpoint too [84].

Fixes made:
1. vLLM speed for Qwen3.6-35B-A3B: the source gives ~102 tok/s answer-only and ~125 tok/s with MTP-3, not "~102 with MTP". Corrected in the Findings table and the Options table [48].
2. vLLM structured outputs: `guided_*` fields were removed in v0.12.0 (not "deprecated"), default backend is `auto`. Corrected [50].
3. Granite IFEval: 89.87 is the instruction-strict figure; the card's average is 87.55. Both now shown [25].
4. Qwen3-Next-80B-A3B "FP8 82 GB": file size not on the card; replaced with the API's 81.3B stored parameters and marked not verified [79].
5. GLM-4.7-Flash release: replaced "secondary sources" with the repository creation date, 19 Jan 2026 [79].
6. GroupShuffleSplit: the docs' caveat is about overlap across repeated splits, not about a group straddling train and test; wording tightened [74].
7. ARC Prize: the policy names zero-data-retention agreements and tracks the semi-private-versus-private gap; "confidentiality" and "public-versus-private" were the author's paraphrase. Corrected [77].
8. Nemotron-Personas-USA: the dataset card shows a 1M-row train split against the blog's 6 million; both now stated, and a new item 11 in the previous section [62][63].
9. text-dedup licence: the "package index says MIT" claim did not hold; PyPI 0.4.1 has no licence metadata and the repository is Apache-2.0 [72][82].
10. Ollama licence: MIT, replacing "not checked today" [81].
11. NVIDIA's NVFP4 checkpoint was opened: Apache-2.0, not gated, modelopt v0.44.0, DGX Spark flags on the card; recommendation updated from "not opened today" [84]. Added `--language-model-only` and the `enable_thinking` switch from the Qwen3.6 card, and confirmed the sampling values are Qwen3.6's own, not borrowed from Qwen3.8 [7].
12. Licences added for every recommended package: vLLM Apache-2.0, llama.cpp MIT, mlx-lm MIT, datasketch MIT, text-dedup Apache-2.0, scikit-learn BSD-3-Clause, SGLang Apache-2.0, xgrammar Apache-2.0 [83]. The NGC vLLM container is under NVIDIA's EULA and AI product terms, which is now stated [80].
13. Gemma Terms page scope (Gemma 1–3, separate Gemma 4 licence) added [3]; Gemma 4 gating status added [79].
14. Source 42 was a search snippet; the page has now been opened and the 2.50 GB figure confirmed.

Not re-verified today and left as the author wrote them, all already hedged in the text: source 37 (Beam, snippet only), 38 and 59 (forum titles only), 19 and 20 (Magistral and Devstral, search listing only). The quotes in the file were counted: the longest is ten words.
