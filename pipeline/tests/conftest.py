from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter

from bundle_pipeline.schema import Candidate, DecisionExample, Person

from .fake_encoder import FakeEncoder

FIXTURE = Path(__file__).parent / "fixtures" / "people.json"


@pytest.fixture(scope="session")
def fixture_path() -> Path:
    return FIXTURE


@pytest.fixture(scope="session")
def people(fixture_path: Path) -> list[Person]:
    return TypeAdapter(list[Person]).validate_json(fixture_path.read_bytes())


def examples_from_person(person: Person, max_examples: int = 8) -> list[DecisionExample]:
    """The tasks contract, re-stated for tests (so they do not depend on tasks.py).

    Walk the chats in day order. A thread's first chat is loose until a second
    arrives; from then on the thread is a bundle holding all its earlier chats.
    """
    bundles: dict[str, list[str]] = {}
    loose: dict[str, tuple[str, str | None]] = {}  # chat_id -> (text, thread_id)
    thread_label = {t.id: t.label for t in person.threads}
    out: list[DecisionExample] = []
    for chat in sorted(person.chats, key=lambda c: c.day):
        cands = [
            Candidate(
                id=f"b:{tid}",
                kind="bundle",
                label=thread_label[tid],
                examples=texts[-max_examples:],
            )
            for tid, texts in bundles.items()
        ]
        cands += [
            Candidate(id=f"c:{cid}", kind="loose", text=text) for cid, (text, _) in loose.items()
        ]
        answer = "none"
        if chat.thread_id is not None:
            if chat.thread_id in bundles:
                answer = f"b:{chat.thread_id}"
            else:
                first = next(
                    (cid for cid, (_, tid) in loose.items() if tid == chat.thread_id), None
                )
                if first is not None:
                    answer = f"c:{first}"
        out.append(
            DecisionExample(
                id=chat.id,
                person_id=person.id,
                chat_id=chat.id,
                chat=chat.text,
                candidates=cands,
                answer=answer,
                difficulty=chat.difficulty,
                day=chat.day,
            )
        )
        # update state
        if chat.thread_id is None:
            loose[chat.id] = (chat.text, None)
        elif chat.thread_id in bundles:
            bundles[chat.thread_id].append(chat.text)
        else:
            first = next((cid for cid, (_, tid) in loose.items() if tid == chat.thread_id), None)
            if first is None:
                loose[chat.id] = (chat.text, chat.thread_id)
            else:
                bundles[chat.thread_id] = [loose.pop(first)[0], chat.text]
    return out


@pytest.fixture(scope="session")
def examples(people: list[Person]) -> list[DecisionExample]:
    return [ex for p in people for ex in examples_from_person(p)]


@pytest.fixture
def fake_encoder() -> FakeEncoder:
    return FakeEncoder()
