"""Metrics for one sorter on a tasks file, and `bundle-pipeline exam`.

Definitions (the scoreboard and the web app quote these, so they are spelled out):

* **prediction**: the argmax of the probability table, "none" included.
* **accuracy**: share of examples whose prediction equals the answer.
* **macro_f1**: the three answer classes are ``bundle`` (answer "b:..."),
  ``loose`` (answer "c:...") and ``none``. A prediction *counts for a class only
  when it names the exact right target*: for class k, TP = prediction == answer
  and the answer is of class k; FP = the prediction is of class k but is not the
  answer (so the wrong bundle is a false positive for ``bundle``, not a hit);
  FN = the answer is of class k and the prediction differs. macro_f1 is the
  unweighted mean of the three per-class F1 scores (a class with no answers and
  no predictions is left out of the mean).
* **none_precision / none_recall**: precision and recall of predicting "none".
* **ece**: expected calibration error of the *chosen class*: p = probability of
  the prediction, hit = prediction == answer, 10 equal-width bins on [0, 1],
  sum over bins of (n_bin / n) * |mean(hit) - mean(p)|.
* **brier**: mean over examples of (p - hit)^2 for the chosen class; in [0, 1].
* **file_precision / file_coverage**: among decisions whose action is "file"
  (p_top >= file_cutoff), the share whose target is the answer, and their share
  of all examples. A "none" answer counts as wrong when filed.
* **suggest_precision / suggest_coverage**: the same among decisions with
  p_top >= suggest_cutoff, i.e. action "suggest" *or* "file" (this is the band
  the calibration searched, so the two numbers match the calibration targets).
* **latency_ms_per_decision**: median wall-clock milliseconds for one decision
  on this Mac: embedding the single chat text (batch of one) plus the maths,
  with the candidates' vectors already known; sampled over up to 100 examples.
* **size_mb**: the model's weights on disk, in MB (10^6 bytes); 0 for B0.

`main` sits the sealed exam: it checks splits/exam.sha256 against
splits/exam.jsonl, runs B0, B1 (base encoder) and B2 (the student, with its
calibration) on tasks/exam.jsonl and writes runs/exam-<run-id>.json for the
scoreboard stage.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from bundle_pipeline.config import DEFAULT_SORTER, SorterParams
from bundle_pipeline.schema import Decision, DecisionExample
from bundle_pipeline.sorter import (
    NONE_ID,
    LeaveSorter,
    Sorter,
    argmax_including_none,
    candidate_vectors,
    cosine_scores,
    decide_from_scores,
    unique_texts,
)
from bundle_pipeline.store import read_examples, sha256_file, write_json

CLASSES: tuple[str, str, str] = ("bundle", "loose", "none")
METRIC_KEYS: tuple[str, ...] = (
    "accuracy",
    "macro_f1",
    "none_precision",
    "none_recall",
    "ece",
    "brier",
    "file_precision",
    "file_coverage",
    "suggest_precision",
    "suggest_coverage",
    "latency_ms_per_decision",
    "size_mb",
)


def answer_class(answer: str) -> str:
    if answer == NONE_ID:
        return "none"
    if answer.startswith("b:"):
        return "bundle"
    if answer.startswith("c:"):
        return "loose"
    raise ValueError(f"not a candidate id or 'none': {answer!r}")


# --- Metric pieces -----------------------------------------------------------


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def expected_calibration_error(
    p_chosen: Sequence[float], hit: Sequence[bool], n_bins: int = 10
) -> float:
    p = np.asarray(p_chosen, dtype=np.float64)
    h = np.asarray(hit, dtype=np.float64)
    if p.size == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # bin i covers (edges[i], edges[i+1]]; p == 0 lands in bin 0
    idx = np.clip(np.searchsorted(edges, p, side="left") - 1, 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        mask = idx == b
        if mask.any():
            total += mask.mean() * abs(h[mask].mean() - p[mask].mean())
    return float(total)


def brier_score(p_chosen: Sequence[float], hit: Sequence[bool]) -> float:
    p = np.asarray(p_chosen, dtype=np.float64)
    h = np.asarray(hit, dtype=np.float64)
    return float(np.mean((p - h) ** 2)) if p.size else 0.0


def macro_f1(answers: Sequence[str], predictions: Sequence[str]) -> float:
    tp = dict.fromkeys(CLASSES, 0)
    fp = dict.fromkeys(CLASSES, 0)
    fn = dict.fromkeys(CLASSES, 0)
    for ans, pred in zip(answers, predictions, strict=True):
        a_cls, p_cls = answer_class(ans), answer_class(pred)
        if pred == ans:
            tp[a_cls] += 1
        else:
            fn[a_cls] += 1
            fp[p_cls] += 1
    f1s: list[float] = []
    for cls in CLASSES:
        if tp[cls] + fp[cls] + fn[cls] == 0:
            continue
        prec = _safe_div(tp[cls], tp[cls] + fp[cls])
        rec = _safe_div(tp[cls], tp[cls] + fn[cls])
        f1s.append(_safe_div(2 * prec * rec, prec + rec))
    return float(sum(f1s) / len(f1s)) if f1s else 0.0


def none_precision_recall(
    answers: Sequence[str], predictions: Sequence[str]
) -> tuple[float, float]:
    pred_none = [p == NONE_ID for p in predictions]
    ans_none = [a == NONE_ID for a in answers]
    tp = sum(1 for p, a in zip(pred_none, ans_none, strict=True) if p and a)
    return _safe_div(tp, sum(pred_none)), _safe_div(tp, sum(ans_none))


def precision_coverage(
    answers: Sequence[str], decisions: Sequence[Decision], actions: frozenset[str]
) -> tuple[float, float]:
    """Precision of ``target == answer`` and share of examples, over decisions in ``actions``."""
    chosen = [(d, a) for d, a in zip(decisions, answers, strict=True) if d.action in actions]
    hits = sum(1 for d, a in chosen if d.target == a)
    return _safe_div(hits, len(chosen)), _safe_div(len(chosen), len(answers))


def compute_metrics(
    examples: Sequence[DecisionExample],
    decisions: Sequence[Decision],
    latencies_ms: Sequence[float] = (),
    size_mb: float = 0.0,
) -> dict[str, float]:
    """Every scoreboard metric for one sorter; keys are exactly ``METRIC_KEYS``."""
    if len(examples) != len(decisions):
        raise ValueError("one decision per example, please")
    answers = [ex.answer for ex in examples]
    predictions = [argmax_including_none(d.probabilities) for d in decisions]
    p_chosen = [d.probabilities[p] for d, p in zip(decisions, predictions, strict=True)]
    hits = [p == a for p, a in zip(predictions, answers, strict=True)]
    none_p, none_r = none_precision_recall(answers, predictions)
    file_p, file_c = precision_coverage(answers, decisions, frozenset({"file"}))
    sugg_p, sugg_c = precision_coverage(answers, decisions, frozenset({"file", "suggest"}))
    latency = float(statistics.median(latencies_ms)) if latencies_ms else 0.0
    return {
        "accuracy": float(np.mean(hits)) if hits else 0.0,
        "macro_f1": macro_f1(answers, predictions),
        "none_precision": none_p,
        "none_recall": none_r,
        "ece": expected_calibration_error(p_chosen, hits),
        "brier": brier_score(p_chosen, hits),
        "file_precision": file_p,
        "file_coverage": file_c,
        "suggest_precision": sugg_p,
        "suggest_coverage": sugg_c,
        "latency_ms_per_decision": latency,
        "size_mb": float(size_mb),
    }


# --- Running a sorter over a tasks file --------------------------------------


@dataclass
class SorterRun:
    sorter_id: str
    name: str
    model: str | None
    params: SorterParams | None
    decisions: list[Decision] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)
    size_mb: float = 0.0
    seconds: float = 0.0

    def metrics(self, examples: Sequence[DecisionExample]) -> dict[str, float]:
        return compute_metrics(examples, self.decisions, self.latencies_ms, self.size_mb)

    def record(self, examples: Sequence[DecisionExample]) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.sorter_id, "name": self.name}
        out.update(self.metrics(examples))
        out["model"] = self.model
        out["params"] = None if self.params is None else self.params.__dict__
        out["n"] = len(examples)
        out["seconds"] = round(self.seconds, 3)
        return out


def run_leave(examples: Sequence[DecisionExample]) -> SorterRun:
    sorter = LeaveSorter()
    run = SorterRun("B0", "always leave", None, None)
    t0 = time.perf_counter()
    for ex in examples:
        t1 = time.perf_counter()
        run.decisions.append(sorter.decide(ex))
        run.latencies_ms.append((time.perf_counter() - t1) * 1000)
    run.seconds = time.perf_counter() - t0
    return run


def run_encoder(
    sorter_id: str,
    name: str,
    encoder: Any,
    examples: Sequence[DecisionExample],
    params: SorterParams = DEFAULT_SORTER,
    latency_sample: int = 100,
) -> SorterRun:
    """Decide every example with a warmed cache, then time single-chat decisions."""
    sorter = Sorter(encoder.encode, params)
    run = SorterRun(sorter_id, name, encoder.name, params, size_mb=encoder.size_mb())
    t0 = time.perf_counter()
    encoder.warm(unique_texts(examples))
    run.decisions = [sorter.decide(ex) for ex in examples]
    run.seconds = time.perf_counter() - t0
    step = max(1, len(examples) // max(1, latency_sample))
    for ex in list(examples)[::step][:latency_sample]:
        t1 = time.perf_counter()
        ids, matrix = candidate_vectors(ex.candidates, encoder.encode)
        chat_vec = encoder.encode_uncached([ex.chat])[0]
        decide_from_scores(ids, cosine_scores(chat_vec, matrix), params)
        run.latencies_ms.append((time.perf_counter() - t1) * 1000)
    return run


def load_params(path: str | Path | None) -> SorterParams:
    """calibration.json -> SorterParams; defaults when the path is None or missing."""
    if path is None or not Path(path).is_file():
        return DEFAULT_SORTER
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return SorterParams(
        temperature=float(data["temperature"]),
        none_score=float(data["none_score"]),
        file_cutoff=float(data["file_cutoff"]),
        suggest_cutoff=float(data["suggest_cutoff"]),
    )


def default_run_id(tag: str = "toy-v0") -> str:
    return f"{datetime.now(UTC):%Y-%m-%d}-{tag}"


def check_seal(exam_file: Path, hash_file: Path) -> str:
    """The exam file must hash to what `split` recorded; returns the hash."""
    if not hash_file.is_file():
        raise FileNotFoundError(f"no exam seal at {hash_file}; run `bundle-pipeline split` first")
    recorded = hash_file.read_text(encoding="utf-8").split()[0].strip()
    actual = sha256_file(exam_file)
    if recorded != actual:
        raise ValueError(f"exam.jsonl changed since it was sealed: {actual} != {recorded}")
    return actual


def render_table(sorters: Sequence[dict[str, Any]]) -> str:
    """A markdown table of the scoreboard metrics (also used by `scoreboard`)."""
    cols = ("id", "name", *METRIC_KEYS)
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    rows = []
    for s in sorters:
        cells = []
        for c in cols:
            v = s.get(c)
            if isinstance(v, float):
                cells.append(
                    f"{v:.3f}" if c not in ("size_mb", "latency_ms_per_decision") else f"{v:.1f}"
                )
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([head, sep, *rows])


def main(args: argparse.Namespace) -> int:
    from bundle_pipeline.encoder import Encoder  # noqa: PLC0415

    tasks_file = Path(args.tasks)
    if not tasks_file.is_file():
        print(f"exam: no tasks file at {tasks_file}; run `bundle-pipeline tasks` first")
        return 2
    exam_hash = "unsealed"
    if not args.allow_unsealed:
        try:
            exam_hash = check_seal(Path(args.split_file), Path(args.hash_file))
        except (FileNotFoundError, ValueError) as e:
            print(f"exam: {e}")
            return 2
    examples = read_examples(tasks_file)
    print(f"exam: {len(examples)} examples from {tasks_file} (seal {exam_hash[:12]})")
    runs: list[SorterRun] = []
    notes: list[str] = []

    runs.append(run_leave(examples))
    print(f"  B0 done in {runs[-1].seconds:.1f}s")

    b1_params = load_params(args.b1_calibration)
    base = Encoder(args.encoder, device=args.device)
    runs.append(run_encoder("B1", "base encoder, untrained", base, examples, b1_params))
    print(f"  B1 done in {runs[-1].seconds:.1f}s ({base.name} on {base.device})")
    if args.b1_calibration and Path(args.b1_calibration).is_file():
        notes.append(f"B1 calibrated from {args.b1_calibration}")
    else:
        notes.append("B1 uses the default sorter parameters (uncalibrated)")
    del base

    model_dir = Path(args.model)
    if model_dir.is_dir():
        b2_params = load_params(args.calibration)
        student = Encoder(str(model_dir), device=args.device)
        runs.append(run_encoder("B2", "student v0", student, examples, b2_params))
        print(f"  B2 done in {runs[-1].seconds:.1f}s ({model_dir.name} on {student.device})")
        if not Path(args.calibration).is_file():
            notes.append(f"B2 uncalibrated: no calibration at {args.calibration}")
    else:
        notes.append(f"B2 skipped: no student at {model_dir}")
        print(f"  B2 skipped: no student at {model_dir}")

    run_id = args.run_id or default_run_id()
    records = [r.record(examples) for r in runs]
    payload = {
        "run_id": run_id,
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "exam_hash": exam_hash,
        "exam_size": len(examples),
        "tasks_file": str(tasks_file),
        "base_model": args.encoder,
        "sorters": records,
        "notes": notes,
    }
    out = Path(args.out_dir) / f"exam-{run_id}.json"
    write_json(out, payload)
    print(render_table(records))
    print(f"exam: wrote {out}")
    return 0


__all__ = [
    "CLASSES",
    "METRIC_KEYS",
    "SorterRun",
    "answer_class",
    "brier_score",
    "check_seal",
    "compute_metrics",
    "default_run_id",
    "expected_calibration_error",
    "load_params",
    "macro_f1",
    "none_precision_recall",
    "precision_coverage",
    "render_table",
    "run_encoder",
    "run_leave",
]
