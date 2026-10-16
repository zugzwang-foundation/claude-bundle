# Decision models: the field in October 2026, and whether Bundle should speak Jev

Status: DRAFT — research note, 2026-10-16.

## The question

Nine products now sell or publish "decision models": models that read a state and typed questions and return a probability for every allowed answer, writing no text. Bundle is one of these in miniature. This note checks, against sources opened today, what each of them is (interface, licence, size, published and independent results), tests the relay's four "checked facts" about them, and answers one design question: should Bundle's API (request: chat plus candidates with ids, kinds, labels and examples; response: probabilities including `none`, an action and a target) also offer Jev's question format, and if so how?

## Findings

### The common shape: the "System One" API

Every product below, hosted or open, uses one request shape, first published by TypeSafe for Jev [2]: `POST /v1/systemone` with `model`, `state` (string, object or array) and `questions`, a map from question id to `{type, instructions, criteria}`. Three types exist. `noul` asks "is this true?" and returns `noul` (0 to 1). `choice` takes `criteria` as a map of option id to description (up to 255 options) and returns `choice`, `probabilities` (one per option) and `confidence`. `score` takes an ordered list of 2 to 10 levels and returns `score`, `legend`, `probabilities` and `confidence`. The response is `{model, answers: {id: ...}, usage: {input_tokens, output_tokens}}` [2][4]. Cloudflare's Clef [9], Perplexity's pplx-decider [16], Laya [23], H2O-Lightning [39] and Microsoft-Decision-1 [20][42] all document this same wire format; Strands Decider's own server uses an `options` array instead of a `criteria` map, so "Jev-compatible" is not perfectly uniform [14]. OpenAI alone renamed things: `input`, an array of questions with `name`, and `predicate` instead of `noul` [7].

Two things follow for Bundle. First, "none of these" has no special primitive anywhere: every product expects it as one more option in `criteria`. Second, the question type Bundle needs is a single `choice`, so an adapter is small.

### Jev (TypeSafe)

- Interface: the reference System One API above; model alias `jev-latest`; 32 MiB body cap; 422 on validation failure [2]. Context 32,000 tokens on Cloudflare's partner listing [4]; OpenRouter's explainer says 64k per request in TypeSafe's docs [5].
- Licence and weights: hosted only. TypeSafe's docs have no download or self-hosting page [2][3]; OpenRouter's explainer states plainly that TypeSafe has published neither weights nor a paper [5]. Only the client SDKs are open.
- Size: unknown. No source states a parameter count.
- Published results: TypeSafe's site claims 193.6× faster and 444.6× cheaper than LLMs on System One workflows, and a 238× lower input price than Claude Fable 5.1; $42 per billion input tokens ($0.042 per million), output free [1][4]. Early access from 15 September 2026; the 1.13 snapshot is dated 17 September [5]; version 1.14 appeared on the Decision Index on 15 October [32].
- Independent results: Decision Index 0.3.2 Full score 60.11 (Jev 1.13, rank 13 of 168) and 61.53 (Jev 1.14, rank 8) [32]. On S1MB, an independent 137-benchmark mosaic by Yuichi Tateno, Jev 1.13 ranks first of 23 and is far ahead on synthetic "follow a new instruction" tasks (96.27 task average) [34]. Cloudflare's own table has Jev's median latency at 524 ms [8].

### OpenAI's Decisions API

- Interface: `POST /v1/decisions` with `model` (only `gpt-6-luna`), `input` (text, or messages with base64 images) and `questions`, an array of `{type, name, instructions, ...}`; types `predicate` (returns `probability`), `choice` (`choices` with `value` and `description`; returns `choice`, `probabilities`, `confidence`) and `score` (`levels`; returns `score`, `probabilities`, `confidence`). Answers can also come back as `type: "refusal"` [7].
- Licence and weights: hosted only; it is a mode of GPT-6 Luna, so no weights exist to publish [6][7].
- Size: unknown.
- Published results: public beta since 6 October 2026; $0.10 per million input tokens, nothing for output or cache; "up to 10x faster" than Luna through the Responses API [6][7].
- Independent results: not on the Decision Index [32]. A community thread reports the `choice` form over-weights the likeliest option (98% where 70% was expected in a loaded-coin test) while `predicate` behaved [6]. That is one anecdote, but it is a warning about trusting any hosted model's probabilities uncalibrated.

### Cloudflare's Clef and Clef-flash

