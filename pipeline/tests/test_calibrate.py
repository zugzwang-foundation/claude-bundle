"""Calibration: the cut-off search reaches its precision target; the NLL fit does not get worse."""

from __future__ import annotations

import numpy as np
import pytest

from bundle_pipeline.calibrate import (
    FILE_TARGET,
    SUGGEST_TARGET,
    Calibration,
    calibrate,
    calibration_payload,
    choose_cutoff,
    fit_temperature_and_none,
    score_examples,
    top_probabilities,
    web_payload,
)
from bundle_pipeline.config import DEFAULT_SORTER, SorterParams
from bundle_pipeline.sorter import Scored, mean_nll


def _synthetic(n: int = 400, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """p_top in [0.3, 1); correctness drawn with probability p_top (perfectly calibrated)."""
    rng = np.random.default_rng(seed)
    p_top = rng.uniform(0.3, 1.0, size=n)
    correct = rng.uniform(size=n) < p_top
    return p_top, correct


@pytest.mark.parametrize("target", [FILE_TARGET, SUGGEST_TARGET, 0.5])
def test_cutoff_reaches_target_precision(target: float) -> None:
    p_top, correct = _synthetic()
    t, support, reached = choose_cutoff(p_top, correct, target, min_support=5)
    assert reached and support >= 5
    mask = p_top >= t
    assert correct[mask].mean() >= target
    assert mask.sum() == support


def test_cutoff_is_the_smallest_qualifying_threshold() -> None:
    p_top = np.array([0.99, 0.95, 0.90, 0.80, 0.70, 0.60])
    correct = np.array([True, True, True, True, False, False])
    t, support, reached = choose_cutoff(p_top, correct, 0.95, min_support=1)
    assert reached and t == 0.80 and support == 4  # 4/4 at 0.80; 4/5 at 0.70 fails


def test_cutoff_falls_back_to_one_when_nothing_qualifies() -> None:
    p_top = np.array([0.9, 0.8, 0.7])
    correct = np.array([False, False, True])
    t, support, reached = choose_cutoff(p_top, correct, 0.95, min_support=1)
    assert (t, support, reached) == (1.0, 0, False)
    assert choose_cutoff([], [], 0.9) == (1.0, 0, False)


def test_cutoff_respects_min_support() -> None:
    p_top = np.array([0.99, 0.5, 0.4])
    correct = np.array([True, False, False])
    _, _, reached = choose_cutoff(p_top, correct, 0.95, min_support=2)
    assert not reached


def _scored_set(seed: int = 1, n: int = 120) -> list[Scored]:
    rng = np.random.default_rng(seed)
    scored = []
    for i in range(n):
        k = int(rng.integers(1, 5))
        scores = rng.uniform(0.0, 0.5, size=k)
        if i % 4 == 0:
            answer = "none"  # all candidates are poor
        else:
            j = int(rng.integers(k))
            scores[j] = rng.uniform(0.55, 0.95)
            answer = f"b:{j}"
        scored.append(Scored(ids=[f"b:{j}" for j in range(k)], scores=scores, answer=answer))
    return scored


def test_fit_never_increases_nll_and_stays_on_the_grids() -> None:
    scored = _scored_set()
    params, nll = fit_temperature_and_none(scored, DEFAULT_SORTER)
    assert nll <= mean_nll(scored, DEFAULT_SORTER) + 1e-12
    assert nll == pytest.approx(mean_nll(scored, params))
    assert 0.01 <= params.temperature <= 1.0
    assert 0.0 <= params.none_score <= 1.0
    assert params.file_cutoff == DEFAULT_SORTER.file_cutoff  # untouched by step 1


def test_calibrate_end_to_end_on_synthetic_scores() -> None:
    scored = _scored_set(n=300)
    cal = calibrate(scored, min_support=5)
    assert isinstance(cal, Calibration)
    assert cal.nll_after <= cal.nll_before
    assert cal.params.suggest_cutoff <= cal.params.file_cutoff
    p_top, correct = top_probabilities(scored, cal.params)
    p_top_a, correct_a = np.asarray(p_top), np.asarray(correct)
    if cal.file_reached:
        assert correct_a[p_top_a >= cal.params.file_cutoff].mean() >= FILE_TARGET
    if cal.suggest_reached:
        assert correct_a[p_top_a >= cal.params.suggest_cutoff].mean() >= SUGGEST_TARGET
    assert "practice split, 300 examples" in cal.source()


def test_payloads_have_the_contract_keys() -> None:
    cal = Calibration(SorterParams(0.07, 0.42, 0.9, 0.6), 1.0, 0.8, 50, 10, 20, True, True)
    payload = calibration_payload("student-v0", cal, note="test")
    assert list(payload) == [
        "model",
        "temperature",
        "none_score",
        "file_cutoff",
        "suggest_cutoff",
        "practice_size",
        "source",
    ]
    web = web_payload(payload)
    assert set(web) == {
        "temperature",
        "noneScore",
        "fileCutoff",
        "suggestCutoff",
        "model",
        "source",
    }
    assert web["noneScore"] == 0.42 and web["fileCutoff"] == 0.9 and web["model"] == "student-v0"


def test_score_examples_uses_the_encoder_cache(fake_encoder, examples) -> None:
    scored = score_examples(fake_encoder, examples)
    assert len(scored) == len(examples)
    assert fake_encoder.calls == 1  # one warm batch, then dict lookups only
    assert all(len(s.ids) == len(s.scores) for s in scored)
