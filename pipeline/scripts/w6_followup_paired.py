"""Paired bootstrap of student minus base on the toy follow-up pairs (same draws for both).

Rebuilds the pairs exactly as `bundle-pipeline followup-toy` does (same seed and
cap), fits each encoder's threshold on the practice pairs, scores the exam
pairs, then resamples the exam pairs with replacement and takes the difference
of accuracy and ROC-AUC on each draw. Writes data/runs/followup-toy-paired.json.

    uv run python scripts/w6_followup_paired.py --device mps
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from bundle_pipeline import config
from bundle_pipeline.encoder import Encoder
from bundle_pipeline.followup_toy import best_threshold, build_pairs, labels, roc_auc, score_pairs
from bundle_pipeline.store import read_people, write_json


def main() -> int:
    paths = config.paths_for()
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--exam", default=str(paths.split_path("exam")))
    ap.add_argument("--practice", default=str(paths.split_path("practice")))
    ap.add_argument("--encoder", default=config.BASE_ENCODER)
    ap.add_argument("--student", default=str(paths.models_dir / "student-v0"))
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--max-pairs", type=int, default=2000)
    ap.add_argument("--resamples", type=int, default=1000)
    ap.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    ap.add_argument("--out", default=str(paths.runs_dir / "followup-toy-paired.json"))
    args = ap.parse_args()

    exam_pairs = build_pairs(read_people(Path(args.exam)), seed=args.seed, max_pairs=args.max_pairs)
    practice_pairs = build_pairs(
        read_people(Path(args.practice)), seed=args.seed, max_pairs=args.max_pairs
    )
    y_p, y_e = labels(practice_pairs), labels(exam_pairs)
    scores: dict[str, np.ndarray] = {}
    correct: dict[str, np.ndarray] = {}
    thresholds: dict[str, float] = {}
    for name, model in (("base", args.encoder), ("student", args.student)):
        enc = Encoder(model, device=args.device)
        t, _ = best_threshold(y_p, score_pairs(enc.encode, practice_pairs))
        s = score_pairs(enc.encode, exam_pairs)
        thresholds[name], scores[name], correct[name] = t, s, (s >= t) == y_e

    rng = np.random.default_rng(args.seed)
    n = len(y_e)
    d_acc: list[float] = []
    d_auc: list[float] = []
    for _ in range(args.resamples):
        idx = rng.integers(0, n, n)
        yy = y_e[idx]
        if yy.all() or not yy.any():
            continue
        d_acc.append(float(correct["student"][idx].mean() - correct["base"][idx].mean()))
        d_auc.append(roc_auc(yy, scores["student"][idx]) - roc_auc(yy, scores["base"][idx]))
    acc = np.array(d_acc)
    auc = np.array(d_auc)
    out = {
        "pairs": n,
        "resamples": len(d_acc),
        "seed": args.seed,
        "thresholds": thresholds,
        "accuracy": {k: float(v.mean()) for k, v in correct.items()},
        "auc": {k: roc_auc(y_e, v) for k, v in scores.items()},
        "accuracy_diff": float(correct["student"].mean() - correct["base"].mean()),
        "accuracy_diff_90": [float(x) for x in np.percentile(acc, [5, 95])],
        "accuracy_diff_positive_share": float((acc > 0).mean()),
        "auc_diff": roc_auc(y_e, scores["student"]) - roc_auc(y_e, scores["base"]),
        "auc_diff_90": [float(x) for x in np.percentile(auc, [5, 95])],
        "auc_diff_positive_share": float((auc > 0).mean()),
        "mcnemar": {
            "student_only_right": int((correct["student"] & ~correct["base"]).sum()),
            "base_only_right": int((~correct["student"] & correct["base"]).sum()),
            "both_right": int((correct["student"] & correct["base"]).sum()),
            "both_wrong": int((~correct["student"] & ~correct["base"]).sum()),
        },
    }
    write_json(Path(args.out), out)
    print(
        f"student minus base on {n} exam pairs: accuracy {out['accuracy_diff']:+.4f} "
        f"90% [{out['accuracy_diff_90'][0]:+.4f}, {out['accuracy_diff_90'][1]:+.4f}] "
        f"(positive in {out['accuracy_diff_positive_share']:.0%}); "
        f"AUC {out['auc_diff']:+.4f} 90% "
        f"[{out['auc_diff_90'][0]:+.4f}, {out['auc_diff_90'][1]:+.4f}] "
        f"(positive in {out['auc_diff_positive_share']:.0%}); McNemar {out['mcnemar']}"
    )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
