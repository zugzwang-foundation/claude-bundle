"""generate: planning, day enforcement, assembly, and a full person against a fake teacher."""

from __future__ import annotations

import json
import random
from pathlib import Path

import httpx

from bundle_pipeline.cli import main
from bundle_pipeline.generate import (
    LONG_GAP_DAYS,
    choose_n_threads,
    enforce_days,
    generate_person,
    person_id_for,
    plan_chats,
)
from bundle_pipeline.schema import Person
from bundle_pipeline.teacher import TeacherClient


def test_plan_chats_hits_the_target_within_bounds() -> None:
    rng = random.Random(3)
    for target in (40, 50, 60):
        for _ in range(30):
            n_threads = choose_n_threads(rng, target)
            assert 3 <= n_threads <= 5
            counts, loose = plan_chats(rng, n_threads, target)
            assert len(counts) == n_threads
            assert all(8 <= c <= 15 for c in counts)
            assert 6 <= loose <= 10
            assert abs(sum(counts) + loose - target) <= 2, (target, counts, loose)


def test_choose_n_threads_can_reach_the_target() -> None:
    rng = random.Random(0)
    assert {choose_n_threads(rng, 60) for _ in range(50)} == {4, 5}
    assert {choose_n_threads(rng, 30) for _ in range(50)} == {3}
    assert {choose_n_threads(rng, 200) for _ in range(50)} == {5}


def test_plan_chats_saturated_threads_raise_loose_count() -> None:
    counts, loose = plan_chats(random.Random(0), 3, 60)
    assert counts == [15, 15, 15] and loose == 10


def test_plan_chats_small_target_still_sane() -> None:
    counts, loose = plan_chats(random.Random(0), 3, 12)
    assert all(c >= 2 for c in counts) and loose >= 6


def test_enforce_days_monotonic_and_long_gap() -> None:
    rng = random.Random(0)
    days = enforce_days(
        [5, 3, 10, 12, 13], ["new_thread", "plain", "long_gap", "plain", "vague"], rng
    )
    assert days[0] == 0
    assert days == sorted(days)
    assert days[2] - days[1] >= LONG_GAP_DAYS


# --- a scripted teacher that answers by prompt kind ------------------------------

PERSONA = {
    "persona": "A fictional night-shift baker in a small coastal town who types in lower case.",
    "interests": ["baking", "sea swimming", "an old van"],
    "threads": [
        {"label": "Sourdough at scale", "description": "Moving from one loaf to forty a night."},
        {"label": "Cold water swims", "description": "Swimming in the sea through the winter."},
        {"label": "Van rebuild", "description": "Getting a rusty van through its inspection."},
    ],
}


def _thread_chats(n: int, mix: list[str]) -> dict:
    chats = []
    day = 0
    for i, d in enumerate(mix[:n]):
        text = {
            "very_short": "proof time?",
            "typos": "ok so teh dough is to wet agian what now",
            "vague": "does that change in winter",
        }.get(d, f"question number {i} about this thread with some detail words {i * 7}")
        chats.append({"day": day, "text": text, "difficulty": d})
        day += 4
    return {"chats": chats}


def _loose(n: int) -> dict:
    return {
        "chats": [
            {"day": i * 20, "text": f"one-off question {i} about an unrelated thing {i * 3}"}
            for i in range(n)
        ]
    }


class ScriptedTeacher:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "scripted"}]})
        body = json.loads(request.content)
        self.posts.append(body)
        user = body["messages"][-1]["content"]
        if "Invent one fictional person" in user:
            payload = PERSONA
        elif "Use exactly this mix" in user:
            mix_line = next(ln for ln in user.splitlines() if ln.startswith("Use exactly this mix"))
            mix = [m.strip() for m in mix_line.split(":", 1)[1].split(",")]
            payload = _thread_chats(len(mix), mix)
        else:
            n = int(user.split("Write ")[1].split(" ")[0])
            payload = _loose(n)
        content = "Here is the JSON you asked for:\n```json\n" + json.dumps(payload) + "\n```"
        return httpx.Response(
            200,
            json={
                "model": "scripted",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            },
        )


