"""tasks.examples_for_person follows the contract on the fixture and on synthetic people."""

from __future__ import annotations

from pathlib import Path

from bundle_pipeline.cli import main
from bundle_pipeline.schema import Chat, DecisionExample, Person, Thread
from bundle_pipeline.store import read_examples, write_people
from bundle_pipeline.tasks import examples_for_person


def _by_chat(examples: list[DecisionExample]) -> dict[str, DecisionExample]:
    return {e.chat_id: e for e in examples}


def test_one_example_per_chat_in_day_order(people: list[Person]) -> None:
    for person in people:
        examples = examples_for_person(person)
        assert [e.chat_id for e in examples] == [c.id for c in person.chats]
        assert [e.day for e in examples] == sorted(e.day for e in examples)
        assert len({e.id for e in examples}) == len(examples)
        assert all(e.person_id == person.id for e in examples)


def test_first_second_third_chat_of_a_thread(people: list[Person]) -> None:
    person = people[0]  # p_fixture_01
    ex = _by_chat(examples_for_person(person))
    # p01-t1: c01 (first), c03 (second), c07 (third)
    assert ex["p01-c01"].answer == "none"
    assert ex["p01-c01"].candidates == []
    assert ex["p01-c03"].answer == "c:p01-c01"
    assert ex["p01-c07"].answer == "b:p01-t1"
    # p01-t2: c02 first -> none; c05 second -> the loose first chat
    assert ex["p01-c02"].answer == "none"
    assert ex["p01-c05"].answer == "c:p01-c02"


def test_loose_nowhere_chats_answer_none_and_become_candidates(people: list[Person]) -> None:
    person = people[0]
    examples = examples_for_person(person)
    ex = _by_chat(examples)
    assert ex["p01-c04"].thread_id if False else True  # noqa: PLR1714 - keep the lookup readable
    assert ex["p01-c04"].answer == "none"
    later = ex["p01-c05"]
    loose_ids = {c.id for c in later.candidates if c.kind == "loose"}
    assert "c:p01-c04" in loose_ids


def test_answer_is_none_or_a_present_candidate(people: list[Person]) -> None:
    for person in people:
        for e in examples_for_person(person):
            ids = {c.id for c in e.candidates}
            assert e.answer == "none" or e.answer in ids, (person.id, e.chat_id, e.answer)


def test_candidate_shapes_and_bundle_creation(people: list[Person]) -> None:
    person = people[0]
    ex = _by_chat(examples_for_person(person))
    at_c07 = ex["p01-c07"]
    bundle = next(c for c in at_c07.candidates if c.id == "b:p01-t1")
    assert bundle.kind == "bundle"
    assert bundle.label == "Half marathon"
    assert bundle.examples == [
        ch.text for ch in person.chats if ch.thread_id == "p01-t1" and ch.day < at_c07.day
    ]
    assert bundle.text is None
    # once the bundle exists the thread's first chat is no longer loose
    assert "c:p01-c01" not in {c.id for c in at_c07.candidates}
    loose = [c for c in at_c07.candidates if c.kind == "loose"]
    assert all(c.text and c.examples == [] and c.label is None for c in loose)
    bundles = [c for c in at_c07.candidates if c.kind == "bundle"]
    assert {b.id for b in bundles} == {"b:p01-t1", "b:p01-t2"}


def _long_thread_person(n: int = 12) -> Person:
    chats = [
        Chat(
            id=f"c{i:02d}",
            thread_id="t1",
            day=i * 3,
            text=f"message number {i}",
            difficulty="plain",
        )
        for i in range(n)
    ]
    return Person(
        id="p_long",
        persona="A made-up person for a unit test.",
        interests=["testing"],
        threads=[Thread(id="t1", label="Long", description="A thread with many chats.")],
        chats=chats,
        teacher={"model": "fixture", "seed": 0, "prompt_version": "test"},
    )


def test_bundle_examples_cap_at_eight_most_recent() -> None:
    person = _long_thread_person(12)
    examples = examples_for_person(person)
    last = examples[-1]
    bundle = last.candidates[0]
    assert bundle.id == "b:t1"
    assert len(bundle.examples) == 8
    assert bundle.examples == [f"message number {i}" for i in range(3, 11)]
    assert [e.answer for e in examples[:3]] == ["none", "c:c00", "b:t1"]
    assert all(e.answer == "b:t1" for e in examples[2:])


def test_same_day_chats_keep_file_order() -> None:
    chats = [
        Chat(id="a", thread_id="t1", day=0, text="first", difficulty="new_thread"),
        Chat(id="b", thread_id="t1", day=0, text="second same day", difficulty="plain"),
        Chat(id="c", thread_id=None, day=0, text="loose same day", difficulty="nowhere"),
    ]
    person = Person(
        id="p_ties",
        persona="Ties.",
        interests=["x"],
        threads=[Thread(id="t1", label="T", description="d")],
        chats=chats,
        teacher={"model": "fixture", "seed": 0, "prompt_version": "test"},
    )
    answers = [e.answer for e in examples_for_person(person)]
    assert answers == ["none", "c:a", "none"]


def test_tasks_cli_writes_each_split(tmp_path: Path, people: list[Person]) -> None:
    splits = tmp_path / "splits"
    write_people(splits / "lessons.jsonl", people[:1])
    write_people(splits / "practice.jsonl", people[1:])
    out = tmp_path / "tasks"
    rc = main(["tasks", "--splits-dir", str(splits), "--out-dir", str(out)])
    assert rc == 0
    lessons = read_examples(out / "lessons.jsonl")
    practice = read_examples(out / "practice.jsonl")
    assert len(lessons) == len(people[0].chats)
    assert len(practice) == len(people[1].chats)
    assert not (out / "exam.jsonl").exists()


def test_tasks_cli_fails_without_splits(tmp_path: Path) -> None:
    rc = main(["tasks", "--splits-dir", str(tmp_path / "none"), "--out-dir", str(tmp_path / "o")])
    assert rc == 1
