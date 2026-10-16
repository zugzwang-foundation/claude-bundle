"""`bundle-pipeline tasks`: turn each chat into a DecisionExample.

Walk a person's chats in day order and keep two pieces of state:

- bundles: thread_id -> the earlier chats of that thread. A bundle exists only
  once its thread has two or more earlier chats; a thread's FIRST chat is a
  loose chat until a second one arrives.
- loose chats: chats with thread_id None, plus first-of-thread chats.

For each chat the candidates are every current bundle (kind "bundle", label =
thread label, examples = up to 8 most recent texts) and every current loose
chat (kind "loose", text). The answer is the bundle id "b:<thread_id>" if the
chat's thread already has a bundle; the loose chat id "c:<chat_id>" if the
thread has exactly one earlier chat; else "none" (thread_id None, or the first
chat of its thread). State is updated after the example is recorded.

`examples_for_person` is the pure function; `main` applies it to each split in
data/splits/ and writes data/tasks/<split>.jsonl.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from bundle_pipeline import config
from bundle_pipeline.schema import Candidate, Chat, DecisionExample, Person
from bundle_pipeline.store import read_people, write_examples


def bundle_id(thread_id: str) -> str:
    return f"b:{thread_id}"


def loose_id(chat_id: str) -> str:
    return f"c:{chat_id}"


def example_id(person_id: str, chat_id: str) -> str:
    return f"{person_id}:{chat_id}"


def examples_for_person(
    person: Person, max_examples: int = config.MAX_BUNDLE_EXAMPLES
) -> list[DecisionExample]:
    """One DecisionExample per chat, in day order, exactly as the contract says."""
    labels = {t.id: t.label for t in person.threads}
    bundles: dict[str, list[Chat]] = {}
    loose: dict[str, Chat] = {}
    first_of_thread: dict[str, Chat] = {}
    out: list[DecisionExample] = []

    for chat in sorted(person.chats, key=lambda c: c.day):  # stable: ties keep file order
        candidates = [
            Candidate(
                id=bundle_id(tid),
                kind="bundle",
                label=labels.get(tid, tid),
                examples=[c.text for c in earlier[-max_examples:]],
            )
            for tid, earlier in bundles.items()
        ]
        candidates.extend(
            Candidate(id=loose_id(cid), kind="loose", text=c.text) for cid, c in loose.items()
        )

        tid = chat.thread_id
        if tid is None:
            answer = "none"
        elif tid in bundles:
            answer = bundle_id(tid)
        elif tid in first_of_thread:
            answer = loose_id(first_of_thread[tid].id)
        else:
            answer = "none"

        out.append(
            DecisionExample(
                id=example_id(person.id, chat.id),
                person_id=person.id,
                chat_id=chat.id,
                chat=chat.text,
                candidates=candidates,
                answer=answer,
                difficulty=chat.difficulty,
                day=chat.day,
            )
        )

        if tid is None:
            loose[chat.id] = chat
        elif tid in bundles:
            bundles[tid].append(chat)
        elif tid in first_of_thread:
            first = first_of_thread.pop(tid)
            loose.pop(first.id, None)
            bundles[tid] = [first, chat]
        else:
            first_of_thread[tid] = chat
            loose[chat.id] = chat
    return out


def examples_for_people(people: list[Person]) -> list[DecisionExample]:
    out: list[DecisionExample] = []
    for person in people:
        out.extend(examples_for_person(person))
    return out


def answer_kind(answer: str) -> str:
    if answer == "none":
        return "none"
    return "bundle" if answer.startswith("b:") else "loose"


def summarise(examples: list[DecisionExample]) -> dict:
    kinds = Counter(answer_kind(e.answer) for e in examples)
    difficulties = Counter(e.difficulty for e in examples)
    n_cand = [len(e.candidates) for e in examples]
    return {
        "examples": len(examples),
        "answers": dict(kinds),
        "difficulties": dict(sorted(difficulties.items())),
        "candidates_mean": round(sum(n_cand) / len(n_cand), 2) if n_cand else 0.0,
        "candidates_max": max(n_cand, default=0),
    }


def main(args: argparse.Namespace) -> int:
    splits_dir = Path(args.splits_dir)
    out_dir = Path(args.out_dir)
    found = 0
    for name in config.SPLIT_NAMES:
        src = splits_dir / f"{name}.jsonl"
        if not src.is_file():
            print(f"tasks: {src} missing, skipped", file=sys.stderr)
            continue
        found += 1
        people = read_people(src)
        examples = examples_for_people(people)
        n = write_examples(out_dir / f"{name}.jsonl", examples)
        s = summarise(examples)
        print(
            f"tasks: {name}: {len(people)} people -> {n} examples; answers {s['answers']}; "
            f"candidates mean {s['candidates_mean']} max {s['candidates_max']}; "
            f"difficulties {s['difficulties']}"
        )
    if not found:
        print(f"tasks: no split files under {splits_dir}; run `split` first", file=sys.stderr)
        return 1
    return 0


__all__ = [
    "answer_kind",
    "bundle_id",
    "example_id",
    "examples_for_people",
    "examples_for_person",
    "loose_id",
    "main",
    "summarise",
]
