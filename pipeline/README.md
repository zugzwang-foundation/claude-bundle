# pipeline — Bundle's learning loop at toy scale

`bundle_pipeline` is a small uv-managed Python project that runs the whole loop
on this Mac: a local teacher model invents people and their chats, we validate
and split them, turn each chat into a decision example, score a baseline sorter,
train and calibrate a student, sit a sealed exam, export to ONNX for the browser,
and write a scoreboard run. Today's run proves the loop; the real training
happens on the Spark later.

## How to run

```sh
cd pipeline
uv sync                      # creates .venv with CPython 3.14 and the exact pins below
uv run bundle-pipeline --help
uv run bundle-pipeline smoke            # runtime check: Python, packages, device, paths, fixture
uv run bundle-pipeline smoke --encoder  # also downloads and loads the base encoder (87 MB on disk)

uv run ruff check .          # lint (E, F, I, UP, B; line length 100)
uv run pytest                # tests (quiet by default)
```

The loop, in order (each a subcommand; defaults come from `config.py`):

```
generate -> validate -> split -> tasks -> baseline -> train -> calibrate -> exam -> export -> scoreboard
```

Never use the system `python3` (3.9). Always go through `uv run` or `.venv/bin/python`.

### Module convention

Every subcommand is a module `bundle_pipeline/<name>.py` exposing
`main(args: argparse.Namespace) -> int`. `cli.py` imports it lazily, so
`--help` never loads torch. Modules that are still stubs raise
`NotImplementedError`; the CLI prints `not implemented yet` and exits with code 3.

### Data layout (`pipeline/data/`, gitignored)

```
raw/people/<person_id>.json     one Person each (teacher output)
validated/people.jsonl          one Person per line
splits/{lessons,practice,exam}.jsonl   one Person per line; 80/10/10 by person, deterministic
splits/exam.sha256              hash of exam.jsonl; written once, checked by `exam`
tasks/{lessons,practice,exam}.jsonl    one DecisionExample per line
models/                         student checkpoints, calibration.json, ONNX export
runs/                           per-run metrics
```

Outputs outside `pipeline/`: `scoreboard/runs/<run-id>.json` at the repository
root, and a camelCase copy of the calibration at `web/src/sorter/calibration.json`.

A second data tree keeps a trial run away from the real one: pass
`--data-root data/smoke` (or set `BUNDLE_DATA_ROOT`) to any subcommand and every
default path above is rebuilt under it.

### Smoke run (one person, 20 chats, separate data root)

```
uv run bundle-pipeline generate --people 1 --chats-per-person 20 --seed 1 --data-root data/smoke
uv run bundle-pipeline validate --data-root data/smoke
uv run bundle-pipeline split    --data-root data/smoke   # one person lands in one split
uv run bundle-pipeline tasks    --data-root data/smoke
uv run bundle-pipeline baseline --data-root data/smoke --split lessons --device cpu
```

Measured 2026-10-16 against llama-server (Qwen3-4B-Instruct-2507 Q4_K_M, Mac
under load from other agents): generate 66 s for 20 chats (18.2 chats/min,
11.6 tok/s, 5 completions, no retries); validate 20 -> 20; tasks 20 examples
(answers none 9 / loose 3 / bundle 8); baseline B0 0.450 accuracy, B1 0.550
accuracy, macro-F1 0.509, 70.8 ms per decision on CPU. docs/toy-run.md has the
full numbers and the real run's command and PID.

### Environment variables

| variable | default | meaning |
|---|---|---|
| `BUNDLE_TEACHER_URL` | `http://127.0.0.1:8081/v1` | OpenAI-compatible chat completions (llama-server) |
| `BUNDLE_TEACHER_MODEL` | `local` | model name sent in requests |
| `BUNDLE_TEACHER_TIMEOUT` | `180` | seconds per request |
| `BUNDLE_DATA_ROOT` | `pipeline/data` | where all generated data lives; every subcommand also takes `--data-root <dir>`, which wins (`BUNDLE_DATA_DIR` is accepted as the older spelling) |
| `BUNDLE_PIPELINE_ROOT` | auto (parent of `src/`) | override when not running from the checkout |
| `HF_HUB_CACHE` / `HF_HOME` | `~/.cache/huggingface/hub` | encoder downloads (disk is tight: 20 GB free) |

## Generation side (teacher -> validate -> split -> tasks)

