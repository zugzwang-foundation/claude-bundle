"""`bundle-pipeline followup-toy`: the second question at toy scale, "is this a follow-up?".

Bundle's first question is "which bundle does this chat belong to?" (``sorter.py``).
The second question looks at one earlier chat instead of a bundle: given a new
chat and one chat the person opened before it, is the new chat a follow-up to
that one? This module builds labelled pairs from the people of a split and
scores them with nothing but the cosine of the two chats' vectors, for the base
encoder and for the trained student, so both are judged on the same pairs.

Pairs (``build_pairs``):

* a positive is (chat, an earlier chat of the same thread);
* a negative is (chat, an earlier chat of another thread) or (chat, an earlier
  loose chat of the same person);
* "earlier" means earlier in the person's chat order (day order, file order on
  equal days); every pair stays inside one person;
* the set is balanced: every positive gets one negative with the same later
  chat where one is left (so the negative shares the anchor's text and
  history), otherwise one drawn from the remaining negatives; draws come from
  ``random.Random(seed)`` over pairs listed in a fixed order, so the same seed
  gives the same pairs; at most ``max_pairs`` in total.

Scores and metrics: score = cosine(chat, earlier). ROC-AUC is rank based (ties
get the average rank). The threshold is the one that maximises accuracy on the
practice pairs (the middle candidate on ties) and is applied unchanged to the
exam pairs, where accuracy, precision and recall for "follow-up" are reported
with 90% bootstrap intervals (percentiles 5 and 95 over resamples of the exam
pairs). The best threshold on the exam itself is reported only as an "oracle"
figure for reference.

Toy scale: two people per split; a cosine threshold is not a follow-up model,
it is the floor such a model must beat.
"""

from __future__ import annotations

import argparse
import random
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from bundle_pipeline import config
from bundle_pipeline.schema import Person
from bundle_pipeline.sorter import normalise
from bundle_pipeline.store import read_people, write_json

EmbedFn = Callable[[list[str]], np.ndarray]

NEGATIVE_KINDS: tuple[str, str] = ("other_thread", "loose")
GAP_BUCKETS: tuple[tuple[str, int, int], ...] = (("0-7", 0, 7), ("8-44", 8, 44), ("45+", 45, 10**9))


@dataclass(frozen=True)
class Pair:
    """A later chat (the anchor) and one earlier chat of the same person."""

    person_id: str
    chat_id: str
    earlier_id: str
    chat: str
    earlier: str
    label: int
    """1 when the later chat follows the earlier one (same thread), else 0."""
    kind: str
    """"same_thread", "other_thread" or "loose" (the earlier chat's relation)."""
    gap_days: int


# --- Pairs -------------------------------------------------------------------


def candidate_pairs(person: Person) -> tuple[list[Pair], list[Pair]]:
    """Every (later, earlier) pair of one person: positives and negatives, in a fixed order."""
    chats = sorted(person.chats, key=lambda c: c.day)  # stable: file order on equal days
    pos: list[Pair] = []
    neg: list[Pair] = []
    for i, chat in enumerate(chats):
        for earlier in chats[:i]:
            if chat.thread_id is not None and earlier.thread_id == chat.thread_id:
                label, kind = 1, "same_thread"
            elif earlier.thread_id is None:
                label, kind = 0, "loose"
            else:
                label, kind = 0, "other_thread"
            pair = Pair(
                person_id=person.id,
                chat_id=chat.id,
                earlier_id=earlier.id,
                chat=chat.text,
                earlier=earlier.text,
                label=label,
                kind=kind,
                gap_days=chat.day - earlier.day,
            )
            (pos if label else neg).append(pair)
    return pos, neg


