"""The two-person fixture loads into the contract and covers what the relay asks for."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from bundle_pipeline.schema import (
    DIFFICULTIES,
    Candidate,
    Chat,
    Decision,
    DecisionExample,
    Person,
)


def test_fixture_is_small(fixture_path: Path) -> None:
    assert fixture_path.stat().st_size < 20_000


def test_fixture_has_two_people(people: list[Person]) -> None:
    assert len(people) == 2
    assert len({p.id for p in people}) == 2


def test_each_person_has_three_threads_of_two_to_four_chats(people: list[Person]) -> None:
    for person in people:
        assert len(person.threads) == 3
        thread_ids = {t.id for t in person.threads}
        per_thread = Counter(c.thread_id for c in person.chats if c.thread_id is not None)
        assert set(per_thread) == thread_ids, person.id
        for tid, n in per_thread.items():
            assert 2 <= n <= 4, (person.id, tid, n)


def test_each_person_has_two_or_three_loose_chats(people: list[Person]) -> None:
    for person in people:
        loose = [c for c in person.chats if c.thread_id is None]
        assert 2 <= len(loose) <= 3, person.id


def test_each_person_covers_all_eight_difficulties(people: list[Person]) -> None:
    for person in people:
        seen = {c.difficulty for c in person.chats}
        assert seen == set(DIFFICULTIES), (person.id, set(DIFFICULTIES) - seen)


def test_chats_are_in_day_order_with_unique_ids(people: list[Person]) -> None:
    for person in people:
        days = [c.day for c in person.chats]
        assert days == sorted(days), person.id
        assert days[0] == 0, person.id
        ids = [c.id for c in person.chats]
        assert len(ids) == len(set(ids)), person.id


def test_teacher_record_has_required_keys(people: list[Person]) -> None:
    for person in people:
        assert {"model", "seed", "prompt_version"} <= set(person.teacher)


def test_persona_has_no_real_names_marker(people: list[Person]) -> None:
    # Personas describe a role, never a named real person; a crude guard.
    for person in people:
        assert person.persona.strip()
        assert "http" not in person.persona


def test_difficulty_literal_is_enforced() -> None:
    with pytest.raises(ValidationError):
        Chat(id="x", thread_id=None, day=0, text="hi", difficulty="easy")  # type: ignore[arg-type]


def test_chat_day_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        Chat(id="x", thread_id=None, day=-1, text="hi", difficulty="plain")


def test_decision_example_round_trip() -> None:
    ex = DecisionExample(
        id="p01-c03",
        person_id="p_fixture_01",
        chat_id="p01-c03",
        chat="what should i eat before a long run",
        candidates=[
            Candidate(id="b:p01-t1", kind="bundle", label="Half marathon", examples=["a", "b"]),
            Candidate(id="c:p01-c02", kind="loose", text="my starter smells odd"),
        ],
        answer="b:p01-t1",
        difficulty="overlap",
        day=4,
    )
    again = DecisionExample.model_validate_json(ex.model_dump_json())
    assert again == ex
    assert again.candidates[1].examples == []


def test_decision_shape() -> None:
    d = Decision(probabilities={"b:p01-t1": 0.9, "none": 0.1}, action="file", target="b:p01-t1")
    assert d.model_dump()["target"] == "b:p01-t1"
    with pytest.raises(ValidationError):
        Decision(probabilities={"none": 1.0}, action="ignore")  # type: ignore[arg-type]