- Interface: System One, described by Cloudflare as switchable from Jev by changing endpoint and model [9]. Hosted as `@cf/cloudflare/clef` and `@cf/cloudflare/clef-flash`. The open weights ship with `joint_schema_model.py` (functions `encode_record`, `collate_records`, `systemone`); records carry `state`, optional `images`/`videos`, and `questions` with the same `type`/`instructions`/`criteria` fields [10][11].
- Licence: Apache-2.0, following the Qwen base models [10][11].
- Size: Clef 27B on Qwen3.8-27B; Clef-flash 9B on Qwen3.5-9B; both keep the vision encoder [10][11]. Architecture: a joint schema head on the backbone's final hidden states gives one logit per allowed option; softmax per question [10].
- Context: the blog and changelog say 64,000 tokens [8][9]; the model cards' default `max_length` is 16,384 [10][11]. Treat 64k as the hosted figure.
- Published results: released 1 October 2026 [8][9]. Cloudflare's ten-benchmark table has a Clef model ahead of Jev on seven (e.g. BANKING77 macro-F1 94.20 vs 79.74; CLINC150+OOS 97.43 vs 89.27 for Clef, but Clef-flash only 66.77). Median latency 209.3 ms (Clef) and 38.8 ms (Clef-flash) [8]. Workers AI price $0.240 (Clef) and $0.038 (Clef-flash) per million input tokens [12]. The card was tested with Torch 2.11 and Transformers 5.10.2 on a single H200, or SGLang's `dev-clef` image [10].
- Independent results: Decision Index 0.3.2 Full 53.08 for Clef (rank 45) and 47.61 for Clef-flash (rank 63); both score well on the public suite (61.71, 56.15) and fall away on new domains (41.88, 42.50) [32]. A third model, `clef-omni (30B-A3B)`, sits at 48.28 on the same board; not checked further today [32].

### AWS Strands Decider 2B

- Interface: Python package `strands-decider` with a CLI and an HTTP server. The server's request is `{state, questions: {id: {type, instructions, options: [...]}}}` and the response matches Jev's (`answers`, `noul`/`choice`/`score`, `probabilities`, `confidence`, `usage`, plus `latency_ms`) [14].
- Licence: Apache-2.0 (repo and model card) [14][15]. Training data: 246,678 rows from 25 public Hugging Face datasets, code and generated rows, with a per-source licence list; the teacher for v1 was Gemma-4-31B-it [14][15].
- Size: 1.9B. A LoRA adapter on Qwen3.5-2B-Base plus a roughly one-million-parameter pointer head that scores each option against the hidden state [13][14][15]. Context 4,096 tokens [15]. Gemma-4 variants from E2B to 26B-A4B are on the main branch [14].
- Published results: announced 1 October 2026 [13]; the recommended checkpoint `strands-decider-2B-qwen3.5-v1-2610` is dated 9 October [15]. On JevBench's 231 public tasks: 180 correct, Brier 0.280, ECE 0.072; median latency about 115 ms on an RTX 3090 and 153 ms on an M3 Pro MacBook [13][14]. The card says it is weak on long documents and that score and noul transfer poorly to new rubrics [15].
- Independent results: Decision Index 0.3.2 Full 21.34 (rank 129) [32].

### pplx-decider (Perplexity)

- Interface: `POST https://api.perplexity.ai/v1/decisions` with the System One body; 1 to 128 questions, up to 255 options, inputs under 262,144 tokens, 10 requests a second, $0.02 per million input tokens [16].
- Licence: Apache-2.0 [17].
- Size: 26.09B by safetensors total (the card rounds to 27B) on Qwen3.8-27B, with a BF16 [255, 5120] decision head in `readout.safetensors` [17][43]. Not gated: the repository downloads without agreeing to terms [43]. The open checkpoint's context is 8,192 tokens (rejects longer inputs); the hosted service advertises much more [16][17]. Needs a CUDA GPU with about 49 GB of VRAM and custom code; non-causal attention in full-attention layers [17].
- Published results: v1.1 lifts the Decision Index from 56.4 to 61.56 by lifting the causal mask and adding data [17]. The Hugging Face repository was created on 5 October 2026 and last changed on 12 October [43]; a 1 October launch appears only in secondary reports (NOT VERIFIED against a primary source today).
- Independent results: Decision Index 0.3.2 Full 62.75 (rank 6), the best score of any product in this brief, ahead of Jev 1.14 [32].

### Microsoft-Decision-1

