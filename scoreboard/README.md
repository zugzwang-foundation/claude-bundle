# Scoreboard

Every exam result Bundle produces is published here, one JSON file per run under
`scoreboard/runs/<run-id>.json`, next to a no-training baseline and, later, the previous student
and open comparators (decision D7 in docs/DECISIONS.md: a release ships only if it beats the last
one on the sealed exam; every result is published). The files are written by the Python pipeline
(`pipeline/src/bundle_pipeline/scoreboard.py`) and read by the website's tech view
(`web/src/tech/scoreboard.ts`, which resolves `scoreboard/runs/*.json` at build time), so the
shape below is a contract between the two.

## The JSON fields

Top level, always present (the contract):

| field | type | meaning |
|---|---|---|
| `run_id` | string | the run's name, also the file name; today `<date>-<scale>-<student>` |
| `label` | string | `"toy scale"` for every run made on the Mac; the website shows it next to the numbers |
| `date` | string | `YYYY-MM-DD` of the exam |
| `exam_hash` | string | sha256 of `splits/exam.jsonl`, written by `split` before any model saw the exam and checked by `exam` |
| `base_model` | string | the encoder the student was trained from |
| `sorters` | list | one entry per sorter, below |
| `notes` | list of strings | free text: parameters, teacher, counts, caveats; the last note is the winner line (below) |

Each entry of `sorters` carries exactly fourteen keys: `id`, `name` and the twelve metrics.
Metric definitions are spelled out in `pipeline/src/bundle_pipeline/exam.py`; in short:

| key | meaning |
|---|---|
| `accuracy` | share of exam decisions whose prediction (argmax over the candidates and "none") equals the answer |
| `macro_f1` | unweighted mean of F1 over the classes bundle, loose and none; a prediction counts for a class only when it names the exact right target, so the wrong bundle is a false positive for bundle, not a hit |
| `none_precision`, `none_recall` | precision and recall of predicting "none" (research item 14 asks for these above accuracy) |
| `ece` | expected calibration error of the chosen class, 10 equal-width bins |
| `brier` | mean squared error of the chosen class's probability against hit or miss |
| `file_precision`, `file_coverage` | among decisions at or above the file cut-off, the share whose target is the answer, and their share of all decisions (target 95% precision) |
| `suggest_precision`, `suggest_coverage` | the same at or above the suggest cut-off, which includes the filed decisions (target 80%) |
| `latency_ms_per_decision` | median wall-clock milliseconds for one decision on the exam machine: embedding one chat plus the maths, the candidates' vectors already known |
| `size_mb` | the model's weights on disk, in MB (10^6 bytes); 0 for B0 |

The sorters on a board: **B0** always leaves a chat loose; **B1** is the base encoder without
training; **B2** is the student; **B1b** (when present) is a second base encoder, untrained, put
through the same calibration. Every sorter on a board sat the same sealed exam with its own
parameters calibrated on the practice split.

The winner line is the last note and follows one rule (`scoreboard.winner_note`): B2 beats B1 when
its accuracy is higher and its macro-F1 is not lower; then the line says "wire B2 into the site
through the manifest", otherwise "the site keeps B1". It is the rule's verdict, not a decision:
the note before it (`site: ...`) says what the site actually uses and why.

Extra top-level keys may follow the contract keys; a strict reader ignores them (the website
does). Today's run carries `people`, `chats`, `examples` (counts per split and answer type),
`calibration` (temperature, none score and both cut-offs per encoder, with bootstrap intervals),
`teacher`, `student`, `export` (file sizes; `parity` of the ONNX export against PyTorch through
onnxruntime and `parity_node` through Transformers.js in Node), `accuracy_by_history` (research
item 13), `accuracy_by_answer_type`, `accuracy_by_difficulty`, `b2_minus_b1` (paired bootstrap),
`int8_exam_effect`, `second_encoder` and `follow_up_toy`. Paths inside the file are repository
relative; nothing in it identifies a person or a machine.

## How a run is produced

From `pipeline/` with the uv-managed environment (`uv sync` once; the full list of switches is in
`pipeline/README.md`):

