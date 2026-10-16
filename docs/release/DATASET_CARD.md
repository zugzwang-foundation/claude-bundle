---
# DRAFT written in BDL-3, not published (D13). Placeholders are in <angle brackets>.
license: cc-by-4.0
pretty_name: <public name> invented chats
language:
  - en
task_categories:
  - feature-extraction
  - sentence-similarity
  - text-classification
annotations_creators:
  - machine-generated
language_creators:
  - machine-generated
size_categories:
  - <n<1K | 1K<n<10K | 10K<n<100K | 100K<n<1M, from the published row count>
tags:
  - synthetic
  - chat-organisation
  - decision-model
  - bundles
# configs: the syntax follows the Hub's manual configuration page (config_name, data_files, split, path;
# https://huggingface.co/docs/hub/datasets-manual-configuration, checked 16 Oct 2026). Whether the Dataset
# Viewer accepts split names other than train, validation and test is NOT VERIFIED; check before publishing.
configs:
  - config_name: people
    data_files:
      - split: lessons
        path: people/lessons.jsonl
      - split: practice
        path: people/practice.jsonl
  - config_name: decisions
    data_files:
      - split: lessons
        path: decisions/lessons.jsonl
      - split: practice
        path: decisions/practice.jsonl
---

# Dataset card for <public name> invented chats

> DRAFT. "Bundle" is a working name; the public name is not settled (D13). Nothing here is published. Values in angle brackets are not yet known; counts marked "to be filled" come from the pipeline's own reports for the release that ships.

## Dataset details

### Dataset description

Invented people and the AI chats they might have opened over about nine months, written by an open-licensed teacher model, with each chat labelled with the thread it belongs to or with none. From these, one decision example per chat: the new chat, the person's bundles and loose chats at that moment, and the right answer. The dataset exists to train and examine a small open decision model that sorts a person's AI chats into bundles (docs/SPEC.md), and to let anyone reproduce that model.

- Curated by: <organisation>.
- Language: English.
- Licence: CC BY 4.0 (D12).
- Rows: people <count>, chats <count>, decision examples <count>, to be filled from `validated/report.json`, `splits/split.json` and the `tasks` summary of the shipping run.

### Dataset sources

- Repository: <repository URL>, folder `pipeline/`, package `bundle_pipeline`.
- Specification and architecture: `docs/SPEC.md`, `docs/ARCHITECTURE.md`.
- Research behind the recipe: `docs/research/teacher-and-data.md` (R3), `docs/research/student-and-method.md` (R2).

## Uses

### Direct use

- Training and calibrating a model that answers "which bundle, or none" for short English chat openers.
- Benchmarking such models: the practice split for development, the sealed exam (by hash, see below) for the published scoreboard.
- Studying synthetic-data practice: the difficulty labels, the per-person structure and the deduplication report are all in the data.

### Out-of-scope use

- Anything that treats the people as real. They are inventions of a language model; nothing in the data describes a living person.
- Training a model to generate chat text. The data holds opening messages only, written by a teacher model; it is not a corpus of conversations.
- Evaluating a model on the sealed exam rows while that exam is live. The rows are withheld on purpose; see "Splits".

## Dataset structure

### Splits

| split | share of people | published | used for |
|---|---|---|---|
| `lessons` | 80% | yes | training the student |
| `practice` | 10% | yes | calibration and development; never training |
| `exam` | 10% | **hash only** while live | the sealed exam that decides releases (D7) |

The split is by person and deterministic: every person is ranked by SHA-256 of their id plus a salt, the first 80% of the ranking are lessons, the next 10% practice and the last 10% the exam, with at least one person in each split whenever there are three or more. No person appears in two splits, so a chat in the exam never shares a thread, a persona or a life with a chat in the lessons (`pipeline/src/bundle_pipeline/split.py`, W3; D7).

The exam is sealed. `splits/exam.sha256` records the hash of the exam file when it is first written; a later run that would change the exam refuses to write anything unless forced, and the exam runner checks the hash before it sits the exam. The same hash appears as `exam_hash` in every `scoreboard/runs/<run-id>.json`, so a published result can be tied to the exact exam it was sat on. The exam rows are not read by any person or model during training or calibration; thresholds are set on practice, never on exam (docs/research/teacher-and-data.md, recipe step 8, checked 16 Oct 2026).

Exam hash for this release: `<exam sha256>`. Salt: `<salt>`. Policy for retired exams: R3 recommends regenerating the exam with a new seed for each major version and keeping the old one to track the gap between public and sealed scores; whether a retired exam's rows are then published is <to decide>.