- Interface: System One on Foundry at `<resource endpoint>/providers/microsoft/v1/systemone`, with `state` (text or JSON), `questions` of type `noul`, `choice` or `score`, and `criteria` [42]; also on OpenRouter [41]. No images [42]; 32,768-token context [19] (not stated on the Foundry how-to page read today).
- Licence and weights: hosted only; neither Microsoft page read today mentions weights or a licence [41][42]; no Hugging Face repository found [19][21].
- Size: 9B, post-trained from Qwen3.5-9B [18][19].
- Published results: announced 9 October 2026 on Microsoft's Command Line blog, by Achint Srivastava [41]; the Foundry how-to page is dated 7 October and was updated 9 October [42]. Microsoft's own claims: highest accuracy across 36 benchmarks and about 150,000 questions; 2.5× faster than H2O-Lightning-4B v1.1 and about 35× faster than GPT-6 Sol at P50; $0.042 per million input tokens, output free [41]. The figures "83.5% against Jev's 82.3%" and "median 85 ms" come only from secondary reports [18][19]; they were not visible in the primary post read today. No per-benchmark table is published anywhere found today [21][41][42]. The Foundry how-to itself advises an abstention option such as `cannot tell` and randomised option order [42], which is Bundle's `none` by another name.
- Independent results: not on the Decision Index [32].

### Laya (Convai Innovations)

