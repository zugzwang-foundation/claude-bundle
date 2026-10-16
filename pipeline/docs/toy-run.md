# Toy run (BDL-3, W3): the real generation on this Mac

Started 2026-10-16 18:11 IST (2026-10-16T12:41:48Z) from `pipeline/` on branch `bdl-3-pipeline`.

## Command

```
cd /Users/hrishikesh/Developer/claude-bundle/.claude/worktrees/w3-pipeline/pipeline
nohup uv run bundle-pipeline generate --people 24 --chats-per-person 60 --seed 42 \
  --out data/raw/people --workers 4 --time-budget-min 55 > data/generate.nohup.log 2>&1 &
```

- PID: 25538
- Teacher: llama-server 0.5.0 at http://127.0.0.1:8081/v1, Qwen3-4B-Instruct-2507 Q4_K_M
  (`-np 4`, Metal), see docs/toy-teacher.md.
- Prompts: v0.2 (strict JSON schemas via `response_format: json_schema`; see prompts.py).
- Logs: `data/generate.nohup.log` (stdout/stderr), `data/generate.log` (one line per person).
- Idempotent: rerunning the same command skips people already on disk.

## Why 24 people

The relay asks for about 24 people of about 60 chats within 60 minutes. The teacher report
(docs/toy-teacher.md) estimated 2 h for 24 x 60 at 4 concurrent slots and recommended 10 people
for 55 minutes; the smoke run measured 18.2 chats/min on a single stream while other agents loaded
the Mac. `--time-budget-min 55` stops starting new people after 55 minutes (+5 min grace for
people in flight), so asking for 24 costs nothing extra: the run writes whatever finishes, and
W6 runs on what exists at the deadline. The split is by person-id hash, so a partial run still
gives lessons/practice/exam.

## Smoke run before it (data/smoke, 1 person, 20 chats, seed 1)

- First attempt with prompts v0.1 failed: the 4B model returned `{"day": 3}` entries without
  `text` (3 completions, all invalid). Fix: strict JSON schemas sent as
  `response_format: {"type": "json_schema", ...}`, which llama-server compiles to a grammar
  (probed and verified 2026-10-16), plus a numbered difficulty list in the prompt.
- Second attempt (v0.2): 1 person, 3 threads, 20 chats, 5 calls, 5 completions (no retries),
  66 s, 18.2 chats/min, 11.6 tok/s, 766 completion tokens, 2131 prompt tokens.
- validate: 20 -> 20 chats, 0 exact / 0 near duplicates. split: 1 person -> lessons (practice and
  exam empty, as expected with one person). tasks: 20 examples, answers none 9 / loose 3 / bundle
  8, candidates mean 5.7 max 9.

## Throughput watch

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

## Results (W6, 2026-10-16, toy scale)

Times are IST unless marked Z. Every number below was measured in this run; nothing is filled
from memory. Branch `bdl-3-student`, worktree `w3-pipeline`, `uv run` on CPython 3.14.8.

### Generation outcome

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
| 19:11 | calibrate B2 | `calibrate` | 2.7 s | temperature 0.0562, none_score 0.280, file 0.9092 (support 50), suggest 0.3762 (support 87); NLL 0.708 -> 0.695; writes `data/models/calibration.json` and `web/src/sorter/calibration.json` |
| 19:11 | exam | `exam --run-id 2026-10-16-toy-v0 --b1-calibration data/models/calibration-b1.json` | 7.4 s | seal checked; table below; `data/runs/exam-2026-10-16-toy-v0.json` |
| 19:11 | export | `export --run-id 2026-10-16-toy-v0` | 3.9 s | `data/models/student-v0-onnx/` (below) |
| 19:14 | scoreboard | `scoreboard --run-id 2026-10-16-toy-v0 --notes ...` (six notes) | about 1 s (not timed) | `scoreboard/runs/2026-10-16-toy-v0.json`, label "toy scale" |
| 19:16 | bootstrap | `uv run python scripts/w6_bootstrap_cutoffs.py --model data/models/student-v0 --calibration data/models/calibration.json --resamples 200`, then the same with `--model sentence-transformers/all-MiniLM-L6-v2 --calibration data/models/calibration-b1.json` | 0.7 s and 0.8 s after model load | `data/runs/bootstrap-calibration.json`, `data/runs/bootstrap-calibration-b1.json` |
| 19:16 | buckets | `uv run python scripts/w6_history_buckets.py --run-id 2026-10-16-toy-v0 --b1-calibration data/models/calibration-b1.json` | about 1 min (not timed) | `data/runs/exam-2026-10-16-toy-v0-buckets.json` |
| 19:21 | board extras | `uv run python scripts/w6_board_extras.py --run-id 2026-10-16-toy-v0` | under 1 s | adds counts, calibration, teacher, student, export and bucket facts to the board JSON |