```sh
uv run bundle-pipeline generate --people 24 --chats-per-person 60 --seed 42 --workers 4 --time-budget-min 55
uv run bundle-pipeline validate                       # schema, duplicates, repairs -> validated/people.jsonl
uv run bundle-pipeline split                          # by person-id hash 80/10/10 -> splits/, writes exam.sha256 once
uv run bundle-pipeline tasks                          # one decision per chat -> tasks/{lessons,practice,exam}.jsonl
uv run bundle-pipeline baseline --split practice      # B0 and B1 with the default parameters
uv run bundle-pipeline train --epochs 2 --device mps  # lessons -> models/student-v0/
uv run bundle-pipeline calibrate --model sentence-transformers/all-MiniLM-L6-v2 --out data/models/calibration-b1.json --no-web
uv run bundle-pipeline calibrate                      # the student, on practice -> models/calibration.json
uv run bundle-pipeline exam --run-id <run-id> --b1-calibration data/models/calibration-b1.json
uv run bundle-pipeline export --run-id <run-id>       # ONNX fp32 and int8, Transformers.js layout, parity report
uv run bundle-pipeline scoreboard --run-id <run-id> --notes "..."   # -> scoreboard/runs/<run-id>.json
```

`exam` refuses to run when `splits/exam.jsonl` no longer matches `splits/exam.sha256`, and
`split` refuses to change a sealed exam without `--force`. The scripts under `pipeline/scripts/`
(`w6_*.py`) add the extra keys above and `w6_board_finalise.py` checks the finished file: valid
JSON, the label, the contract keys and their values against the exam records, the seal, counts
that add up, a calibration entry for every encoder, the teacher block and the notes. It exits
non-zero on a gap.

## The toy-scale caveat

Every run labelled "toy scale" was made on one Mac in one afternoon: one 4B teacher (Qwen3-4B-
Instruct-2507 Q4_K_M under llama-server), one prompt version, 23 invented people, and an exam of
**two people and 114 decisions**. At that size three decisions move accuracy by 2.6 points, the
90% bootstrap interval of the student-minus-baseline difference includes zero, and the file
cut-off re-chosen on bootstrap resamples of the 117 practice decisions ranges from 0.69 to 0.94.
Read the numbers as "the loop runs and nothing contradicts the student", not as a measured
improvement. The exam people also share the teacher and the prompt with the lessons people, so
the board says nothing about out-of-distribution chats. Decision D10: the real run happens on
the DGX Spark from BDL-4.

## Run 2026-10-16-toy-v0

Exam of 114 decisions (bundle 76, loose 9, none 29) from 2 people; seal
`7c3024b85b8392ec54e35adefcf745e438eb9e6a637a84c274e159d8afe05607`; base model
`sentence-transformers/all-MiniLM-L6-v2`; all sorters calibrated on the 117 practice decisions.

| id | name | accuracy | macro_f1 | none_precision | none_recall | ece | brier | file_precision | file_coverage | suggest_precision | suggest_coverage | latency_ms_per_decision | size_mb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | always leave | 0.254 | 0.135 | 0.254 | 1.000 | 0.746 | 0.746 | 0.000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.0 |
| B1 | base encoder, untrained | 0.632 | 0.606 | 0.692 | 0.621 | 0.096 | 0.197 | 0.838 | 0.325 | 0.632 | 0.763 | 4.7 | 91.6 |
| B1b | second base encoder, untrained (mxbai-embed-xsmall-v1, calibrated on practice) | 0.614 | 0.594 | 0.708 | 0.586 | 0.104 | 0.195 | 0.861 | 0.316 | 0.600 | 0.789 | 4.1 | 49.2 |
| B2 | student v0 | 0.658 | 0.627 | 0.692 | 0.621 | 0.115 | 0.201 | 0.861 | 0.316 | 0.659 | 0.772 | 4.6 | 91.6 |

Winner line: "B2 beats B1 (accuracy 0.658 vs 0.632); wire B2 into the site through the
manifest". Paired bootstrap of B2 minus B1 (1,000 resamples): accuracy +0.026, 90% interval
-0.018 to +0.070; McNemar 5 decisions B2 alone gets right against 2 for B1. The site keeps B1
with its toy calibration (docs/DECISIONS.md, 2026-10-16). Also recorded in the file: the int8
export changes none of the 114 decisions although its min cosine to PyTorch is 0.9915 in both
onnxruntime and Transformers.js (fp32: 0.99999994 and 1.00000000, above the 0.999 bar); B1b is
two decisions behind B1 and never ahead; on the toy follow-up question the student's AUC is 0.752
against the base encoder's 0.735. The full account, with every caveat, is `pipeline/docs/toy-run.md`;
the parity run is `pipeline/docs/parity.md` and the follow-up toy `pipeline/docs/follow-up-toy.md`.
