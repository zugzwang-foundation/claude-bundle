---
# DRAFT written in BDL-3, not published (D13). Placeholders are in <angle brackets>.
license: apache-2.0
base_model: sentence-transformers/all-MiniLM-L6-v2
# NOT VERIFIED as final: R2 says mxbai-embed-xsmall-v1 may become the primary base if the
# chats run longer than 256 word pieces; the sealed exam decides (docs/research/student-and-method.md).
library_name: transformers.js
# library_name is a single value in the Hub's metadata (https://huggingface.co/docs/hub/model-cards, checked 16 Oct 2026),
# and "transformers.js" is the value the base model's Transformers.js mirror carries
# (https://huggingface.co/api/models/Xenova/all-MiniLM-L6-v2, checked 16 Oct 2026);
# sentence-transformers, which trains and saves the student, is carried as a tag so both show.
pipeline_tag: feature-extraction
language:
  - en
tags:
  - sentence-transformers
  - transformers.js
  - onnx
  - bert
  - feature-extraction
  - sentence-similarity
  - decision-model
  - chat-organisation
  - synthetic-data
datasets:
  - <organisation>/<dataset-name>
# model-index: to be filled from the latest run in scoreboard/runs/ before publishing.
---

# Model card for <public name> student v<N>

> DRAFT. "Bundle" is a working name; the public name is not settled (D13). Nothing here is published. Every value in angle brackets is not yet known, and every number marked "to be filled from the latest run" is copied from `scoreboard/runs/<run-id>.json` for the run that ships, never typed by hand.

## Model summary

<public name> is a small open decision model that sorts a person's AI chats into bundles. Given one new chat and the person's existing bundles and loose chats, it returns a probability for each of them plus one for "none of these". It never writes text, and it is small enough to run in a web browser.

What is released under this card:

| file | what it is |
|---|---|
| `onnx/model.onnx` | the student encoder, fp32, exported with opset 14 and dynamic batch and sequence axes |
| `onnx/model_quantized.onnx` | the same encoder at int8 (dynamic quantisation, per-channel weights), the file the browser loads |
| `config.json`, `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json` | the layout Transformers.js expects for a local model id |
| `manifest.json` | `{id, name, dtype, size_bytes, base_model, run_id}`: which run this export came from |
| `calibration.json` | `model`, `temperature`, `none_score`, `file_cutoff`, `suggest_cutoff`, `practice_size` and a `source` line saying how they were fitted on the practice split |
| `export_report.json` | PyTorch-versus-ONNX parity on the fixture texts, sizes and tool versions |
| `LICENSE`, `NOTICE` | the Apache-2.0 text, and the base model's name, repository and licence, so the upstream notice travels with the export (docs/research/licences.md, checked 16 Oct 2026) |

The encoder is a fine-tune of `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0, 22.7M parameters, 384 dimensions, English, input truncated at 256 word pieces; docs/research/student-and-method.md, checked 16 Oct 2026). The base's own int8 ONNX file is 23 MB; the student's export measured 23.0 MB at int8 and 90.4 MB at fp32 on the version-0 pipeline (pipeline/README.md, W3). NOT VERIFIED for the shipping student: to be filled from the latest run.

The probabilities come from the encoder plus a few lines of fixed maths, identical in Python (`pipeline/src/bundle_pipeline/sorter.py`) and TypeScript (`web/src/sorter/`), described under "How it was trained". The encoder on its own is a sentence embedder; the decision model is the encoder, the maths and `calibration.json` together.

Developed by: <organisation>. Model type: BERT-family sentence encoder (6 layers) with a calibrated similarity head. Language: English. Licence: Apache-2.0. Fine-tuned from: `sentence-transformers/all-MiniLM-L6-v2` (NOT VERIFIED as final, see the front matter).

Sources: repository <repository URL>; specification `docs/SPEC.md`; architecture `docs/ARCHITECTURE.md`; decisions `docs/DECISIONS.md`; research notes `docs/research/`.

## Intended use

### Direct use: which bundle, or none

One question, version 0 of the decision API (docs/ARCHITECTURE.md, section 2). Request:

```json
{"chat": "banana calories after my long run",
 "candidates": [
   {"id": "b1", "kind": "bundle", "label": "Running", "examples": ["beginner half marathon plan", "knee hurts after 10k"]},
   {"id": "c9", "kind": "loose", "text": "why do cats knead blankets"}]}