From the generator's exit (19:06) to the finished board (19:21): 15 minutes, most of it
writing the three scripts; the pipeline commands themselves took under a minute together.

### Baselines with the default parameters (temperature 0.05, none 0.30, file 0.85, suggest 0.55)

| split | sorter | accuracy | macro-F1 | none P / R | ECE | Brier | file P @ coverage | suggest P @ coverage | ms/decision | MB |
|---|---|---|---|---|---|---|---|---|---|---|
| exam | B0 always leave | 0.254 | 0.135 | 0.254 / 1.000 | 0.746 | 0.746 | - | - | 0.0 | 0 |
| exam | B1 base encoder | 0.649 | 0.629 | 0.656 / 0.724 | 0.152 | 0.207 | 0.833 @ 0.368 | 0.714 @ 0.614 | 4.8 | 91.6 |
| practice | B0 always leave | 0.222 | 0.121 | 0.222 / 1.000 | 0.778 | 0.778 | - | - | 0.0 | 0 |
| practice | B1 base encoder | 0.726 | 0.678 | 0.512 / 0.808 | 0.122 | 0.172 | 0.923 @ 0.444 | 0.853 @ 0.581 | 4.9 | 91.6 |

The uncalibrated B1 scores higher on the exam (0.649) than the calibrated one on the board
(0.632): fitting the none score on practice lowered it from 0.30 to 0.26, so B1 says "none" less
often (none recall 0.724 -> 0.621), which costs it on this exam's 29 "none" answers. Both
encoders were calibrated the same way, so the B1-B2 comparison on the board is fair; the
uncalibrated numbers stay in `data/runs/baseline-exam.json`.

### Calibration on practice (117 decisions; toy scale)

