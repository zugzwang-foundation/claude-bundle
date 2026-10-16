"""Bootstrap intervals for a calibration on the practice split (toy scale).

Usage (from pipeline/):

    uv run python scripts/w6_bootstrap_cutoffs.py --model data/models/student-v0 \\
        --calibration data/models/calibration.json --resamples 200

The practice examples are scored once with the model. Then they are resampled
with replacement ``--resamples`` times; on every resample the temperature and
none score are re-fitted with the same coordinate descent as `calibrate` (same
grids, same moves, same stopping rule, vectorised here so 200 refits take
seconds) and the two cut-offs are re-chosen with `calibrate.choose_cutoff`.
Reported with a 90% interval (5th to 95th percentile): the refitted temperature
and none score, the re-chosen cut-offs, how often each precision target was
reached, and the precision and coverage of the ORIGINAL cut-offs (the ones in
calibration.json) on each resample, which is what a reader of the board needs:
how far the 0.95 / 0.80 precision figures can move on a practice split this
small. Writes runs/bootstrap-<calibration stem>.json.
"""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from bundle_pipeline import config
from bundle_pipeline.calibrate import (
    FILE_TARGET,
    NONE_GRID,
    SUGGEST_TARGET,
    TEMPERATURE_GRID,
    choose_cutoff,
    score_examples,
)
from bundle_pipeline.config import SorterParams
from bundle_pipeline.encoder import Encoder
from bundle_pipeline.exam import load_params
from bundle_pipeline.sorter import NONE_ID, Scored
from bundle_pipeline.store import read_examples, write_json

KEYS = (
    "temperature",
    "none_score",
    "file_cutoff",
    "suggest_cutoff",
    "file_precision",
    "file_coverage",
    "suggest_precision",
    "suggest_coverage",
)


def pad(scored: list[Scored]) -> tuple[np.ndarray, np.ndarray]:
    """(n, 1 + k) score matrix: column 0 is "none" (filled per evaluation), then the candidates."""
    k = max((len(s.ids) for s in scored), default=0)
    mat = np.full((len(scored), 1 + k), -np.inf, dtype=np.float64)
    answer = np.zeros(len(scored), dtype=np.int64)
    for i, s in enumerate(scored):
        mat[i, 1 : 1 + len(s.ids)] = s.scores
        answer[i] = 0 if s.answer == NONE_ID else 1 + s.ids.index(s.answer)
    return mat, answer


def probabilities(mat: np.ndarray, temperature: float, none_score: float) -> np.ndarray:
    z = mat.copy()
    z[:, 0] = none_score
    z /= temperature
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def mean_nll(mat: np.ndarray, answer: np.ndarray, temperature: float, none_score: float) -> float:
    p = probabilities(mat, temperature, none_score)[np.arange(len(answer)), answer]
    return float(-np.log(np.maximum(p, 1e-12)).mean())


def fit(mat: np.ndarray, answer: np.ndarray, start: SorterParams) -> tuple[float, float, float]:
    """calibrate.fit_temperature_and_none, vectorised: same grids, same moves, same stop."""
    temp, none = start.temperature, start.none_score
    best = mean_nll(mat, answer, temp, none)
    for _ in range(8):
        moved = False
        for t in TEMPERATURE_GRID:
            v = mean_nll(mat, answer, t, none)
            if v < best - 1e-12:
                best, temp, moved = v, t, True
        for n in NONE_GRID:
            v = mean_nll(mat, answer, temp, n)
            if v < best - 1e-12:
                best, none, moved = v, n, True
        if not moved:
            break
    return temp, none, best


def top(
    mat: np.ndarray, answer: np.ndarray, temperature: float, none_score: float
) -> tuple[np.ndarray, np.ndarray]:
    """p_top and hit of the best candidate (never "none"), as calibrate.top_probabilities."""
    p = probabilities(mat, temperature, none_score)
    if p.shape[1] == 1:
        return np.zeros(len(answer)), np.zeros(len(answer), dtype=bool)
    idx = p[:, 1:].argmax(axis=1) + 1
    p_top = p[np.arange(len(answer)), idx]
    return p_top, (idx == answer) & (answer != 0)


def precision_coverage(
    p_top: np.ndarray, correct: np.ndarray, cutoff: float
) -> tuple[float, float]:
    mask = p_top >= cutoff
    n = int(mask.sum())
    return (float(correct[mask].mean()) if n else float("nan")), n / max(1, p_top.size)


