"""Data contract for the Bundle pipeline (pydantic v2).

These models are the fixed contract shared by every module and every parallel
agent in BDL-3. Field names and types follow the relay word for word; do not
rename or widen them without a decision in docs/DECISIONS.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal[
    "plain",
    "overlap",
    "vague",
    "nowhere",
    "long_gap",
    "typos",
    "very_short",
    "new_thread",
]
"""The eight difficulty labels the teacher must produce."""

DIFFICULTIES: tuple[str, ...] = (
    "plain",
    "overlap",
    "vague",
    "nowhere",
    "long_gap",
    "typos",
    "very_short",
    "new_thread",
)

CandidateKind = Literal["bundle", "loose"]
Action = Literal["file", "suggest", "leave"]


class Chat(BaseModel):
    """One chat a person opened, reduced to its opening message."""

    id: str
    thread_id: str | None = None
    """None means a loose chat that belongs to no thread."""
    day: int = Field(ge=0)
    """Days since the person's first chat."""
    text: str
    """The opening message the person typed."""
    difficulty: Difficulty


class Thread(BaseModel):
    """A bundle-to-be: a short label and a one-line description."""

    id: str
    label: str
    description: str


class Person(BaseModel):
    """One synthetic person with their threads and chats, in day order."""

    id: str
    persona: str
    """One paragraph: who they are. No real names of real people."""
    interests: list[str]
    threads: list[Thread]
    chats: list[Chat]
    """In day order."""
    teacher: dict
    """model, seed, prompt_version of the teacher that produced this person."""


class Candidate(BaseModel):
    """Something a chat could be filed into: an existing bundle or a loose chat."""

    id: str
    """"b:<thread_id>" for bundles, "c:<chat_id>" for loose chats."""
    kind: CandidateKind
    label: str | None = None
    """Bundle label (bundles only)."""
    examples: list[str] = Field(default_factory=list)
    """Up to 8 most recent texts of the bundle (bundles only)."""
    text: str | None = None
    """The loose chat's text (loose only)."""


class DecisionExample(BaseModel):
    """One decision: a new chat, the candidates at that moment, the right answer."""

    id: str
    person_id: str
    chat_id: str
    chat: str
    candidates: list[Candidate]
    answer: str
    """A candidate id, or "none"."""
    difficulty: Difficulty
    day: int = Field(ge=0)


class Decision(BaseModel):
    """The API response: probabilities over candidates plus "none", and the action."""

    probabilities: dict[str, float]
    """Keyed by candidate id, including "none"."""
    action: Action
    target: str | None = None
    """The top candidate id when action != "leave", else None."""


__all__ = [
    "DIFFICULTIES",
    "Action",
    "Candidate",
    "CandidateKind",
    "Chat",
    "Decision",
    "DecisionExample",
    "Difficulty",
    "Person",
    "Thread",
]
