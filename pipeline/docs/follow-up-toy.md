# The second question at toy scale: "is this a follow-up to that chat?"

Written 2026-10-16 (BDL-3, relay extra 3). Every number below was measured in this run on the
day's data; nothing is filled from memory. Branch `bdl-3-student`, worktree `w3-pipeline`,
`uv run` on CPython 3.14.8, MPS. Label: **toy scale** (two people per split).

## What was asked

Bundle's first question is "which bundle does this chat belong to?" (the sorter on the board).
The second question looks at one earlier chat instead of a bundle: given a new chat and one chat
the person opened before it, is the new chat a follow-up to that one? This is the toy version:
no model is trained for it; each pair is scored by the cosine of the two chats' vectors, once with
the base encoder (`sentence-transformers/all-MiniLM-L6-v2`) and once with the student trained
for the first question (`data/models/student-v0`), and one threshold turns the cosine into yes/no.

## Method (`src/bundle_pipeline/followup_toy.py`, `bundle-pipeline followup-toy`)

- **Pairs.** From the people of a split (`splits/<split>.jsonl`), every (later chat, earlier chat)
  pair inside one person, "earlier" by day order (file order on equal days). A **positive** is
  (chat, an earlier chat of the same thread). A **negative** is (chat, an earlier chat of another
  thread) or (chat, an earlier loose chat of the same person). Balanced: every positive gets one
  negative with the same later chat when one is left (so the negative shares the anchor's text
  and history), otherwise one from the remaining negatives; draws come from `random.Random(seed)`
  over pairs listed in a fixed order (seed 3, the pipeline default), so the same seed gives the
  same pairs; cap 2,000 pairs per split (not reached).
- **Score.** cosine(chat, earlier) from the encoder's normalised vectors.
- **Threshold.** The cut (follow-up when cosine >= t) with the highest accuracy on the
  **practice** pairs (middle candidate on ties), applied unchanged to the **exam** pairs. The
  best cut on the exam itself is reported only as an "oracle" figure.
- **Metrics.** ROC-AUC (rank based, ties get the average rank; checked against scikit-learn in
  the tests), accuracy, precision and recall for "follow-up" at the practice threshold, 90%
  bootstrap intervals (percentiles 5 and 95 over 200 resamples of the exam pairs), recall by day
  gap, and the share of each negative kind correctly rejected. `scripts/w6_followup_paired.py`
  adds a paired bootstrap of student minus base (1,000 resamples, the same draws for both).

## Pairs built

| split | people | pairs | follow-ups | not follow-ups | of which other thread | of which loose |
|---|---|---|---|---|---|---|
| practice (threshold) | 2 (p42-001, p42-015) | 1,040 | 520 | 520 | 395 | 125 |
| exam (judged) | 2 (p42-000, p42-022) | 904 | 452 | 452 | 342 | 110 |

All 452 exam positives and all 520 practice positives were used (the cap of 1,000 per class was
not reached). Chance accuracy is 0.500 by construction.

## Results (exam pairs, threshold fit on practice)

