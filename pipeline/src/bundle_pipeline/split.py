"""`bundle-pipeline split`: deterministic per-person 80/10/10 split with a sealed exam.

Every person is ranked by sha256(person_id + salt). The first 80% of the
ranking are lessons, the next 10% practice and the last 10% the exam, so the
same people always land in the same split for a given salt, whatever order the
input arrives in. Each split is written as JSONL (one Person per line, sorted
by id) under data/splits/, and splits/exam.sha256 records the hash of the exam
file.

The exam is sealed: on a re-run that would change exam.jsonl while exam.sha256
exists, the command refuses and writes nothing unless --force is given.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from bundle_pipeline import config
from bundle_pipeline.schema import Person
from bundle_pipeline.store import (
    jsonl_text,
    read_people,
    sha256_file,
    sha256_text,
    write_json,
    write_text_atomic,
)

DEFAULT_SALT = "bundle-bdl3"
MANIFEST_NAME = "split.json"


def rank_key(person_id: str, salt: str) -> str:
    return hashlib.sha256(f"{person_id}{salt}".encode()).hexdigest()


def split_counts(n: int, fractions: Mapping[str, float] = config.SPLIT_FRACTIONS) -> dict[str, int]:
    """How many people go to each split: round, but keep at least one each when n >= 3."""
    if n <= 0:
        return dict.fromkeys(config.SPLIT_NAMES, 0)
    if n < 3:
        return {"lessons": n, "practice": 0, "exam": 0}
    exam = max(1, round(n * fractions["exam"]))
    practice = max(1, round(n * fractions["practice"]))
    lessons = n - exam - practice
    if lessons < 1:  # only possible for tiny n with odd fractions
        lessons, practice, exam = n - 2, 1, 1
    return {"lessons": lessons, "practice": practice, "exam": exam}


def assign_splits(ids: Iterable[str], salt: str = DEFAULT_SALT) -> dict[str, str]:
    """person_id -> split name; deterministic in `ids` as a set and `salt`."""
    ordered = sorted(set(ids), key=lambda i: (rank_key(i, salt), i))
    counts = split_counts(len(ordered))
    assignment: dict[str, str] = {}
    pos = 0
    for name in config.SPLIT_NAMES:
        for pid in ordered[pos : pos + counts[name]]:
            assignment[pid] = name
        pos += counts[name]
    return assignment


def split_people(people: list[Person], salt: str = DEFAULT_SALT) -> dict[str, list[Person]]:
    assignment = assign_splits((p.id for p in people), salt)
    out: dict[str, list[Person]] = {name: [] for name in config.SPLIT_NAMES}
    for person in sorted(people, key=lambda p: p.id):
        out[assignment[person.id]].append(person)
    return out


def read_exam_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text.split()[0] if text else None


def write_exam_hash(path: Path, digest: str, exam_name: str = "exam.jsonl") -> None:
    write_text_atomic(path, f"{digest}  {exam_name}\n")


def exam_hash_matches(exam_path: Path, hash_path: Path) -> bool:
    """True when exam.jsonl on disk still hashes to what exam.sha256 recorded."""
    recorded = read_exam_hash(hash_path)
    return recorded is not None and exam_path.is_file() and sha256_file(exam_path) == recorded


def main(args: argparse.Namespace) -> int:
    people_path = Path(args.people)
    out_dir = Path(args.out_dir)
    salt = args.salt
    if not people_path.is_file():
        print(f"split: no people file at {people_path}", file=sys.stderr)
        return 1
    people = read_people(people_path)
    if not people:
        print("split: people file is empty", file=sys.stderr)
        return 1
    ids = [p.id for p in people]
    if len(set(ids)) != len(ids):
        print("split: duplicate person ids", file=sys.stderr)
        return 1

    splits = split_people(people, salt)
    texts = {name: jsonl_text(items) for name, items in splits.items()}
    exam_digest = sha256_text(texts["exam"])

    hash_path = out_dir / config.EXAM_SHA256.name
    recorded = read_exam_hash(hash_path)
    if recorded is not None and recorded != exam_digest:
        if not args.force:
            print(
                f"split: refusing to change the sealed exam: {hash_path} records "
                f"{recorded[:12]}..., this run would write {exam_digest[:12]}... "
                "(pass --force to reseal)",
                file=sys.stderr,
            )
            return 2
        print(
            f"split: --force given, resealing the exam "
            f"({recorded[:12]}... -> {exam_digest[:12]}...)"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    for name in config.SPLIT_NAMES:
        write_text_atomic(out_dir / f"{name}.jsonl", texts[name])
    if recorded is None or args.force:
        write_exam_hash(hash_path, exam_digest)
    counts = {name: len(items) for name, items in splits.items()}
    chats = {name: sum(len(p.chats) for p in items) for name, items in splits.items()}
    write_json(
        out_dir / MANIFEST_NAME,
        {
            "salt": salt,
            "fractions": config.SPLIT_FRACTIONS,
            "people": counts,
            "chats": chats,
            "exam_sha256": exam_digest,
            "written_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": str(people_path),
        },
    )
    print(
        f"split: {len(people)} people -> "
        + ", ".join(f"{name} {counts[name]} ({chats[name]} chats)" for name in config.SPLIT_NAMES)
        + f"; exam sha256 {exam_digest[:16]}... "
        + ("(sealed now)" if recorded is None else "(resealed)" if args.force else "(unchanged)")
    )
    return 0


__all__ = [
    "DEFAULT_SALT",
    "MANIFEST_NAME",
    "assign_splits",
    "exam_hash_matches",
    "main",
    "rank_key",
    "read_exam_hash",
    "split_counts",
    "split_people",
    "write_exam_hash",
]