- Interface: System One; `laya-serve` exposes the same `/v1/systemone` wire protocol, and the response adds a `routing` field naming the checkpoint used [23].
- Licence: Apache-2.0 [22][23].
- Size: three checkpoints: `laya` (ModernBERT-large, 421M, 512-token context, English), `laya-multilingual` (mmBERT-base, 322M, 1,024 tokens, 100+ languages) and `laya-typed-decisions` (421M, fine-tuned on one benchmark's training split) [22]. Encoder, not decoder: one forward pass [23]. An fp32 ONNX export exists (receptron/laya-onnx, MIT export code, Apache-2.0 weights); no int8 [24]; a TypeScript client and ONNX runtime path exist [23].
- Published results: single question 39.5 ms (English) and 32.8 ms (multilingual) on a T4; MASSIVE intent 0.783, XNLI 0.860. The card is frank that the base checkpoints are near chance on typed decisions zero-shot (0.362 against a 0.461 majority baseline), that it ships over-confident and needs temperature scaling, that `noul` can follow its option labels rather than the state (the card suggests a two-option `choice` instead), and that options get trimmed from about 20 short options at the default token budget, with accuracy falling at 50 or more; the server caps a question at 100 options [22][23]. Refitting one temperature per question type and option count moves mean ECE from 0.466 to 0.081 [22].
- Independent results: Decision Index 0.3.2 Full 4.43 (rank 158) [32]; S1MB has laya-multilingual at a Borda score of 24.14 [34].

### Liquid AI's d1

- Interface: System One (`state`, `questions`, `noul`/`choice`/`score`), hosted at $0.04 per million input tokens (the blog) or $0.02 (OpenRouter listing; NOT VERIFIED), with images as base64 [25]. The blog page read today is dated 5 October 2026 and adds vision; it refers to an experimental text-only release "last week", so late September 2026 (exact date NOT VERIFIED).
- Open weights: `d1-3B` (3.12B, from LFM2.5-VL-3B, 32,768 context) and `d1-omni-600M` (587M, from LFM2.5-Encoder-350M, text, vision and audio, 16,384 context), released 7 October 2026 [26][27][28]. Transformers with `trust_remote_code`; llama.cpp quantisations exist [27].
- Licence: LFM Open License v1.0, "LFM1.0" [27][28]; Hugging Face tags it `license:other` [43]. Commercial use by an entity with annual revenue of US$10 million or more is not licensed [29]. That fails Bundle's D12 (Apache-2.0 or MIT only), whatever else the licence allows.
- Published results: d1-3B Decision Index 0.2.1 48.57 ("best under 10B" at the time); 8 ms per question on an RTX 4090, 30 ms on an Apple M5 Pro [26][27]. d1-omni-600M 15.95 on the same index [28].
- Independent results: Decision Index 0.3.2 Full 38.90 for d1-3B (rank 93) and 9.09 for d1-omni-600M (rank 150) [32].

### Anthropic

Anthropic's current model list is Claude Fable 5.1, Opus 5.5, Sonnet 5.5 and Haiku 5.5, all "text and images → text" [30]. There is no decision endpoint or probability-returning product. Haiku 5.5 was released 7 October 2026 and is priced at $0.10 per million input and $0.50 per million output tokens for prompts up to 100,000 tokens ($0.50 and $2.50 above that) [31]. The relay's figures are exact.

### Other open models seen while checking (not in the brief, but relevant to Bundle)

- vLLM Semantic Router's Decision 3.0 family, Apache-2.0, not gated, six sizes from `d3-edge` (0.59B, Qwen3.5-0.8B base) to `d3` (26.09B, Qwen3.8-27B base) [37][38][43][44]. `d3-flash` is 8.39B on Qwen3.5-9B (the board calls it 9B) [43]. On the Decision Index 0.3.2: `d3` 66.26 (rank 1), `d3-flash` 55.79 (38), `d3-mini` (4B) 52.61 (46), `d3-nano` (2B) 38.86 (94), `d3-lite` (0.8B) 32.33 (109), `d3-edge` 20.24 (132) [32]. The `d3` card quotes 66.3 on the same board [44]. Context lengths are not on the cards read today (unknown).
- H2O-Lightning-4B, Apache-2.0, not gated, 4.66B by safetensors total on Qwen3.5-4B, 40,960 context, serves `/v1/systemone` through a vLLM 0.30.0 shim; its card reports Decision Index 0.3 public text 57.10 (two-way), JevBench 205/231 (88.7%) and ECE 0.017 on 1,877 validation images [39][43]. Not on the 0.3.2 board file read today, so its 57.10 is a public-suite figure, not a Full score, and is not comparable with the Full column below.
- Bekko System One (hotchpotch), 17M to 400M encoders on Ettin rerankers, with a 29 MB ONNX browser build for the 17M model. Decision Index 0.3.2 Full 15.24 (400M), 8.42 (68M), 2.93 (17M). Its licence "remains to be finalized", so Bundle cannot use it [35][36][32].
- LocalLLaMA's `typed-decisions` dataset, Apache-2.0, 1,600 rows over four workflows, labelled with probability distributions rather than single gold labels [40]. A useful pattern for Bundle's exam.

### Checking the relay's facts

| Relay says | Verdict |
|---|---|
| Jev is hosted-only with no published weights | Right [2][5]. |
| Clef (27B) and Clef-flash (9B) released 1 Oct under Apache-2.0, API-compatible with Jev | Right [8][9][10][11]. Nuance: context 64k hosted, 16,384 default in the open card; a third `clef-omni` exists. |
| Strands Decider 2B released the same day under Apache-2.0 | Right [13][14]. The current checkpoint is dated 9 Oct and is 1.9B [15]. |
| Anthropic sells no decision model; Haiku 5.5 released 7 Oct at $0.10/$0.50 up to 100k tokens | Right [30][31]. |

Nothing in the four facts is wrong. What the relay does not say, and should: on the one independent board that ranks them, Clef-flash is a middling comparator (47.61, rank 63) beaten by open Apache-2.0 models of similar or smaller size (d3-flash 55.79 at 8.4B; d3-mini 52.61 at 4B), and pplx-decider v1.1 (62.75) is the strongest open model in the brief; d3 (66.26) tops the whole board [32]. H2O-Lightning-4B's 57.10 is its own public-suite number and is not on the board [39]. Strands Decider 2B (21.34) is also beaten at its own size by d3-nano 2B (38.86) [32].

## Options compared

Decision Index Full score is the 0.3.2 board of 15 October 2026 (0 = chance, 100 = perfect; 20% public, 50% private same-skill, 30% private new-domain tests) [32][33].

| Model | Weights and licence | Size | Context | Interface | Maker's headline | Decision Index 0.3.2 Full (rank/168) | Use for Bundle |
|---|---|---|---|---|---|---|---|
| Jev 1.14 (TypeSafe) | Hosted only | unknown | 32k–64k | System One reference | 193.6× faster than LLMs | 61.53 (8) | Format reference; no paid API today |
| OpenAI Decisions API | Hosted only (GPT-6 Luna) | unknown | unknown | Own naming (`input`, `predicate`) | 10× faster than Responses | not listed | None (paid, no weights) |
| Clef | Apache-2.0, not gated | 27.4B | 64k / 16k | System One | 7 of 10 benchmarks over Jev | 53.08 (45) | Too big for Mac; Spark possible |
| Clef-flash | Apache-2.0, not gated | 9.4B | 64k / 16k | System One | 38.8 ms median | 47.61 (63) | D11 comparator, on the Spark |
| Strands Decider 2B | Apache-2.0, not gated, data and scripts open | 1.9B | 4k | System One-like (`options`) | JevBench 180/231, ECE 0.072 | 21.34 (129) | Runs on the Mac; a recipe to read |
| pplx-decider v1.1 | Apache-2.0, not gated | 26.1B | 8k open / 262k hosted | System One | Decision Index 61.56 | 62.75 (6) | Strongest open comparator in the brief, Spark only |
| Microsoft-Decision-1 | Hosted only, licence unpublished | 9B | 32k (secondary) | System One | Top of 36 benchmarks (no per-benchmark data) | not listed | None |
| Laya | Apache-2.0, not gated, fp32 ONNX exists | 322M–421M | 512–1,024 | System One | 32.8 ms on T4 | 4.43 (158) | Encoder recipe worth reading; weak zero-shot |
| d1-3B / d1-omni-600M | LFM1.0 ($10M revenue cap) | 3.1B / 587M | 32k / 16k | System One | 48.57 on index 0.2.1 | 38.90 (93) / 9.09 (150) | Excluded by D12 |
| Claude Haiku 5.5 | Hosted LLM | unknown | 1M | Messages API, text out | n/a | not listed | D11 frontier comparator, with approval |
| d3-flash / d3-mini / d3-edge (vLLM-SR) | Apache-2.0, not gated | 8.4B / 4B / 0.59B | unknown | System One | d3 card: 66.3 on index 0.3.2 | 55.79 (38) / 52.61 (46) / 20.24 (132) | Better open comparators than Clef-flash at equal or smaller size |
| H2O-Lightning-4B | Apache-2.0, not gated | 4.7B | 40,960 | System One via vLLM shim | Index 0.3 public text 57.10 (not a Full score) | not on board file | Fits the Spark easily |

## Recommendation

1. Keep Bundle's version 0 API as the native, primary form. It carries structure that the System One `choice` form flattens: each candidate's `kind`, `label`, `examples` or loose `text`, and the three-rule `action` and `target`. A bi-encoder student can use that structure (encode examples separately, compare against a bundle centroid); a flat description string cannot give it back.

2. Offer the System One form as a thin, deterministic adapter in both directions, in the shared TypeScript package and in `bundle_pipeline`, and expose it as a `/v1/systemone`-shaped function for anyone who already has a Jev client. It is lossless from Bundle's request to the System One request and from the System One answer to Bundle's probabilities. The mapping:

   Bundle request → System One request:
   - `model`: `"bundle-v0"` (the manifest's model id).
   - `state`: `{"chat": <chat>}`.
   - `questions`: one question, id `bundle`, `type: "choice"`, `instructions`: "Which existing bundle or loose chat does this new chat belong with? Choose none if it belongs with none of them."
   - `criteria`: one entry per candidate, keyed by the candidate's `id`. For `kind: "bundle"`: `"Bundle '<label>'. Earlier chats: <examples joined by '; '>"`. For `kind: "loose"`: `"Loose chat: <text>"`. Always append `"none": "None of these. The chat starts something new."`.
   - Reserve the id `none`: Bundle's schema must reject a candidate with that id.

   System One answer → Bundle response:
   - `probabilities` copied as is (the keys are the candidate ids plus `none`).
   - `action` and `target` come from Bundle's calibrated cut-offs, never from the model's `choice` or `confidence`; Bundle sets `confidence` to the top probability and documents that, since no vendor defines it.
   - `usage.output_tokens` is 0.

   Worked example, from the relay's own request: `criteria` becomes `{"b1": "Bundle 'Running'. Earlier chats: beginner half marathon plan; knee hurts after 10k", "c9": "Loose chat: why do cats knead blankets", "none": "None of these. The chat starts something new."}` and the answer `{"type": "choice", "choice": "b1", "confidence": 0.94, "probabilities": {"b1": 0.94, "c9": 0.01, "none": 0.05}}` maps straight back to the relay's response once the rules add `"action": "file", "target": "b1"`.

3. Use the adapter for the scoreboard. The same System One request runs Clef-flash, pplx-decider, Strands Decider, H2O-Lightning or d3 unchanged, and its `instructions` plus `criteria` text is the prompt for Haiku 5.5. Store exam items in both forms, so a third party can score Bundle's exam with any System One engine or with the decision-index kit.

4. Handle the 255-option cap. Jev, Clef and pplx-decider stop at 255 options and Laya degrades past about 20 [2][16][22]. Bundle's native API should accept any number of candidates; the adapter should send at most 254 plus `none`, choosing them by the baseline encoder's nearest candidates, and record that pre-selection in the response metadata.

5. Change D11's open comparator, or add to it. Clef-flash is fine to keep because the relay names it and it is Apache-2.0, but on the independent board it is behind d3-flash at the same size and behind d3-mini at 4B; pplx-decider v1.1 is the best open model in the brief, and d3 the best on the board. Run two open comparators on the Spark: Clef-flash and pplx-decider v1.1 (or d3-flash, or d3-mini if memory is short). All of Clef-flash, pplx-decider v1.1, d3-flash, d3-mini and H2O-Lightning-4B are Apache-2.0 and none is gated (checked against the Hugging Face API today [43]). None of these runs on the 24 GB Mac in BF16; whether community 4-bit builds of Clef-flash exist is unknown (not checked).

6. Do not adopt an existing open decision model as Bundle's student. The smallest Apache-2.0 ones (Laya 322M, d3-edge 0.59B) are 8 to 15 times over the 40 MB download budget even at int8, and the only browser-sized one (Bekko 17M, 29 MB) has no settled licence. Bundle's own small encoder student (R2) stays necessary.

## What doesn't work, or would change the plan

- Jev's `confidence` is undefined in public docs and the OpenAI community thread shows the `choice` form over-confident on a toy test. Bundle must calibrate its own cut-offs on practice data and ignore vendors' confidence fields; D6 is right to insist on that.
- `noul` is the wrong primitive for "does this chat belong here?": Laya's card documents a label-following bias and recommends a two-option `choice` [22]. Bundle should only ever ask one `choice` with `none`, never a `noul` per candidate.
- Clef-flash's own benchmark table shows the kind of failure Bundle must test for: it scores 66.77 macro-F1 on CLINC150 with out-of-scope, against Clef's 97.43 [8]. Out-of-scope detection, which is Bundle's `none`, is exactly where small decision models fall over. The exam's precision and recall for `none` (W6 metrics) matter more than accuracy.
- Open-weight contexts are shorter than hosted ones: Clef cards default to 16,384, pplx-decider's open checkpoint rejects inputs over 8,192, Strands stops at 4,096 [10][15][17]. A heavy user's candidate list with examples could exceed 8k tokens; the adapter's pre-selection (recommendation 4) also keeps requests inside comparators' limits.
- Microsoft-Decision-1 cannot be verified from a primary source today and publishes no per-benchmark scores [21]; OpenAI's and Microsoft's products are paid and hosted, so neither is a comparator Bundle can run without money and approval. Neither needs to be on the board.
- The relay calls these "general decision models" and compares Bundle against one. The independent boards show general skill and new-instruction generalisation are different things (S1MB [34]; Decision Index's new-domain split [32]). A general model fine-tuned on nothing like Bundle's task may still beat a tiny student zero-shot; if it does, that is a result to publish, not a reason to drop the student.
- The ranking evidence here leans on one board, the Decision Index, run by one person and regenerated often: Jev moved five places between 1.13 and 1.14 inside a month, and the 0.3.2 file is a 15 October snapshot [32][33]. Treat ranks as this week's picture, not a verdict, and re-pull the data file before D11 is fixed.
- Microsoft's own how-to for Decision-1 tells users to add an abstention option and to randomise option order because wording and order change the scores [42]. Bundle's adapter fixes option order by candidate id; the exam should include an order-shuffled run so the scoreboard shows how much comparators move.
- Strands Decider's repo is the one fully open recipe (data inventory, teacher Gemma-4-31B-it, LoRA plus pointer head, calibration on held-out short tasks) [14]. R2 and R3 should read it before fixing Bundle's method; it is closer to Bundle's constraints than anything else here.
- Liquid's d1 models are out under D12 because of LFM1.0's revenue cap [29]; note it in docs/research/licences.md so nobody picks them later.

## Sources

1. https://typesafe.ai/ (checked 16 Oct 2026)
2. https://docs.typesafe.ai/api (checked 16 Oct 2026)
3. https://docs.typesafe.ai/introduction (checked 16 Oct 2026)
4. https://developers.cloudflare.com/ai/models/typesafe/jev/ (checked 16 Oct 2026)
5. https://openrouter.ai/blog/insights/what-is-jev/ (checked 16 Oct 2026)
6. https://community.openai.com/t/decisions-api-is-now-available-in-public-beta/1403877 (checked 16 Oct 2026)
7. https://developers.openai.com/api/docs/guides/decisions (checked 16 Oct 2026)
8. https://blog.cloudflare.com/clef-decision-models (checked 16 Oct 2026)
9. https://developers.cloudflare.com/changelog/post/2026-10-01-clef-workers-ai/ (checked 16 Oct 2026)
10. https://huggingface.co/Cloudflare/clef (checked 16 Oct 2026)
11. https://huggingface.co/Cloudflare/clef-flash (checked 16 Oct 2026)
12. https://developers.cloudflare.com/workers-ai/platform/pricing/ (checked 16 Oct 2026)
13. https://strandsagents.com/blog/introducing-strands-decider/ (checked 16 Oct 2026)
14. https://github.com/strands-labs/strands-decider (checked 16 Oct 2026)
15. https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 (checked 16 Oct 2026)
16. https://docs.perplexity.ai/docs/decisions/quickstart (checked 16 Oct 2026)
17. https://huggingface.co/perplexity-ai/pplx-decider-v1.1-27b (checked 16 Oct 2026)
18. https://www.helpnetsecurity.com/2026/10/12/microsoft-decision-1-model/ (checked 16 Oct 2026; secondary)
19. https://www.eesel.ai/blog/microsoft-decision-1 (checked 16 Oct 2026; secondary)
20. https://www.logeshwaran.org/2026/10/microsoft-decision-1-model-foundry.html (checked 16 Oct 2026; secondary)
21. https://www.orcarouter.ai/blog/microsoft-decision-1-ga-foundry-no-published-benchmarks (checked 16 Oct 2026; secondary)
22. https://huggingface.co/convaiinnovations/laya (checked 16 Oct 2026)
23. https://github.com/NandhaKishorM/laya (checked 16 Oct 2026)
24. https://huggingface.co/receptron/laya-onnx (checked 16 Oct 2026)
25. https://www.liquid.ai/blog/d1-decision-model (checked 16 Oct 2026)
26. https://www.liquid.ai/blog/d1-open (checked 16 Oct 2026)
27. https://huggingface.co/LiquidAI/d1-3b (checked 16 Oct 2026)
28. https://huggingface.co/LiquidAI/d1-omni-600M (checked 16 Oct 2026)
29. https://huggingface.co/LiquidAI/d1-3b/blob/main/LICENSE (checked 16 Oct 2026)
30. https://platform.claude.com/docs/en/about-claude/models/overview (checked 16 Oct 2026)
31. https://platform.claude.com/docs/en/models/haiku-5-5/overview (checked 16 Oct 2026)
32. https://huggingface.co/spaces/multimodalart/jev-decision-index — data file https://huggingface.co/spaces/multimodalart/jev-decision-index/resolve/main/data/v03.json, labelled "Decision Index 0.3.2", generated 2026-10-15T14:44:30Z, 168 models, weights 0.2/0.5/0.3 (checked 16 Oct 2026)
33. https://github.com/apolinario/decision-index (checked 16 Oct 2026)
34. https://huggingface.co/blog/hotchpotch/system-one-mosaic-benchmark (checked 16 Oct 2026)
35. https://huggingface.co/hotchpotch/bekko-system-one-v0-400m (checked 16 Oct 2026)
36. https://huggingface.co/blog/hotchpotch/bekko-system-one-v0-release (checked 16 Oct 2026)
37. https://huggingface.co/vllm-sr/d3-edge (checked 16 Oct 2026)
38. https://www.orcarouter.ai/blog/decision-3-0-open-multimodal-decision-models (checked 16 Oct 2026; secondary)
39. https://huggingface.co/h2oai/h2o-lightning-4b (checked 16 Oct 2026)
40. https://huggingface.co/datasets/LocalLLaMA/typed-decisions (checked 16 Oct 2026)
41. https://commandline.microsoft.com/microsoft-decision-1-model-foundry/ (checked 16 Oct 2026; primary)
42. https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision (checked 16 Oct 2026; primary)
43. https://huggingface.co/api/models/<repo> for each model named above — `gated`, `private`, licence tag, `createdAt`, `safetensors.total` (checked 16 Oct 2026)
44. https://huggingface.co/vllm-sr/d3 (checked 16 Oct 2026)

Not readable today: https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-microsoft-decision-1-in-microsoft-foundry-for-decision-and-classific/4562742 (served only its title) and https://www.marktechpost.com/2026/10/09/microsoft-ai-releases-microsoft-decision-1-a-qwen3-5-9b-decision-scoring-model/ (HTTP 403). Sources 41 and 42 replace two entries that the first draft listed but never cited.

## Verification notes (skeptic)

Second pass on 16 October 2026 by the R1 skeptic. Twenty-two of the cited pages were reopened, plus the Hugging Face API for every open model and the Decision Index data file itself.

Confirmed exactly as written: Clef and Clef-flash cards (Apache-2.0, 27B and 9B, Qwen3.8-27B and Qwen3.5-9B, `max_length` 16,384, Torch 2.11, Transformers 5.10.2, H200, `lmsysorg/sglang:dev-clef`); Cloudflare's blog (1 October, 64k, every BANKING77 and CLINC150 figure, 7 of 10, latencies 524.1/209.3/38.8 ms); Workers AI prices ($0.240 and $0.038); the Jev partner listing (32,000 tokens, $0.042, output $0.00); Strands card and repo (Apache-2.0, 1.9B, ~1M pointer head, Qwen3.5-2B-Base, 4,096, Gemma-4-31B-it teacher, 9 October, 180/231, Brier 0.280, ECE 0.072, 246,678 rows from 25 datasets, `options` array); pplx-decider card (Apache-2.0, [255, 5120] head, 8,192, ~49 GiB, 56.4 to 61.56) and Perplexity docs ($0.02, 1–128 questions, 1–255 options, under 262,144 tokens, 10 requests a second); Laya card (Apache-2.0, 421M/322M, 512/1,024, 39.5 and 32.8 ms, 0.783, 0.860, 0.362 against 0.461) and `laya-onnx` (MIT export, Apache-2.0 weights, fp32 only); d1-3B card and licence (3.12B, LFM2.5-VL-3B, 32,768, LFM1.0, US$10 million clause, 48.57 on 0.2.1, 8 and 30 ms) and both Liquid posts (5 and 7 October, $0.04 hosted); Haiku 5.5 (7 October, $0.10/$0.50 up to 100,000 tokens, $0.50/$2.50 above, 1M context); OpenAI Decisions docs and thread (`/v1/decisions`, `gpt-6-luna`, `predicate`/`choice`/`score`, refusal type, $0.10, output free, first post 6 October, the 98%-for-70% report); H2O-Lightning card (Apache-2.0, Qwen3.5-4B, 40,960, 57.10, 205/231, ECE 0.017); Bekko card (sizes, Ettin rerankers, 29 MB ONNX for 17M, licence "remains to be finalized"); S1MB post (137 benchmarks, 23 models, Jev 1.13 first, 96.27, laya-multilingual 24.14, Yuichi Tateno); OpenRouter explainer (no weights or paper, 15 September early access); `typed-decisions` (Apache-2.0, 1,600 rows, four workflow configs plus `all`). Every Decision Index score and rank quoted in the Findings and the table matches the 0.3.2 data file, including the public and new-domain splits for Clef and Clef-flash; H2O-Lightning, Microsoft and OpenAI are indeed absent from it.

Changed:
1. Jev: "238× cheaper" was wrong. TypeSafe's page says 444.6× cheaper on System One workflows and 238× lower input price than Claude Fable 5.1. "Version 1.13 in late September" became the dated 17 September snapshot.
2. pplx-decider: added that it is not gated (the API reports `gated: false`); gave the safetensors total 26.09B against the card's 27B; replaced the unverified 1 October launch with the repository's creation date, 5 October.
3. Microsoft-Decision-1: the first draft said no primary source could be read. Two exist and were read: the Command Line post (9 October, Achint Srivastava, 36 benchmarks, ~150,000 questions, 2.5× H2O-Lightning-4B v1.1, 35× GPT-6 Sol, $0.042) and the Foundry how-to (endpoint path, question types, `criteria`, text or JSON). The "83.5% vs 82.3%" and "85 ms" figures were not in the primary post, so they are now marked as secondary only, and the table's headline for Microsoft was changed to match.
4. Laya: "accuracy drops past about 20 options" was a conflation. The repo says trimming begins around 20 short options at the default token budget; the card says accuracy falls at 50 or more; the server caps a question at 100. Added the ECE 0.466 to 0.081 calibration figure and the card's exact `noul` advice.
5. d1: removed "Apache-2.0-like" (the licence text does not say so; Hugging Face tags it `other`); dated the earlier text-only release to "last week" relative to the 5 October post.
6. d3 family: d3-flash is 8.39B by safetensors (the board says 9B); d3 is 26.09B; added d3-mini (4B, 52.61), d3-nano (2B, 38.86) and d3-lite; the table's "Index 65.5 for d3" was unsourced and now reads 66.3 from the d3 card. Context lengths marked unknown.
7. H2O-Lightning-4B: its 57.10 is a public-suite score, not a Full score, so it was removed from the direct comparison with Clef-flash in the relay-check paragraph and the table says so.
8. Strands latency: "M3 MacBook" is "M3 Pro MacBook" in the repo.
9. Sources 41 and 42 (Hanno-Labs DecisionBench, Bekko results dataset) were never cited and were replaced by the two Microsoft primaries; 43 (Hugging Face API) and 44 (d3 card) added; the direct URL of the Decision Index data file added to 32.
10. Added two bullets to "What doesn't work": the board is one person's weekly snapshot, and Microsoft's own docs call for abstention options and order-shuffling.
11. Recommendation 5 now names the licence and gating status of every comparator it proposes; the unchecked claim that 4-bit MLX builds of Clef-flash exist is now "unknown".

Not changed, still open: the Microsoft techcommunity post and the MarkTechPost article remain unread; the 1 October launch date for pplx-decider has no primary source; Jev's parameter count and OpenAI's model size remain unknown; d3 context lengths are unknown. Quotes in the file are all under 15 words; the only longer quoted strings are Bundle's own adapter text. No gated model is recommended anywhere in the note.
