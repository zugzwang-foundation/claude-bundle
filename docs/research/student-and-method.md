# R2: the student encoder and the method

Status: DRAFT — research note, 2026-10-16.

## The question

Bundle needs a model that, given one new chat and a person's existing bundles and loose chats, returns a probability for each candidate plus "none of these", runs in a phone browser from a download under 40 MB, and whose probabilities are honest enough that a 95% file cut-off is right about 95% of the time. Four things have to be chosen: the base encoder (and its licence), the way the "which bundle, or none" question is posed to it, the way "none" is handled, and the calibration recipe and metrics. The relay asks for a version-0 answer (today, toy scale, on a Mac) and a version-1 answer (the DGX Spark). Everything below comes from pages opened on 16 October 2026; nothing is from memory. Where a size is derived rather than read, it says so.

## Findings

### (a) Small open encoders that fit in a browser

Size figures are the ONNX files published on Hugging Face. "int8" means the `model_int8` / `model_quantized` / `model_qint8_*` file; "fp16" the `model_fp16` or `model_O4` file. Transformers.js loads a model from `config.json` + `tokenizer.json` + `onnx/model*.onnx` and selects the file by `dtype` (fp32, fp16, q8/int8/uint8, q4, bnb4, q4f16) (https://huggingface.co/docs/transformers.js/guides/dtypes, checked 16 Oct 2026).

**Within the 40 MB budget at int8 (English only):**

- **sentence-transformers/all-MiniLM-L6-v2**: licence `apache-2.0`, 22.7M parameters, 384 dimensions, 256 word-piece truncation, English (https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2, checked 16 Oct 2026). The official repo ships an `onnx/` folder: `model.onnx` 90.4 MB, `model_O4.onnx` 45.2 MB (fp16), and four int8 variants at 23 MB (`model_qint8_arm64`, `model_qint8_avx512`, `model_qint8_avx512_vnni`, `model_quint8_avx2`) (https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/main/onnx, checked 16 Oct 2026). The Transformers.js mirror `Xenova/all-MiniLM-L6-v2` (licence tag apache-2.0, usage `pipeline('feature-extraction', …)` with `pooling: 'mean', normalize: true`) has `model_int8.onnx` 23 MB, `model_fp16.onnx` 45.3 MB, `model_q4f16.onnx` 30 MB, `model.onnx` 90.4 MB (https://huggingface.co/Xenova/all-MiniLM-L6-v2 and …/tree/main/onnx, checked 16 Oct 2026). The newer `onnx-community/all-MiniLM-L6-v2-ONNX` listing showed only fp32 (90.3 MB), fp16 (45.1 MB), q4 (54.4 MB) and q4f16 (29.8 MB) — no int8 file in the listing I saw (https://huggingface.co/onnx-community/all-MiniLM-L6-v2-ONNX/tree/main/onnx, checked 16 Oct 2026). Lesson: we should ship our own quantised file rather than depend on a mirror's dtype set.
- **Snowflake/snowflake-arctic-embed-xs**: Apache-2.0, 22M parameters, 384 dimensions, 512 tokens, English, Transformers.js example on the card (CLS pooling, normalise), official `onnx/` with `model_int8.onnx` 23 MB and `model_fp16.onnx` 45.3 MB (https://huggingface.co/Snowflake/snowflake-arctic-embed-xs and …/tree/main/onnx, checked 16 Oct 2026). It is a retrieval model trained with a query prefix, so it is asymmetric; our task (chat versus chats) is symmetric.
- **mixedbread-ai/mxbai-embed-xsmall-v1**: `apache-2.0`, 24.1M parameters, 384 dimensions, built on all-MiniLM-L6-v2 with 4096-token context, English; official `onnx/` with `model_int8.onnx` 24.4 MB, `model_fp16.onnx` 48.1 MB, `model_q4f16.onnx` 32.9 MB (https://huggingface.co/mixedbread-ai/mxbai-embed-xsmall-v1 and …/tree/main/onnx, checked 16 Oct 2026). The Transformers.js dtype guide names it as an example model. A natural second base encoder for the "if time remains" item.
- **BAAI/bge-small-en-v1.5**: MIT (FlagEmbedding), 33.4M parameters, 384 dimensions, 512 tokens, English; official `onnx/model.onnx` 133 MB only; the `Xenova/bge-small-en-v1.5` mirror has `model_int8.onnx` 33.8 MB and `model_fp16.onnx` 66.7 MB (https://huggingface.co/BAAI/bge-small-en-v1.5, …/tree/main/onnx and https://huggingface.co/Xenova/bge-small-en-v1.5/tree/main/onnx, checked 16 Oct 2026). In budget at int8, over it at fp16.
- **thenlper/gte-small**: `mit`, 33.4M parameters, 384 dimensions, 512 tokens, English only; the `Supabase/gte-small` mirror has `model_quantized.onnx` 34 MB and `model_fp16.onnx` 66.7 MB (https://huggingface.co/thenlper/gte-small and https://huggingface.co/Supabase/gte-small/tree/main/onnx, checked 16 Oct 2026).
- **cross-encoder/ms-marco-MiniLM-L6-v2** (a cross-encoder, not an embedder): Apache 2.0, 22.7M parameters; mirror `Xenova/ms-marco-MiniLM-L-6-v2` has `model_int8.onnx` 23 MB (https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2 and https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2/tree/main/onnx, checked 16 Oct 2026). Relevant to option (b2) below.
- **TaylorAI/bge-micro-v2**: MIT, 17.4M parameters, 384 dimensions, distilled from bge-small-en-v1.5; ONNX tag present but file sizes not checked; no Transformers.js example (https://huggingface.co/TaylorAI/bge-micro-v2, checked 16 Oct 2026).
- **Snowflake/snowflake-arctic-embed-s**: Apache-2.0, 33M parameters, 384 dimensions, Transformers.js example present; ONNX sizes not checked (https://huggingface.co/Snowflake/snowflake-arctic-embed-s, checked 16 Oct 2026).
- **ibm-granite/granite-embedding-30m-english**: Apache 2.0, 30M parameters, 384 dimensions, 512 tokens, English, r1.1 dated 29 August 2025; repo has `model.onnx` 121 MB (fp32) and `model.safetensors` 60.6 MB, no quantised file (https://huggingface.co/ibm-granite/granite-embedding-30m-english and …/tree/main, checked 16 Oct 2026). Would need our own int8 export (expected about 30 MB, derived, not verified).
- **jinaai/jina-embeddings-v2-small-en**: Apache 2.0, 33M parameters, 8192 tokens via ALiBi, English, but needs `trust_remote_code` for its custom architecture (https://huggingface.co/jinaai/jina-embeddings-v2-small-en, checked 16 Oct 2026). Custom code is a risk for ONNX export and Transformers.js; skip.

**Static (bag-of-token) models, in budget with work:**

- **minishlab/potion-base-8M**: MIT, 7.56M parameters, 256 dimensions (config: `model2vec`/`StaticModel`, bge-base tokenizer, normalise true), distilled from bge-base-en-v1.5, English; MTEB mean 51.32, stated as 91.96% of all-MiniLM-L6-v2; `model.safetensors` 30.2 MB and `onnx/model.onnx` 30.2 MB, both fp32 (https://huggingface.co/minishlab/potion-base-8M, …/tree/main, …/tree/main/onnx and …/raw/main/config.json, checked 16 Oct 2026). An int8 table would be about 7.6 MB (derived). Transformers.js has no native model2vec class; the maintainer closed the request saying correctly exported model2vec models work, pointing to a thread with an export script and a hand-rolled tokenise-then-offsets loader (https://github.com/huggingface/transformers.js/issues/970 and https://github.com/MinishLab/model2vec/issues/75, checked 16 Oct 2026). The `model2vec` package (MIT, 0.10.0 released 11 October 2026, Python 3.10+) includes `StaticModelForClassification` for training classifiers (https://github.com/MinishLab/model2vec and https://pypi.org/project/model2vec/, checked 16 Oct 2026).
- **sentence-transformers/static-retrieval-mrl-en-v1**: `apache-2.0`, 1024 dimensions, English, Matryoshka-trained (32 to 1024 dims), 87.4% of all-mpnet-base-v2 on NanoBEIR, claimed 100–400× faster on CPU; the `0_StaticEmbedding` folder is 126 MB fp32 (https://huggingface.co/sentence-transformers/static-retrieval-mrl-en-v1 and …/tree/main/0_StaticEmbedding; https://huggingface.co/blog/static-embeddings, checked 16 Oct 2026). Truncated to 256 dims and int8 this would be about 8 MB (derived).
- **sentence-transformers/static-similarity-mrl-multilingual-v1**: Apache 2.0, 51 languages, BERT multilingual uncased tokenizer, 1024 dims with Matryoshka; card reports a 0.15% loss at 256 dims and 0.56% at 128 dims on English STS; about 125× faster on CPU than multilingual-e5-small; `model.safetensors` 434 MB fp32 (https://huggingface.co/sentence-transformers/static-similarity-mrl-multilingual-v1 and …/tree/main/0_StaticEmbedding, checked 16 Oct 2026). At 256 dims and int8 this is about 27 MB (derived, not verified) — the only multilingual path I found inside 40 MB.

**Over the 40 MB budget (listed because the relay named them or they are new):**

- **intfloat/multilingual-e5-small**: `mit`, 100+ languages; parameter count not on the card; the `Xenova/multilingual-e5-small` mirror has `model_int8.onnx` 118 MB and `model_fp16.onnx` 235 MB (https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md and https://huggingface.co/Xenova/multilingual-e5-small/tree/main/onnx, checked 16 Oct 2026). Three times the budget.
- **sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2**: `apache-2.0`, 0.1B parameters, 50 languages, 128 tokens; mirror int8 118 MB, fp16 235 MB (https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 and https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/tree/main/onnx, checked 16 Oct 2026).
- **nomic-ai/nomic-embed-text-v1.5**: `apache-2.0`, 0.1B parameters, Matryoshka 64–768 dims, 8192 tokens, English, Transformers.js example on the card; `model_int8.onnx` 137 MB, `model_q4f16.onnx` 111 MB (https://huggingface.co/nomic-ai/nomic-embed-text-v1.5 and …/tree/main/onnx, checked 16 Oct 2026). Matryoshka shrinks the output vector, not the weights.
- **minishlab/potion-multilingual-128M**: `mit`, 0.1B parameters, 256 dims, 101 languages, distilled from bge-m3 (https://huggingface.co/minishlab/potion-multilingual-128M, checked 16 Oct 2026). About 128 MB at int8 (derived).
- **ibm-granite/granite-embedding-97m-multilingual-r2**: Apache 2.0, 97M parameters, 384 dims, 200+ languages, 32k context, released 14 May 2026 with ONNX and OpenVINO weights; the blog puts the quantised ONNX file for the 97M model at 98 MB (https://huggingface.co/blog/ibm-granite/granite-embedding-multilingual-r2, checked 16 Oct 2026). Two and a half times the budget.
- **Horizon-Labs/multilingual-embedding-small**: Apache-2.0, 141M parameters (mmBERT-small distilled from bge-m3), about 90 languages, `onnx/model_quantized.onnx` 269 MB (https://huggingface.co/Horizon-Labs/multilingual-embedding-small, checked 16 Oct 2026).
- **google/embeddinggemma-2**: Apache 2.0, not gated (Hub API `gated: false`; repository created 14 September 2026), 270M text backbone (740M with vision and audio), 768 dims, 100+ languages; the ONNX text encoder alone is 157 MB at q4f16, 175 MB at q4 and 314 MB at q8; supported from Transformers.js 4.3.1 (https://huggingface.co/google/embeddinggemma-2, https://huggingface.co/api/models/google/embeddinggemma-2, https://huggingface.co/onnx-community/embeddinggemma-2-ONNX and https://github.com/huggingface/transformers.js/releases, checked 16 Oct 2026).
- **Qwen/Qwen3-Embedding-0.6B**: Apache 2.0, 600M parameters, 100+ languages, no ONNX mentioned (https://huggingface.co/Qwen/Qwen3-Embedding-0.6B, checked 16 Oct 2026). A possible Spark-side teacher of embeddings, never a student.
- **jinaai/jina-embeddings-v5-text-small**: released 18 February 2026, 677M parameters, licence CC BY-NC 4.0 (https://huggingface.co/jinaai/jina-embeddings-v5-text-small, checked 16 Oct 2026). Non-commercial: excluded by D12 regardless of size.

No new sub-50M transformer encoder released in 2026 turned up in today's searches; the small-model field is still the 2023–2024 MiniLM/BGE/GTE/Arctic generation plus static models. The 2026 releases found (EmbeddingGemma 2, Granite R2, Jina v5) are all 97M or larger.

**Tooling versions (for pinning):** `@huggingface/transformers` 4.3.1 (7 October 2026; 4.3.0 on 16 September; 4.2.0 on 23 April), Transformers.js v4 released 9 February 2026 with a rewritten WebGPU runtime, about 4× faster BERT embeddings, and `env.useWasmCache` for offline use (https://github.com/huggingface/transformers.js/releases and https://huggingface.co/blog/transformersjs-v4, checked 16 Oct 2026). `sentence-transformers` 6.1.0, 18 September 2026, Apache-2.0, Python 3.10–3.13 (https://pypi.org/project/sentence-transformers/, checked 16 Oct 2026). `setfit` 1.2.0, 4 September 2026, Apache 2.0 (https://pypi.org/project/setfit/, checked 16 Oct 2026). `onnxruntime` 1.31.0, 9 October 2026, MIT, Python 3.11+; the release before it is 1.30.0, 10 September 2026 (https://pypi.org/project/onnxruntime/, checked 16 Oct 2026). `optimum-onnx` 0.1.0, 23 December 2025, Apache-2.0; its export covers Bert, MPNet, XLM-Roberta, ModernBert and all Transformer-based sentence-transformers models (https://pypi.org/project/optimum-onnx/ and https://huggingface.co/docs/optimum-onnx/onnx/overview, checked 16 Oct 2026). Transformers.js's own docs point to optimum-onnx for conversion and to `env.localModelPath` / `env.allowRemoteModels = false` for self-hosted models (https://huggingface.co/docs/transformers.js/custom_usage, checked 16 Oct 2026). ONNX Runtime recommends dynamic quantisation for transformer models and S8S8 as the default CPU format, via `quantize_dynamic(model_fp32, model_quant)` (https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html, checked 16 Oct 2026). PyTorch's current version and macOS arm64 support were not checked here: unknown, W3 must check.

### (b) Ways to pose "which bundle, or none"

1. **Bi-encoder with a calibrated head.** Embed the new chat once; represent each bundle by the normalised mean of its chats' embeddings (a prototype, as in Prototypical Networks: classify by distance to class means in a learned embedding space, https://arxiv.org/abs/1703.05175, checked 16 Oct 2026) and each loose chat by its own embedding. Scores are cosines; a small head turns the score vector into logits over candidates plus "none"; softmax gives probabilities. Training the encoder uses sentence-transformers' `MultipleNegativesRankingLoss` or its cached variant on (chat, bundle-mate) pairs with in-batch negatives, which is the documented loss for anchor-positive data; `BatchHardTripletLoss` is the documented choice for labelled classes (https://sbert.net/docs/sentence_transformer/training_overview.html, checked 16 Oct 2026). SetFit does the same thing as a package: contrastive fine-tuning of a sentence transformer, then a logistic-regression or differentiable torch head, with ONNX export (https://arxiv.org/abs/2209.11055 and https://huggingface.co/docs/setfit/index, checked 16 Oct 2026), but SetFit's head is over a fixed label set, and our label set changes per person, so we would use its recipe, not its classifier. Cost in the browser: one encoder pass per new chat; candidate vectors are cached and updated by a running mean.
2. **Cross-encoder.** Feed (chat, candidate description) pairs through one transformer and read a score; trained with `BinaryCrossEntropyLoss` or listwise losses, and the docs say the strongest ones are trained on hard negatives and recommend them as second-stage rerankers because every pair costs a forward pass (https://sbert.net/docs/cross_encoder/training_overview.html, checked 16 Oct 2026). A person with 20 bundles and 60 loose chats needs 80 passes per decision; the relay's budget is 50 ms per decision. ms-marco-MiniLM-L6-v2 fits the size budget (23 MB int8) but not the latency budget. Use only as a V1 reranker over the top three candidates if accuracy demands it.
3. **Set classification.** A permutation-invariant head that reads the whole candidate set at once (the Set Transformer: attention over set elements with pooling by multihead attention, https://arxiv.org/abs/1810.00825, checked 16 Oct 2026) sitting on frozen or fine-tuned embeddings. It can learn facts a per-candidate score cannot, such as "two bundles are equally close, so probably neither" or "this person files food with running". The head is tiny (well under 1 MB) and runs in JavaScript. The risk is overfitting to the teacher's invented people. The softmax-over-candidates-plus-none in option 1 is already the minimal set-aware model; a learned set head is its V1 extension.
4. **Fine-tuning a decision model.** Strands Decider 2B is Apache-2.0, a LoRA adapter on Qwen3.5-2B-Base with a small readout head, answers `noul`/`choice`/`score` questions with calibrated confidences, reports 0.723 accuracy, 0.348 Brier and 0.050 ECE on public JevBench, and publishes its training recipe (https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v19, checked 16 Oct 2026). Its ONNX conversion is 1.80 GB at q8 and 1.09 GB at q4f16 (https://huggingface.co/onnx-community/strands-decider-2B-hobson-v19-ONNX, checked 16 Oct 2026), 27× our budget. Clef-flash is 9B, Apache 2.0, 64k context, and the changelog invites design partners for a reinforcement-learning tuning service rather than offering one openly (https://developers.cloudflare.com/changelog/post/2026-10-01-clef-workers-ai/, checked 16 Oct 2026); its weights are at `Cloudflare/clef-flash`, Hub API `gated: false`, licence tag apache-2.0, created 30 September 2026 (https://huggingface.co/api/models/Cloudflare/clef-flash, checked 16 Oct 2026). Strands Decider 2B is likewise `gated: false` (https://huggingface.co/api/models/StrandsAgents/strands-decider-2B-hobson-v19, checked 16 Oct 2026). These are comparators (D11) and possible Spark-side labellers or distillation teachers, never the browser student.

### (c) Handling chats that belong to no bundle

- **Threshold on the top probability.** The classic baseline: correctly classified inputs tend to have higher maximum softmax probability than misclassified or out-of-distribution ones (https://arxiv.org/abs/1610.02136, checked 16 Oct 2026). This is B1's "none" for free. Vaze et al. found that the ability to say "none of the above" correlates strongly with closed-set accuracy, and a maximum-logit baseline on a well-trained classifier matches specialised open-set methods (https://arxiv.org/abs/2110.06207, checked 16 Oct 2026). Translation: spend effort on a better encoder before a cleverer rejection rule.
- **Energy score.** The negative log-sum-exp of the logits tracks input density and is less overconfident than softmax; on CIFAR-10 the abstract reports the average FPR at 95% TPR reduced by 18.03% against softmax confidence (https://arxiv.org/abs/2010.03759, checked 16 Oct 2026), and has been applied to unknown-intent detection (https://aclanthology.org/2021.findings-acl.252/, checked 16 Oct 2026). Cheap to compute from the same logits; worth logging as a second signal.
- **An explicit "none" class.** CLINC150 (150 intents, 22,500 in-scope and 1,200 out-of-scope queries, split 100/100/1,000) found that every classifier tested struggles with out-of-scope queries (best out-of-scope recall 66% even with plenty of out-of-scope training data), that more out-of-scope training data helps but is costly to make, and that a probability threshold is the general rule usable with any model; in its own table BERT's out-of-scope recall was higher with the threshold than with a trained 151st class (https://aclanthology.org/D19-1131.pdf, https://aclanthology.org/D19-1131/ and https://github.com/clinc/oos-eval, checked 16 Oct 2026). It does not recommend a trained none class over thresholding; it shows neither is enough on its own. DETER (2024) reaches its gains on CLINC150 and Banking77 by generating synthetic outliers and then thresholding (https://aclanthology.org/2024.lrec-main.763/, checked 16 Oct 2026). Our teacher already writes "belongs nowhere" chats (relay difficulty mix), so a trained none logit costs nothing extra. But a fixed "none vector" in embedding space is the wrong shape for us: whether a chat is "none" depends on which bundles this person has, so the none logit must be a function of the candidate scores (top score, margin, count), not a point in space.
- **Per-class boundaries.** Adaptive Decision Boundary learns a spherical radius per known class around its centroid without open examples (https://arxiv.org/abs/2012.10209, checked 16 Oct 2026). Natural for bundles of different tightness; a V1 refinement.
- **Mahalanobis distance** needs class-conditional covariances (https://arxiv.org/abs/1807.03888, checked 16 Oct 2026); bundles of two to eight chats cannot support that. Skip.

### (d) Calibration methods and metrics

- **Temperature scaling**: one scalar on the logits, fitted on a held-out set, found "surprisingly effective" against Platt, isotonic and histogram binning, and it leaves accuracy unchanged (https://arxiv.org/abs/1706.04599, checked 16 Oct 2026). scikit-learn offers Platt (sigmoid), isotonic and temperature scaling in `CalibratedClassifierCV`, and warns that isotonic overfits below roughly 1,000 samples (https://scikit-learn.org/stable/modules/calibration.html, checked 16 Oct 2026).
- **Conformal prediction** gives a distribution-free guarantee that the prediction set contains the truth with probability 1−α, given an exchangeable calibration set and a score (https://arxiv.org/abs/2107.07511, checked 16 Oct 2026); MAPIE (BSD-3-Clause, scikit-learn-contrib) implements classification sets (https://mapie.readthedocs.io/en/stable/, checked 16 Oct 2026). It guarantees coverage, not precision, so it fits "suggest" (a small set that nearly always contains the right bundle) better than "file".
- **Metrics.** ECE is the binned gap between confidence and accuracy (Guo et al., above). Brier is a strictly proper score that mixes calibration and discrimination, so a lower Brier does not by itself mean better calibration (scikit-learn, above). "Precision and coverage at a cut-off" is selective classification's risk–coverage trade-off with the softmax response as the selector (https://arxiv.org/abs/1705.08500, checked 16 Oct 2026). A torchmetrics reference for ECE did not load today: unknown; compute ECE by hand with 10–15 bins.

## Options compared

| Option | Download (int8) | Licence | Browser cost per decision | Handles "none" | Verdict |
|---|---|---|---|---|---|
| all-MiniLM-L6-v2 bi-encoder + tiny head | 23 MB + ~1 MB tokenizer/head | Apache-2.0 | 1 encoder pass; dot products | Learned none logit from scores | **V0 pick** |
| snowflake-arctic-embed-xs, same design | 23 MB | Apache-2.0 | same | same | Equal size; asymmetric retrieval model; second encoder candidate |
| mxbai-embed-xsmall-v1, same design | 24.4 MB | Apache-2.0 | same | same | Good second encoder ("if time remains" item 2) |
| bge-small-en-v1.5 / gte-small | 34 MB | MIT | about 1.5× MiniLM | same | In budget, no fp16 fallback, bigger for little gain unknown |
| potion-base-8M static + head | ~8 MB (derived) | MIT | microseconds | same | V0 fallback if the Mac is slow; needs custom JS loader |
| static-similarity-mrl-multilingual-v1 @256d | ~27 MB (derived) | Apache-2.0 | microseconds | same | Only multilingual path in budget; V1 experiment |
| Cross-encoder (ms-marco-MiniLM-L6-v2) | 23 MB | Apache-2.0 | N passes (N = candidates) | threshold | Fails 50 ms budget; V1 reranker at most |
| Set-Transformer head on embeddings | +<1 MB | ours | ms | learned from set | V1 extension |
| Fine-tune Strands Decider 2B | 1.09 GB (q4f16) | Apache-2.0 | seconds | native | Comparator/labeller only |
| multilingual-e5-small / paraphrase-multilingual-MiniLM | 118 MB | MIT / Apache-2.0 | 5× MiniLM | same | Over budget 3× |
| nomic-embed-text-v1.5 | 137 MB | Apache-2.0 | 6× | same | Over budget |
| EmbeddingGemma 2 (text) | 175 MB (q4) | Apache 2.0 | 10×+ | same | Over budget; V1 teacher of embeddings maybe |

## Recommendation

**Base encoder: `sentence-transformers/all-MiniLM-L6-v2`, licence Apache-2.0, not gated** (Hub API `gated: false`, https://huggingface.co/api/models/sentence-transformers/all-MiniLM-L6-v2, checked 16 Oct 2026; 22.7M parameters, 384 dims, 23 MB at int8, official ONNX in the repo, Transformers.js mirrors and examples, exportable with optimum-onnx). It is symmetric (chat-to-chat), the most widely mirrored small encoder, and the one every later comparison will be read against. Second encoder for the board: `mixedbread-ai/mxbai-embed-xsmall-v1` (Apache-2.0, not gated per the Hub API, 24.4 MB int8; https://huggingface.co/api/models/mixedbread-ai/mxbai-embed-xsmall-v1, checked 16 Oct 2026), same family and tokenizer, so the browser code does not change. One caveat the first draft under-weighted: MiniLM truncates input at 256 word pieces, while mxbai-xsmall reads 4,096 tokens (both cards, above). A multi-turn chat is longer than 256 word pieces, so MiniLM would see only its opening. If R3's chats are long, mxbai-xsmall should be the primary and MiniLM the challenger; the 1.4 MB difference is nothing. Both go on the V0 board either way, and the exam decides.

**Version 0 (today, Mac, toy scale):**
1. B1 baseline: frozen MiniLM, bundle prototype = normalised mean of member embeddings, loose chat = its embedding, softmax over scaled cosines, "none" when the top probability is under a cut-off tuned on practice.
2. B2 student: the same encoder with a fitted head of about six parameters: logits `z_i = a·s_i + b_kind(i)` for each candidate and `z_none = c0 + c1·max_i s_i + c2·(top1 − top2) + c3·log(n_candidates)`, fitted by cross-entropy on the lessons split (the teacher's "belongs nowhere" chats supply the none labels), then one temperature on practice, then cut-offs. Ship the head as JSON in the model manifest; it is twenty lines of JavaScript. If time allows, also fine-tune the encoder with MultipleNegativesRankingLoss on (chat, bundle-mate) pairs with same-person hard negatives for one or two epochs and put it on the board as B2b. Put both on the board; do not assume fine-tuning beats the head on 1,400 toy chats.
3. Export: `optimum-cli export onnx` to fp32, then `quantize_dynamic` to int8 (S8S8), and keep the fp32 and int8 files side by side. Check PyTorch versus fp32 ONNX at cosine ≥ 0.999 on the 32 fixtures, and int8 versus fp32 separately; report the int8 gap and its effect on exam accuracy rather than gating on 0.999 for int8.
4. Calibration: temperature only. The toy practice split is roughly 24 people × 60 chats × 10% ≈ 144 chats; isotonic and conformal need far more, and a 95% precision cut-off estimated on 144 examples has an error bar wider than the target. Report ECE (10 bins), Brier, precision and coverage at both cut-offs, with bootstrap intervals, labelled toy scale.
5. Pins: Transformers.js 4.3.0 (16 September) rather than 4.3.1 (7 October, nine days old) under the fourteen-day rule; sentence-transformers 6.1.0; optimum-onnx 0.1.0; onnxruntime 1.30.0 (10 September 2026), since 1.31.0 is seven days old; Python 3.12, since onnxruntime now needs 3.11+ and sentence-transformers supports up to 3.13.

**Version 1 (DGX Spark, BDL-4 onwards):**
1. Fine-tune MiniLM (and mxbai-xsmall as the challenger) with MNRL plus hard negatives on the full lesson set; keep the prototype design.
2. Replace the six-parameter head with a small set-aware head (Set Transformer or an MLP over per-candidate features and set statistics) and add per-bundle adaptive radii; train none on the teacher's none chats plus held-out bundles treated as none.
3. With a practice set of several thousand chats, compare temperature, isotonic and conformal "suggest" sets; keep whichever gives the best precision at 95% coverage on practice and confirm on the exam.
4. Add a cross-encoder rerank over the top three only if the exam shows a gap that the bi-encoder cannot close, and measure it against the 50 ms budget on a phone.
5. Multilingual: test `static-similarity-mrl-multilingual-v1` truncated to 256 dims (about 27 MB int8, derived) as a separate student. It is not gated (Hub API `gated: false`, https://huggingface.co/api/models/sentence-transformers/static-similarity-mrl-multilingual-v1, checked 16 Oct 2026). If it is not good enough, multilingual means a 98–118 MB download, and that is a product decision for Hrishikesh, not a research one.
6. Use Strands Decider 2B and Clef-flash on the Spark as comparators and as labellers for ambiguous teacher output, as D11 says.

## What doesn't work, or would change the plan

1. **No multilingual transformer encoder fits in 40 MB.** Every one found (multilingual-e5-small 118 MB, paraphrase-multilingual-MiniLM 118 MB, Granite 97M at 98 MB, Horizon-Labs 269 MB, EmbeddingGemma 2 157 MB at q4f16) is two to seven times the budget, because the vocabulary alone is 90–250M parameters. The relay's "multilingual reach" and the 40 MB budget cannot both hold with a transformer; only a Matryoshka-truncated static model does both, at unknown quality for our task. Decide which rule bends.
2. **Two of the relay's named candidates are out of budget**: nomic-embed-text-v1.5 (137 MB int8) and multilingual-e5-small (118 MB). Matryoshka dimensions do not shrink the download.
3. **"An explicit none vector" is the wrong idea for this task.** None is relative to the person's candidate set, so it must be computed from the candidate scores, not stored as a point in embedding space. The relay's spec is fine; the phrasing in the R2 brief would mislead an implementer.
4. **The cosine ≥ 0.999 check after int8 quantisation will probably fail** and would be the wrong gate: 0.999 is a sensible bar for fp32 PyTorch versus fp32 ONNX; int8 should be judged by its exam effect. Not verified by running; W6 should measure and record, not block.
5. **Toy-scale calibration numbers are not meaningful at the 95% level.** With about 144 practice chats, the file cut-off cannot be set with confidence; D6's targets can only be tested on the Spark run. Label the toy board accordingly and do not let it decide anything.
6. **A cross-encoder cannot meet 50 ms per decision** once a person has tens of candidates. Drop it from V0 entirely.
7. **Fine-tuning a decision model as the student is impossible in a browser**: the smallest open one is 1.09 GB at q4f16. They are comparators, as D11 already says.
8. **Freshness rule versus latest versions**: Transformers.js 4.3.1, onnxruntime 1.31.0 and model2vec 0.10.0 are all under fourteen days old. Pin the previous releases.
9. **Mirrors are not uniform**: the onnx-community MiniLM listing showed no int8 file while the Xenova and official repos do. The site must ship its own ONNX files from `web/public/models/` through the manifest, as the relay already plans; never load from the Hub at run time.
10. **Static models need a custom loader in Transformers.js** (tokenise, flatten ids, pass offsets); model2vec support is "works if exported correctly", not a one-line pipeline. That is a day of work; only worth it if MiniLM is too slow on the Mac or a phone, which R4 will tell us.
11. **Unknowns**: PyTorch's current version and macOS arm64 support; the ONNX sizes of bge-micro-v2 and arctic-embed-s; the real quality of a 256-dim static multilingual model on short, typo-ridden chats. Each is marked unknown above rather than guessed.
12. **MiniLM's 256-word-piece truncation may be the wrong default for chats.** all-MiniLM-L6-v2 cuts input at 256 word pieces (its card, checked 16 Oct 2026); a chat of several turns is longer, so the encoder would judge the opening only. mxbai-embed-xsmall-v1 reads 4,096 tokens for 1.4 MB more. The primary pick should follow R3's measured chat lengths, not habit. If chats are long and MiniLM is kept anyway, W4 must say how the chat is cut (first turns, last turns, or a summary) and test it, because that choice will move the exam more than the encoder does.
13. **The relay's own phrasing of CLINC150 lore is backwards.** The paper does not show that a trained none class beats a threshold; its table shows the opposite for BERT, and it says neither is enough. Our teacher's none chats are cheap, so we use them, but the none decision stays a function of the scores.

## Sources

1. https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 (checked 16 Oct 2026)
2. https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/main/onnx (checked 16 Oct 2026)
3. https://huggingface.co/Xenova/all-MiniLM-L6-v2 (checked 16 Oct 2026)
4. https://huggingface.co/Xenova/all-MiniLM-L6-v2/tree/main/onnx (checked 16 Oct 2026)
5. https://huggingface.co/onnx-community/all-MiniLM-L6-v2-ONNX/tree/main/onnx (checked 16 Oct 2026)
6. https://huggingface.co/Snowflake/snowflake-arctic-embed-xs (checked 16 Oct 2026)
7. https://huggingface.co/Snowflake/snowflake-arctic-embed-xs/tree/main/onnx (checked 16 Oct 2026)
8. https://huggingface.co/Snowflake/snowflake-arctic-embed-s (checked 16 Oct 2026)
9. https://huggingface.co/mixedbread-ai/mxbai-embed-xsmall-v1 (checked 16 Oct 2026)
10. https://huggingface.co/mixedbread-ai/mxbai-embed-xsmall-v1/tree/main/onnx (checked 16 Oct 2026)
11. https://huggingface.co/BAAI/bge-small-en-v1.5 (checked 16 Oct 2026)
12. https://huggingface.co/BAAI/bge-small-en-v1.5/tree/main/onnx (checked 16 Oct 2026)
13. https://huggingface.co/Xenova/bge-small-en-v1.5/tree/main/onnx (checked 16 Oct 2026)
14. https://huggingface.co/thenlper/gte-small (checked 16 Oct 2026)
15. https://huggingface.co/Supabase/gte-small/tree/main/onnx (checked 16 Oct 2026)
16. https://huggingface.co/TaylorAI/bge-micro-v2 (checked 16 Oct 2026)
17. https://huggingface.co/ibm-granite/granite-embedding-30m-english (checked 16 Oct 2026)
18. https://huggingface.co/ibm-granite/granite-embedding-30m-english/tree/main (checked 16 Oct 2026)
19. https://huggingface.co/jinaai/jina-embeddings-v2-small-en (checked 16 Oct 2026)
20. https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2 (checked 16 Oct 2026)
21. https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2/tree/main/onnx (checked 16 Oct 2026)
22. https://huggingface.co/minishlab/potion-base-8M (checked 16 Oct 2026)
23. https://huggingface.co/minishlab/potion-base-8M/tree/main (checked 16 Oct 2026)
24. https://huggingface.co/minishlab/potion-base-8M/tree/main/onnx (checked 16 Oct 2026)
25. https://huggingface.co/minishlab/potion-base-8M/raw/main/config.json (checked 16 Oct 2026)
26. https://huggingface.co/minishlab/potion-multilingual-128M (checked 16 Oct 2026)
27. https://github.com/MinishLab/model2vec (checked 16 Oct 2026)
28. https://github.com/MinishLab/model2vec/issues/75 (checked 16 Oct 2026)
29. https://github.com/huggingface/transformers.js/issues/970 (checked 16 Oct 2026)
30. https://pypi.org/project/model2vec/ (checked 16 Oct 2026)
31. https://huggingface.co/sentence-transformers/static-retrieval-mrl-en-v1 (checked 16 Oct 2026)
32. https://huggingface.co/sentence-transformers/static-retrieval-mrl-en-v1/tree/main/0_StaticEmbedding (checked 16 Oct 2026)
33. https://huggingface.co/sentence-transformers/static-similarity-mrl-multilingual-v1 (checked 16 Oct 2026)
34. https://huggingface.co/sentence-transformers/static-similarity-mrl-multilingual-v1/tree/main/0_StaticEmbedding (checked 16 Oct 2026)
35. https://huggingface.co/blog/static-embeddings (checked 16 Oct 2026)
36. https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md (checked 16 Oct 2026)
37. https://huggingface.co/Xenova/multilingual-e5-small/tree/main/onnx (checked 16 Oct 2026)
38. https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (checked 16 Oct 2026)
39. https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/tree/main/onnx (checked 16 Oct 2026)
40. https://huggingface.co/nomic-ai/nomic-embed-text-v1.5 (checked 16 Oct 2026)
41. https://huggingface.co/nomic-ai/nomic-embed-text-v1.5/tree/main/onnx (checked 16 Oct 2026)
42. https://huggingface.co/blog/ibm-granite/granite-embedding-multilingual-r2 (checked 16 Oct 2026)
43. https://huggingface.co/Horizon-Labs/multilingual-embedding-small (checked 16 Oct 2026)
44. https://huggingface.co/google/embeddinggemma-2 (checked 16 Oct 2026)
45. https://huggingface.co/onnx-community/embeddinggemma-2-ONNX (checked 16 Oct 2026)
46. https://huggingface.co/Qwen/Qwen3-Embedding-0.6B (checked 16 Oct 2026)
47. https://huggingface.co/jinaai/jina-embeddings-v5-text-small (checked 16 Oct 2026)
48. https://huggingface.co/blog/transformersjs-v4 (checked 16 Oct 2026)
49. https://github.com/huggingface/transformers.js/releases (checked 16 Oct 2026)
50. https://github.com/huggingface/transformers.js (checked 16 Oct 2026)
51. https://huggingface.co/docs/transformers.js/guides/dtypes (checked 16 Oct 2026)
52. https://huggingface.co/docs/transformers.js/custom_usage (checked 16 Oct 2026)
53. https://huggingface.co/docs/optimum-onnx/onnx/overview (checked 16 Oct 2026)
54. https://pypi.org/project/optimum-onnx/ (checked 16 Oct 2026)
55. https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html (checked 16 Oct 2026)
56. https://pypi.org/project/onnxruntime/ (checked 16 Oct 2026)
57. https://pypi.org/project/sentence-transformers/ (checked 16 Oct 2026)
58. https://sbert.net/docs/sentence_transformer/training_overview.html (checked 16 Oct 2026)
59. https://sbert.net/docs/cross_encoder/training_overview.html (checked 16 Oct 2026)
60. https://pypi.org/project/setfit/ (checked 16 Oct 2026)
61. https://huggingface.co/docs/setfit/index (checked 16 Oct 2026)
62. https://arxiv.org/abs/2209.11055 — SetFit, Tunstall et al. 2022 (checked 16 Oct 2026)
63. https://arxiv.org/abs/1703.05175 — Prototypical Networks, Snell et al. 2017 (checked 16 Oct 2026)
64. https://arxiv.org/abs/1810.00825 — Set Transformer, Lee et al. 2019 (checked 16 Oct 2026)
65. https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v19 (checked 16 Oct 2026)
66. https://huggingface.co/onnx-community/strands-decider-2B-hobson-v19-ONNX (checked 16 Oct 2026)
67. https://developers.cloudflare.com/changelog/post/2026-10-01-clef-workers-ai/ (checked 16 Oct 2026)
68. https://arxiv.org/abs/1610.02136 — Hendrycks and Gimpel 2017, max softmax baseline (checked 16 Oct 2026)
69. https://arxiv.org/abs/2110.06207 — Vaze et al. 2022, open-set recognition (checked 16 Oct 2026)
70. https://arxiv.org/abs/2010.03759 — Liu et al. 2020, energy-based OOD (checked 16 Oct 2026)
71. https://aclanthology.org/2021.findings-acl.252/ — Ouyang et al. 2021, energy for unknown intents (checked 16 Oct 2026)
72. https://aclanthology.org/D19-1131.pdf — Larson et al. 2019, CLINC150 (checked 16 Oct 2026)
73. https://aclanthology.org/2024.lrec-main.763/ — Zawbaa et al. 2024, DETER (checked 16 Oct 2026)
74. https://arxiv.org/abs/2012.10209 — Zhang et al. 2021, adaptive decision boundary (checked 16 Oct 2026)
75. https://arxiv.org/abs/1807.03888 — Lee et al. 2018, Mahalanobis OOD (checked 16 Oct 2026)
76. https://arxiv.org/abs/1706.04599 — Guo et al. 2017, calibration and temperature scaling (checked 16 Oct 2026)
77. https://scikit-learn.org/stable/modules/calibration.html (checked 16 Oct 2026)
78. https://arxiv.org/abs/2107.07511 — Angelopoulos and Bates, conformal prediction (checked 16 Oct 2026)
79. https://mapie.readthedocs.io/en/stable/ (checked 16 Oct 2026)
80. https://arxiv.org/abs/1705.08500 — Geifman and El-Yaniv 2017, selective classification (checked 16 Oct 2026)
81. https://huggingface.co/blog/stephen-solka/embedding-model-in-the-browser — optimum export, int8, WASM worker pattern, 28 May 2026 (checked 16 Oct 2026)
82. https://huggingface.co/api/models/sentence-transformers/all-MiniLM-L6-v2 — Hub API, gated false (checked 16 Oct 2026)
83. https://huggingface.co/api/models/mixedbread-ai/mxbai-embed-xsmall-v1 — Hub API, gated false (checked 16 Oct 2026)
84. https://huggingface.co/api/models/sentence-transformers/static-similarity-mrl-multilingual-v1 — Hub API, gated false (checked 16 Oct 2026)
85. https://huggingface.co/api/models/google/embeddinggemma-2 — Hub API, gated false, created 14 Sep 2026 (checked 16 Oct 2026)
86. https://huggingface.co/api/models/StrandsAgents/strands-decider-2B-hobson-v19 — Hub API, gated false (checked 16 Oct 2026)
87. https://huggingface.co/api/models/Cloudflare/clef-flash — Hub API, gated false, created 30 Sep 2026 (checked 16 Oct 2026)
88. https://aclanthology.org/D19-1131/ — CLINC150 abstract page (checked 16 Oct 2026)
89. https://github.com/clinc/oos-eval — CLINC150 split counts (checked 16 Oct 2026)

## Verification notes (skeptic)

Second pass on 16 Oct 2026 by the R2 skeptic. Every URL below was reopened today; figures were read from the page, not from the first draft.

**Confirmed as written (28 spot checks).** all-MiniLM-L6-v2: apache-2.0, 22.7M, 384 dims, 256 word pieces; official `onnx/` has `model_O4.onnx` 45.2 MB and four int8 files at 23 MB; Xenova mirror `model_int8.onnx` 23 MB, `model_q4f16.onnx` 30 MB; onnx-community listing has no int8 file. mxbai-embed-xsmall-v1: Apache 2.0, 24.1M, 4,096 context, `model_int8.onnx` 24.4 MB. snowflake-arctic-embed-xs: Apache-2, 22M, int8 23 MB, CLS pooling, query prefix. bge-small-en-v1.5: MIT, 33.4M; Xenova int8 33.8 MB. gte-small: MIT, 33.4M, English only; Supabase `model_quantized.onnx` 34 MB. ms-marco-MiniLM-L6-v2: Apache 2.0, 22.7M; mirror int8 23 MB. granite-embedding-30m-english: Apache 2.0, r1.1 of 29 Aug 2025, `model.onnx` 121 MB, safetensors 60.6 MB. jina-embeddings-v2-small-en: Apache 2.0, 33M, ALiBi, `trust_remote_code`. bge-micro-v2: MIT, 17.4M. arctic-embed-s: Apache-2, 33M. potion-base-8M: MIT, 7.56M, MTEB 51.32, 91.96% of MiniLM. potion-multilingual-128M: MIT, 0.1B, 256 dims, 101 languages, from bge-m3. static-retrieval-mrl-en-v1: apache-2.0, 32–1024 dims, 87.4% of all-mpnet-base-v2, 100–400× CPU claim, 126 MB. static-similarity-mrl-multilingual-v1: Apache 2.0, 51 languages, 0.15% and 0.56% loss at 256 and 128 dims, about 125× faster than multilingual-e5-small. multilingual-e5-small: mit, 101 language codes in the front matter, no parameter count; Xenova int8 118 MB. paraphrase-multilingual-MiniLM-L12-v2: apache-2.0, 0.1B, 50 languages, 128 tokens; mirror int8 118 MB. nomic-embed-text-v1.5: int8 137 MB, q4f16 111 MB. Horizon-Labs: Apache-2.0, 141M, 269 MB quantised. Qwen3-Embedding-0.6B: Apache 2.0, no ONNX mentioned. jina-embeddings-v5-text-small: CC BY-NC 4.0, 677M, 18 Feb 2026. Strands Decider 2B: Apache-2.0, LoRA on Qwen3.5-2B-Base, 0.723/0.348/0.050 on JevBench public; ONNX 1.80 GB q8, 1.09 GB q4f16. Clef-flash: 9B, Apache 2.0, 64K. Transformers.js: 4.3.1 on 7 Oct, 4.3.0 on 16 Sep, 4.2.0 on 23 Apr 2026; v4 post of 9 Feb 2026 with the rewritten WebGPU runtime, about 4× faster BERT embeddings and `env.useWasmCache`. sentence-transformers 6.1.0 (18 Sep 2026, Apache-2.0, Python 3.10–3.13); setfit 1.2.0 (4 Sep 2026); model2vec 0.10.0 (11 Oct 2026, MIT); optimum-onnx 0.1.0 (23 Dec 2025); onnxruntime 1.31.0 (9 Oct 2026, MIT, Python 3.11+). optimum-onnx lists Bert, MPNet, ModernBert, XLM-Roberta and all Transformer-based sentence-transformers models. ONNX Runtime recommends dynamic quantisation for transformers and S8S8 as the first choice. Transformers.js custom-usage page shows `env.localModelPath`, `env.allowRemoteModels = false` and points to optimum-onnx. sbert training pages name MNRL and its cached variant, BatchHardTripletLoss, BinaryCrossEntropyLoss, hard negatives and the second-stage-reranker role. SetFit docs have an ONNX tutorial. model2vec README shows `StaticModelForClassification`; transformers.js issue 970 closed 12 Apr 2026 with "exported in the right way" works. MAPIE: BSD-3-Clause, scikit-learn-contrib, classification sets. scikit-learn: temperature scaling is a `CalibratedClassifierCV` method; isotonic needs more than about 1,000 samples; Brier alone does not measure calibration. Paper abstracts for Hendrycks and Gimpel, Vaze et al., Liu et al. (energy), Zhang et al. (ADB, no open samples needed), Lee et al. (Mahalanobis), Guo et al. ("surprisingly effective"), Angelopoulos and Bates, DETER (synthetic outliers; CLINC-150, Stackoverflow, Banking77) and Ouyang et al. all say what the note says. Geifman and El-Yaniv define "softmax response" and the risk–coverage curve in the paper body (read from the PDF), not the abstract. CLINC150 has 150 intents, 22,500 in-scope and 1,200 out-of-scope queries (PDF body and the oos-eval README).

**Changed.**
1. CLINC150 was misread. The first draft said the paper "recommends training with explicit out-of-scope examples rather than thresholding alone". The paper says all methods struggle, more out-of-scope data helps but is costly, and the threshold is the general rule; BERT's out-of-scope recall was higher under oos-threshold than oos-train in Table 2. Rewritten in (c) and added as item 13.
2. Granite 97M: the derived "about 97 MB" replaced by the blog's stated 98 MB for the quantised ONNX file; ranges updated (98–118 MB).
3. onnxruntime: the previous release is 1.30.0 of 10 September 2026 (PyPI); the "unknown" is removed and the pin now names it.
4. EmbeddingGemma 2: added the q4f16 text-encoder size (157 MB), the Hub API gating check (`gated: false`) and the repository creation date; the "over budget" item now quotes the smallest file.
5. Clef-flash: "hosted RL fine-tuning service" softened to what the changelog says (design-partner sign-up); added the weights repo, its licence tag and `gated: false`.
6. Energy score: "18 points" replaced by the abstract's own wording (18.03% reduction in FPR at 95% TPR).
7. Gating: the Hub API was checked for every model the recommendation names or uses as a comparator (all-MiniLM-L6-v2, mxbai-embed-xsmall-v1, static-similarity-mrl-multilingual-v1, Strands Decider 2B, Clef-flash) and for EmbeddingGemma 2; all return `gated: false`. Sources 82–87 added.
8. Added item 12: MiniLM's 256-word-piece truncation against mxbai-xsmall's 4,096 tokens is a real reason the primary pick might flip once R3 reports chat lengths; the recommendation now says so.

**Left as unknown, on purpose.** ONNX sizes for bge-micro-v2 and arctic-embed-s; PyTorch version and macOS arm64 support; quality of a 256-dim static multilingual model on short chats; whether int8 passes cosine 0.999 (to be measured, not guessed).

**Quotes.** The longest quotation in the file is four words; nothing is copied at length.
