"""The toy follow-up question: pairs, metrics and the CLI, all with the fake encoder."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from bundle_pipeline.followup_toy import (
    Pair,
    best_threshold,
    bootstrap_intervals,
    build_pairs,
    candidate_pairs,
    evaluate,
    labels,
    metrics_at,
    pair_counts,
    roc_auc,
    score_pairs,
)
from bundle_pipeline.store import write_jsonl

from .fake_encoder import FakeEncoder


def _index(people) -> dict[str, tuple[str | None, int]]:
    return {c.id: (c.thread_id, c.day) for p in people for c in p.chats}


def test_candidate_pairs_follow_the_contract(people) -> None:
    person = people[0]
    pos, neg = candidate_pairs(person)
    threads = {c.id: c.thread_id for c in person.chats}
    days = {c.id: c.day for c in person.chats}
    assert pos and neg
    for p in pos:
        assert p.label == 1 and p.kind == "same_thread"
        assert threads[p.chat_id] is not None
        assert threads[p.chat_id] == threads[p.earlier_id]
        assert days[p.chat_id] >= days[p.earlier_id]
        assert p.gap_days == days[p.chat_id] - days[p.earlier_id]
    for n in neg:
        assert n.label == 0
        assert threads[n.chat_id] is None or threads[n.chat_id] != threads[n.earlier_id]
        assert n.kind == ("loose" if threads[n.earlier_id] is None else "other_thread")
        assert days[n.chat_id] >= days[n.earlier_id]
    # every ordered (later, earlier) pair of the person appears exactly once
    n_chats = len(person.chats)
    assert len(pos) + len(neg) == n_chats * (n_chats - 1) // 2


def test_build_pairs_is_balanced_capped_and_deterministic(people) -> None:
    pairs = build_pairs(people, seed=3, max_pairs=2000)
    counts = pair_counts(pairs)
    assert counts["positive"] == counts["negative"] == len(pairs) // 2
    assert counts["positive"] == sum(len(candidate_pairs(p)[0]) for p in people)
    assert counts["people"] == 2
    assert len({(p.person_id, p.chat_id, p.earlier_id) for p in pairs}) == len(pairs)
    assert build_pairs(people, seed=3) == pairs
    assert build_pairs(people, seed=4) != pairs
    small = build_pairs(people, seed=3, max_pairs=7)
    assert len(small) == 6 and pair_counts(small)["positive"] == 3
    idx = _index(people)
    for p in small:
        assert idx[p.chat_id][1] >= idx[p.earlier_id][1]


def test_negatives_share_the_anchor_when_one_exists(people) -> None:
    pairs = build_pairs(people, seed=3)
    pos_anchors = sorted(p.chat_id for p in pairs if p.label)
    neg_anchors = sorted(p.chat_id for p in pairs if not p.label)
    # most negatives are anchor-matched; the fixture's second chat of a thread
    # may have no other earlier chat, so allow a few fallbacks
    matched = sum(1 for a in pos_anchors if a in set(neg_anchors))
    assert matched >= len(pos_anchors) * 0.6


def test_roc_auc_matches_sklearn_with_ties() -> None:
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 300).astype(bool)
    s = np.round(rng.normal(size=300) + y * 0.7, 1)  # rounding makes ties
    assert roc_auc(y, s) == pytest.approx(roc_auc_score(y, s), abs=1e-12)
    assert roc_auc(np.array([1, 1, 0, 0], bool), np.array([0.9, 0.8, 0.2, 0.1])) == 1.0
    assert roc_auc(np.array([1, 1, 0, 0], bool), np.array([0.1, 0.2, 0.8, 0.9])) == 0.0
    assert roc_auc(np.array([1, 0], bool), np.array([0.5, 0.5])) == 0.5
    assert np.isnan(roc_auc(np.array([1, 1], bool), np.array([0.5, 0.6])))


def test_best_threshold_and_metrics() -> None:
    y = np.array([0, 0, 0, 1, 1, 1], bool)
    s = np.array([0.1, 0.2, 0.4, 0.3, 0.6, 0.7])
    t, acc = best_threshold(y, s)
    assert acc == pytest.approx(5 / 6)
    # two cuts tie at 5/6 (0.25 and 0.5); the middle rule takes index len//2, so 0.5
    assert t == pytest.approx(0.5)
    m = metrics_at(y, s, t)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 0, 1, 3)
    assert m["precision"] == 1.0 and m["recall"] == pytest.approx(2 / 3)
    assert m["accuracy"] == pytest.approx(5 / 6)
    assert metrics_at(y, s, 0.25)["accuracy"] == pytest.approx(5 / 6)
    m2 = metrics_at(y, s, 10.0)
    assert m2["precision"] == 0.0 and m2["recall"] == 0.0 and m2["accuracy"] == 0.5
    b = bootstrap_intervals(y, s, t, resamples=50, seed=1)
    assert b["resamples"] >= 1
    for k in ("auc_90", "accuracy_90", "precision_90", "recall_90"):
        lo, hi = b[k]
        assert 0.0 <= lo <= hi <= 1.0


def test_score_pairs_is_the_cosine(fake_encoder: FakeEncoder) -> None:
    pairs = [
        Pair("p", "c2", "c1", "running shoes for a marathon", "marathon plan", 1, "same_thread", 3),
        Pair("p", "c2", "c0", "running shoes for a marathon", "potato blight", 0, "loose", 5),
    ]
    s = score_pairs(fake_encoder.encode, pairs)
    a = fake_encoder.encode([pairs[0].chat])[0]
    assert s[0] == pytest.approx(float(a @ fake_encoder.encode([pairs[0].earlier])[0]), abs=1e-6)
    assert s[0] > s[1]
    assert labels(pairs).tolist() == [True, False]


def test_evaluate_with_the_fake_encoder(people, fake_encoder: FakeEncoder) -> None:
    practice = build_pairs([people[0]], seed=3)
    exam = build_pairs([people[1]], seed=3)
    r = evaluate(fake_encoder.encode, practice, exam, resamples=20, seed=3)
    assert r["practice"]["pairs"] == len(practice) and r["exam"]["pairs"] == len(exam)
    e = r["exam"]
    assert e["threshold"] == r["practice"]["threshold"]
    for k in ("auc", "accuracy", "precision", "recall", "f1", "oracle_accuracy"):
        assert 0.0 <= e[k] <= 1.0
    assert e["oracle_accuracy"] >= e["accuracy"]
    assert e["tp"] + e["fp"] + e["fn"] + e["tn"] == len(exam)
    assert set(e["negatives_rejected_by_kind"]) == {"other_thread", "loose"}
    assert set(e["positive_recall_by_gap_days"]) == {"0-7", "8-44", "45+"}


def test_cli_runs_offline_with_a_fake_encoder(people, tmp_path: Path, monkeypatch) -> None:
    import bundle_pipeline.encoder as encoder_module
    from bundle_pipeline.cli import main

    root = tmp_path / "data"
    write_jsonl(root / "splits" / "practice.jsonl", [people[0]])
    write_jsonl(root / "splits" / "exam.jsonl", [people[1]])
    student = root / "models" / "student-v0"
    student.mkdir(parents=True)
    made: list[str] = []

    def fake_factory(model: str, device: str = "auto", **_: object) -> FakeEncoder:
        made.append(model)
        return FakeEncoder()

    monkeypatch.setattr(encoder_module, "Encoder", fake_factory)
    code = main(
        [
            "followup-toy",
            "--data-root",
            str(root),
            "--encoder",
            "fake-base",
            "--student",
            str(student),
            "--resamples",
            "10",
        ]
    )
    assert code == 0
    assert made == ["fake-base", str(student)]
    out = json.loads((root / "runs" / "followup-toy.json").read_text())
    assert out["label"] == "toy scale"
    assert set(out["encoders"]) == {"base", "student"}
    assert out["pairs"]["exam"]["positive"] == out["pairs"]["exam"]["negative"] > 0
    assert 0.0 <= out["encoders"]["student"]["exam"]["auc"] <= 1.0
    # a missing student is skipped, not an error
    assert main(["followup-toy", "--data-root", str(root), "--student", str(root / "nope")]) == 0
    assert main(["followup-toy", "--data-root", str(tmp_path / "empty")]) == 2
