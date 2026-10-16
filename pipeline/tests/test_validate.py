"""validate: deduplication (exact and near), label sanity repairs, CLI report."""

from __future__ import annotations

import json
from pathlib import Path

from bundle_pipeline.cli import main
from bundle_pipeline.schema import Chat, Person, Thread
from bundle_pipeline.store import read_people
from bundle_pipeline.validate import (
    dedupe_chats,
    normalise,
    token_jaccard,
    validate_person,
)


def _chat(cid: str, text: str, day: int = 0, tid: str | None = "t1", diff: str = "plain") -> Chat:
    return Chat(id=cid, thread_id=tid, day=day, text=text, difficulty=diff)  # type: ignore[arg-type]


def _person(chats: list[Chat], threads: list[Thread] | None = None) -> Person:
    return Person(
        id="p_test",
        persona="A made-up person for the validator tests.",
        interests=["testing"],
        threads=threads or [Thread(id="t1", label="T1", description="d1")],
        chats=chats,
        teacher={"model": "fixture", "seed": 0, "prompt_version": "test"},
    )


def test_normalise_strips_case_and_punctuation() -> None:
    assert normalise("Knee hurts!!  ") == "knee hurts"
    assert normalise("whats the differnce, between 700c & 27in?") == normalise(
        "WHATS the differnce between 700c 27in"
    )


def test_token_jaccard() -> None:
    assert token_jaccard("a b c d", "a b c d") == 1.0
    assert token_jaccard("a b c d e f g h i j", "a b c d e f g h i k") == 9 / 11
    assert token_jaccard("", "") == 1.0
    assert token_jaccard("x", "y") == 0.0


def test_dedupe_catches_exact_after_normalisation() -> None:
    chats = [_chat("c1", "Knee hurts"), _chat("c2", "knee hurts!", day=3)]
    kept, dropped = dedupe_chats(chats)
    assert [c.id for c in kept] == ["c1"]
    assert dropped[0].reason == "exact" and dropped[0].kept_id == "c1"


def test_dedupe_catches_a_near_duplicate() -> None:
    a = "can you build me a training plan for a half marathon in twelve weeks around shifts"
    b = "can you build me a training plan for a half marathon in twelve weeks around work"
    assert token_jaccard(a, b) >= 0.8
    kept, dropped = dedupe_chats([_chat("c1", a), _chat("c2", b, day=5)])
    assert [c.id for c in kept] == ["c1"]
    assert dropped[0].reason == "near" and dropped[0].score >= 0.8


def test_dedupe_keeps_genuinely_different_short_chats() -> None:
    kept, dropped = dedupe_chats(
        [_chat("c1", "knee hurts"), _chat("c2", "knee hurts again", day=2)]
    )
    assert len(kept) == 2 and dropped == []


def test_unknown_thread_dropped_and_single_chat_thread_made_loose() -> None:
    threads = [
        Thread(id="t1", label="T1", description="d"),
        Thread(id="t2", label="T2", description="d"),
    ]
    chats = [
        _chat("c1", "first t1 message", 0, "t1", "new_thread"),
        _chat("c2", "second t1 message about something else", 2, "t1"),
        _chat("c3", "lonely t2 message", 4, "t2", "new_thread"),
        _chat("c4", "ghost thread message", 5, "t9"),
        _chat("c5", "a loose question about anything", 6, None, "nowhere"),
    ]
    cleaned, report = validate_person(_person(chats, threads))
    assert cleaned is not None and report.accepted
    assert [t.id for t in cleaned.threads] == ["t1"]
    ids = [c.id for c in cleaned.chats]
    assert ids == ["c1", "c2", "c3", "c5"]
    assert next(c for c in cleaned.chats if c.id == "c3").thread_id is None
    assert any("unknown thread 't9'" in i for i in report.issues)
    assert any("t2 has one chat" in i for i in report.issues)


def test_days_are_reordered_and_shifted_to_zero() -> None:
    chats = [
        _chat("c1", "first message here", 10, "t1", "new_thread"),
        _chat("c2", "earlier message typed later", 7, "t1"),
        _chat("c3", "third message about the thread", 12, "t1"),
    ]
    cleaned, report = validate_person(_person(chats))
    assert cleaned is not None
    assert [c.id for c in cleaned.chats] == ["c2", "c1", "c3"]
    assert [c.day for c in cleaned.chats] == [0, 3, 5]
    assert any("reordered" in i for i in report.issues)
    assert any("shifted" in i for i in report.issues)


def test_person_rejected_when_no_thread_survives() -> None:
    chats = [
        _chat("c1", "only one", 0, "t1", "new_thread"),
        _chat("c2", "loose", 1, None, "nowhere"),
    ]
    cleaned, report = validate_person(_person(chats))
    assert cleaned is None and not report.accepted
    assert report.issues[-1].startswith("rejected")


def test_fixture_passes_unchanged(people: list[Person]) -> None:
    for person in people:
        cleaned, report = validate_person(person)
        assert cleaned == person, report.issues
        assert report.issues == []


def test_cli_writes_people_and_report(tmp_path: Path, people: list[Person]) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    for p in people:
        (raw / f"{p.id}.json").write_text(p.model_dump_json(indent=2))
    # a near-duplicate inside a copy of the first person
    dup = people[0].model_copy(deep=True, update={"id": "p_dup"})
    dup.chats.append(
        dup.chats[2].model_copy(
            update={"id": "dupe", "day": 99, "text": dup.chats[2].text + " please"}
        )
    )
    (raw / "p_dup.json").write_text(dup.model_dump_json(indent=2))
    (raw / "broken.json").write_text('{"id": "x"}')
    out = tmp_path / "validated" / "people.jsonl"
    rc = main(["validate", "--raw", str(raw), "--out", str(out)])
    assert rc == 0
    accepted = read_people(out)
    assert [p.id for p in accepted] == ["p_dup", "p_fixture_01", "p_fixture_02"]
    report = json.loads((out.parent / "report.json").read_text())
    assert report["summary"]["accepted"] == 3
    assert report["summary"]["dropped_near"] == 1
    assert [r["file"] for r in report["summary"]["rejected"]] == ["broken.json"]
    assert len(next(p for p in accepted if p.id == "p_dup").chats) == len(people[0].chats)


def test_cli_fails_on_empty_dir(tmp_path: Path) -> None:
    assert main(["validate", "--raw", str(tmp_path), "--out", str(tmp_path / "o.jsonl")]) == 1