```sh
# 0. a teacher: llama-server (OpenAI-compatible) on http://127.0.0.1:8081/v1,
#    or point BUNDLE_TEACHER_URL / --teacher-url elsewhere
uv run bundle-pipeline generate --people 24 --chats-per-person 60 --seed 3 \
    --out data/raw/people --workers 2 --time-budget-min 60
uv run bundle-pipeline validate      # data/raw/people/*.json -> data/validated/people.jsonl + report.json
uv run bundle-pipeline split         # -> data/splits/{lessons,practice,exam}.jsonl, exam.sha256, split.json
uv run bundle-pipeline tasks         # -> data/tasks/{lessons,practice,exam}.jsonl (DecisionExamples)
```

| module | what it does |
|---|---|
| `teacher.py` | `TeacherClient` over httpx: `health()` (GET /models), `chat()` with transport retries (connection errors, 429, 5xx) and a JSON-mode fallback when the server rejects `response_format`; `chat_json()` extracts the first `{...}` block (`extract_json`: fences, `<think>` blocks, braces in strings, trailing commas, truncated tails), validates with pydantic and retries up to 3 completions with a changed seed (+1,000,003 each) and a one-line nudge. |
| `prompts.py` | `PROMPT_VERSION = "v0.2"` (v0.2 adds strict JSON schemas sent as `response_format: json_schema`, and a numbered difficulty list). PERSONA (one fictional person, 3-6 interests, 3-5 threads; variety hints are generic roles, places, typing habits and domains), CHATS_FOR_THREAD (N opening messages over months with a requested difficulty mix in order) and LOOSE_CHATS (one-offs that belong nowhere). Answer shapes `PersonaOut`, `ChatsOut`, `LooseOut` normalise what a small model writes ("Very short" -> `very_short`, `"12"` -> 12). |
| `generate.py` | one person per worker: persona, then each thread (8-15 chats), then 6-10 loose chats, so the total is about `--chats-per-person`. `choose_n_threads` picks 3-5 threads that can reach the target; `enforce_days` makes thread days start at 0, never decrease and gives every `long_gap` chat a gap of at least 45 days; `assemble_person` merges onto one timeline (first thread starts day 0, others start at random days within ~6 months, loose chats anywhere in 0-270) and re-labels `very_short`/`plain` when the text contradicts the label. Writes `<person_id>.json` atomically; skips ids already on disk; prints chats/min and tok/s per person; appends to `data/generate.log`; stops starting people at `--time-budget-min` and abandons in-flight people after `--grace-min` more. Exit 2 when the teacher is unreachable. Person ids are `p<seed>-<index:03d>`, person seeds `seed*10000+index`. |
| `validate.py` | schema (reject), exact duplicates after normalising (lower case, `[a-z0-9]+` tokens) and near duplicates at token Jaccard >= 0.8 (drop the later one), unknown thread ids (drop the chat), days non-decreasing (stable sort) and starting at 0 (shift), threads with one chat (make it loose) or none (drop the thread); a person needs one thread and three chats. Writes `validated/people.jsonl` and `validated/report.json` with every repair per person. |
| `split.py` | rank by `sha256(person_id + salt)` (`--salt`, default `bundle-bdl3`), first 80% lessons, next 10% practice, last 10% exam, at least one each from three people; writes JSONL sorted by id, `exam.sha256` (`sha256sum` format) and `split.json`. With an existing `exam.sha256` a run that would change `exam.jsonl` exits 2 and writes nothing unless `--force`. `exam_hash_matches()` is what `exam` uses to check the seal. |
| `tasks.py` | `examples_for_person(person)`: the contract word for word (bundles exist once a thread has 2+ earlier chats; a thread's first chat is loose until then; candidates = bundles with up to 8 most recent texts, then loose chats; answer = `b:<thread_id>`, `c:<chat_id>` or `none`). Example ids are `<person_id>:<chat_id>`. |
| `store.py` | JSONL read/write (atomic), sha256 helpers. |

Tests (`uv run pytest`, no network, no model downloads): `test_teacher.py` (extraction from messy text; client against `httpx.MockTransport`: health, seeds, JSON-mode fallback, 5xx/timeouts, give-up), `test_prompts.py` (version, shapes, difficulty mix, rendered messages), `test_generate.py` (planning bounds, day enforcement, a whole person and the CLI against a scripted teacher: idempotent, logs, exit 2 when down), `test_validate.py` (exact and near duplicates, repairs, fixture unchanged, CLI report), `test_split.py` (determinism, no person in two splits, counts, sealed exam refusal and `--force`), `test_tasks.py` (fixture: first chat of a thread -> `none`, second -> the loose id, third -> the bundle id; 8-example cap; ties; CLI).

## Python: CPython 3.14 (pinned in `.python-version`)

Checked on PyPI on 2026-10-16 (wheel filenames read from each release's JSON):

| package | macOS arm64 wheels for |
|---|---|
| torch 2.14.1 | cp310, cp311, cp312, cp313, **cp314**, cp314t |
| onnxruntime 1.30.0 | cp311, cp312, cp313, **cp314** |
| onnx 1.23.1 | cp310, cp311, **cp312-abi3** (covers 3.12 to 3.14), cp314t (universal2) |
| numpy 2.5.3 | cp312, cp313, **cp314**, cp315 |
| scikit-learn 1.9.1 / scipy 1.18.1 | cp311 to **cp314**, cp315 |
| tokenizers 0.23.2, safetensors 0.8.0, protobuf 7.36.2 | cp310-abi3 |
| pydantic-core 2.46.5, regex 2026.9.29, pyyaml 6.0.3, markupsafe 3.0.4 | up to cp314 (and cp315) |
| sentence-transformers, transformers, optimum | pure Python |

3.14 is therefore the newest CPython for which every binary dependency has a
native arm64 wheel; 3.15 fails on torch and onnxruntime. `requires-python` is
`>=3.14,<3.15` so the universal lock never has to resolve for 3.15. uv
downloaded `cpython-3.14.8-macos-aarch64-none` (25.4 MiB). The wheels for
torch and onnxruntime are tagged `macosx_14_0_arm64`; this Mac runs macOS 15.7.3.

## Pinned versions

All exact (`==`). Rule for today: released at least 14 days before 2026-10-16,
that is on or before 2026-10-02. Dates are the first upload of the release on PyPI.

| package | version | released | note |
|---|---|---|---|
| pydantic | 2.13.5 | 2026-08-28 | 2.14.0/2.14.1 (Oct 8/11) too new |
| httpx | 0.28.1 | 2024-12-06 | latest |
| numpy | 2.5.3 | 2026-09-06 | 2.5.4 (Oct 10) too new |
| torch | 2.14.1 | 2026-09-30 | CPU/MPS wheel `macosx_14_0_arm64`, 127 MB |
| sentence-transformers | 6.1.0 | 2026-09-18 | pins `transformers>=5,<6`, `huggingface-hub>=1.3,<2` |
| scikit-learn | 1.9.1 | 2026-09-10 | latest |
| onnx | 1.23.1 | 2026-09-29 | 1.23.2 (Oct 6) too new |
| onnxruntime | 1.30.0 | 2026-09-10 | 1.31.0 (Oct 9) too new; 21.5 MB |
| transformers | 5.18.0 | 2026-09-30 | newest allowed by sentence-transformers and the 14-day rule; 5.19/5.20 too new |
| tokenizers | 0.23.2 | 2026-09-03 | transformers 5.18 needs `>=0.23.1,<0.24`; 0.23.3 (Oct 9) too new |
| ruff (dev) | 0.16.10 | 2026-10-01 | 0.17.x (Oct 9/15) too new |
| pytest (dev) | 9.1.1 | 2026-06-19 | latest |
| build backend | uv_build >=0.13.1,<0.14 | | matches the installed uv 0.13.1 |

`uv sync` resolved 75 packages (universal lock, all platforms) and installed 55 into `.venv` (936 MB, of which torch is 121 MiB downloaded); see `uv.lock`.

### What did not resolve: optimum / optimum-onnx

The ONNX exporter now ships as the separate package `optimum-onnx`
(`optimum[onnxruntime]` is just an alias for `optimum-onnx[onnxruntime]`).
Its only non-dev release, **optimum-onnx 0.1.0 (2025-12-23)**, pins
`transformers>=4.36,<4.58` and `optimum~=2.1.0`. Every current
sentence-transformers (6.0.0 onward) pins `transformers>=5.0.0`, so the two
cannot be installed together in any released combination; uv confirms:

```
optimum-onnx>=0.1.0 depends on transformers>=4.36,<4.58.0 and you require transformers==5.18.0
```

Decision for today: **no optimum, no optimum-onnx.** The `export` stage uses
`torch.onnx.export` (torch 2.14.1) plus `onnxruntime.quantization.quantize_dynamic`
for int8, and copies the tokenizer files next to `onnx/model.onnx` in the layout
Transformers.js expects. The alternative, kept for the record, is the whole
older stack: sentence-transformers 5.7.0 (2026-08-06, allows `transformers<6`),
transformers 4.57.6 (2026-01-16), tokenizers 0.22.2, optimum 2.1.0, optimum-onnx 0.1.0.
It is nine months stale and its compatibility with torch 2.14 is NOT VERIFIED,
so it was not chosen. Reopen if the torch exporter cannot produce a model that
Transformers.js loads.

`typer` 0.27.3 is in the environment as a dependency of transformers 5.18, but
the CLI uses `argparse` from the standard library and does not depend on it.

## Base encoder

`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, mean pooling. Downloaded by
`smoke --encoder` on 2026-10-16: 87 MB in `~/.cache/huggingface/hub` (model.safetensors via
hf-xet, tokenizer.json 466 KB). Loads on CPython 3.14.8 with torch 2.14.1 (MPS available) in
about a minute including download.
Licence: **Apache-2.0**, read from the model card's licence tag through the
Hub API (`https://huggingface.co/api/models/sentence-transformers/all-MiniLM-L6-v2`,
`cardData.license: apache-2.0`) on 2026-10-16; model card:
<https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2>.
Browser copy: `Xenova/all-MiniLM-L6-v2` (also tagged Apache-2.0, 2026-10-16),
which ships `onnx/model.onnx`, `onnx/model_quantized.onnx`, `onnx/model_int8.onnx`
and others.

## Tests

`tests/fixtures/people.json` holds two invented people (a nurse training for a
half marathon, a retired teacher with an allotment), three threads each with
two to four chats, two or three loose chats each, and every one of the eight
difficulty labels in each person. 6.8 KB. `tests/test_schema.py` checks it loads
into `Person` and meets those counts; `tests/test_cli.py` checks the subcommand
set, that stubs fail loudly and that `--data-root` rebuilds every default path.
The whole suite runs offline (`HF_HUB_OFFLINE=1 uv run pytest`): the teacher is
`httpx.MockTransport`, the encoder a hash-based fake. 129 passed, 1 skipped,
about 1.5 s, on 2026-10-16.

## Disk, recorded on 2026-10-16

| item | size |
|---|---|
| `pipeline/.venv` (55 packages) | 936 MB |
| `~/.cache/uv` after the sync (wheels, CPython 3.14.8) | 1.8 GB |
| `~/.cache/huggingface/hub` after `smoke --encoder` | 87 MiB per `du -sh` (smoke prints 92 MB, decimal) |
| free disk before / after | 20 GB / 17 GB |

## Training and evaluation side (sorter, baseline, train, calibrate, exam, export, scoreboard)

Written 2026-10-16. Everything below was run end to end on the two-person fixture
(25 decision examples, 14 training pairs) in a scratch data dir, and `train` was
timed on a 1000-example replica. Nothing here needs `datasets`, `accelerate`,
`optimum` or scipy.

| module | what it does |
|---|---|
| `sorter.py` | the maths, pure numpy: bundle vector = normalised mean of example vectors, cosine scores, "none" at `none_score`, softmax over scores / temperature, file / suggest / leave rules, `Decision`. `Sorter` (embed function + params), `LeaveSorter` (B0), `Scored` (ids + scores, params-free, for calibration), `mean_nll`. |
| `encoder.py` | `Encoder(model_or_path, device="auto"|"cpu"|"mps")` around `SentenceTransformer`; `encode` normalises and caches text -> vector per run; `encode_uncached` for honest single-decision timing; `model_size_mb` follows the hf-xet symlinks in the Hub cache. |
| `baseline.py` | B0 and B1 on `tasks/<split>.jsonl` (practice by default) -> `runs/baseline-<split>.json` and a markdown table. |
| `train.py` | pairs (chat, one text of the answer bundle or the answer loose chat) from `tasks/lessons.jsonl`; `MultipleNegativesRankingLoss` with in-batch negatives (scale 20); batches never hold two pairs with the same (person, answer); plain PyTorch loop: AdamW lr 2e-5, 10% linear warm-up then linear decay, grad clip 1.0, batch 32, 1 epoch, seeded; saves `data/models/student-v0/` (`SentenceTransformer.save`) plus `train_meta.json`. |
| `calibrate.py` | on practice: coordinate descent over temperature (geometric 0.01..1, 41 points) and none_score (0..1, 51 points) minimising mean NLL of the answer; then `file_cutoff` = smallest observed p_top with precision >= 0.95 over decisions at or above it (min support 5), `suggest_cutoff` likewise for 0.80, never above `file_cutoff`; 1.0 when no threshold qualifies (said in `source`). Writes `calibration.json` and the camelCase web copy. |
| `exam.py` | the metrics (definitions in the module docstring) and the sealed exam: checks `splits/exam.sha256`, runs B0, B1 (defaults, or `--b1-calibration`) and B2 (student + `calibration.json`), writes `runs/exam-<run-id>.json`. |
| `scoreboard.py` | `runs/exam-<run-id>.json` -> `scoreboard/runs/<run-id>.json` at the repository root in the contract shape (sorter entries carry exactly the fourteen contract keys; parameters go into `notes`), plus the winner line (B2 beats B1 or the site keeps B1). |
| `export.py` | `torch.onnx.export(dynamo=False)` of the student's transformer (opset 14, dynamic batch and sequence), `quantize_dynamic` int8 per-channel, Transformers.js layout, `manifest.json`, `export_report.json`, `compare_embeddings` (PyTorch vs onnxruntime on 32 fixture texts). |

### Commands, in order (after `generate`, `validate`, `split`, `tasks`)

```sh
cd pipeline
uv run bundle-pipeline baseline --split practice            # B0 + B1 on practice -> data/runs/baseline-practice.json
uv run bundle-pipeline train --epochs 1                     # lessons -> data/models/student-v0/
uv run bundle-pipeline calibrate                            # practice -> data/models/calibration.json + web/src/sorter/calibration.json
uv run bundle-pipeline exam --run-id 2026-10-16-toy-v0      # sealed exam: B0, B1, B2 -> data/runs/exam-<run-id>.json
uv run bundle-pipeline export --run-id 2026-10-16-toy-v0    # -> data/models/student-v0-onnx/{config.json,tokenizer*.json,onnx/,manifest.json}
uv run bundle-pipeline scoreboard --run-id 2026-10-16-toy-v0  # -> scoreboard/runs/2026-10-16-toy-v0.json (repo root)
```

Useful switches: `--device cpu|mps` everywhere a model loads (default `auto`:
MPS when available); `calibrate --model sentence-transformers/all-MiniLM-L6-v2
--out data/models/calibration-b1.json --no-web` to calibrate the base encoder
too and pass it to `exam --b1-calibration`; `exam --allow-unsealed` for dry runs
without `split`; `train --max-pairs N` for a quick check; `export --per-tensor`
for the smaller, worse int8 variant.

### Measured on this Mac, 2026-10-16

| what | result |
|---|---|
| `train`, 1 epoch, 1000 examples (560 pairs, 18 batches of 32) | 6 s on CPU, 5 s on MPS, plus ~6 s to load; 2 epochs on a 24-person run stay far under the 10-minute budget |
| `exam`, 25 examples, three sorters | 7 s wall, almost all of it model loading |
| single-decision latency (chat embedding, batch of one, plus maths) | 5 ms on an idle CPU; 13-30 ms while other agents were running |
| student checkpoint `data/models/student-v0/` | 91.6 MB (`model.safetensors` 90.9 MB) |
| `onnx/model.onnx` fp32 / `onnx/model_quantized.onnx` int8 | 90.4 MB / 23.0 MB |
| ONNX parity vs PyTorch, 32 fixture texts, min cosine | fp32 0.99999994; int8 per-channel 0.9944 (mean 0.9975); int8 per-tensor 0.936 |

The relay asks for cosine >= 0.999 between PyTorch and the browser runtime.
fp32 ONNX meets it; **no int8 variant does on this stack** (best 0.994 with
per-channel weights), and `export_report.json` records the gap
(`int8_meets_target: false`). The Transformers.js (Node) comparison is W6's,
not run here. `dtype` in `manifest.json` is `"q8"`, the name Transformers.js
uses for its dynamically quantised int8 weights (NOT VERIFIED against the
installed Transformers.js version). transformers 5 no longer writes
`special_tokens_map.json`; `export` writes it from `tokenizer.special_tokens_map`.

### Known limits

- One pair per decision example and a single epoch: enough to move the loss
  (fixture: 4.0 -> 0.9) but not a tuned recipe. Siblings of a thread never
  share a batch; nothing else guards against false negatives.
- Calibration cut-offs are chosen on the practice split's observed p_top
  values with a minimum support of 5 decisions; on a toy practice split that
  is coarse and the cut-offs can sit far from the defaults.
- `latency_ms_per_decision` is wall-clock on a shared machine and moves with
  load; `size_mb` is the checkpoint on disk, not the int8 export.
- B1's `size_mb` reads the Hub cache snapshot (follows hf-xet symlinks); if
  the cache is elsewhere, set `HF_HUB_CACHE`.
- `macro_f1` counts a wrong bundle as a miss for the bundle class (see the
  `exam.py` docstring); numbers are not comparable with a plain type-level F1.
