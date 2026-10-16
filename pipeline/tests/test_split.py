"""split: deterministic by person, no person in two splits, sealed exam."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from bundle_pipeline.cli import main
from bundle_pipeline.schema import Chat, Person, Thread
from bundle_pipeline.split import (
    assign_splits,
    exam_hash_matches,
    read_exam_hash,
    split_counts,
)
from bundle_pipeline.store import read_people, sha256_file, write_people


def _ids(n: int) -> list[str]:
    return [f"p3-{i:03d}" for i in range(n)]


def test_assignment_is_deterministic_and_order_independent() -> None:
    ids = _ids(50)
    a = assign_splits(ids, "salt-a")
    b = assign_splits(list(reversed(ids)), "salt-a")
    assert a == b
    assert set(a) == set(ids)


def test_no_person_in_two_splits_and_counts_are_80_10_10() -> None:
    a = assign_splits(_ids(50), "salt-a")
    counts = Counter(a.values())
    assert counts == {"lessons": 40, "practice": 5, "exam": 5}
    assert sum(counts.values()) == 50


def test_salt_changes_the_assignment() -> None:
    ids = _ids(50)
    a = assign_splits(ids, "salt-a")
    b = assign_splits(ids, "salt-b")
    assert a != b


def test_small_counts_keep_one_in_each_split() -> None:
    assert split_counts(24) == {"lessons": 20, "practice": 2, "exam": 2}
    assert split_counts(3) == {"lessons": 1, "practice": 1, "exam": 1}
    assert split_counts(2) == {"lessons": 2, "practice": 0, "exam": 0}
    assert split_counts(0) == {"lessons": 0, "practice": 0, "exam": 0}
    for n in range(3, 120):
        c = split_counts(n)
        assert sum(c.values()) == n and min(c.values()) >= 1


def _people(n: int) -> list[Person]:
    out = []
    for i in range(n):
        pid = f"p3-{i:03d}"
        out.append(
            Person(
                id=pid,
                persona=f"Synthetic person {i}.",
                interests=["x"],
                threads=[Thread(id=f"{pid}-t1", label="T", description="d")],
                chats=[
                    Chat(
                        id=f"{pid}-c1",
                        thread_id=f"{pid}-t1",
                        day=0,
                        text="a",
                        difficulty="new_thread",
                    ),
                    Chat(
                        id=f"{pid}-c2", thread_id=f"{pid}-t1", day=1, text="b", difficulty="plain"
                    ),
                ],
                teacher={"model": "fixture", "seed": 0, "prompt_version": "test"},
            )
        )
    return out


def test_cli_writes_splits_and_seals_the_exam(tmp_path: Path) -> None:
    people_path = tmp_path / "people.jsonl"
    write_people(people_path, _people(30))
    out = tmp_path / "splits"
    assert main(["split", "--people", str(people_path), "--out-dir", str(out)]) == 0
    lessons = read_people(out / "lessons.jsonl")
    practice = read_people(out / "practice.jsonl")
    exam = read_people(out / "exam.jsonl")
    assert (len(lessons), len(practice), len(exam)) == (24, 3, 3)
    all_ids = [p.id for p in lessons + practice + exam]
    assert len(all_ids) == len(set(all_ids)) == 30
    recorded = read_exam_hash(out / "exam.sha256")
    assert recorded == sha256_file(out / "exam.jsonl")
    assert exam_hash_matches(out / "exam.jsonl", out / "exam.sha256")
    # a second identical run is fine and leaves the seal alone
    assert main(["split", "--people", str(people_path), "--out-dir", str(out)]) == 0
    assert read_exam_hash(out / "exam.sha256") == recorded


def test_cli_refuses_to_change_a_sealed_exam_unless_forced(tmp_path: Path) -> None:
    people_path = tmp_path / "people.jsonl"
    write_people(people_path, _people(30))
    out = tmp_path / "splits"
    assert main(["split", "--people", str(people_path), "--out-dir", str(out)]) == 0
    before = (out / "exam.jsonl").read_bytes()
    recorded = read_exam_hash(out / "exam.sha256")

    # more people would move the exam boundary: refused, nothing rewritten
    write_people(people_path, _people(40))
    rc = main(["split", "--people", str(people_path), "--out-dir", str(out)])
    assert rc == 2
    assert (out / "exam.jsonl").read_bytes() == before
    assert read_exam_hash(out / "exam.sha256") == recorded

    rc = main(["split", "--people", str(people_path), "--out-dir", str(out), "--force"])
    assert rc == 0
    assert (out / "exam.jsonl").read_bytes() != before
    assert read_exam_hash(out / "exam.sha256") == sha256_file(out / "exam.jsonl")


def test_cli_fails_on_missing_people(tmp_path: Path) -> None:
    rc = main(["split", "--people", str(tmp_path / "nope.jsonl"), "--out-dir", str(tmp_path / "s")])
    assert rc == 1