| encoder | practice AUC | threshold | exam AUC | accuracy | precision | recall | F1 | oracle accuracy |
|---|---|---|---|---|---|---|---|---|
| base encoder (B1's weights) | 0.788 | 0.1941 | 0.735 | 0.678 | 0.688 | 0.653 | 0.670 | 0.689 (cut 0.1490) |
| student v0 (B2's weights) | 0.816 | 0.1882 | 0.752 | 0.690 | 0.681 | 0.715 | 0.698 | 0.697 (cut 0.2017) |

90% bootstrap intervals (200 resamples of the 904 exam pairs):

| encoder | AUC | accuracy | precision | recall |
|---|---|---|---|---|
| base | 0.711 - 0.756 | 0.654 - 0.701 | 0.653 - 0.725 | 0.620 - 0.687 |
| student | 0.728 - 0.774 | 0.667 - 0.713 | 0.646 - 0.712 | 0.680 - 0.747 |

Confusion counts at the practice threshold (follow-up = positive): base TP 295, FP 134, FN 157,
TN 318; student TP 323, FP 151, FN 129, TN 301. Mean cosine of positives / negatives: base
0.294 / 0.143, student 0.325 / 0.165. Accuracy on practice at the fitted cut: base 0.720,
student 0.741 (the exam is 4-5 points lower for both: the cut is tuned to two other people).

Recall of follow-ups by gap in days between the two chats, and share of negatives rejected:

| | n | base | student |
|---|---|---|---|
| gap 0-7 days | 75 | 0.720 | 0.773 |
| gap 8-44 days | 178 | 0.646 | 0.691 |
| gap 45+ days (the `long_gap` range) | 199 | 0.633 | 0.714 |
| negatives from another thread, rejected | 342 | 0.655 | 0.617 |
| negatives that are loose chats, rejected | 110 | 0.855 | 0.818 |

### Student minus base, paired (`data/runs/followup-toy-paired.json`)

Same 904 exam pairs, each encoder at its own practice threshold, 1,000 paired resamples:
accuracy **+0.012** (11 pairs), 90% interval -0.001 to +0.027, positive in 91% of resamples;
AUC **+0.017**, 90% interval +0.011 to +0.023, positive in 100% of resamples. McNemar counts:
student right and base wrong 34, base right and student wrong 23, both right 590, both wrong 257.

## Reading

- A cosine threshold answers the toy question right about two times in three (0.68-0.69 against
  0.50 by chance) with AUC 0.73-0.75. That is the floor a real follow-up model has to beat.
- The student, trained only for the first question (chat against bundle, in-batch negatives),
  ranks follow-up pairs a little better (AUC +0.017, every paired resample positive) and finds
  more follow-ups (recall 0.653 -> 0.715, the gain concentrated on gaps of 45+ days, 0.633 ->
  0.714), at the cost of rejecting fewer non-follow-ups (other-thread negatives 0.655 -> 0.617).
  Accuracy moves by 11 pairs and its interval touches zero: a direction, not a result.
- The hard negatives are chats from another thread of the same person (rejected 0.62-0.66);
  loose chats are easy (0.82-0.86). Threads of one person share the persona's vocabulary, so a
  bag-of-meaning cosine confuses them; a follow-up model would need the earlier chat's context,
  not just its topic.
- Toy scale: two people per split, both from one 4B teacher and one prompt version, pairs
  built from the same chats the sorter exam uses, no held-out people beyond the exam split. The
  exam seal (`splits/exam.sha256`) was not touched: the pairs are read from `exam.jsonl`, nothing
  is written to `splits/`.

## Files and commands

```sh
cd pipeline
uv run bundle-pipeline followup-toy --device mps          # 6.9 s wall incl. two model loads
uv run python scripts/w6_followup_paired.py --device mps  # paired bootstrap, 1,000 resamples
uv run python scripts/w6_followup_board.py --run-id 2026-10-16-toy-v0
```

- `src/bundle_pipeline/followup_toy.py`: pairs, scores, metrics, `main(args)`; also runnable as
  `uv run python -m bundle_pipeline.followup_toy`. Registered in `cli.py` as `followup-toy`
  (`_resolve` now maps the hyphen to the module name's underscore).
- `tests/test_followup_toy.py`: pair contract and balance, determinism and the cap, AUC against
  scikit-learn with ties, threshold and metrics on a hand-made case, cosine scoring and the whole
  CLI against the fake hash encoder on the two-person fixture (no downloads).
- Outputs: `data/runs/followup-toy.json`, `data/runs/followup-toy-paired.json`;
  `scoreboard/runs/2026-10-16-toy-v0.json` gets a top-level `follow_up_toy` object and a one-line
  summary in `notes`, placed before the winner line (`scripts/w6_followup_board.py`, idempotent,
  re-reads the board right before writing). The object first landed inside `notes`;
  `scripts/w6_board_finalise.py` moved it to the top level, so `notes` stays text only.
- Nothing was downloaded; both encoders were already on disk (Hub cache 87 MiB, student 91.6 MB).