Method (the CLI's): coordinate descent over temperature (geometric grid 0.01-1, 41 points) and
none score (0-1, 51 points) on the mean NLL of the right answer, then the smallest observed
p_top whose precision over the decisions at or above it is >= 0.95 (file) or >= 0.80 (suggest)
with at least 5 decisions. Research item 6 asks for temperature-only calibration with bootstrap
intervals and a "toy scale" label: the none score here is a constant, not a learned function,
so this is still temperature scaling of a fixed scorer; no isotonic or conformal step was run;
both calibration files now say "toy scale" in `source`. Bootstrap:
`scripts/w6_bootstrap_cutoffs.py`, 200 resamples with replacement of the 117 decisions, re-fitting
temperature and none score and re-choosing both cut-offs on each (the vectorised refit reproduces
the CLI's values on the full split); 90% interval = 5th to 95th percentile.

| quantity | B2 (student) | B2 90% interval | B1 (base encoder) | B1 90% interval |
|---|---|---|---|---|
| temperature | 0.0562 | 0.0501-0.0631 | 0.0631 | 0.0562-0.0794 |
| none score | 0.280 | 0.26-0.32 | 0.260 | 0.22-0.30 |
| file cut-off (re-chosen per resample) | 0.9092 | 0.6875-0.9366 | 0.8696 | 0.7112-0.9305 |
| suggest cut-off (re-chosen per resample) | 0.3762 | 0.2089-0.5827 | 0.4016 | 0.2324-0.6127 |
| precision at the file cut-off, on practice | 0.960 | 0.909-1.000 | 0.959 | 0.909-1.000 |
| coverage at the file cut-off | 0.427 | 0.350-0.504 | 0.419 | 0.342-0.488 |
| precision at the suggest cut-off | 0.805 | 0.732-0.866 | 0.807 | 0.728-0.868 |
| coverage at the suggest cut-off | 0.744 | 0.675-0.803 | 0.709 | 0.641-0.778 |

Both targets were reached on the full split and on all 200 resamples, but the re-chosen file
cut-off ranges from 0.69 to 0.94: the exact value is an artefact of which 117 decisions were
drawn, and the exam agrees (file precision 0.861 for B2 and 0.838 for B1, both under 0.95). The
95% / 80% figures hold on practice only.

### Sealed exam (114 decisions from 2 people; seal `7c3024b8...` checked by `exam`)

| id | name | accuracy | macro_f1 | none_precision | none_recall | ece | brier | file_precision | file_coverage | suggest_precision | suggest_coverage | latency_ms_per_decision | size_mb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | always leave | 0.254 | 0.135 | 0.254 | 1.000 | 0.746 | 0.746 | 0.000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.0 |
| B1 | base encoder, untrained (calibrated on practice) | 0.632 | 0.606 | 0.692 | 0.621 | 0.096 | 0.197 | 0.838 | 0.325 | 0.632 | 0.763 | 4.7 | 91.6 |
| B2 | student v0 | 0.658 | 0.627 | 0.692 | 0.621 | 0.115 | 0.201 | 0.861 | 0.316 | 0.659 | 0.772 | 4.6 | 91.6 |
| B2q (not on the board) | student v0, int8 ONNX via onnxruntime on CPU | 0.658 | 0.627 | 0.692 | 0.621 | 0.134 | 0.200 | 0.842 | 0.333 | 0.659 | 0.772 | 0.9 | 23.0 |

Latency is the median over 100 single-chat decisions (batch of one plus the maths) on MPS on a
shared Mac; B2q's is the same measurement through onnxruntime on the CPU. `size_mb` is the
checkpoint on disk (the int8 export is 23.0 MB).

Accuracy by history length (validated chats the person already had; `scripts/w6_history_buckets.py`):

| history length | n | B0 | B1 | B2 | B2q |
|---|---|---|---|---|---|
| <5 | 10 | 0.300 | 0.800 | 0.800 | 0.800 |
| 5-15 | 22 | 0.364 | 0.636 | 0.591 | 0.591 |
| >15 | 82 | 0.220 | 0.610 | 0.658 | 0.658 |

| answer type | n | B0 | B1 | B2 | B2q |
|---|---|---|---|---|---|
| bundle | 76 | 0.000 | 0.645 | 0.684 | 0.684 |
| loose | 9 | 0.000 | 0.556 | 0.556 | 0.556 |
| none | 29 | 1.000 | 0.621 | 0.621 | 0.621 |

| difficulty | n | B0 | B1 | B2 | B2q |
|---|---|---|---|---|---|
| long_gap | 9 | 0.000 | 0.556 | 0.778 | 0.778 |
| new_thread | 9 | 1.000 | 0.333 | 0.333 | 0.333 |
| nowhere | 20 | 1.000 | 0.750 | 0.750 | 0.750 |
| overlap | 11 | 0.000 | 0.545 | 0.545 | 0.545 |
| plain | 26 | 0.000 | 0.846 | 0.846 | 0.846 |
| typos | 17 | 0.000 | 0.882 | 0.882 | 0.882 |
| vague | 13 | 0.000 | 0.231 | 0.308 | 0.308 |
| very_short | 9 | 0.000 | 0.333 | 0.333 | 0.333 |

Paired bootstrap (1,000 resamples of the exam decisions, the same draws for both sorters):
B2 minus B1 = +0.0263 accuracy, 90% interval -0.0175 to +0.0702, positive in 82% of resamples;
macro-F1 +0.0213, 90% interval -0.0136 to +0.0627. McNemar counts: B2 right and B1 wrong 5,
B1 right and B2 wrong 2, both right 70, both wrong 37.

### Export (`pipeline/data/models/student-v0-onnx/`, Transformers.js layout)

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
1.30.0; export 0.3 s, quantisation 0.6 s. Parity, PyTorch vs onnxruntime on 32 fixture texts,
min cosine: **fp32 0.99999994** (mean 1.0), **int8 0.99153** (mean 0.99752, worst text index 8).
fp32 meets the 0.999 bar; int8 does not (`int8_meets_target: false`), the same gap W3 measured
on the base encoder (0.994). Judged by the exam effect, as research item 4 asks: the int8 model
made the same prediction as the PyTorch student on all 114 exam decisions (accuracy and
macro-F1 unchanged; ECE 0.115 -> 0.134, Brier 0.201 -> 0.200; file precision 0.861 -> 0.842
because one more decision crossed the 0.9092 cut-off wrongly, coverage 0.316 -> 0.333), at
0.9 ms per decision on the CPU through onnxruntime. The Transformers.js (Node) comparison is a
separate task and was not run here.

### Scoreboard

`scoreboard/runs/2026-10-16-toy-v0.json` (17.4 KB): `label` "toy scale", `exam_hash`
`7c3024b8...`, `base_model` sentence-transformers/all-MiniLM-L6-v2, the three sorters with
exactly the fourteen contract keys, and notes. `scripts/w6_board_extras.py` adds, as extra
top-level keys a strict reader can ignore: `people`, `chats`, `examples` (per split by answer
type), `calibration` (B2 and B1 with the bootstrap intervals), `teacher` (Qwen3-4B-Instruct-2507,
the GGUF file, licence Apache-2.0, prompt v0.2, seed 42, the totals from generate.log),
`student` (train_meta.json), `export` (files, parity), `accuracy_by_history`,
`accuracy_by_answer_type`, `accuracy_by_difficulty`, `b2_minus_b1`, `int8_exam_effect`; the same
facts are repeated as notes, absolute paths are made repository-relative, and the winner line
stays last. The web copy `web/src/sorter/calibration.json` carries B2's parameters with `model`
"student-v0" (the manifest id; the CLI had written the local checkpoint path) and "toy scale" in
`source`.

### Does B2 beat B1, and what the toy scale shows

Rule used (the one `scoreboard.winner_note` applies): B2 beats B1 when its exam accuracy is
higher and its macro-F1 is not lower. B2 0.658 against B1 0.632 accuracy and 0.627 against
0.606 macro-F1: by the rule B2 wins, and the board says "wire B2 into the site through the
manifest". The honest reading: that is 75 against 72 right answers out of 114, five decisions
B2 alone gets right against two for B1, a 90% interval on the difference that includes zero,
and 82% of resamples in B2's favour. The gain is all in bundle answers (0.645 -> 0.684) for
people with more than 15 earlier chats (0.610 -> 0.658); the 5-15 bucket lost one decision
(0.636 -> 0.591, n 22), the under-5 bucket is unchanged (0.800, n 10), and "none" precision and
recall are identical (0.692 / 0.621) because training uses only chats that belong somewhere and
"none" stays a constant score. B2's ECE is worse (0.115 against 0.096). The two difficulty
labels the student improved are `long_gap` (0.556 -> 0.778, n 9) and `vague` (0.231 -> 0.308,
n 13), both tiny. What the toy scale does show: the loop runs end to end on this Mac on the
day's data; the exam seal holds; every contract metric is computed and lands on a board;
training moves the loss and the exam in the expected direction; the int8 export changes no exam
decision. What it does not show: a real improvement from training (two exam people, one 4B
teacher, one prompt version, 55 minutes of generation), stable cut-offs (the file cut-off's 90%
interval spans 0.69-0.94), out-of-distribution behaviour (the exam people share the teacher and
the prompt with the lessons people), or a "none" detector worth the name (recall 0.62 for both
encoders; research items 5 and 14). Recommendation: keep the board as it stands, labelled toy
scale, treat the site wiring as an open point for Hrishikesh rather than read a three-decision
lead as a result, and answer the question on the Spark with thousands of practice chats.

## What the site uses, and what was not finished (added 20:55 IST)
The demo site keeps B1 (the untrained base encoder) with B1's calibration from this run (temperature 0.0631, none score 0.26, file cut-off 0.870, suggest cut-off 0.402). B2 beats B1 by the stated rule, but by 3 of 114 exam decisions, inside the 90% bootstrap interval of the difference; and shipping the student needs a hosted 23 MB file, which the repository's 5 MB rule forbids. Both belong to BDL-4. The Node/Transformers.js parity check, the second encoder (B1b) and the follow-up toy were interrupted by the session pause and are not on this board.