def test_generate_person_end_to_end_against_scripted_teacher() -> None:
    teacher = ScriptedTeacher()
    client = TeacherClient("http://t.test/v1", "scripted", transport=httpx.MockTransport(teacher))
    person, stats = generate_person(
        client, "p9-000", seed=90000, target_chats=40, model_name="scripted"
    )
    assert isinstance(person, Person)
    assert person.id == "p9-000"
    assert len(person.threads) == 3
    assert [t.id for t in person.threads] == ["p9-000-t1", "p9-000-t2", "p9-000-t3"]
    assert person.teacher["model"] == "scripted"
    assert person.teacher["prompt_version"] == "v0.2"
    assert person.teacher["seed"] == 90000
    # chats are in day order, start at 0, with ids in order
    days = [c.day for c in person.chats]
    assert days == sorted(days) and days[0] == 0
    assert [c.id for c in person.chats] == [
        f"p9-000-c{i + 1:03d}" for i in range(len(person.chats))
    ]
    # loose chats are labelled nowhere; the first chat of each thread is new_thread
    assert all(c.difficulty == "nowhere" for c in person.chats if c.thread_id is None)
    for t in person.threads:
        mine = [c for c in person.chats if c.thread_id == t.id]
        assert mine[0].difficulty == "new_thread"
        assert 8 <= len(mine) <= 15
        gaps = [b.day - a.day for a, b in zip(mine, mine[1:], strict=False)]
        for chat, gap in zip(mine[1:], gaps, strict=True):
            if chat.difficulty == "long_gap":
                assert gap >= LONG_GAP_DAYS
    loose = [c for c in person.chats if c.thread_id is None]
    assert 6 <= len(loose) <= 10
    assert 36 <= len(person.chats) <= 44
    assert stats.calls == 5  # persona + 3 threads + loose
    assert stats.usage.completion_tokens == 250
    seeds = [p["seed"] for p in teacher.posts]
    assert len(set(seeds)) == 5


def test_generate_cli_writes_files_is_idempotent_and_logs(tmp_path: Path, monkeypatch) -> None:
    teacher = ScriptedTeacher()
    monkeypatch.setattr(
        "bundle_pipeline.generate.TeacherClient",
        lambda url, model: TeacherClient(url, model, transport=httpx.MockTransport(teacher)),
    )
    out = tmp_path / "raw" / "people"
    log = tmp_path / "generate.log"
    argv = [
        "generate",
        "--people",
        "2",
        "--chats-per-person",
        "40",
        "--seed",
        "9",
        "--out",
        str(out),
        "--workers",
        "2",
        "--time-budget-min",
        "5",
        "--log",
        str(log),
    ]
    assert main(argv) == 0
    files = sorted(p.name for p in out.glob("*.json"))
    assert files == [f"{person_id_for(9, 0)}.json", f"{person_id_for(9, 1)}.json"]
    first_posts = len(teacher.posts)
    for f in files:
        Person.model_validate_json((out / f).read_bytes())
    # a second run skips both people and makes no completion calls
    assert main(argv) == 0
    assert len(teacher.posts) == first_posts
    text = log.read_text()
    assert "| start |" in text and "| end |" in text
    assert text.count("| ok |") == 2
    assert "skipped" in text


def test_generate_cli_exits_2_when_teacher_is_down(tmp_path: Path, monkeypatch) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(
        "bundle_pipeline.generate.TeacherClient",
        lambda url, model: TeacherClient(url, model, transport=httpx.MockTransport(down)),
    )
    rc = main(
        ["generate", "--people", "1", "--out", str(tmp_path / "o"), "--log", str(tmp_path / "l")]
    )
    assert rc == 2
