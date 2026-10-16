"""Exam metrics on tiny synthetic sets: ECE, Brier, macro-F1, none P/R, cut-off precision."""

from __future__ import annotations

import numpy as np
import pytest

from bundle_pipeline.config import SorterParams
from bundle_pipeline.exam import (
    METRIC_KEYS,
    answer_class,
    brier_score,
    compute_metrics,
    expected_calibration_error,
    load_params,
    macro_f1,
    none_precision_recall,
    render_table,
    run_encoder,
    run_leave,
)
from bundle_pipeline.schema import Candidate, Decision, DecisionExample


def _example(answer: str, cands: list[str]) -> DecisionExample:
    candidates = [
        Candidate(id=c, kind="bundle" if c.startswith("b:") else "loose", label="L", examples=["x"])
        if c.startswith("b:")
        else Candidate(id=c, kind="loose", text="t")
        for c in cands
    ]
    return DecisionExample(
        id="e",
        person_id="p",
        chat_id="c",
        chat="chat",
        candidates=candidates,
        answer=answer,
        difficulty="plain",
        day=0,
    )


def _decision(probs: dict[str, float], params: SorterParams) -> Decision:
    from bundle_pipeline.sorter import decide

    return decide(probs, params)


def test_ece_is_zero_for_perfect_calibration() -> None:
    # every prediction at 0.8 and exactly 80% of them right, all in one bin
    p = [0.8] * 10
    hit = [True] * 8 + [False] * 2
    assert expected_calibration_error(p, hit) == pytest.approx(0.0)
    assert expected_calibration_error([1.0, 1.0], [True, True]) == 0.0
    assert expected_calibration_error([], []) == 0.0


def test_ece_is_one_minus_accuracy_for_overconfident_wrong_answers() -> None:
    assert expected_calibration_error([1.0] * 4, [True, False, False, False]) == pytest.approx(0.75)


def test_brier_bounds_and_values() -> None:
    assert brier_score([1.0, 1.0], [True, True]) == 0.0
    assert brier_score([1.0, 1.0], [False, False]) == 1.0
    assert brier_score([0.5, 0.5], [True, False]) == pytest.approx(0.25)
    rng = np.random.default_rng(0)
    p = rng.uniform(size=50)
    h = rng.uniform(size=50) < 0.5
    assert 0.0 <= brier_score(p, h) <= 1.0


def test_answer_class() -> None:
    assert answer_class("b:t1") == "bundle"
    assert answer_class("c:c1") == "loose"
    assert answer_class("none") == "none"
    with pytest.raises(ValueError):
        answer_class("x:1")


def test_macro_f1_counts_the_wrong_bundle_as_a_miss() -> None:
    answers = ["b:a", "b:a", "c:x", "none"]
    perfect = ["b:a", "b:a", "c:x", "none"]
    assert macro_f1(answers, perfect) == pytest.approx(1.0)
    wrong_bundle = ["b:b", "b:a", "c:x", "none"]  # right class, wrong target
    f1 = macro_f1(answers, wrong_bundle)
    # bundle: tp 1, fp 1, fn 1 -> P 0.5 R 0.5 F1 0.5; loose 1; none 1 -> mean 0.8333
    assert f1 == pytest.approx((0.5 + 1.0 + 1.0) / 3)


def test_none_precision_recall() -> None:
    answers = ["none", "none", "b:a", "c:x"]
    preds = ["none", "b:a", "none", "c:x"]
    p, r = none_precision_recall(answers, preds)
    assert p == pytest.approx(0.5) and r == pytest.approx(0.5)
    assert none_precision_recall(["b:a"], ["b:a"]) == (0.0, 0.0)


def test_compute_metrics_on_a_tiny_set() -> None:
    params = SorterParams(0.05, 0.30, 0.85, 0.55)
    examples = [
        _example("b:a", ["b:a", "c:x"]),  # filed right
        _example("b:a", ["b:a", "c:x"]),  # suggested right
        _example("none", ["b:a", "c:x"]),  # filed wrong (none answer)
        _example("c:x", ["b:a", "c:x"]),  # left, argmax none -> miss
    ]
    decisions = [
        _decision({"b:a": 0.90, "c:x": 0.05, "none": 0.05}, params),
        _decision({"b:a": 0.60, "c:x": 0.30, "none": 0.10}, params),
        _decision({"b:a": 0.86, "c:x": 0.04, "none": 0.10}, params),
        _decision({"b:a": 0.20, "c:x": 0.30, "none": 0.50}, params),
    ]
    m = compute_metrics(examples, decisions, latencies_ms=[1.0, 3.0, 2.0], size_mb=12.5)
    assert set(m) == set(METRIC_KEYS)
    assert m["accuracy"] == pytest.approx(0.5)
    assert m["file_coverage"] == pytest.approx(0.5)  # examples 1 and 3
    assert m["file_precision"] == pytest.approx(0.5)  # 3 filed a "none" answer
    assert m["suggest_coverage"] == pytest.approx(0.75)  # 1, 2, 3
    assert m["suggest_precision"] == pytest.approx(2 / 3)
    assert m["none_precision"] == pytest.approx(0.0) and m["none_recall"] == pytest.approx(0.0)
    assert m["latency_ms_per_decision"] == 2.0
    assert m["size_mb"] == 12.5
    assert 0.0 <= m["ece"] <= 1.0 and 0.0 <= m["brier"] <= 1.0
    # brier: chosen p/hit = (0.90,1) (0.60,1) (0.86,0) (0.50,0)
    assert m["brier"] == pytest.approx((0.01 + 0.16 + 0.86**2 + 0.25) / 4)


def test_compute_metrics_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        compute_metrics([_example("none", [])], [], [])


def test_run_leave_and_run_encoder_on_fixture(fake_encoder, examples) -> None:
    b0 = run_leave(examples)
    m0 = b0.metrics(examples)
    n_none = sum(ex.answer == "none" for ex in examples)
    assert m0["accuracy"] == pytest.approx(n_none / len(examples))
    assert m0["none_recall"] == 1.0 and m0["file_coverage"] == 0.0
    b1 = run_encoder("B1", "fake", fake_encoder, examples, SorterParams(0.05, 0.30, 0.85, 0.55))
    m1 = b1.metrics(examples)
    assert len(b1.decisions) == len(examples)
    assert len(b1.latencies_ms) == len(examples)  # sample covers all 25
    rec = b1.record(examples)
    assert rec["id"] == "B1" and rec["model"] == "fake-hash-encoder" and rec["n"] == 25
    assert m1["accuracy"] >= 0.0


def test_load_params_defaults_when_missing(tmp_path) -> None:
    assert load_params(None).temperature == 0.05
    assert load_params(tmp_path / "nope.json").none_score == 0.30
    (tmp_path / "c.json").write_text(
        '{"temperature": 0.1, "none_score": 0.4, "file_cutoff": 0.9, "suggest_cutoff": 0.6}'
    )
    p = load_params(tmp_path / "c.json")
    assert (p.temperature, p.none_score, p.file_cutoff, p.suggest_cutoff) == (0.1, 0.4, 0.9, 0.6)


def test_render_table_has_header_and_rows() -> None:
    rows = [{"id": "B0", "name": "leave", **dict.fromkeys(METRIC_KEYS, 0.0)}]
    table = render_table(rows)
    lines = table.splitlines()
    assert lines[0].startswith("| id | name | accuracy")
    assert len(lines) == 3 and lines[2].startswith("| B0 | leave |")
