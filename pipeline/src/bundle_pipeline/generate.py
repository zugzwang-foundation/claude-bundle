"""`bundle-pipeline generate`: ask the teacher for people and their chats.

    bundle-pipeline generate --people 24 --chats-per-person 60 --seed 3 \
        --out data/raw/people --workers 2 --time-budget-min 60

One person at a time per worker: PERSONA, then CHATS_FOR_THREAD for each of the
3-5 threads (8-15 chats each), then LOOSE_CHATS (6-10), so the total is about
--chats-per-person. Each person is written as one JSON file once it validates
as `schema.Person`. Throughput (chats/min, and tokens/s when the server
reports usage) is printed per person and appended to data/generate.log.

Idempotent: a person whose file already exists is skipped, so a stopped run can
be resumed with the same arguments. The time budget stops new people from
starting; a person already in flight gets a short grace period and is then
abandoned (not written).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import deque
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from bundle_pipeline import prompts
from bundle_pipeline.prompts import (
    PROMPT_VERSION,
    ChatOut,
    ChatsOut,
    LooseChatOut,
    LooseOut,
    PersonaOut,
)
from bundle_pipeline.schema import Chat, Person, Thread
from bundle_pipeline.store import write_text_atomic
from bundle_pipeline.teacher import BudgetExceeded, TeacherClient, TeacherError, Usage

MIN_THREADS, MAX_THREADS = 3, 5
MIN_THREAD_CHATS, MAX_THREAD_CHATS = 8, 15
MIN_LOOSE, MAX_LOOSE = 6, 10
LONG_GAP_DAYS = 45
HORIZON_DAYS = 270
"""Roughly nine months of a person's chats."""


# --- Planning -------------------------------------------------------------------


