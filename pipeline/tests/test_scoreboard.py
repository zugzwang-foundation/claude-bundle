"""The board file follows the contract exactly."""

from __future__ import annotations

from bundle_pipeline.exam import METRIC_KEYS
from bundle_pipeline.scoreboard import build_board, winner_note

CONTRACT_SORTER_KEYS = ("id", "name", *METRIC_KEYS)


def _record(sid: str, acc: float, f1: float) -> dict:
    rec = {"id": sid, "name": sid, **dict.fromkeys(METRIC_KEYS, 0.0), "n": 10}
    rec["accuracy"], rec["macro_f1"] = acc, f1
    rec["params"] = {
        "temperature": 0.05,
        "none_score": 0.3,
        "file_cutoff": 0.85,
        "suggest_cutoff": 0.55,
    }
    rec["model"] = "m"
    return rec


def test_build_board_contract_shape() -> None:
    exam = {
        "run_id": "2026-10-16-toy-v0",
        "date": "2026-10-16",
        "exam_hash": "abc",
        "base_model": "sentence-transformers/all-MiniLM-L6-v2",
        "sorters": [_record("B0", 0.2, 0.1), _record("B1", 0.6, 0.5), _record("B2", 0.7, 0.6)],
        "notes": ["from exam"],
    }
    board = build_board(exam, notes=["extra"])
    assert list(board) == ["run_id", "label", "date", "exam_hash", "base_model", "sorters", "notes"]
    assert board["label"] == "toy scale"
    for s in board["sorters"]:
        assert tuple(s) == CONTRACT_SORTER_KEYS
    assert "from exam" in board["notes"] and "extra" in board["notes"]
    assert any(n.startswith("B2 params") for n in board["notes"])
    assert winner_note(board).startswith("B2 beats B1")


def test_winner_note_when_student_loses_or_is_missing() -> None:
    exam = {
        "run_id": "r",
        "date": "d",
        "exam_hash": "h",
        "base_model": "b",
        "sorters": [_record("B1", 0.6, 0.5), _record("B2", 0.5, 0.4)],
        "notes": [],
    }
    assert "does not beat" in winner_note(build_board(exam))
    exam["sorters"] = [_record("B1", 0.6, 0.5)]
    assert "no student" in winner_note(build_board(exam))