```

Response:

```json
{"probabilities": {"b1": 0.94, "c9": 0.01, "none": 0.05}, "action": "file", "target": "b1"}
```

- A candidate of kind `bundle` has a label and up to eight recent example chats. A candidate of kind `loose` is one chat that sits in no bundle yet.
- Choosing a loose chat means "start a new bundle with it".
- `none` means the chat belongs with nothing the person has, so it stays loose on its own.

The three rules (D6) turn the probabilities into an action:

| action | when |
|---|---|
| `file` | the top probability belongs to a candidate and is at least the file cut-off |
| `suggest` | the top probability belongs to a candidate and is at least the suggest cut-off |
| `leave` | otherwise, including every case where the top probability belongs to `none` |

The cut-offs are not chosen by hand. They are fitted on the practice split so that decisions at or above the file cut-off are right at least 95% of the time and decisions at or above the suggest cut-off at least 80% of the time (D6), then published with every scoreboard run. Values for this release, to be filled from the latest run:

| parameter | value | meaning |
|---|---|---|
| `temperature` | <temperature> | divides the cosine scores before the softmax |
| `none_score` | <none_score> | the constant score given to "none" |
| `file_cutoff` | <file_cutoff> | lowest top probability that files automatically |
| `suggest_cutoff` | <suggest_cutoff> | lowest top probability that suggests |

A stated 90% should be right about nine times in ten. Whether it is, on the sealed exam, is in the evaluation section below; the honesty of the percentages is measured, not assumed.

### Downstream use

- A chat platform that wants to offer automatic organisation to every user, running the model on the user's device so chats never leave it (D5).
- Researchers who want a small open baseline, and an honest benchmark, for "which group does this short text belong to, or none".
- The demo website in this repository, which runs the int8 export in a Web Worker through Transformers.js, trying WebGPU and falling back to WASM (docs/ARCHITECTURE.md; `web/src/sorter/worker.ts`, W5). R4 measured the int8 file slower on WebGPU than on WASM and recommends WASM everywhere (docs/research/browser-and-web.md, checked 16 Oct 2026); which the site ships is to be settled.

### How to get started

The browser pattern is the one the base model's Transformers.js mirror documents: a `feature-extraction` pipeline with `pooling: 'mean'` and `normalize: true` (https://huggingface.co/Xenova/all-MiniLM-L6-v2, checked 16 Oct 2026). Load the files from your own host, not the Hub: set `env.allowLocalModels = true` (browsers default it to false), `env.allowRemoteModels = false`, and point `env.localModelPath` at the files (https://huggingface.co/docs/transformers.js/custom_usage, checked 16 Oct 2026; docs/research/browser-and-web.md, checked 16 Oct 2026). Then apply the maths in `web/src/sorter/scoring.ts` and the rules in `web/src/sorter/rules.ts` with the values in `calibration.json`. A worked snippet is to be filled once the site's sorter is merged (W5); NOT VERIFIED against the released files.

## Out-of-scope use

- Writing text of any kind. The model returns probabilities only.
- Sorting anything other than short English chat openers into a person's own bundles. It has not been trained or tested on long documents, e-mail, code, other languages, or shared or multi-user collections.
- Deciding anything about a person. The model knows nothing about who the person is; it compares texts. Using it to infer traits, interests for advertising, or anything about a real individual is outside its purpose and against the project's privacy decisions (D2).
- Running on a server to process users' chats centrally. The design point is on-device; a central deployment would need its own privacy analysis that this card does not provide.
- Treating the probabilities as calibrated outside the conditions they were calibrated under (English chat openers, candidate sets of the size the teacher produced). See the limitations.

## How it was trained

### The loop

Every student comes out of one loop (docs/ARCHITECTURE.md, sections 1 and 5; D3, D7):

1. A teacher, an open-licensed instruct model that the project runs itself, writes invented people, their lives (three to five threads that will become bundles, plus loose interests) and their chats, each chat labelled with the thread it belongs to or with none, and with one of eight difficulty labels.
2. The output is validated, deduplicated and split **by person** into lessons (80%), practice (10%) and a sealed exam (10%). No person appears in two splits. The exam file's SHA-256 is recorded, and the exam is never read during training or calibration.
3. The student is fine-tuned from the base encoder on the lessons split only.
4. Calibration on the practice split fixes the temperature, the "none" score and the two cut-offs.
5. The student sits the sealed exam. The result is written to `scoreboard/runs/<run-id>.json` and published, whether or not it ships.
6. The student ships only if it beats the previous release on the exam (D7). Otherwise the site keeps the previous model and the board says so.

### Training data

Synthetic lessons only. The dataset card at `<organisation>/<dataset-name>` describes the teacher, the prompts, the difficulty mix and the splits. In short: no real person's chats, no text copied from the web, no visitor data from the demo site (D2, D3). The demo website's own chat library is written separately and is never used for lessons or exams (D4).

Teacher for the version-0 toy run on a Mac: `Qwen3-4B-Instruct-2507` (Apache-2.0, not gated) as the `unsloth` Q4_K_M GGUF conversion (Apache-2.0 tag, linking Qwen's licence) behind `llama-server` (docs/research/licences.md, checked 16 Oct 2026). Teacher recommended for the full run: `Qwen3.6-35B-A3B` (Apache-2.0, not gated), with `gemma-4-26B-A4B-it` (Apache-2.0, not gated) writing one person in five so the student does not learn one model's habits (docs/research/teacher-and-data.md, checked 16 Oct 2026). Which teacher wrote the lessons for this release: <teacher model and hash, from the dataset card>. Prompt version: <prompt_version; `v0.2` at the end of BDL-3>.

### Training procedure

Version-0 recipe, as implemented in `pipeline/src/bundle_pipeline/train.py` (W3) and recommended by R2 (docs/research/student-and-method.md, checked 16 Oct 2026):

- Pairs: (the new chat, one text of the bundle or loose chat it belongs to), drawn from the lessons split's decision examples. Chats whose answer is "none" supply no pair.
- Loss: `MultipleNegativesRankingLoss` with in-batch negatives, scale 20; a batch never holds two pairs with the same (person, answer), so a bundle-mate is never a false negative within a batch.
- Optimiser: AdamW, learning rate 2e-5, weight decay 0.01, 10% linear warm-up then linear decay, gradient clipping at 1.0, batch size 32, one epoch, fixed seed.
- Sequence length: 128 word pieces during training and in the export parity check (`train.py` and `export.py` defaults, W3), half the base encoder's 256.
- Saved with `SentenceTransformer.save`, so the checkpoint loads in sentence-transformers as well as through the ONNX export.

Values for the shipping student (epochs, pairs, loss curve, seed) are to be filled from its `train_meta.json`. R2 also proposes a small learned head over the candidate scores (top score, margin, number of candidates) for the "none" logit in place of a constant score; version 0 uses the constant, and the head is a planned refinement.

### The maths after the encoder

Identical in Python and TypeScript (docs/ARCHITECTURE.md, section 2):

1. Embed each text: mean pooling over tokens, then L2 normalisation.
2. A bundle's vector is the normalised mean of its examples' vectors. A loose chat's vector is its own.
3. Each candidate's score is the cosine similarity between the chat's vector and the candidate's vector. `none` gets the constant `none_score`.
4. Probabilities are `softmax(scores / temperature)`.
5. The three rules give the action.

### Calibration

On the practice split only, never on the exam: coordinate descent over temperature and `none_score` minimising the mean negative log-likelihood of the right answer; then `file_cutoff` is the smallest observed top probability at or above which precision is at least 0.95 (with a minimum of five decisions), and `suggest_cutoff` likewise for 0.80, never above `file_cutoff`. If no threshold qualifies the cut-off is 1.0 and the calibration file says so (`pipeline/src/bundle_pipeline/calibrate.py`, W3). R2 chose temperature scaling alone for version 0 because the toy practice split is far too small for isotonic or conformal methods (docs/research/student-and-method.md, checked 16 Oct 2026).

### Export

`torch.onnx.export` (TorchScript path, opset 14) to fp32, then `onnxruntime.quantization.quantize_dynamic` with per-channel int8 weights, written in the Transformers.js layout. Parity is checked on 32 fixture texts: fp32 ONNX against PyTorch, and int8 against fp32, as minimum cosine similarity. The version-0 pipeline's fixture run gave 0.99999994 for fp32 and 0.9944 for int8 per-channel (pipeline/README.md, W3); the architecture's 0.999 target (docs/ARCHITECTURE.md, section 5) is met by fp32 and not by any int8 variant, and R2 says the int8 gap should be judged by its effect on exam accuracy rather than used as a gate. Values for this release: to be filled from `export_report.json`.

Compute: the toy run trained on a Mac with Apple silicon (CPU or MPS); the full runs are planned for one NVIDIA DGX Spark (D10). Hardware and wall-clock for the shipping student: <to be filled>.

## Evaluation

### Testing data

The sealed exam split: 10% of the invented people, chosen deterministically, hashed, and never read by any training or calibration step. The exam's SHA-256 is in every run file (`exam_hash`) and in the dataset card. The exam rows are not published while that exam is in use; see the dataset card for the policy on retired exams.

### Metrics

As defined in `pipeline/src/bundle_pipeline/exam.py` (W3), and quoted by the scoreboard and the site:

| key | meaning |
|---|---|
| `accuracy` | share of examples whose prediction (argmax including "none") equals the answer |
| `macro_f1` | unweighted mean of F1 over the three answer classes bundle, loose and none, where a prediction counts for a class only when it names the exact right target (a wrong bundle is a false positive, not a hit) |
| `none_precision`, `none_recall` | precision and recall of predicting "none" |
| `ece` | expected calibration error of the chosen class, 10 equal-width bins |
| `brier` | mean of (p − hit)² for the chosen class |
| `file_precision`, `file_coverage` | among decisions at or above the file cut-off: share that are right, and their share of all examples |
| `suggest_precision`, `suggest_coverage` | the same at or above the suggest cut-off (this band includes the filed ones; it is the band the calibration searched) |
| `latency_ms_per_decision` | median wall-clock for one decision on the exam machine: embedding one chat plus the maths, candidates already embedded; it moves with the machine's load |
| `size_mb` | weights on disk in MB (10⁶ bytes); in the version-0 pipeline this is the checkpoint, not the int8 export (pipeline/README.md, W3) |

### Results

To be filled from the latest run, `scoreboard/runs/<run-id>.json`. Every run is labelled with its scale; the BDL-3 runs are labelled "toy scale", and R2 warns that a 95% cut-off cannot be set with confidence on a practice split of about 144 chats (docs/research/student-and-method.md, checked 16 Oct 2026). Do not copy toy-scale numbers into a published card as if they were the release's.

| sorter | accuracy | macro-F1 | none P / R | ECE | Brier | file P / coverage | suggest P / coverage | ms per decision | size MB |
|---|---|---|---|---|---|---|---|---|---|
| B0 always leave | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> | 0 |
| B1 base encoder, untrained | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> |
| B2 this student | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> |
| previous release | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> |
| open decision model (D11) | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> |
| frontier small model (D11) | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> | <…> |

Run id: <run-id>. Exam hash: <exam sha256>. Label: <toy scale | full scale>. Did B2 beat B1 and the previous release: <yes/no, from the run's notes>.

### Comparators

Decided in D11: a no-training baseline (B1, the base encoder as it is), the previous student, an open general decision model (Clef-flash, Apache-2.0), and a frontier small model reached over a paid API, checked weekly. The frontier model needs a paid key and the founder's approval, is never part of the product, its answers are never kept as data (its provider's terms forbid training on them; docs/research/licences.md, checked 16 Oct 2026), and its presence on the board implies no affiliation with or endorsement by its provider. The scoreboard history lives in `scoreboard/runs/` and is published in full, including runs that did not ship (D7).

## Limitations and biases

- **English only.** The base encoder and the teacher prompts are English. R2 found no multilingual transformer encoder that fits the 40 MB download budget; the only in-budget path is a truncated static model of untested quality (docs/research/student-and-method.md, checked 16 Oct 2026). Chats in other languages will get low, uninformative probabilities.
- **Short texts only.** The model sees a chat's opening message, not the conversation; the base truncates input at 256 word pieces and the version-0 training and parity check use 128. Long or multi-turn openers are judged by their start.
- **Synthetic data.** Every lesson was written by a teacher model about an invented person. The student inherits the teacher's idea of what people ask, how they type, and which topics overlap; R3 recommends a second teacher for one person in five to dilute this, and a diversity report per run (docs/research/teacher-and-data.md, checked 16 Oct 2026). Real sidebars will differ in ways the exam cannot see.
- **Candidate sets.** The invented people have three to five threads and a handful of loose chats; a real sidebar can hold hundreds. How the probabilities behave with many candidates has not been measured.
- **Calibration is conditional.** The cut-offs hold for the distribution they were fitted on. A platform with different users should re-calibrate on its own practice data before trusting the 95% and 80% targets.
- **Toy-scale caveats.** While the board is labelled "toy scale", none of its numbers, and in particular none of its cut-offs, should decide anything (R2).
- **int8 parity.** The browser file is int8 and does not reproduce the fp32 embeddings to 0.999 cosine on this stack; the effect on exam accuracy is reported per run rather than hidden.
- **Persona bias.** If the full run seeds personas from a public persona dataset (R3 suggests NVIDIA's Nemotron-Personas, CC BY 4.0, built to one country's census distributions; docs/research/teacher-and-data.md and docs/research/licences.md, checked 16 Oct 2026), the invented people will follow that country's distribution and that dataset's gaps. The dataset card says which seeds were used.
- **Open questions.** What `target` holds when the action is `leave`, and whether a Jev-compatible form of the question is also offered, are open (docs/ARCHITECTURE.md, section 6).

Recommendations: use the three actions, not raw probabilities; keep humans able to undo a filing; re-calibrate for your own population; and read the scoreboard run before trusting any number in this card.

## Privacy

- The model was never trained on real chats, on anyone's exported history, or on anything a visitor to the demo site did (D2, D3). The demo site stores nothing about visitors: no chats, quiz answers, accounts, cookies, analytics or browser storage (docs/ARCHITECTURE.md, section 4).
- The lessons contain no real people. Personas are invented; the validation step rejects real names and brands where it can, and the dataset card lists what is and is not in the data.
- The model runs on the user's device. It makes no network request of its own; the only download is the model file itself.
- The model has no memory and keeps no state between decisions.

## Environmental impact

Not measured. To be filled for the shipping run with hardware, hours and an estimate, or left as "not measured". The toy run used a laptop for minutes.

## Licence

- Weights, exports and `calibration.json`: Apache License 2.0 (D12; `LICENSE` in the repository).
- Base model: `sentence-transformers/all-MiniLM-L6-v2`, Apache-2.0 (https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2, checked 16 Oct 2026).
- Training data: the dataset under CC BY 4.0, written by teacher models whose licences place no condition on training with their outputs: the Qwen3 models and Gemma 4 are Apache-2.0 (docs/research/teacher-and-data.md and docs/research/licences.md, checked 16 Oct 2026). One loose end: Google's site links a prohibited-use policy beside Gemma 4's Apache text; the Apache text does not incorporate it, so Gemma 4 is kept as a secondary teacher and the reasoning is recorded (docs/research/licences.md). Teachers whose terms pass through to derived models (Gemma 3, Llama) were excluded for that reason.
- Every licence named here was checked on 16 Oct 2026 (docs/research/licences.md) and is re-checked against its source on the day of publishing, with the check recorded there.

## Citation

To be filled when the public name and the repository exist.

```bibtex
@software{<key>,
  title   = {<public name>: a small open decision model that sorts AI chats into bundles},
  author  = {<organisation>},
  year    = {<year>},
  url     = {<repository URL>},
  license = {Apache-2.0},
  note    = {Student v<N>, run <run-id>, exam <exam sha256>}
}
```

## Model card authors and contact

Drafted in BDL-3 by Claude Code from the specification, architecture, decisions and research notes in the repository; to be reviewed by the founder before publishing. Contact: <to be filled>.

An independent open-source project, not affiliated with any AI company. "Bundle" is a working name.