def choose_n_threads(rng: random.Random, target: int) -> int:
    """A thread count in 3-5 from which 8-15 chats each plus 6-10 loose can reach `target`."""
    lo = max(MIN_THREADS, -(-(target - MAX_LOOSE) // MAX_THREAD_CHATS))  # ceil
    hi = min(MAX_THREADS, (target - MIN_LOOSE) // MIN_THREAD_CHATS)
    lo = min(lo, MAX_THREADS)
    hi = max(hi, lo)
    return rng.randint(lo, hi)


def plan_chats(rng: random.Random, n_threads: int, target: int) -> tuple[list[int], int]:
    """Chats per thread and loose count so the total is about `target`.

    Keeps 8-15 per thread and 6-10 loose when the target allows (target >= 30
    for three threads); below that the per-thread floor drops to 2 so a smoke
    run with a small target still produces a sane person. When the threads
    saturate at 15 each, the loose count rises towards 10 to close the gap.
    """
    n_loose = rng.randint(MIN_LOOSE, MAX_LOOSE)
    # Fewer loose chats before fewer thread chats: keep every thread at 8+ when possible.
    n_loose = min(n_loose, max(MIN_LOOSE, target - MIN_THREAD_CHATS * n_threads))
    remaining = max(0, target - n_loose)
    floor = MIN_THREAD_CHATS if remaining >= MIN_THREAD_CHATS * n_threads else 2
    base = max(floor, min(MAX_THREAD_CHATS, remaining // n_threads))
    counts = [base] * n_threads
    extra = remaining - base * n_threads
    i = 0
    while extra > 0 and any(c < MAX_THREAD_CHATS for c in counts):
        if counts[i % n_threads] < MAX_THREAD_CHATS:
            counts[i % n_threads] += 1
            extra -= 1
        i += 1
    if extra > 0:
        n_loose = min(MAX_LOOSE, n_loose + extra)
    rng.shuffle(counts)
    return counts, n_loose


def enforce_days(days: Sequence[int], mix: Sequence[str], rng: random.Random) -> list[int]:
    """Make a thread's day offsets start at 0, never decrease, and honour long_gap."""
    out: list[int] = []
    prev = 0
    for i, (day, difficulty) in enumerate(zip(days, mix, strict=True)):
        d = 0 if i == 0 else max(int(day), prev)
        if i > 0 and difficulty == "long_gap" and d - prev < LONG_GAP_DAYS:
            d = prev + LONG_GAP_DAYS + rng.randint(0, 30)
        out.append(d)
        prev = d
    return out


# --- Assembly -------------------------------------------------------------------


@dataclass
class ThreadDraft:
    label: str
    description: str
    mix: list[str]
    chats: list[ChatOut]


@dataclass
class PersonStats:
    calls: int = 0
    json_attempts: int = 0
    http_attempts: int = 0
    busy_s: float = 0.0
    usage: Usage = field(default_factory=Usage)
    relabelled: int = 0

    def add(self, result_json_attempts: int, result_http_attempts: int, elapsed: float, usage):
        self.calls += 1
        self.json_attempts += result_json_attempts
        self.http_attempts += result_http_attempts
        self.busy_s += elapsed
        self.usage.add(usage)


def _label_for(requested: str, text: str) -> str:
    """The requested label, unless the text plainly contradicts it."""
    words = len(text.split())
    if requested == "very_short" and words > 6:
        return "plain"
    if requested == "plain" and words <= 2:
        return "very_short"
    return requested


def assemble_person(
    person_id: str,
    persona: PersonaOut,
    drafts: Sequence[ThreadDraft],
    loose: Sequence[LooseChatOut],
    rng: random.Random,
    teacher: dict,
    stats: PersonStats | None = None,
) -> Person:
    """Merge thread chats and loose chats onto one timeline and build the Person."""
    threads = [
        Thread(id=f"{person_id}-t{k + 1}", label=d.label, description=d.description)
        for k, d in enumerate(drafts)
    ]
    rows: list[tuple[int, int, str | None, str, str]] = []  # day, order, thread_id, text, diff
    order = 0
    for k, draft in enumerate(drafts):
        start = 0 if k == 0 else rng.randint(0, int(HORIZON_DAYS * 0.6))
        days = enforce_days([c.day for c in draft.chats], draft.mix, rng)
        for chat, rel_day, requested in zip(draft.chats, days, draft.mix, strict=True):
            label = _label_for(requested, chat.text)
            if stats is not None and label != requested:
                stats.relabelled += 1
            rows.append((start + rel_day, order, threads[k].id, chat.text, label))
            order += 1
    for chat in loose:
        rows.append((min(int(chat.day), HORIZON_DAYS), order, None, chat.text, "nowhere"))
        order += 1
    rows.sort(key=lambda r: (r[0], r[1]))
    first_day = rows[0][0] if rows else 0
    chats = [
        Chat(
            id=f"{person_id}-c{i + 1:03d}",
            thread_id=thread_id,
            day=day - first_day,
            text=text,
            difficulty=difficulty,  # type: ignore[arg-type]
        )
        for i, (day, _, thread_id, text, difficulty) in enumerate(rows)
    ]
    return Person(
        id=person_id,
        persona=persona.persona,
        interests=persona.interests,
        threads=threads,
        chats=chats,
        teacher=teacher,
    )


# --- One person -----------------------------------------------------------------


def generate_person(
    client: TeacherClient,
    person_id: str,
    seed: int,
    target_chats: int,
    *,
    model_name: str,
    before_call: Callable[[], None] | None = None,
) -> tuple[Person, PersonStats]:
    """Drive the three prompts for one person. Raises TeacherError on failure."""
    rng = random.Random(seed)
    stats = PersonStats()

    def call() -> None:
        if before_call is not None:
            before_call()

    call()
    n_threads = choose_n_threads(rng, target_chats)
    persona, res = client.chat_json(
        prompts.persona_messages(prompts.persona_hints(rng), n_threads),
        PersonaOut,
        seed=seed,
        temperature=0.9,
        max_tokens=800,
        schema=prompts.persona_schema(n_threads),
        schema_name="persona",
    )
    stats.add(res.json_attempts, res.http_attempts, res.elapsed_s, res.usage)

    thread_outs = persona.threads[:MAX_THREADS]
    counts, n_loose = plan_chats(rng, len(thread_outs), target_chats)
    drafts: list[ThreadDraft] = []
    for k, (thread, n) in enumerate(zip(thread_outs, counts, strict=True)):
        call()
        mix = prompts.difficulty_mix(rng, n)
        out, res = client.chat_json(
            prompts.chats_for_thread_messages(
                persona.persona, thread.label, thread.description, mix
            ),
            ChatsOut,
            seed=seed + 10 * (k + 1),
            temperature=0.8,
            max_tokens=2048,
            schema=prompts.chats_schema(n),
            schema_name="chats",
        )
        stats.add(res.json_attempts, res.http_attempts, res.elapsed_s, res.usage)
        chats = [c for c in out.chats if c.text][:n]
        if len(chats) < 2:
            raise TeacherError(f"{person_id} thread {k + 1}: fewer than 2 usable chats")
        drafts.append(ThreadDraft(thread.label, thread.description, mix[: len(chats)], chats))

    call()
    loose_out, res = client.chat_json(
        prompts.loose_chats_messages(persona.persona, [t.label for t in thread_outs], n_loose),
        LooseOut,
        seed=seed + 999,
        temperature=0.9,
        max_tokens=1200,
        schema=prompts.loose_schema(n_loose),
        schema_name="loose_chats",
    )
    stats.add(res.json_attempts, res.http_attempts, res.elapsed_s, res.usage)
    loose = [c for c in loose_out.chats if c.text][:n_loose]

    teacher = {
        "model": model_name,
        "seed": seed,
        "prompt_version": PROMPT_VERSION,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    person = assemble_person(person_id, persona, drafts, loose, rng, teacher, stats)
    return person, stats


# --- The run --------------------------------------------------------------------


def person_id_for(seed: int, index: int) -> str:
    return f"p{seed}-{index:03d}"


def person_seed_for(seed: int, index: int) -> int:
    return seed * 10_000 + index


@dataclass
class Outcome:
    person_id: str
    person: Person | None
    stats: PersonStats
    wall_s: float
    error: str | None = None


def _run_one(
    client_factory: Callable[[], TeacherClient],
    person_id: str,
    seed: int,
    target: int,
    model_name: str,
    before_call: Callable[[], None],
) -> Outcome:
    started = time.monotonic()
    with client_factory() as client:
        try:
            person, stats = generate_person(
                client,
                person_id,
                seed,
                target,
                model_name=model_name,
                before_call=before_call,
            )
            return Outcome(person_id, person, stats, time.monotonic() - started)
        except TeacherError as e:
            return Outcome(person_id, None, PersonStats(), time.monotonic() - started, str(e))


def _append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")


def _rate(n: float, seconds: float) -> float:
    return n / seconds if seconds > 0 else 0.0


def main(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(args.log)
    workers = max(1, int(args.workers))
    budget_s = float(args.time_budget_min) * 60.0
    grace_s = float(args.grace_min) * 60.0
    started = time.monotonic()
    deadline = started + budget_s
    hard_deadline = deadline + grace_s

    def client_factory() -> TeacherClient:
        return TeacherClient(args.teacher_url, args.model)

    with client_factory() as probe:
        try:
            served = probe.health()
        except TeacherError as e:
            print(f"generate: {e}", file=sys.stderr)
            print("generate: start the teacher first (llama-server on :8081)", file=sys.stderr)
            return 2
    model_name = args.model if args.model != "local" or not served else served[0]
    print(f"teacher {args.teacher_url} serves {served or ['?']}; using model name {model_name!r}")

    ids = [person_id_for(args.seed, i) for i in range(args.people)]
    todo = deque(pid for pid in ids if not (out_dir / f"{pid}.json").exists())
    skipped = len(ids) - len(todo)
    print(
        f"generate: {len(ids)} people planned, {skipped} already on disk, {len(todo)} to do; "
        f"target {args.chats_per_person} chats each; {workers} worker(s); "
        f"budget {args.time_budget_min} min (+{args.grace_min} grace)"
    )
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    _append_log(
        log_path,
        f"| {stamp} | start | seed={args.seed} people={len(ids)} todo={len(todo)} "
        f"target={args.chats_per_person} workers={workers} model={model_name} "
        f"prompt={PROMPT_VERSION} |",
    )

    def before_call() -> None:
        if time.monotonic() > hard_deadline:
            raise BudgetExceeded("time budget (plus grace) spent")

    written = 0
    failed = 0
    total_chats = 0
    total_usage = Usage()
    total_busy = 0.0
    running: dict[Future[Outcome], str] = {}
    budget_hit = False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while todo or running:
            while todo and len(running) < workers:
                if time.monotonic() > deadline:
                    budget_hit = True
                    break
                pid = todo.popleft()
                index = int(pid.rsplit("-", 1)[1])
                fut = pool.submit(
                    _run_one,
                    client_factory,
                    pid,
                    person_seed_for(args.seed, index),
                    args.chats_per_person,
                    model_name,
                    before_call,
                )
                running[fut] = pid
            if not running:
                break
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for fut in done:
                running.pop(fut)
                outcome = fut.result()
                stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                if outcome.person is None:
                    failed += 1
                    print(
                        f"person {outcome.person_id}: FAILED after {outcome.wall_s:.0f}s: "
                        f"{outcome.error}",
                        file=sys.stderr,
                    )
                    _append_log(
                        log_path, f"| {stamp} | {outcome.person_id} | failed | {outcome.error} |"
                    )
                    continue
                person, stats = outcome.person, outcome.stats
                path = out_dir / f"{person.id}.json"
                write_text_atomic(path, person.model_dump_json(indent=2) + "\n")
                written += 1
                total_chats += len(person.chats)
                total_usage.add(stats.usage)
                total_busy += stats.busy_s
                chats_per_min = _rate(len(person.chats), outcome.wall_s) * 60
                tok_s = _rate(stats.usage.completion_tokens, stats.busy_s)
                tok_text = f"{tok_s:.1f} tok/s" if stats.usage.completion_tokens else "tok/s n/a"
                line = (
                    f"person {person.id}: {len(person.threads)} threads, "
                    f"{len(person.chats)} chats, "
                    f"{stats.calls} calls ({stats.json_attempts} completions), "
                    f"{outcome.wall_s:.0f}s, {chats_per_min:.1f} chats/min, {tok_text}, "
                    f"{path.stat().st_size / 1024:.1f} KB"
                )
                print(line)
                _append_log(
                    log_path,
                    f"| {stamp} | {person.id} | ok | threads={len(person.threads)} "
                    f"chats={len(person.chats)} calls={stats.calls} "
                    f"completions={stats.json_attempts} wall_s={outcome.wall_s:.0f} "
                    f"chats_per_min={chats_per_min:.1f} completion_tokens="
                    f"{stats.usage.completion_tokens} tok_s={tok_s:.1f} "
                    f"relabelled={stats.relabelled} |",
                )
        if todo:
            budget_hit = True

    elapsed = time.monotonic() - started
    summary = (
        f"generate: done in {elapsed / 60:.1f} min: {written} written, {skipped} skipped, "
        f"{failed} failed, {len(todo)} not started"
        f"{' (time budget reached)' if budget_hit else ''}; "
        f"{total_chats} chats, {_rate(total_chats, elapsed) * 60:.1f} chats/min overall"
    )
    if total_usage.completion_tokens:
        summary += (
            f", {total_usage.completion_tokens} completion tokens, "
            f"{_rate(total_usage.completion_tokens, total_busy):.1f} tok/s while busy"
        )
    print(summary)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    _append_log(log_path, f"| {stamp} | end | {summary} |")
    _append_log(
        log_path,
        "| "
        + stamp
        + " | totals | "
        + json.dumps(
            {
                "written": written,
                "skipped": skipped,
                "failed": failed,
                "not_started": len(todo),
                "chats": total_chats,
                "elapsed_s": round(elapsed, 1),
                "completion_tokens": total_usage.completion_tokens,
                "prompt_tokens": total_usage.prompt_tokens,
            }
        )
        + " |",
    )
    if written == 0 and failed > 0:
        return 1
    return 0


__all__ = [
    "HORIZON_DAYS",
    "LONG_GAP_DAYS",
    "Outcome",
    "PersonStats",
    "ThreadDraft",
    "assemble_person",
    "choose_n_threads",
    "enforce_days",
    "generate_person",
    "main",
    "person_id_for",
    "person_seed_for",
    "plan_chats",
]