def build_pairs(people: Sequence[Person], seed: int = 3, max_pairs: int = 2000) -> list[Pair]:
    """Balanced, deterministic pairs for a split (see the module docstring)."""
    if max_pairs < 2:
        raise ValueError("max_pairs must be at least 2")
    pos_all: list[Pair] = []
    neg_all: list[Pair] = []
    for person in sorted(people, key=lambda p: p.id):
        p, n = candidate_pairs(person)
        pos_all.extend(p)
        neg_all.extend(n)
    rng = random.Random(seed)
    cap = max_pairs // 2
    pos = pos_all if len(pos_all) <= cap else rng.sample(pos_all, cap)
    by_anchor: dict[tuple[str, str], list[Pair]] = defaultdict(list)
    for pair in neg_all:
        by_anchor[(pair.person_id, pair.chat_id)].append(pair)
    used: set[Pair] = set()
    neg: list[Pair] = []
    for pair in pos:
        options = [n for n in by_anchor[(pair.person_id, pair.chat_id)] if n not in used]
        if not options:
            options = [n for n in neg_all if n not in used]
        if not options:
            break
        pick = rng.choice(options)
        used.add(pick)
        neg.append(pick)
    pos = pos[: len(neg)]
    pairs = pos + neg
    rng.shuffle(pairs)
    return pairs


def labels(pairs: Sequence[Pair]) -> np.ndarray:
    return np.array([p.label for p in pairs], dtype=bool)


def pair_counts(pairs: Sequence[Pair]) -> dict[str, int]:
    counts: dict[str, int] = {"total": len(pairs), "positive": 0, "negative": 0}
    for kind in NEGATIVE_KINDS:
        counts[f"negative_{kind}"] = 0
    for p in pairs:
        if p.label:
            counts["positive"] += 1
        else:
            counts["negative"] += 1
            counts[f"negative_{p.kind}"] += 1
    counts["people"] = len({p.person_id for p in pairs})
    return counts


# --- Scores and metrics ------------------------------------------------------


def score_pairs(embed: EmbedFn, pairs: Sequence[Pair]) -> np.ndarray:
    """cosine(chat, earlier) for every pair, as float64."""
    if not pairs:
        return np.zeros(0, dtype=np.float64)
    a = normalise(embed([p.chat for p in pairs]))
    b = normalise(embed([p.earlier for p in pairs]))
    return np.einsum("ij,ij->i", a, b).astype(np.float64)