def interval(values: list[float]) -> list[float] | None:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return None
    return [round(float(np.percentile(arr, 5)), 4), round(float(np.percentile(arr, 95)), 4)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default=str(config.MODELS_DIR / "student-v0"))
    ap.add_argument("--calibration", default=str(config.CALIBRATION_JSON))
    ap.add_argument("--tasks", default=str(config.tasks_path("practice")))
    ap.add_argument("--resamples", type=int, default=200)
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--min-support", type=int, default=5)
    ap.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    ap.add_argument("--out", default=None, help="default runs/bootstrap-<calibration stem>.json")
    args = ap.parse_args()

    examples = read_examples(Path(args.tasks))
    params = load_params(args.calibration)
    encoder = Encoder(args.model, device=args.device)
    t0 = time.perf_counter()
    mat, answer = pad(score_examples(encoder, examples))
    n = len(answer)

    full_t, full_n, full_nll = fit(mat, answer, config.DEFAULT_SORTER)
    matches = abs(full_t - params.temperature) < 1e-9 and abs(full_n - params.none_score) < 1e-9
    p_top, correct = top(mat, answer, params.temperature, params.none_score)
    point_file = precision_coverage(p_top, correct, params.file_cutoff)
    point_suggest = precision_coverage(p_top, correct, params.suggest_cutoff)

    rng = np.random.default_rng(args.seed)
    rows: dict[str, list[float]] = {k: [] for k in KEYS}
    reached = {"file": 0, "suggest": 0}
    for _ in range(args.resamples):
        idx = rng.integers(0, n, n)
        m, a = mat[idx], answer[idx]
        t, ns, _ = fit(m, a, config.DEFAULT_SORTER)
        pt, cr = top(m, a, t, ns)
        file_cut, _, file_ok = choose_cutoff(pt, cr, FILE_TARGET, args.min_support)
        sugg_cut, _, sugg_ok = choose_cutoff(pt, cr, SUGGEST_TARGET, args.min_support)
        reached["file"] += int(file_ok)
        reached["suggest"] += int(sugg_ok)
        fp, fc = precision_coverage(p_top[idx], correct[idx], params.file_cutoff)
        sp, sc = precision_coverage(p_top[idx], correct[idx], params.suggest_cutoff)
        values = (t, ns, file_cut, min(sugg_cut, file_cut), fp, fc, sp, sc)
        for k, v in zip(KEYS, values, strict=True):
            rows[k].append(float(v))

    result = {
        "label": "toy scale",
        "model": encoder.name,
        "tasks": args.tasks,
        "n_examples": n,
        "resamples": args.resamples,
        "seed": args.seed,
        "min_support": args.min_support,
        "interval": "90% (5th to 95th percentile of the bootstrap distribution)",
        "calibration": {
            "temperature": params.temperature,
            "none_score": params.none_score,
            "file_cutoff": params.file_cutoff,
            "suggest_cutoff": params.suggest_cutoff,
        },
        "refit_on_full_split": {
            "temperature": full_t,
            "none_score": full_n,
            "nll": round(full_nll, 4),
            "matches_calibration": matches,
        },
        "point": {
            "file_precision": point_file[0],
            "file_coverage": point_file[1],
            "suggest_precision": point_suggest[0],
            "suggest_coverage": point_suggest[1],
        },
        "intervals": {k: interval(v) for k, v in rows.items()},
        "target_reached_share": {k: v / args.resamples for k, v in reached.items()},
        "resamples_without_filed_decision": int(np.isnan(np.asarray(rows["file_precision"])).sum()),
        "seconds": round(time.perf_counter() - t0, 1),
        "date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = (
        Path(args.out)
        if args.out
        else config.RUNS_DIR / f"bootstrap-{Path(args.calibration).stem}.json"
    )
    write_json(out, result)

    cal = result["calibration"]
    iv = result["intervals"]
    print(f"bootstrap: {n} examples, {args.resamples} resamples, model {encoder.name}")
    print(
        f"  refit on the full split: temperature {full_t:.4f} none_score {full_n:.3f} "
        f"({'matches' if matches else 'DIFFERS FROM'} calibration.json)"
    )
    print("| quantity | calibration.json | point on practice | 90% bootstrap interval |")
    print("|---|---|---|---|")
    for k in ("temperature", "none_score", "file_cutoff", "suggest_cutoff"):
        print(f"| {k} | {cal[k]:.4f} | - | {iv[k]} |")
    for k in ("file_precision", "file_coverage", "suggest_precision", "suggest_coverage"):
        print(f"| {k} at the calibration cut-off | - | {result['point'][k]:.3f} | {iv[k]} |")
    share = result["target_reached_share"]
    print(
        f"  target reached on resamples: file {share['file']:.2f}, suggest {share['suggest']:.2f}; "
        f"resamples with no filed decision: {result['resamples_without_filed_decision']}"
    )
    print(f"bootstrap: wrote {out} in {result['seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
