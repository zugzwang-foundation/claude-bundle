"""`bundle-pipeline calibrate`: temperature, none score and the two cut-offs, on practice.

Step 1, calibration proper: with the candidate cosine scores fixed, find the
``temperature`` and ``none_score`` that minimise the mean negative log-likelihood
of the right answer (``sorter.mean_nll``). The search is a coordinate descent
over two small grids (temperature geometric in [0.01, 1], none score linear in
[0, 1]), alternating until neither coordinate moves; no scipy.

Step 2, cut-offs: with those parameters, p_top is the probability of the best
candidate (never "none") and a decision is right when that candidate is the
answer ("none" answers are wrong when filed). ``file_cutoff`` is the smallest
threshold t, among the observed p_top values, such that the precision over all
decisions with p_top >= t is at least 0.95 and at least ``min_support`` decisions
are covered; ``suggest_cutoff`` likewise for 0.80. When no threshold reaches the
target the cut-off is 1.0 (the action never fires) and the source string says so.
``suggest_cutoff`` is never above ``file_cutoff``.

Outputs: calibration.json in the models dir (keys model, temperature, none_score,
file_cutoff, suggest_cutoff, practice_size, source) and a camelCase copy for the
web app at web/src/sorter/calibration.json (temperature, noneScore, fileCutoff,
suggestCutoff, model, source).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from bundle_pipeline.config import DEFAULT_SORTER, SorterParams
from bundle_pipeline.sorter import Scored, Sorter, mean_nll, top_candidate, unique_texts
from bundle_pipeline.store import read_examples, write_json

TEMPERATURE_GRID: tuple[float, ...] = tuple(float(x) for x in np.geomspace(0.01, 1.0, 41))
NONE_GRID: tuple[float, ...] = tuple(float(x) for x in np.linspace(0.0, 1.0, 51))
FILE_TARGET = 0.95
SUGGEST_TARGET = 0.80


@dataclass(frozen=True)
class Calibration:
    params: SorterParams
    nll_before: float
    nll_after: float
    practice_size: int
    file_support: int
    suggest_support: int
    file_reached: bool
    suggest_reached: bool

    def source(self, note: str = "") -> str:
        bits = [
            f"practice split, {self.practice_size} examples",
            f"coordinate search over temperature x none_score, NLL {self.nll_before:.3f} -> "
            f"{self.nll_after:.3f}",
            f"file cut-off {'reached' if self.file_reached else 'NOT reached'} "
            f"({FILE_TARGET:.2f} precision, support {self.file_support})",
            f"suggest cut-off {'reached' if self.suggest_reached else 'NOT reached'} "
            f"({SUGGEST_TARGET:.2f} precision, support {self.suggest_support})",
            datetime.now(UTC).strftime("%Y-%m-%d"),
        ]
        if note:
            bits.append(note)
        return "; ".join(bits)


# --- Step 1: temperature and none score --------------------------------------


def fit_temperature_and_none(
    scored: Sequence[Scored],
    start: SorterParams = DEFAULT_SORTER,
    temperatures: Sequence[float] = TEMPERATURE_GRID,
    none_scores: Sequence[float] = NONE_GRID,
    max_rounds: int = 8,
) -> tuple[SorterParams, float]:
    """Coordinate descent on mean NLL; returns the params (cut-offs untouched) and the NLL."""
    temp, none = start.temperature, start.none_score

    def nll(t: float, n: float) -> float:
        return mean_nll(scored, SorterParams(t, n, start.file_cutoff, start.suggest_cutoff))

    best = nll(temp, none)
    for _ in range(max_rounds):
        moved = False
        for t in temperatures:
            v = nll(t, none)
            if v < best - 1e-12:
                best, temp, moved = v, t, True
        for n in none_scores:
            v = nll(temp, n)
            if v < best - 1e-12:
                best, none, moved = v, n, True
        if not moved:
            break
    return SorterParams(temp, none, start.file_cutoff, start.suggest_cutoff), best


# --- Step 2: cut-offs --------------------------------------------------------


def choose_cutoff(
    p_top: Sequence[float], correct: Sequence[bool], target: float, min_support: int = 5
) -> tuple[float, int, bool]:
    """Smallest observed p_top threshold whose precision (over p_top >= t) reaches the target.

    Returns (threshold, support, reached). Without any qualifying threshold:
    (1.0, 0, False), which makes the action never fire.
    """
    p = np.asarray(p_top, dtype=np.float64)
    c = np.asarray(correct, dtype=bool)
    if p.size == 0:
        return 1.0, 0, False
    order = np.argsort(-p, kind="stable")  # highest first
    p_sorted, c_sorted = p[order], c[order]
    cum_hits = np.cumsum(c_sorted)
    counts = np.arange(1, p.size + 1)
    precision = cum_hits / counts
    best: tuple[float, int] | None = None
    for i in range(p.size):
        # only evaluate at the last index of a run of equal p values (the full set >= t)
        if i + 1 < p.size and p_sorted[i + 1] == p_sorted[i]:
            continue
        if counts[i] >= min_support and precision[i] >= target:
            best = (float(p_sorted[i]), int(counts[i]))  # keep going: smaller t wins
    if best is None:
        return 1.0, 0, False
    return best[0], best[1], True


def top_probabilities(
    scored: Sequence[Scored], params: SorterParams
) -> tuple[list[float], list[bool]]:
    p_top: list[float] = []
    correct: list[bool] = []
    for s in scored:
        top_id, p = top_candidate(s.probabilities(params))
        p_top.append(p)
        correct.append(top_id is not None and top_id == s.answer)
    return p_top, correct


def calibrate(
    scored: Sequence[Scored], start: SorterParams = DEFAULT_SORTER, min_support: int = 5
) -> Calibration:
    nll_before = mean_nll(scored, start)
    fitted, nll_after = fit_temperature_and_none(scored, start)
    p_top, correct = top_probabilities(scored, fitted)
    file_cut, file_sup, file_ok = choose_cutoff(p_top, correct, FILE_TARGET, min_support)
    sugg_cut, sugg_sup, sugg_ok = choose_cutoff(p_top, correct, SUGGEST_TARGET, min_support)
    sugg_cut = min(sugg_cut, file_cut)
    params = SorterParams(fitted.temperature, fitted.none_score, file_cut, sugg_cut)
    return Calibration(
        params, nll_before, nll_after, len(scored), file_sup, sugg_sup, file_ok, sugg_ok
    )


# --- Files -------------------------------------------------------------------


def calibration_payload(model: str, cal: Calibration, note: str = "") -> dict[str, Any]:
    p = cal.params
    return {
        "model": model,
        "temperature": p.temperature,
        "none_score": p.none_score,
        "file_cutoff": p.file_cutoff,
        "suggest_cutoff": p.suggest_cutoff,
        "practice_size": cal.practice_size,
        "source": cal.source(note),
    }


def web_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """The camelCase copy the web app reads (exactly these six keys)."""
    return {
        "temperature": payload["temperature"],
        "noneScore": payload["none_score"],
        "fileCutoff": payload["file_cutoff"],
        "suggestCutoff": payload["suggest_cutoff"],
        "model": payload["model"],
        "source": payload["source"],
    }


def score_examples(encoder: Any, examples: Sequence[Any]) -> list[Scored]:
    encoder.warm(unique_texts(examples))
    sorter = Sorter(encoder.encode)
    return [sorter.score(ex) for ex in examples]


def main(args: argparse.Namespace) -> int:
    from bundle_pipeline.encoder import Encoder  # noqa: PLC0415

    tasks_file = Path(args.tasks)
    if not tasks_file.is_file():
        print(f"calibrate: no tasks file at {tasks_file}; run `bundle-pipeline tasks` first")
        return 2
    examples = read_examples(tasks_file)
    encoder = Encoder(args.model, device=args.device)
    print(f"calibrate: {len(examples)} practice examples, model {encoder.name} on {encoder.device}")
    scored = score_examples(encoder, examples)
    cal = calibrate(scored, min_support=args.min_support)
    payload = calibration_payload(encoder.name, cal, note=f"tasks {tasks_file.name}")
    out = write_json(Path(args.out), payload) or Path(args.out)
    print(f"calibrate: wrote {args.out}")
    if args.web_out and not args.no_web:
        write_json(Path(args.web_out), web_payload(payload))
        print(f"calibrate: wrote {args.web_out}")
    p = cal.params
    print(
        f"  temperature {p.temperature:.4f}  none_score {p.none_score:.3f}  "
        f"file_cutoff {p.file_cutoff:.4f}  suggest_cutoff {p.suggest_cutoff:.4f}"
    )
    print(f"  {payload['source']}")
    return 0 if out else 1


__all__ = [
    "FILE_TARGET",
    "NONE_GRID",
    "SUGGEST_TARGET",
    "TEMPERATURE_GRID",
    "Calibration",
    "calibrate",
    "calibration_payload",
    "choose_cutoff",
    "fit_temperature_and_none",
    "score_examples",
    "top_probabilities",
    "web_payload",
]
