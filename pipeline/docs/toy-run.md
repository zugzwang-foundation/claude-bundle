# Toy run (BDL-3): the generation and the learning loop at toy scale on this Mac

This file began as W3's record of the real generation (started 2026-10-16 18:11 IST,
2026-10-16T12:41:48Z, from `pipeline/` on branch `bdl-3-pipeline`) and W6 added its results as
they landed. This version (21:12 IST) gathers them into one results section. Times are IST unless
marked Z. Every number below was measured in this run; nothing is filled from memory. Branch
`bdl-3-student`, worktree `w3-pipeline`, `uv run` on CPython 3.14.8, MPS where a model loads.
Label: **toy scale** (two people per split).

## Summary

One 4B teacher on this Mac wrote 23 people and 1,380 chats in 55 minutes; 1,334 chats survived
validation and were split by person into 19 / 2 / 2 people (1,103 / 117 / 114 chats). The exam
was sealed (`splits/exam.sha256` = `7c3024b85b8392ec54e35adefcf745e438eb9e6a637a84c274e159d8afe05607`)
before any model saw it, and `exam` checked the seal. Four sorters sat it:

| id | sorter | accuracy | macro-F1 | none P / R | ECE | Brier | file P @ cov | suggest P @ cov | ms | MB |
|---|---|---|---|---|---|---|---|---|---|---|
| B0 | always leave loose | 0.254 | 0.135 | 0.254 / 1.000 | 0.746 | 0.746 | 0 @ 0 | 0 @ 0 | 0.0 | 0 |
| B1 | base encoder all-MiniLM-L6-v2, untrained, calibrated on practice | 0.632 | 0.606 | 0.692 / 0.621 | 0.096 | 0.197 | 0.838 @ 0.325 | 0.632 @ 0.763 | 4.7 | 91.6 |
| B1b | second base encoder mxbai-embed-xsmall-v1, untrained, calibrated on practice | 0.614 | 0.594 | 0.708 / 0.586 | 0.104 | 0.195 | 0.861 @ 0.316 | 0.600 @ 0.789 | 4.1 | 49.2 |
| B2 | student v0 (B1's encoder fine-tuned on lessons), calibrated on practice | 0.658 | 0.627 | 0.692 / 0.621 | 0.115 | 0.201 | 0.861 @ 0.316 | 0.659 @ 0.772 | 4.6 | 91.6 |

The verdict, in one breath: by the board's rule (higher accuracy, macro-F1 not lower) **B2 beats
B1**, but by 3 of 114 decisions, with a 90% bootstrap interval on the difference that includes
zero; B1b is a near twin of B1, two decisions behind and never ahead. The fp32 ONNX export matches
PyTorch to 0.999 in both onnxruntime and Transformers.js in Node; the int8 export does not (min
cosine 0.9915 in both runtimes, the same gap, so it is the quantisation), yet it changes none of
the 114 exam decisions. The student also answers the toy follow-up question a little better than
its base (AUC 0.752 against 0.735). The demo site keeps B1 (docs/DECISIONS.md, 2026-10-16). What
this run proves is that the loop runs end to end on the day's data; what it does not prove is a
real improvement from training. Details and every caveat follow.

## The generation run (W3; 18:11 to 19:06)

### Command

```
cd <worktree>/pipeline
nohup uv run bundle-pipeline generate --people 24 --chats-per-person 60 --seed 42 \
  --out data/raw/people --workers 4 --time-budget-min 55 > data/generate.nohup.log 2>&1 &
```

- PID: 25538
- Teacher: llama-server 0.5.0 at http://127.0.0.1:8081/v1, Qwen3-4B-Instruct-2507 Q4_K_M
  (`-np 4`, Metal), see docs/toy-teacher.md.
- Prompts: v0.2 (strict JSON schemas via `response_format: json_schema`; see prompts.py).
- Logs: `data/generate.nohup.log` (stdout/stderr), `data/generate.log` (one line per person).
- Idempotent: rerunning the same command skips people already on disk.

### Why 24 people

The relay asks for about 24 people of about 60 chats within 60 minutes. The teacher report
(docs/toy-teacher.md) estimated 2 h for 24 x 60 at 4 concurrent slots and recommended 10 people
for 55 minutes; the smoke run measured 18.2 chats/min on a single stream while other agents loaded
the Mac. `--time-budget-min 55` stops starting new people after 55 minutes (+5 min grace for
people in flight), so asking for 24 costs nothing extra: the run writes whatever finishes, and
W6 runs on what exists at the deadline. The split is by person-id hash, so a partial run still
gives lessons/practice/exam.

### Smoke run before it (data/smoke, 1 person, 20 chats, seed 1)

- First attempt with prompts v0.1 failed: the 4B model returned `{"day": 3}` entries without
  `text` (3 completions, all invalid). Fix: strict JSON schemas sent as
  `response_format: {"type": "json_schema", ...}`, which llama-server compiles to a grammar
  (probed and verified 2026-10-16), plus a numbered difficulty list in the prompt.
- Second attempt (v0.2): 1 person, 3 threads, 20 chats, 5 calls, 5 completions (no retries),
  66 s, 18.2 chats/min, 11.6 tok/s, 766 completion tokens, 2131 prompt tokens.
- validate: 20 -> 20 chats, 0 exact / 0 near duplicates. split: 1 person -> lessons (practice and
  exam empty, as expected with one person). tasks: 20 examples, answers none 9 / loose 3 / bundle
  8, candidates mean 5.7 max 9.

### Throughput watch

- 18:12-18:14 IST (2 min in): 0 people written yet (a 60-chat person is 5-7 completions, so the
  first ones land after several minutes). llama-server's log shows all four slots decoding at
  3.9-4.9 tok/s each (`tg_3s` 4.9-5.1), about 19-20 tok/s aggregate, with a load average of 12-15
  from the other agents on the Mac. The smoke run cost 38 completion tokens per chat, so the
  expected rate is roughly 30 chats/min aggregate, i.e. about 1,600 chats in 55 minutes if nothing
  retries; the ~600-chat floor for W6 is far below that.
- 18:20 IST (8.6 min in): first person written, p42-003: 5 threads, 60 chats, 7 calls, 7
  completions (no JSON retries), 519 s wall, 1,979 completion tokens, 3.8 tok/s on its slot,
  6.9 chats/min per worker; 12.6 KB. llama-server's log counted 21 completions in the first 8.5
  min across the four slots (mean 865 tokens each incl. prompt). With four workers that is about
  28 chats/min aggregate: roughly 6 rounds of 4 people in 55 minutes, so expect 20-24 people and
  1,200-1,450 chats by the deadline (people still in flight at 55 min get 5 min grace, the rest
  are dropped). Above the ~600-chat floor; W6 runs on whatever exists at the deadline either way.
- Check progress with `cat data/generate.log` (one line per person) or `ls data/raw/people | wc -l`.

### Outcome

- Ended 19:06 (13:36:35Z) after 54.8 min: 23 people written (24 asked), 0 skipped, 1 failed
  (p42-018: `teacher failed after 3 attempts: ReadTimeout: timed out`), 0 not started. Raw files:
  1,380 chats, 110 threads (18 people with 5 threads, 5 with 4), 188 loose chats; 60 chats per
  person, 6-7 completions each, no JSON retries, 354-745 s wall per person. 25.2 chats/min
  overall; 55,339 completion tokens, 80,992 prompt tokens; 4.5 tok/s per slot while busy (3.7 at
  the start under a load average of 12-15, 6.8 for the last person once slots freed).
- 19:07: `pkill -f llama-server` (gone within 0.5 s); deleted
  `models/teacher/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (2,497,281,120 bytes); `server.log`
  (479 KB) kept. `df -h ~`: 6.5 GiB free before, 11 GiB after (the 8.7 GiB free at 19:04 had
  fallen to 6.5 GiB while other agents worked).

## Results (W6, 2026-10-16, toy scale)

### Commands and wall times (from `pipeline/`; `uv run bundle-pipeline ...` unless noted)

| when | step | command | wall | result |
|---|---|---|---|---|
| 19:07 | validate | `validate` | 0.16 s | 23 -> 23 people; chats 1380 -> 1334 (44 exact and 2 near duplicates dropped; 22 people had at least one repair) |
| 19:07 | split | `split` | 0.09 s | lessons 19 people / 1103 chats, practice 2 / 117, exam 2 / 114; `splits/exam.sha256` = `7c3024b85b8392ec54e35adefcf745e438eb9e6a637a84c274e159d8afe05607  exam.jsonl` (sealed 13:37:38Z, salt `bundle-bdl3`) |
| 19:07 | tasks | `tasks` | 0.11 s | lessons 1103 decisions (bundle 768 / loose 92 / none 243; candidates mean 8.43, max 15); practice 117 (82 / 9 / 26; mean 8.27); exam 114 (76 / 9 / 29; mean 8.82) |
| 19:09 | baseline | `baseline --split exam` | 11.2 s | B0 and B1 with the default parameters on the exam (table below) |
| 19:09 | baseline | `baseline --split practice` | 7.1 s | B0 and B1 with the default parameters on practice (table below) |
| 19:09 | calibrate B1 | `calibrate --model sentence-transformers/all-MiniLM-L6-v2 --out data/models/calibration-b1.json --no-web` | 6.4 s | temperature 0.0631, none_score 0.260, file 0.8696 (support 49), suggest 0.4016 (support 83); NLL 0.860 -> 0.787 |
| 19:09 | train | `train --epochs 2 --device mps` | 15.2 s (8.9 s of training) | 860 pairs from the 1103 lessons decisions (the 243 "none" answers give no pair), 28 batches/epoch, 56 steps, warm-up 5, lr 2e-5, batch 32; loss 3.815 -> 1.633 (mean 2.031); `data/models/student-v0/` 91.6 MB |
| 19:11 | calibrate B2 | `calibrate` | 2.7 s | temperature 0.0562, none_score 0.280, file 0.9092 (support 50), suggest 0.3762 (support 87); NLL 0.708 -> 0.695; writes `data/models/calibration.json` and the camelCase web copy |
| 19:11 | exam | `exam --run-id 2026-10-16-toy-v0 --b1-calibration data/models/calibration-b1.json` | 7.4 s | seal checked; table below; `data/runs/exam-2026-10-16-toy-v0.json` |
| 19:11 | export | `export --run-id 2026-10-16-toy-v0` | 3.9 s | `data/models/student-v0-onnx/` (below) |
| 19:14 | scoreboard | `scoreboard --run-id 2026-10-16-toy-v0 --notes ...` (six notes) | about 1 s (not timed) | `scoreboard/runs/2026-10-16-toy-v0.json`, label "toy scale" |
| 19:16 | bootstrap | `uv run python scripts/w6_bootstrap_cutoffs.py --model data/models/student-v0 --calibration data/models/calibration.json --resamples 200`, then the same with `--model sentence-transformers/all-MiniLM-L6-v2 --calibration data/models/calibration-b1.json` | 0.7 s and 0.8 s after model load | `data/runs/bootstrap-calibration.json`, `data/runs/bootstrap-calibration-b1.json` |
| 19:16 | buckets | `uv run python scripts/w6_history_buckets.py --run-id 2026-10-16-toy-v0 --b1-calibration data/models/calibration-b1.json` | about 1 min (not timed) | `data/runs/exam-2026-10-16-toy-v0-buckets.json` |
| 19:21 | board extras | `uv run python scripts/w6_board_extras.py --run-id 2026-10-16-toy-v0` | under 1 s | adds counts, calibration, teacher, student, export and bucket facts to the board JSON |
| 20:54 | parity texts | `uv run python -c "...export.fixture_texts(32)..."` | not timed | `data/runs/parity-texts.json`, the 32 texts `export` used (sha256 of the list `69f70cad...`) |
| 20:55 | B1b exam, defaults | `baseline --split exam --encoder mixedbread-ai/mxbai-embed-xsmall-v1 --out-dir data/runs/b1b` | 11.4 s (0.7 s of sorting) | first load downloads the encoder (48,100 KiB into the Hub cache, 27.6 s incl. download); table below |
| 20:55 | B1b practice, defaults | `baseline --split practice --encoder mixedbread-ai/mxbai-embed-xsmall-v1 --out-dir data/runs/b1b` | 8.3 s | table below |
| 20:55 | calibrate B1b | `calibrate --model mixedbread-ai/mxbai-embed-xsmall-v1 --out data/models/calibration-b1b.json --no-web` | 7.5 s | temperature 0.0631, none_score 0.260, file 0.8696 (support 47), suggest 0.3442 (support 85); NLL 0.838 -> 0.781 |
| 20:56 | B1b exam, calibrated | `baseline --split exam --encoder mixedbread-ai/mxbai-embed-xsmall-v1 --calibration data/models/calibration-b1b.json --out-dir data/runs/b1b-calibrated` | 7.8 s | the B1b row of the board |
| 20:56 | bootstrap B1b | `uv run python scripts/w6_bootstrap_cutoffs.py --model mixedbread-ai/mxbai-embed-xsmall-v1 --calibration data/models/calibration-b1b.json --resamples 200` | 0.8 s after load | `data/runs/bootstrap-calibration-b1b.json` |
| 20:57 | parity, Node | `node --input-type=module < scripts/w6_parity_node.mjs` (run from the `w5-web/web` checkout so `@huggingface/transformers` 4.3.0 resolves) | 0.94 s | `data/runs/parity-node-q8.json`, `parity-node-fp32.json` (vectors, token ids, 40 timings each) |
| 20:57 | parity, PyTorch | `uv run python scripts/w6_parity_torch.py` | 2.9 s | `data/runs/parity-torch.json` |
| 20:57 | follow-up toy | `followup-toy --device mps` | 6.9 s incl. two model loads | `data/runs/followup-toy.json` (1,040 practice pairs, 904 exam pairs) |
| 20:59 | parity, compare | `uv run python scripts/w6_parity_compare.py` | not timed | `data/runs/parity-summary.json` and the parity table (docs/parity.md) |
| 20:59 | follow-up, paired | `uv run python scripts/w6_followup_paired.py --device mps` | not timed | `data/runs/followup-toy-paired.json` (1,000 paired resamples) |
| 21:00 | follow-up, board | `uv run python scripts/w6_followup_board.py --run-id 2026-10-16-toy-v0` | under 1 s | `follow_up_toy` and its summary note on the board |
| 21:00 | B1b, board | `uv run python scripts/w6_second_encoder.py --run-id 2026-10-16-toy-v0 --encoder mixedbread-ai/mxbai-embed-xsmall-v1 --facts ...` | 18 s | re-runs B1 and B1b through `exam.run_encoder` (reproduces the CLI records exactly), per-decision analyses, B1b merged into the board |
| 21:12 | finalise | `uv run python scripts/w6_board_finalise.py --run-id 2026-10-16-toy-v0` | under 1 s | checks the contract and the extras; moved the follow-up object out of `notes`, added `export.parity_node` and the Node parity and site notes; 0 problems on re-run |

From the generator's exit (19:06) to the first finished board (19:21): 15 minutes, most of it
writing the three scripts; the pipeline commands themselves took under a minute together. The
three extras (parity in Node, B1b, the follow-up toy) ran 20:52-21:03 after the session's
usage-limit pause, and the board was finalised at 21:12.

### Baselines with the default parameters (temperature 0.05, none 0.30, file 0.85, suggest 0.55)

| split | sorter | accuracy | macro-F1 | none P / R | ECE | Brier | file P @ coverage | suggest P @ coverage | ms/decision | MB |
|---|---|---|---|---|---|---|---|---|---|---|
| exam | B0 always leave | 0.254 | 0.135 | 0.254 / 1.000 | 0.746 | 0.746 | - | - | 0.0 | 0 |
| exam | B1 all-MiniLM-L6-v2 | 0.649 | 0.629 | 0.656 / 0.724 | 0.152 | 0.207 | 0.833 @ 0.368 | 0.714 @ 0.614 | 4.8 | 91.6 |
| exam | B1b mxbai-embed-xsmall-v1 | 0.640 | 0.625 | 0.656 / 0.724 | 0.144 | 0.203 | 0.814 @ 0.377 | 0.697 @ 0.579 | 4.2 | 49.2 |
| practice | B0 always leave | 0.222 | 0.121 | 0.222 / 1.000 | 0.778 | 0.778 | - | - | 0.0 | 0 |
| practice | B1 all-MiniLM-L6-v2 | 0.726 | 0.678 | 0.512 / 0.808 | 0.122 | 0.172 | 0.923 @ 0.444 | 0.853 @ 0.581 | 4.9 | 91.6 |
| practice | B1b mxbai-embed-xsmall-v1 | 0.726 | 0.664 | 0.513 / 0.769 | 0.093 | 0.167 | 0.920 @ 0.427 | 0.864 @ 0.564 | 4.2 | 49.2 |

The uncalibrated B1 scores higher on the exam (0.649) than the calibrated one on the board
(0.632), and B1b likewise (0.640 against 0.614): fitting the none score on practice lowered it
from 0.30 to 0.26, so both say "none" less often (B1's none recall 0.724 -> 0.621, B1b's
0.724 -> 0.586), which costs them on this exam's 29 "none" answers. All three encoders were
calibrated the same way, so the comparison on the board is fair; the uncalibrated numbers stay in
`data/runs/baseline-exam.json` and `data/runs/b1b/`.

### Calibration on practice (117 decisions; toy scale)

Method (the CLI's): coordinate descent over temperature (geometric grid 0.01-1, 41 points) and
none score (0-1, 51 points) on the mean NLL of the right answer, then the smallest observed
p_top whose precision over the decisions at or above it is >= 0.95 (file) or >= 0.80 (suggest)
with at least 5 decisions. Research item 6 asks for temperature-only calibration with bootstrap
intervals and a "toy scale" label: the none score here is a constant, not a learned function,
so this is still temperature scaling of a fixed scorer; no isotonic or conformal step was run;
all three calibration files say "toy scale" in `source`. Bootstrap:
`scripts/w6_bootstrap_cutoffs.py`, 200 resamples with replacement of the 117 decisions, re-fitting
temperature and none score and re-choosing both cut-offs on each (the vectorised refit reproduces
the CLI's values on the full split); 90% interval = 5th to 95th percentile.

| quantity | B2 (student) | B2 90% interval | B1 (base encoder) | B1 90% interval | B1b (second encoder) | B1b 90% interval |
|---|---|---|---|---|---|---|
| temperature | 0.0562 | 0.0501-0.0631 | 0.0631 | 0.0562-0.0794 | 0.0631 | 0.0559-0.0712 |
| none score | 0.280 | 0.26-0.32 | 0.260 | 0.22-0.30 | 0.260 | 0.24-0.30 |
| file cut-off (re-chosen per resample) | 0.9092 | 0.6875-0.9366 | 0.8696 | 0.7112-0.9305 | 0.8696 | 0.7062-0.9344 |
| suggest cut-off (re-chosen per resample) | 0.3762 | 0.2089-0.5827 | 0.4016 | 0.2324-0.6127 | 0.3442 | 0.2623-0.6156 |
| precision at the file cut-off, on practice | 0.960 | 0.909-1.000 | 0.959 | 0.909-1.000 | 0.957 | 0.905-1.000 |
| coverage at the file cut-off | 0.427 | 0.350-0.504 | 0.419 | 0.342-0.488 | 0.393 | 0.324-0.462 |
| precision at the suggest cut-off | 0.805 | 0.732-0.866 | 0.807 | 0.728-0.868 | 0.800 | 0.723-0.864 |
| coverage at the suggest cut-off | 0.744 | 0.675-0.803 | 0.709 | 0.641-0.778 | 0.726 | 0.658-0.795 |

Both targets were reached on the full split and on all 200 resamples for all three encoders, but
the re-chosen file cut-off ranges from 0.69 to 0.94: the exact value is an artefact of which 117
decisions were drawn, and the exam agrees (file precision 0.861 for B2 and B1b and 0.838 for B1,
all under 0.95). The 95% / 80% figures hold on practice only.

### Sealed exam (114 decisions from 2 people; seal `7c3024b8...` checked by `exam`)

| id | name | accuracy | macro_f1 | none_precision | none_recall | ece | brier | file_precision | file_coverage | suggest_precision | suggest_coverage | latency_ms_per_decision | size_mb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | always leave | 0.254 | 0.135 | 0.254 | 1.000 | 0.746 | 0.746 | 0.000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.0 |
| B1 | base encoder, untrained (calibrated on practice) | 0.632 | 0.606 | 0.692 | 0.621 | 0.096 | 0.197 | 0.838 | 0.325 | 0.632 | 0.763 | 4.7 | 91.6 |
| B1b | second base encoder, untrained (mxbai-embed-xsmall-v1, calibrated on practice) | 0.614 | 0.594 | 0.708 | 0.586 | 0.104 | 0.195 | 0.861 | 0.316 | 0.600 | 0.789 | 4.1 | 49.2 |
| B2 | student v0 | 0.658 | 0.627 | 0.692 | 0.621 | 0.115 | 0.201 | 0.861 | 0.316 | 0.659 | 0.772 | 4.6 | 91.6 |
| B2q (not on the board) | student v0, int8 ONNX via onnxruntime on CPU | 0.658 | 0.627 | 0.692 | 0.621 | 0.134 | 0.200 | 0.842 | 0.333 | 0.659 | 0.772 | 0.9 | 23.0 |

Latency is the median over 100 single-chat decisions (batch of one plus the maths) on MPS on a
shared Mac; B2q's is the same measurement through onnxruntime on the CPU. `size_mb` is the
checkpoint on disk (B1b's 49.2 is a float16 file against MiniLM's float32 91.6, a storage format,
not a smaller model: 24.1M against 22.7M parameters; the int8 export of the student is 23.0 MB).

Accuracy by history length (validated chats the person already had; research item 13;
`scripts/w6_history_buckets.py` and `scripts/w6_second_encoder.py`):

| history length | n | B0 | B1 | B1b | B2 | B2q |
|---|---|---|---|---|---|---|
| <5 | 10 | 0.300 | 0.800 | 0.800 | 0.800 | 0.800 |
| 5-15 | 22 | 0.364 | 0.636 | 0.591 | 0.591 | 0.591 |
| >15 | 82 | 0.220 | 0.610 | 0.598 | 0.658 | 0.658 |

| answer type | n | B0 | B1 | B1b | B2 | B2q |
|---|---|---|---|---|---|---|
| bundle | 76 | 0.000 | 0.645 | 0.632 | 0.684 | 0.684 |
| loose | 9 | 0.000 | 0.556 | 0.556 | 0.556 | 0.556 |
| none | 29 | 1.000 | 0.621 | 0.586 | 0.621 | 0.621 |

| difficulty | n | B0 | B1 | B1b | B2 | B2q |
|---|---|---|---|---|---|---|
| long_gap | 9 | 0.000 | 0.556 | 0.556 | 0.778 | 0.778 |
| new_thread | 9 | 1.000 | 0.333 | 0.333 | 0.333 | 0.333 |
| nowhere | 20 | 1.000 | 0.750 | 0.700 | 0.750 | 0.750 |
| overlap | 11 | 0.000 | 0.545 | 0.545 | 0.545 | 0.545 |
| plain | 26 | 0.000 | 0.846 | 0.808 | 0.846 | 0.846 |
| typos | 17 | 0.000 | 0.882 | 0.882 | 0.882 | 0.882 |
| vague | 13 | 0.000 | 0.231 | 0.231 | 0.308 | 0.308 |
| very_short | 9 | 0.000 | 0.333 | 0.333 | 0.333 | 0.333 |

Paired bootstraps (1,000 resamples of the exam decisions, the same draws for both sorters):

- **B2 minus B1**: accuracy +0.0263, 90% interval -0.0175 to +0.0702, positive in 82% of
  resamples; macro-F1 +0.0213, 90% interval -0.0136 to +0.0627. McNemar counts: B2 right and B1
  wrong 5, B1 right and B2 wrong 2, both right 70, both wrong 37.
- **B1b minus B1** (both calibrated): accuracy -0.0175, 90% interval -0.0351 to 0.0, positive in
  0% of resamples; macro-F1 -0.0113, 90% interval -0.0302 to +0.0034. McNemar: B1b right and B1
  wrong 0, B1 right and B1b wrong 2; the two agree on 110 of 114 decisions (96.5%). With the
  default parameters: -0.0088 (one decision), McNemar 0 against 1.

### The second base encoder, B1b (relay extra 2; research item 3)

`mixedbread-ai/mxbai-embed-xsmall-v1`, R2's challenger (docs/research/student-and-method.md,
recommendation 3). Hub API, read 20:52 (`curl -s
https://huggingface.co/api/models/mixedbread-ai/mxbai-embed-xsmall-v1`): `gated: false`,
`private: false`, licence tag `apache-2.0`, `model.safetensors` 48,190,272 bytes, so the relay's
three gates (not gated, Apache-2.0 or MIT, ONNX weights that work with Transformers.js) and the
150 MB download cap all pass; the "24.4 MB" R2 quotes is its `onnx/model_int8.onnx` (24,448,010
bytes), and the repository also ships `onnx/model.onnx` (96,025,279) and `onnx/model_quantized.onnx`
(24,448,010). The checkpoint is stored as float16, 24,089,472 parameters, 6 layers, hidden 384,
`max_position_embeddings` 4,096, mean pooling, both prompts empty, the same 30,522-piece uncased
vocabulary as MiniLM. Download, by the first load at 20:53: Hub cache 89,480 -> 137,580 KiB
(+48,100 KiB; the snapshot holds 49,218,165 bytes: the safetensors, `tokenizer.json` 711,661,
`vocab.txt` 231,508, `README.md` 81,201 and six small configs; no onnx/, gguf/ or openvino/ file),
`df` available 16,442,972 -> 16,378,060 KiB. Nothing else was downloaded today.

Reading: B1b is a near twin of B1 on this exam, one or two decisions behind and never ahead; the
order on the board is B2 0.658 > B1 0.632 > B1b 0.614 and the winner line is unchanged. Two
checks on the encoder itself: it runs as stored, float16 on MPS, while MiniLM runs in float32;
against a float32 copy on the CPU its vectors have min cosine 0.999998 (mean 1.0) over the exam's
114 distinct texts and the same prediction on 100% of decisions, so the dtype changes nothing
here. Token lengths with its tokenizer: the exam's 114 distinct texts are at most 22 word pieces
(mean 12.3), practice's 117 at most 46 (mean 16.2), so the 128-piece truncation in
`encoder.Encoder` cuts nothing and the 4,096-token context, R2's main argument for this encoder,
cannot show on this data: the teacher writes one short opening message per chat. Research item
3's "decide how a chat is cut" is moot at this scale and returns when chats carry several turns.
Recommendation: keep MiniLM as the v0 base and B1b as the challenger on the board. Details:
`data/runs/b1b-2026-10-16-toy-v0.json`, `data/runs/b1b/`, `data/runs/b1b-calibrated/`,
`data/models/calibration-b1b.json`, `data/runs/bootstrap-calibration-b1b.json`, and the board's
`second_encoder` block.

### Export and parity: PyTorch, onnxruntime and Transformers.js in Node

`pipeline/data/models/student-v0-onnx/`, Transformers.js layout:

| file | bytes |
|---|---|
| `config.json` | 745 |
| `tokenizer.json` | 711,649 |
| `tokenizer_config.json` | 593 |
| `special_tokens_map.json` | 125 |
| `onnx/model.onnx` (fp32) | 90,382,557 |
| `onnx/model_quantized.onnx` (int8, dynamic, per-channel) | 22,977,287 |
| `manifest.json` (`id` student-v0, `dtype` q8, `size_bytes` 22977287, `base_model`, `run_id`) | 215 |
| `export_report.json` | 1,058 |

Exporter `torch.onnx.export(dynamo=False)`, opset 14; torch 2.14.1, onnx 1.23.1, onnxruntime
1.30.0; export 0.3 s, quantisation 0.6 s. The relay asks for cosine >= 0.999 between PyTorch and
the browser runtime on 32 fixture texts, or the gap recorded; research item 4 says to keep 0.999
as the fp32 bar and to judge int8 by its exam effect. Measured, on the same 32 texts
(`export.fixture_texts(32)`: the fixture's 25 chats, 6 thread descriptions and the first persona):

| comparison | fp32 min cosine | int8 min cosine | int8 median / mean | texts >= 0.999 (int8) |
|---|---|---|---|---|
| PyTorch vs Python onnxruntime 1.30.0 (`export_report.json`, 19:11) | 0.99999994 | 0.99153 (worst text 8, "hi") | - / 0.99752 | not counted |
| PyTorch (CPU) vs Transformers.js 4.3.0 in Node v24.21.0, onnxruntime-node 1.30.0, CPU (docs/parity.md, 20:57) | 1.00000000 (max element difference 2.5e-7) | 0.99153044 (worst text 8) | 0.99782964 / 0.99752311 | 0 of 32 |

So **fp32 meets the bar in both runtimes and int8 misses it in both by the same amount**: the
loss is the dynamic int8 quantisation, not the JavaScript runtime, which reproduces Python
onnxruntime to five decimals. Token ids are identical on all 32 texts (BertTokenizer, lower-casing,
`model_max_length` 128). Two things the Node run showed that `export_report.json` could not:
int8 vectors depend on the batch shape (the same text embedded alone and in a padded batch of 32
has self-cosine min 0.9924, median 0.9982; fp32 gives identical vectors either way), which
matters because the site embeds its library in batches of 32 and a live chat alone; and the
dtype-to-file mapping of Transformers.js 4.3.0, verified in its source and at run time: `q8` opens
`onnx/model_quantized.onnx`, `fp32` opens `onnx/model.onnx`, and `int8`, `fp16` or `q4` fail with a
file-not-found error, so `manifest.json`'s `dtype` "q8" is the right string. Latency in Node, 40
single decisions on the CPU: q8 median 1.64 ms (min 0.59, p90 2.74, max 5.78), fp32 1.66 ms;
loading q8 108 ms, fp32 72 ms; PyTorch on the CPU 5.11 ms median. Judged by the exam effect, the
int8 model (through onnxruntime) made the same prediction as the PyTorch student on all 114 exam
decisions: accuracy and macro-F1 unchanged, ECE 0.115 -> 0.134, Brier 0.201 -> 0.200, file
precision 0.861 -> 0.842 because one more decision crossed the 0.9092 cut-off wrongly (coverage
0.316 -> 0.333), at 0.9 ms per decision on the CPU. The browser itself (onnxruntime-web on WASM or
WebGPU) was not measured; the same `.onnx` bytes run there, but the WASM kernels can differ in the
last bits (NOT VERIFIED). The gap is recorded on the board (`export.parity`,
`export.parity_node`, `int8_exam_effect` and two notes).

### The follow-up toy (relay extra 3; docs/follow-up-toy.md)

The second question, at toy scale and without a model trained for it: given a new chat and one
chat the person opened earlier, is the new chat a follow-up? Each pair is scored by the cosine of
the two chats' vectors, with the base encoder (B1's weights) and with the student (B2's), and one
threshold fit on the practice pairs (highest accuracy) turns the cosine into yes or no. Pairs stay
inside one person; a positive is (chat, an earlier chat of the same thread), a negative (chat, an
earlier chat of another thread) or (chat, an earlier loose chat), balanced and anchor-matched where
possible, seed 3, cap 2,000 not reached: practice 1,040 pairs (520 / 520; negatives 395 other
thread, 125 loose), exam 904 (452 / 452; 342 / 110). Chance accuracy is 0.500. The exam seal was
not touched: pairs are read from `exam.jsonl`, nothing is written to `splits/`.

| encoder | practice AUC | threshold | exam AUC | accuracy | precision | recall | F1 | oracle accuracy |
|---|---|---|---|---|---|---|---|---|
| base encoder | 0.788 | 0.1941 | 0.735 [0.711, 0.756] | 0.678 [0.654, 0.701] | 0.688 [0.653, 0.725] | 0.653 [0.620, 0.687] | 0.670 | 0.689 |
| student v0 | 0.816 | 0.1882 | 0.752 [0.728, 0.774] | 0.690 [0.667, 0.713] | 0.681 [0.646, 0.712] | 0.715 [0.680, 0.747] | 0.698 | 0.697 |

Brackets are 90% bootstrap intervals (200 resamples of the 904 exam pairs). Recall of follow-ups
by gap in days (0-7 / 8-44 / 45+; n 75 / 178 / 199): base 0.720 / 0.646 / 0.633, student 0.773 /
0.691 / 0.714. Negatives rejected: other thread (342) base 0.655, student 0.617; loose (110) 0.855
against 0.818. Student minus base, paired (1,000 resamples): accuracy +0.012 (11 pairs), 90%
interval -0.001 to +0.027, positive in 91%; AUC +0.017, 90% interval +0.011 to +0.023, positive in
100%; McNemar 34 against 23. Reading: a cosine threshold answers the toy question right about two
times in three; the student, trained only for the first question, ranks follow-up pairs a little
better and finds more of them, most clearly at gaps of 45+ days, at the cost of rejecting fewer
chats from the person's other threads. A direction, not a result; the floor a real follow-up model
has to beat.

### The board file

`scoreboard/runs/2026-10-16-toy-v0.json` (39,231 bytes after finalising): `label` "toy scale",
`exam_hash` `7c3024b8...`, `base_model` sentence-transformers/all-MiniLM-L6-v2, four sorters (B0,
B1, B1b, B2) with exactly the fourteen contract keys, and 24 notes, all text; the last note is the
rule's winner line, the one before it says what the site actually uses. The W6 scripts add, as
extra top-level keys a strict reader can ignore: `people`, `chats`, `examples` (per split by
answer type), `calibration` (B2, B1 and B1b with the bootstrap intervals), `teacher`
(Qwen3-4B-Instruct-2507, the GGUF file, licence Apache-2.0, prompt v0.2, seed 42, the totals from
generate.log), `student` (train_meta.json), `export` (files, `parity` against onnxruntime,
`parity_node` against Transformers.js), `accuracy_by_history`, `accuracy_by_answer_type`,
`accuracy_by_difficulty`, `b2_minus_b1`, `int8_exam_effect`, `second_encoder` and `follow_up_toy`.
`scripts/w6_board_finalise.py` checks all of it (contract keys, values against the exam records,
the seal, counts that add up, calibration for every encoder, the teacher block, the notes) and
exits non-zero on a gap; `scoreboard/README.md` at the repository root describes the format. The
camelCase web copy of B2's calibration that `calibrate` wrote is kept at
`pipeline/data/models/calibration-web-student-v0.json` (gitignored), not in `web/`, because the
site keeps B1 and `web/src/sorter/calibration.json` on main holds B1's values (below).

## Verdict: does B2 beat B1?

Rule used (the one `scoreboard.winner_note` applies): B2 beats B1 when its exam accuracy is
higher and its macro-F1 is not lower. B2 0.658 against B1 0.632 accuracy and 0.627 against
0.606 macro-F1: by the rule B2 wins, and the board's last line says "wire B2 into the site through
the manifest". The honest reading: that is 75 against 72 right answers out of 114, five decisions
B2 alone gets right against two for B1, a 90% interval on the difference that includes zero, and
82% of resamples in B2's favour. The gain is all in bundle answers (0.645 -> 0.684) for people
with more than 15 earlier chats (0.610 -> 0.658); the 5-15 bucket lost one decision (0.636 ->
0.591, n 22), the under-5 bucket is unchanged (0.800, n 10), and "none" precision and recall are
identical (0.692 / 0.621) because training uses only chats that belong somewhere and "none" stays
a constant score. B2's ECE is worse (0.115 against 0.096). The two difficulty labels the student
improved are `long_gap` (0.556 -> 0.778, n 9) and `vague` (0.231 -> 0.308, n 13), both tiny. The
follow-up toy points the same way with a tighter interval (AUC +0.017, every paired resample
positive), but on the same two exam people. Taken together: training moved the exam in the
expected direction and nothing contradicts the student; nothing yet proves it either.

## What the site uses

The demo site keeps B1, the untrained base encoder (`Xenova/all-MiniLM-L6-v2` from the Hub,
`web/src/sorter/model-manifest.json`), with B1's calibration from this run (temperature 0.0631,
none score 0.26, file cut-off 0.8696, suggest cut-off 0.4016; `web/src/sorter/calibration.json`,
applied in the W5 pull request). Decision of 2026-10-16 in docs/DECISIONS.md: a lead of 3 of 114
decisions inside the bootstrap interval is not a result, and a shipped student needs a hosted
23 MB model file, which the repository's 5 MB rule forbids. Both belong to BDL-4. If and when B2
is wired in: `id` `student-v0`, `source` `local`, `dtype` `q8`, `sizeMB` 22.98, the four files
`config.json`, `tokenizer.json`, `tokenizer_config.json`, `onnx/model_quantized.onnx` under
`web/public/models/student-v0/` (the directory name must equal the id; the export directory is
`student-v0-onnx`), then `npm run precompute` again (docs/parity.md).

## What the toy proves, and what it does not

It proves that the loop runs end to end on this Mac on the day's data: teacher, validation, a
sealed exam whose seal holds, every contract metric computed and landed on a board, a student
whose loss falls (3.815 -> 1.633) and whose exam moves in the expected direction, calibration
that reaches both precision targets on practice with intervals that say how loose they are, an
export that loads in the browser runtime with fp32 parity to the last bit and int8 that changes no
exam decision, a second encoder checked and placed on the board through the same path, and a
second question asked of the same models.

It does not prove a real improvement from training (two exam people, one 4B teacher, one prompt
version, 55 minutes of generation), stable cut-offs (the file cut-off's 90% interval spans
0.69-0.94 for every encoder), out-of-distribution behaviour (the exam people share the teacher
and the prompt with the lessons people), a "none" detector worth the name (recall 0.62 for B1
and B2, 0.59 for B1b; research items 5 and 14), anything about long chats (no text exceeds 46
word pieces, so the 4,096-token challenger cannot differ), or int8 parity to 0.999 (0.9915 in
both runtimes; the browser's WASM kernels unmeasured). Recommendation: keep the board as it
stands, labelled toy scale; keep B1 on the site; answer the question on the Spark with thousands
of practice chats.

## Open points

1. The B2-B1 lead (3 of 114) is inside the bootstrap interval; the real answer needs the Spark run.
2. int8 parity misses 0.999 in every runtime on this stack (0.99153); judged by the exam effect
   it is harmless here. A static-quantised or fp16 export could be tried on the Spark.
3. int8 vectors depend on the batch shape (self-cosine min 0.9924); the site precomputes its
   library in batches of 32 and embeds live chats alone. Embed both the same way, or both alone.
4. Browser parity (onnxruntime-web on WASM or WebGPU) was not measured; Node used onnxruntime-node
   1.30.0 on the CPU.
5. The export directory is `student-v0-onnx` while the manifest id is `student-v0`; the web copy
   must make them agree.
6. "none" is a constant score; recall 0.59-0.62 for every encoder. Research items 5 and 14 (a
   learned none logit, a written out-of-scope set) are the fix.
7. The calibrated baselines score lower than the default ones on this exam because the fitted
   none score (0.26) says "none" less often; the choice of fitting the none score on practice is
   worth revisiting when practice has more than two people.
8. Wiring B2 into the site (a hosted 23 MB file, the manifest, precompute) is BDL-4's.