def roc_auc(y: np.ndarray, scores: np.ndarray) -> float:
    """Area under the ROC curve by average ranks (equal to the Mann-Whitney statistic)."""
    y = np.asarray(y, dtype=bool)
    s = np.asarray(scores, dtype=np.float64)
    n_pos = int(y.sum())
    n_neg = int(len(y) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    _, inverse, counts = np.unique(s, return_inverse=True, return_counts=True)
    starts = np.concatenate(([0], np.cumsum(counts)[:-1]))
    ranks = (starts + (counts + 1) / 2)[inverse]  # 1-based average rank per tied value
    return float((ranks[y].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def best_threshold(y: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """The cut (predict follow-up when score >= t) with the highest accuracy; ties -> middle."""
    y = np.asarray(y, dtype=bool)
    s = np.asarray(scores, dtype=np.float64)
    if len(s) == 0:
        raise ValueError("no scores to choose a threshold from")
    uniq = np.unique(s)
    cands = np.concatenate(([uniq[0] - 1e-6], (uniq[:-1] + uniq[1:]) / 2, [uniq[-1] + 1e-6]))
    accs = np.array([float(np.mean((s >= t) == y)) for t in cands])
    best = np.flatnonzero(accs == accs.max())
    return float(cands[best[len(best) // 2]]), float(accs.max())


def metrics_at(y: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, float | int]:
    """Accuracy, precision, recall and F1 for "follow-up" at a fixed threshold."""
    y = np.asarray(y, dtype=bool)
    pred = np.asarray(scores, dtype=np.float64) >= threshold
    tp = int((pred & y).sum())
    fp = int((pred & ~y).sum())
    fn = int((~pred & y).sum())
    tn = int((~pred & ~y).sum())
    n = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": float(threshold),
        "accuracy": (tp + tn) / n if n else float("nan"),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def bootstrap_intervals(
    y: np.ndarray, scores: np.ndarray, threshold: float, resamples: int = 200, seed: int = 3
) -> dict[str, list[float] | int]:
    """90% intervals (percentiles 5 and 95) of AUC, accuracy, precision and recall."""
    y = np.asarray(y, dtype=bool)
    s = np.asarray(scores, dtype=np.float64)
    rng = np.random.default_rng(seed)
    draws: dict[str, list[float]] = {"auc": [], "accuracy": [], "precision": [], "recall": []}
    n = len(y)
    for _ in range(resamples):
        idx = rng.integers(0, n, n)
        yy, ss = y[idx], s[idx]
        if yy.all() or not yy.any():
            continue
        m = metrics_at(yy, ss, threshold)
        draws["auc"].append(roc_auc(yy, ss))
        for k in ("accuracy", "precision", "recall"):
            draws[k].append(float(m[k]))
    out: dict[str, list[float] | int] = {"resamples": len(draws["auc"])}
    for k, vals in draws.items():
        arr = np.array(vals, dtype=np.float64)
        lo, hi = np.percentile(arr, [5, 95]) if arr.size else (float("nan"), float("nan"))
        out[f"{k}_90"] = [float(lo), float(hi)]
    return out


def breakdown(pairs: Sequence[Pair], scores: np.ndarray, threshold: float) -> dict[str, dict]:
    """Recall of positives by day gap and the share of each negative kind correctly rejected."""
    pred = np.asarray(scores, dtype=np.float64) >= threshold
    by_gap: dict[str, dict] = {}
    for name, lo, hi in GAP_BUCKETS:
        idx = [i for i, p in enumerate(pairs) if p.label and lo <= p.gap_days <= hi]
        by_gap[name] = {
            "n": len(idx),
            "recall": float(np.mean(pred[idx])) if idx else None,
        }
    by_kind: dict[str, dict] = {}
    for kind in NEGATIVE_KINDS:
        idx = [i for i, p in enumerate(pairs) if not p.label and p.kind == kind]
        by_kind[kind] = {
            "n": len(idx),
            "rejected": float(np.mean(~pred[idx])) if idx else None,
        }
    return {"positive_recall_by_gap_days": by_gap, "negatives_rejected_by_kind": by_kind}


def evaluate(
    embed: EmbedFn,
    practice_pairs: Sequence[Pair],
    exam_pairs: Sequence[Pair],
    resamples: int = 200,
    seed: int = 3,
) -> dict:
    """Fit the threshold on the practice pairs, judge the exam pairs with it."""
    t0 = time.perf_counter()
    y_prac = labels(practice_pairs)
    s_prac = score_pairs(embed, practice_pairs)
    threshold, prac_acc = best_threshold(y_prac, s_prac)
    y_exam = labels(exam_pairs)
    s_exam = score_pairs(embed, exam_pairs)
    at = metrics_at(y_exam, s_exam, threshold)
    oracle_t, oracle_acc = best_threshold(y_exam, s_exam)
    return {
        "practice": {
            "pairs": len(practice_pairs),
            "auc": roc_auc(y_prac, s_prac),
            "threshold": threshold,
            "accuracy_at_threshold": prac_acc,
        },
        "exam": {
            "pairs": len(exam_pairs),
            "auc": roc_auc(y_exam, s_exam),
            **at,
            "oracle_threshold": oracle_t,
            "oracle_accuracy": oracle_acc,
            "bootstrap": bootstrap_intervals(y_exam, s_exam, threshold, resamples, seed),
            **breakdown(exam_pairs, s_exam, threshold),
            "score_mean_positive": float(s_exam[y_exam].mean()) if y_exam.any() else None,
            "score_mean_negative": float(s_exam[~y_exam].mean()) if (~y_exam).any() else None,
        },
        "seconds": time.perf_counter() - t0,
    }


def render_table(results: dict[str, dict]) -> str:
    head = (
        "| encoder | practice AUC | threshold | exam AUC | accuracy | precision | recall "
        "| F1 | oracle acc. |\n|---|---|---|---|---|---|---|---|---|"
    )
    rows = [head]
    for name, r in results.items():
        e, p = r["exam"], r["practice"]
        rows.append(
            f"| {name} ({r['model']}) | {p['auc']:.3f} | {e['threshold']:.4f} | {e['auc']:.3f} "
            f"| {e['accuracy']:.3f} | {e['precision']:.3f} | {e['recall']:.3f} | {e['f1']:.3f} "
            f"| {e['oracle_accuracy']:.3f} |"
        )
    return "\n".join(rows)


# --- CLI ---------------------------------------------------------------------


def main(args: argparse.Namespace) -> int:
    from bundle_pipeline.encoder import Encoder  # noqa: PLC0415

    paths = config.paths_for(getattr(args, "data_root", None))
    exam_file = Path(args.exam) if args.exam else paths.split_path("exam")
    practice_file = Path(args.practice) if args.practice else paths.split_path("practice")
    for f in (exam_file, practice_file):
        if not f.is_file():
            print(f"followup-toy: no people file at {f}; run `bundle-pipeline split` first")
            return 2
    exam_pairs = build_pairs(read_people(exam_file), seed=args.seed, max_pairs=args.max_pairs)
    practice_pairs = build_pairs(
        read_people(practice_file), seed=args.seed, max_pairs=args.max_pairs
    )
    counts = {"exam": pair_counts(exam_pairs), "practice": pair_counts(practice_pairs)}
    for split, c in counts.items():
        print(
            f"followup-toy: {split} {c['total']} pairs ({c['positive']} follow-ups, "
            f"{c['negative']} not: {c['negative_other_thread']} other thread, "
            f"{c['negative_loose']} loose) from {c['people']} people"
        )
    if not exam_pairs or not practice_pairs:
        print("followup-toy: a split has no pairs; nothing to score")
        return 2

    encoders: list[tuple[str, str]] = [("base", args.encoder)]
    if args.student and Path(args.student).exists():
        encoders.append(("student", args.student))
    else:
        print(f"followup-toy: no student at {args.student}; scoring the base encoder only")
    results: dict[str, dict] = {}
    for name, model in encoders:
        enc = Encoder(model, device=args.device)
        r = evaluate(enc.encode, practice_pairs, exam_pairs, args.resamples, args.seed)
        results[name] = {
            "model": model,
            "device": getattr(enc, "device", "cpu"),
            "load_seconds": getattr(enc, "load_seconds", None),
            **r,
        }
        print(f"  {name} done in {r['seconds']:.1f}s ({model} on {results[name]['device']})")

    out = Path(args.out)
    write_json(
        out,
        {
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "label": "toy scale",
            "task": "is this a follow-up to that chat? (cosine of the two chats, one threshold)",
            "seed": args.seed,
            "max_pairs": args.max_pairs,
            "exam_file": str(exam_file),
            "practice_file": str(practice_file),
            "pairs": counts,
            "pair_fields": list(asdict(exam_pairs[0]).keys()),
            "encoders": results,
        },
    )
    print(render_table(results))
    print(f"followup-toy: wrote {out}")
    return 0


if __name__ == "__main__":  # python -m bundle_pipeline.followup_toy
    import sys

    from bundle_pipeline.cli import main as cli_main

    sys.exit(cli_main(["followup-toy", *sys.argv[1:]]))


__all__ = [
    "Pair",
    "best_threshold",
    "bootstrap_intervals",
    "breakdown",
    "build_pairs",
    "candidate_pairs",
    "evaluate",
    "labels",
    "main",
    "metrics_at",
    "pair_counts",
    "render_table",
    "roc_auc",
    "score_pairs",
]