### Fields

The data contract is `pipeline/src/bundle_pipeline/schema.py` (pydantic v2); field names follow the architecture word for word and do not change without a decision in `docs/DECISIONS.md`.

**`people/*.jsonl`: one `Person` per line.**

| field | type | meaning |
|---|---|---|
| `id` | string | `p<seed>-<index>`; unique across the dataset |
| `persona` | string | one paragraph: who they are; never a real person |
| `interests` | list of strings | three to six interests |
| `threads` | list of `Thread` | the bundles-to-be |
| `chats` | list of `Chat` | in day order |
| `teacher` | object | `model`, `seed`, `prompt_version` of the teacher that wrote this person |

`Thread`: `id` (string), `label` (a short bundle name), `description` (one line).

`Chat`: `id` (string), `thread_id` (string, or null for a loose chat that belongs to no thread), `day` (integer ≥ 0, days since the person's first chat), `text` (the opening message the person typed), `difficulty` (one of `plain`, `overlap`, `vague`, `nowhere`, `long_gap`, `typos`, `very_short`, `new_thread`).

**`decisions/*.jsonl`: one `DecisionExample` per line**, built from the people by `pipeline/src/bundle_pipeline/tasks.py`.

| field | type | meaning |
|---|---|---|
| `id` | string | `<person_id>:<chat_id>` |
| `person_id`, `chat_id` | string | back-references |
| `chat` | string | the new chat's text |
| `candidates` | list of `Candidate` | the person's bundles and loose chats at that moment |
| `answer` | string | `b:<thread_id>` (file into that bundle), `c:<chat_id>` (start a bundle with that loose chat) or `none` |
| `difficulty` | string | copied from the chat |
| `day` | integer | copied from the chat |

`Candidate`: `id` (`b:<thread_id>` for bundles, `c:<chat_id>` for loose chats), `kind` (`bundle` or `loose`), `label` (bundles only), `examples` (bundles only: up to eight most recent texts), `text` (loose only).

How the examples are built: walk a person's chats in day order. A bundle exists only once its thread has two or more earlier chats; a thread's first chat is a loose chat until a second one arrives. For each chat the candidates are every current bundle and every current loose chat; the answer is the bundle if the chat's thread already has one, the loose chat if the thread has exactly one earlier chat, and `none` if the chat has no thread or is the first of its thread. State is updated after the example is recorded.

The decision API that consumes these examples, and the response shape (`probabilities`, `action`, `target`), are in `docs/ARCHITECTURE.md`, section 2.

### An example (invented, abridged)

```json
{"id": "p3-017:c04", "person_id": "p3-017", "chat_id": "c04",
 "chat": "banana calories after my long run",
 "candidates": [
   {"id": "b:t1", "kind": "bundle", "label": "Running", "examples": ["beginner half marathon plan", "knee hurts after 10k"]},
   {"id": "c:c03", "kind": "loose", "text": "why do cats knead blankets"}],
 "answer": "b:t1", "difficulty": "overlap", "day": 61}
```

## Dataset creation

### Curation rationale

The product needs a model that learns the task without ever seeing a real person's chats, and a benchmark that anyone can reproduce and nobody can overfit to in secret (D3, D7). Writing the data with an open-licensed teacher the project runs itself gives both: no privacy or copyright exposure, a recipe that can be re-run, and a sealed exam whose hash is public while its rows are not.

### Source data

#### Who wrote it

A teacher model, not people. Every chat, persona and thread label was written by an instruct model running on the project's own hardware, reached over an OpenAI-compatible API so the same code drives a laptop and the training machine (D9).

| run | teacher | licence | serving |
|---|---|---|---|
| version-0 toy run, Mac | `Qwen3-4B-Instruct-2507` at Q4_K_M (the `unsloth` GGUF conversion, Apache-2.0 tag linking Qwen's licence) | Apache-2.0, not gated | `llama-server` (llama.cpp, MIT) with JSON output and seeds |
| full run, planned | `Qwen3.6-35B-A3B`, with `gemma-4-26B-A4B-it` writing one person in five for variety | both Apache-2.0, not gated (Gemma 4: Google's site also links a prohibited-use policy that the Apache text does not incorporate, so it stays secondary) | vLLM (Apache-2.0) on one NVIDIA DGX Spark; thinking disabled; JSON schema output; the card's own sampling (temperature 0.7, top-p 0.8, top-k 20, presence penalty 1.5) |

Sources: docs/research/teacher-and-data.md and docs/research/licences.md (checked 16 Oct 2026). Teachers whose terms pass through to models trained on their outputs were excluded (the note names the families and the clauses). The teacher that wrote this release, its weights hash and its sampling settings: <to be filled>; each `Person` also carries `teacher.model`, `teacher.seed` and `teacher.prompt_version`.

#### Prompts, versioned

Three prompts, one version string: `PERSONA` (one fictional person, three to six interests, three to five threads with a label and a description), `CHATS_FOR_THREAD` (N opening messages for one thread in time order over months, each with a day offset and a difficulty label, following a requested difficulty mix), and `LOOSE_CHATS` (one-offs that belong to none of the person's threads). The variety hints inside the prompts are generic roles, places, typing habits and domains, never a real person, company or product. The version is `prompts.PROMPT_VERSION`, recorded on every person and in every scoreboard run (`pipeline/src/bundle_pipeline/prompts.py`, W3). BDL-3 ended on `v0.2`: v0.1 asked for JSON by instruction; v0.2 sends strict JSON schemas as `response_format: json_schema` and numbers the difficulty list. Prompt version for this release: <prompt_version>.

R3 adds for the full run: seed personas from NVIDIA's Nemotron-Personas (CC BY 4.0; docs/research/licences.md, checked 16 Oct 2026), stratified by age, occupation and region, plus a small hand-written generator for rare combinations; and ask the teacher for five candidate openers with stated probabilities and keep one at random rather than the most typical, which raises diversity (docs/research/teacher-and-data.md, checked 16 Oct 2026). Whether seed personas were used for this release, and from where: <to be filled; if used, credit the source dataset here under its licence>.

#### Difficulty mix

The architecture lists seven kinds of hard chat the teacher must produce (docs/ARCHITECTURE.md, section 5), and the pipeline adds `plain` for the rest:

| label | what it is |
|---|---|
| `overlap` | belongs with one thread but reads like another (a food question that belongs with running) |
| `vague` | a vague one-liner |
| `nowhere` | belongs to none of the person's threads |
| `long_gap` | a follow-up after a long gap (at least 45 days in the version-0 generator) |
| `typos` | typos and lower case |
| `very_short` | very short |
| `new_thread` | opens a new thread |
| `plain` | none of the above |

Each thread is written to a requested mix; R3 suggests quotas of about 20% overlaps, 15% vague, 15% nowhere, 10% long gap, 15% typos, 10% very short and 15% new thread (docs/research/teacher-and-data.md, checked 16 Oct 2026). The actual mix per split for this release, from the `tasks` summary: <to be filled>.

#### Validation

As implemented in `pipeline/src/bundle_pipeline/validate.py` (W3): a person must load as `Person` or is rejected, as is one with an empty persona or duplicate thread or chat ids; chats with empty text or pointing at an unknown thread are dropped; days are made non-decreasing and start at 0; a thread left with one chat becomes a loose chat and a thread with none is removed; a person needs at least one thread and three chats. Every repair is written to `validated/report.json` under the person's id so the teacher's habits stay visible. R3 adds, for the full run: tag rules (a `vague` chat has at most eight words; a `nowhere` chat shares no noun with any bundle name), a language check, and a check for real names and brands.

#### Deduplication

Version 0: exact duplicates after normalising (lower case, letters and digits only) and near-duplicates at token Jaccard ≥ 0.8 within a person are dropped, keeping the earlier chat. Full run, per R3: exact hash, then MinHash near-duplicates (5-gram shingles, 240 permutations, threshold 0.7, with datasketch under MIT or text-dedup under Apache-2.0), then embedding near-duplicates (cosine ≥ 0.92 within a person, ≥ 0.95 across people, thresholds tuned on the toy run), keeping the first; and a diversity report per run (mean pairwise cosine distance, unigram and bigram entropy, duplicate rate, tag mix) that fails the run if any figure falls below the previous one (docs/research/teacher-and-data.md, checked 16 Oct 2026). Duplicate rate for this release: <to be filled from the report>.

#### Decontamination against the demo

The demo website's chat library is written separately and never used for lessons or exams (D4). R3's recipe checks all three splits against it with 10-gram overlap plus a sequence-match ratio over 0.5 and embedding cosine ≥ 0.9, and drops matches from the data, never from the library. Done for this release: <yes/no, matches dropped: n>.

### Annotations

There is no annotation step. The labels (which thread a chat belongs to, the difficulty, and therefore every decision example's answer) come from how the data was constructed: the teacher wrote each chat for a named thread or as a loose chat, and the pipeline derived the answers mechanically. No human labelled anything; no crowd workers were involved.

### Personal and sensitive information

None by construction. The people are invented; the prompts forbid real names; the validation step rejects what it can detect. The data was never drawn from real chats, exports, scraped pages or visitors to the demo site (D2, D3). If a reader nevertheless finds text that identifies a real person, the project will remove it: <contact>.

## What is NOT in it

- No real people: no real names, no real lives, no personas copied from anyone.
- No real chats: nobody's chat history, export or logs, including the founder's own.
- No scraped or copied text from the web.
- No visitor data: nothing anyone did on the demo website (D2).
- No demo content: the website's library is separate (D4).
- No exam rows while that exam is live; only its hash.
- No model replies: each chat is an opening message, not a conversation.
- No output of any hosted model: the scoreboard's frontier comparator answers exam questions, and its answers are never kept as data (docs/research/licences.md, checked 16 Oct 2026).

## Bias, risks and limitations

- **One voice, or two.** Everything was written by one teacher model (two in the full run). Its habits of phrasing, topic choice and typing are baked in; the diversity report measures sameness but cannot remove it.
- **English, typed, short.** The data covers English opening messages of a few words to a few sentences. Other languages, long messages and spoken-style input are absent.
- **Invented lives are tidy.** Each person has three to five threads and a handful of loose chats over about nine months. Real sidebars are larger, messier and longer-lived.
- **Difficulty labels are the teacher's.** The teacher was asked to write to a label; the version-0 generator re-labels `very_short` and `plain` when the text contradicts them, but the other labels are taken on trust.
- **Persona skew.** If seed personas from a public dataset are used, the invented population follows that dataset's country and distribution (R3 names NVIDIA's Nemotron-Personas, built to a single country's census distributions). The "who wrote it" section says which seeds were used.
- **Toy scale.** While the data is labelled "toy scale" (about 24 people, the pipeline's default `--people 24`), nothing fitted on it is meaningful at the 95% level (docs/research/student-and-method.md, checked 16 Oct 2026).
- **Thin evidence on teacher writing quality.** R3 notes that the newest teacher cards publish coding and knowledge scores, not writing scores, and asks for a human read of a pilot before a full run.

### Recommendations

Read the `teacher`, `difficulty` and `day` fields rather than treating the rows as a sample of real users; keep the exam sealed; publish any model's results with the exam hash they were sat on; and re-check the people against a real population before claiming anything about one.

## Licence and attribution

The dataset is licensed under Creative Commons Attribution 4.0 International (CC BY 4.0), like the project's documentation (D12; `LICENSE-docs` in the repository). In short, from the licence's own Section 3(a): if you share it, in original or modified form, you must

1. keep the identification of the creator, the copyright notice, the notice referring to the licence, the notice referring to the disclaimer of warranties, and a link to the material, where supplied;
2. say whether you modified it, and keep any earlier modification notices;
3. say that it is licensed under CC BY 4.0 and include the licence text or a link to it (https://creativecommons.org/licenses/by/4.0/).

You may meet these conditions in any reasonable way for the medium, for instance with a link to a page that holds the required information. A suggested attribution line: "<public name> invented chats, by <creator>, licensed CC BY 4.0, <repository URL>, exam <exam sha256>; modified: <yes/no>."

Upstream attribution the dataset itself carries:

- The teacher models' licences (Apache-2.0 for the Qwen3 and Gemma 4 models named above) place no condition on training with or distributing their outputs (docs/research/teacher-and-data.md and docs/research/licences.md, checked 16 Oct 2026); the models are named here so the recipe can be reproduced.
- If seed personas from a CC BY 4.0 persona dataset (R3: NVIDIA's Nemotron-Personas) are used in the full run, that dataset and its publisher must be credited here under its own attribution terms: <to be filled, or "none used">.

## Citation

To be filled when the public name and the repository exist.

```bibtex
@dataset{<key>,
  title   = {<public name> invented chats: synthetic lessons for sorting AI chats into bundles},
  author  = {<creator>},
  year    = {<year>},
  url     = {<repository URL>},
  license = {CC-BY-4.0},
  note    = {Prompt version <prompt_version>, teacher <teacher model>, exam <exam sha256>}
}
```

## Dataset card authors and contact

Drafted in BDL-3 by Claude Code from the specification, architecture, decisions, pipeline contract and research notes in the repository; to be reviewed by the founder before publishing. Contact: <to be filled>.

An independent open-source project, not affiliated with any AI company. "Bundle" is a working name.
