"""`bundle-pipeline validate`: schema, deduplication and label sanity.

Reads every raw/people/*.json, keeps the people that pass, repairs what can be
repaired, and writes validated/people.jsonl plus validated/report.json.

Per person:
- schema: the file must load as `schema.Person`, else the person is rejected;
- dedupe: exact duplicates after normalising the text (lower case, letters and
  digits only, single spaces) and near-duplicates with token Jaccard >= 0.8
  are dropped, keeping the earlier chat;
- label sanity: chats pointing at an unknown thread id are dropped; chat days
  must be non-decreasing (a stable sort repairs them) and start at 0 (shifted);
  a thread with one chat left becomes a loose chat, a thread with none is
  removed; a person needs at least one thread and three chats to be kept.

Every repair is recorded in the report under the person's id so the teacher's
habits are visible.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from bundle_pipeline.schema import Chat, Person, Thread
from bundle_pipeline.store import write_json, write_people

NEAR_DUPLICATE_JACCARD = 0.8
MIN_CHATS_PER_PERSON = 3

_WORD = re.compile(r"[a-z0-9]+")


def normalise(text: str) -> str:
    """Lower case, letters and digits only, single spaces."""
    return " ".join(_WORD.findall(text.lower()))


def tokens(text: str) -> set[str]:
    return set(normalise(text).split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def token_jaccard(a: str, b: str) -> float:
    return jaccard(tokens(a), tokens(b))


@dataclass
class Dropped:
    chat_id: str
    kept_id: str
    reason: str  # "exact" or "near"
    score: float


def dedupe_chats(chats: list[Chat]) -> tuple[list[Chat], list[Dropped]]:
    """Keep the first of each duplicate group; report what was dropped and why."""
    kept: list[Chat] = []
    kept_tokens: list[set[str]] = []
    by_norm: dict[str, Chat] = {}
    dropped: list[Dropped] = []
    for chat in chats:
        norm = normalise(chat.text)
        if norm in by_norm:
            dropped.append(Dropped(chat.id, by_norm[norm].id, "exact", 1.0))
            continue
        toks = set(norm.split())
        near = None
        best = 0.0
        for other, other_tokens in zip(kept, kept_tokens, strict=True):
            score = jaccard(toks, other_tokens)
            if score >= NEAR_DUPLICATE_JACCARD and score > best:
                near, best = other, score
        if near is not None:
            dropped.append(Dropped(chat.id, near.id, "near", round(best, 3)))
            continue
        by_norm[norm] = chat
        kept.append(chat)
        kept_tokens.append(toks)
    return kept, dropped


@dataclass
class PersonReport:
    person_id: str
    accepted: bool
    chats_in: int
    chats_out: int
    dropped_exact: int = 0
    dropped_near: int = 0
    issues: list[str] = field(default_factory=list)


def validate_person(person: Person) -> tuple[Person | None, PersonReport]:
    """Repair what can be repaired; return None when the person must be rejected."""
    report = PersonReport(person.id, accepted=False, chats_in=len(person.chats), chats_out=0)
    issues = report.issues

    if not person.persona.strip():
        issues.append("rejected: empty persona")
        return None, report
    thread_ids = [t.id for t in person.threads]
    if len(set(thread_ids)) != len(thread_ids):
        issues.append("rejected: duplicate thread ids")
        return None, report
    chat_ids = [c.id for c in person.chats]
    if len(set(chat_ids)) != len(chat_ids):
        issues.append("rejected: duplicate chat ids")
        return None, report

    known = set(thread_ids)
    chats: list[Chat] = []
    for chat in person.chats:
        if not chat.text.strip():
            issues.append(f"dropped {chat.id}: empty text")
            continue
        if chat.thread_id is not None and chat.thread_id not in known:
            issues.append(f"dropped {chat.id}: unknown thread {chat.thread_id!r}")
            continue
        chats.append(chat)

    chats, dropped = dedupe_chats(chats)
    for d in dropped:
        if d.reason == "exact":
            report.dropped_exact += 1
        else:
            report.dropped_near += 1
        issues.append(f"dropped {d.chat_id}: {d.reason} duplicate of {d.kept_id} ({d.score})")

    days = [c.day for c in chats]
    if days != sorted(days):
        chats = sorted(chats, key=lambda c: c.day)  # stable: ties keep teacher order
        issues.append("reordered chats so days never decrease")
    if chats and chats[0].day != 0:
        shift = chats[0].day
        chats = [c.model_copy(update={"day": c.day - shift}) for c in chats]
        issues.append(f"shifted days by -{shift} so the first chat is day 0")

    counts: dict[str, int] = {tid: 0 for tid in thread_ids}
    for c in chats:
        if c.thread_id is not None:
            counts[c.thread_id] += 1
    threads: list[Thread] = []
    for thread in person.threads:
        n = counts[thread.id]
        if n >= 2:
            threads.append(thread)
        elif n == 1:
            issues.append(f"thread {thread.id} has one chat: made it loose, dropped the thread")
            chats = [
                c.model_copy(update={"thread_id": None}) if c.thread_id == thread.id else c
                for c in chats
            ]
        else:
            issues.append(f"thread {thread.id} has no chats: dropped the thread")

    report.chats_out = len(chats)
    if not threads:
        issues.append("rejected: no thread with two or more chats")
        return None, report
    if len(chats) < MIN_CHATS_PER_PERSON:
        issues.append(f"rejected: only {len(chats)} chats after cleaning")
        return None, report

    report.accepted = True
    cleaned = person.model_copy(update={"threads": threads, "chats": chats})
    return cleaned, report


def load_raw(path: Path) -> Person:
    return Person.model_validate_json(path.read_bytes())


def main(args: argparse.Namespace) -> int:
    raw_dir = Path(args.raw)
    out_path = Path(args.out)
    report_path = Path(args.report) if args.report else out_path.with_name("report.json")
    files = sorted(p for p in raw_dir.glob("*.json") if p.is_file())
    if not files:
        print(f"validate: no *.json under {raw_dir}", file=sys.stderr)
        return 1

    accepted: list[Person] = []
    rejected: list[dict[str, str]] = []
    reports: dict[str, dict] = {}
    totals = {"chats_in": 0, "chats_out": 0, "dropped_exact": 0, "dropped_near": 0}
    for path in files:
        try:
            person = load_raw(path)
        except (ValidationError, ValueError) as e:
            first_line = str(e).splitlines()[0][:200]
            rejected.append({"file": path.name, "reason": f"schema: {first_line}"})
            continue
        cleaned, report = validate_person(person)
        reports[person.id] = {
            "file": path.name,
            "accepted": report.accepted,
            "chats_in": report.chats_in,
            "chats_out": report.chats_out,
            "dropped_exact": report.dropped_exact,
            "dropped_near": report.dropped_near,
            "issues": report.issues,
        }
        totals["chats_in"] += report.chats_in
        totals["dropped_exact"] += report.dropped_exact
        totals["dropped_near"] += report.dropped_near
        if cleaned is None:
            reason = report.issues[-1] if report.issues else "?"
            rejected.append({"file": path.name, "reason": reason})
            continue
        totals["chats_out"] += report.chats_out
        accepted.append(cleaned)

    accepted.sort(key=lambda p: p.id)
    ids = [p.id for p in accepted]
    if len(set(ids)) != len(ids):
        print("validate: duplicate person ids across files; refusing to write", file=sys.stderr)
        return 1
    n = write_people(out_path, accepted)
    summary = {
        "input_files": len(files),
        "accepted": len(accepted),
        "rejected": rejected,
        **totals,
        "people_with_issues": sum(1 for r in reports.values() if r["issues"]),
        "output": str(out_path),
    }
    write_json(report_path, {"summary": summary, "people": reports})
    print(
        f"validate: {len(files)} files -> {n} people accepted, {len(rejected)} rejected; "
        f"chats {totals['chats_in']} -> {totals['chats_out']} "
        f"(exact dupes {totals['dropped_exact']}, near dupes {totals['dropped_near']}); "
        f"report {report_path}"
    )
    if args.verbose:
        print(json.dumps(summary, indent=2))
    return 0 if accepted else 1


__all__ = [
    "MIN_CHATS_PER_PERSON",
    "NEAR_DUPLICATE_JACCARD",
    "Dropped",
    "PersonReport",
    "dedupe_chats",
    "jaccard",
    "main",
    "normalise",
    "token_jaccard",
    "tokens",
    "validate_person",
]
