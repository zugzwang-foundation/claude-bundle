"""Prompts for the teacher, version "v0.2", and the pydantic shapes of its answers.

Three prompts, all short enough for a 4B instruct model to follow:

- PERSONA: invent one fictional person (persona paragraph, 3-6 interests,
  3-5 threads with label and description). Never a real person.
- CHATS_FOR_THREAD: given the persona and one thread, write N opening messages
  in time order over months, each with a day offset and a difficulty label,
  following a requested difficulty mix.
- LOOSE_CHATS: one-off chats that belong to none of the person's threads.

The teacher returns JSON. `generate.py` turns these answers into `schema.Person`.

Each prompt also has a strict JSON schema (`persona_schema`, `chats_schema`,
`loose_schema`). llama-server turns it into a grammar through
`response_format: json_schema`, which is what makes a 4B model return exactly
N chats with every key present; without it the smoke run saw `{"day": 3}`
entries with no text. Servers that reject the field fall back to json_object
and then to plain instructions (teacher.py).

v0.2 (2026-10-16): numbered difficulty list and "every chat has all three
keys" added to CHATS_FOR_THREAD; the JSON schemas added. v0.1 was the first
live-checked version.
Every list of hints below is generic (roles, places, habits), never a real
person, company or product.
"""

from __future__ import annotations

import random
import re
from collections.abc import Sequence

from pydantic import BaseModel, Field, field_validator

from bundle_pipeline.schema import DIFFICULTIES, Difficulty

PROMPT_VERSION = "v0.2"

Message = dict[str, str]

# --- Answer shapes ---------------------------------------------------------------

_DIFFICULTY_SYNONYMS = {
    "short": "very_short",
    "veryshort": "very_short",
    "tiny": "very_short",
    "typo": "typos",
    "misspelled": "typos",
    "lowercase": "typos",
    "gap": "long_gap",
    "longgap": "long_gap",
    "late": "long_gap",
    "new": "new_thread",
    "newthread": "new_thread",
    "first": "new_thread",
    "normal": "plain",
    "easy": "plain",
    "clear": "plain",
    "simple": "plain",
    "overlapping": "overlap",
    "crossover": "overlap",
    "ambiguous": "vague",
    "none": "nowhere",
    "loose": "nowhere",
}


def normalise_difficulty(value: object) -> object:
    """Map what a small model writes ("Very short", "typo") onto the eight labels."""
    if not isinstance(value, str):
        return value
    key = re.sub(r"[\s\-]+", "_", value.strip().lower())
    return _DIFFICULTY_SYNONYMS.get(key) or _DIFFICULTY_SYNONYMS.get(key.replace("_", "")) or key


def coerce_day(value: object) -> object:
    """Accept "12", 12.0 or -3 for a day; negative days become 0."""
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        value = int(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return max(0, int(value))
    return value


class ThreadOut(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=400)

    @field_validator("label", "description", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class PersonaOut(BaseModel):
    persona: str = Field(min_length=20)
    interests: list[str] = Field(min_length=3, max_length=6)
    threads: list[ThreadOut] = Field(min_length=3, max_length=5)

    @field_validator("persona", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @field_validator("interests", mode="before")
    @classmethod
    def _clean_interests(cls, v: object) -> object:
        if isinstance(v, list):
            cleaned = [s.strip() for s in v if isinstance(s, str) and s.strip()]
            return cleaned[:6]
        return v


class ChatOut(BaseModel):
    day: int = Field(ge=0)
    text: str
    difficulty: Difficulty = "plain"

    @field_validator("day", mode="before")
    @classmethod
    def _day(cls, v: object) -> object:
        return coerce_day(v)

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @field_validator("difficulty", mode="before")
    @classmethod
    def _difficulty(cls, v: object) -> object:
        return normalise_difficulty(v)


class ChatsOut(BaseModel):
    chats: list[ChatOut] = Field(min_length=1)


class LooseChatOut(BaseModel):
    day: int = Field(ge=0)
    text: str

    @field_validator("day", mode="before")
    @classmethod
    def _day(cls, v: object) -> object:
        return coerce_day(v)

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class LooseOut(BaseModel):
    chats: list[LooseChatOut] = Field(min_length=1)


# --- Strict JSON schemas (grammar-constrained decoding on llama-server) ----------

_TEXT = {"type": "string", "minLength": 1}
_DAY = {"type": "integer", "minimum": 0}


def _array(items: dict, n: int | None = None, lo: int | None = None, hi: int | None = None) -> dict:
    out: dict = {"type": "array", "items": items}
    if n is not None:
        lo = hi = n
    if lo is not None:
        out["minItems"] = lo
    if hi is not None:
        out["maxItems"] = hi
    return out


def _object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def persona_schema(n_threads: int) -> dict:
    """PersonaOut as a strict schema: exactly `n_threads` threads, 3-6 interests."""
    return _object(
        {
            "persona": {"type": "string", "minLength": 20},
            "interests": _array(_TEXT, lo=3, hi=6),
            "threads": _array(_object({"label": _TEXT, "description": _TEXT}), n=n_threads),
        }
    )


def chats_schema(n: int) -> dict:
    """ChatsOut as a strict schema: exactly `n` chats, each with day, text and difficulty."""
    item = _object(
        {"day": _DAY, "text": _TEXT, "difficulty": {"type": "string", "enum": list(DIFFICULTIES)}}
    )
    return _object({"chats": _array(item, n=n)})


def loose_schema(n: int) -> dict:
    """LooseOut as a strict schema: exactly `n` chats, each with day and text."""
    return _object({"chats": _array(_object({"day": _DAY, "text": _TEXT}), n=n)})


# --- Variety hints (generic, fictional) -----------------------------------------

LIFE_STAGES: tuple[str, ...] = (
    "a student in the final year of a degree",
    "a new parent on leave from an office job",
    "a shift worker at a hospital",
    "a recently retired engineer",
    "a freelancer who works from cafes",
    "the owner of a small shop",
    "a postgraduate researcher",
    "a long-distance commuter with a desk job",
    "someone who has just moved to a new city for work",
    "a carer for an older relative",
    "an apprentice in a trade",
    "a secondary-school teacher on a long summer break",
    "a nurse studying part time",
    "a warehouse supervisor who coaches a kids' team",
    "a translator working from home",
    "a chef who has just opened a food stall",
)

SETTINGS: tuple[str, ...] = (
    "a rainy northern city",
    "a small coastal town",
    "a farming village",
    "a dense capital city",
    "a mountain town",
    "a hot desert suburb",
    "a river-delta city",
    "a small island",
    "a university town",
    "a former mining town",
    "a sprawling suburb with long drives",
    "a cold city with long winters",
)

TYPING_HABITS: tuple[str, ...] = (
    "types everything in lower case and rarely uses punctuation",
    "writes long careful sentences with full punctuation",
    "asks many short questions, one line each",
    "opens with please and closes with thanks",
    "uses lots of abbreviations and the odd typo",
    "pastes numbers and details and expects precise answers",
    "writes as if talking to a friend",
    "is terse and a little impatient",
)

DOMAINS: tuple[str, ...] = (
    "fitness",
    "travel",
    "food and cooking",
    "money",
    "work",
    "study",
    "music",
    "home and DIY",
    "pets",
    "tech",
    "health and wellbeing",
    "parenting",
    "gardening",
    "a car or bike",
    "a craft",
    "games",
    "writing",
    "a language",
    "photography",
    "moving house",
)


def persona_hints(rng: random.Random) -> list[str]:
    """Three to four short hints that push the teacher towards a different person each time."""
    domains = rng.sample(DOMAINS, 2)
    return [
        rng.choice(LIFE_STAGES),
        f"lives in {rng.choice(SETTINGS)}",
        rng.choice(TYPING_HABITS),
        f"one thread is about {domains[0]} and another about {domains[1]}",
    ]


def difficulty_mix(rng: random.Random, n: int) -> list[str]:
    """The difficulty labels for a thread of n chats, in day order.

    The first chat is always "new_thread". Each of overlap, vague, typos,
    very_short and long_gap appears once when there is room, a few twice for
    long threads, and the rest are plain. Positions after the first are shuffled.
    """
    if n <= 0:
        return []
    if n == 1:
        return ["new_thread"]
    specials = ["overlap", "vague", "typos", "very_short", "long_gap"]
    if n >= 10:
        specials += ["typos", "vague"]
    if n >= 13:
        specials += ["overlap"]
    rest = n - 1
    if len(specials) > rest:
        specials = rng.sample(specials, rest)
    tail = specials + ["plain"] * (rest - len(specials))
    rng.shuffle(tail)
    mix = ["new_thread", *tail]
    assert all(d in DIFFICULTIES for d in mix)
    return mix


# --- Prompt text ----------------------------------------------------------------

SYSTEM = (
    "You write realistic synthetic data for testing a tool that sorts a person's AI chats. "
    "Everything you write is fiction. Never name or describe a real person, company, "
    "product, song or artist. Reply with exactly one JSON object and no other text."
)

PERSONA_PROMPT = """Invent one fictional person who uses an AI assistant for everyday questions.
Hints for variety: {hints}.

Return this JSON:
{{"persona": "<one paragraph of 60 to 100 words: who they are, their situation, how they type;
  no name>",
 "interests": ["<3 to 6 short phrases>"],
 "threads": [{{"label": "<2 to 4 word bundle name>",
              "description": "<one line: the ongoing project or question they keep coming back
              to over months>"}}]}}

Give exactly {n_threads} threads. Each thread is a distinct, concrete topic the person works on
over months (a goal, a project, a problem), not a general interest."""

CHATS_FOR_THREAD_PROMPT = """Persona: {persona}

Thread "{label}": {description}

Write {n} chats this person opened with an AI assistant about this thread, in time order over
about {span_months} months. Each chat is only the FIRST message they typed: a question or request
in their own voice. Do not write the assistant's replies.

"day" is days since the first chat of this thread: the first is 0, later ones increase
(the same day is allowed).

Each chat has one difficulty label:
- new_thread: the first chat only; it introduces the topic from scratch.
- plain: a clear follow-up that obviously belongs to this thread.
- overlap: sounds like it belongs to a different topic (what to eat before a race is really about
  the running thread; what a move costs is really about the house thread) but is for this thread.
- vague: a follow-up of at most ten words that only makes sense after the earlier chats of this
  thread and names nothing specific (a pronoun instead of the thing, a "what about the other one").
- long_gap: picks the topic up again at least 45 days after the previous chat.
- typos: lower case, misspellings, missing punctuation.
- very_short: 1 to 4 words.

Use exactly this mix, in this order: {mix}
That is exactly {n} chats: {numbered}.

Every chat object has all three keys, "day", "text" and "difficulty"; never leave out "text".
Write every message in the person's own words about this thread. Never copy phrases from these
instructions, and make every message different from the others.

Return this JSON:
{{"chats": [{{"day": 0, "text": "<the message>", "difficulty": "new_thread"}}, ...]}}"""

LOOSE_CHATS_PROMPT = """Persona: {persona}

Their ongoing threads, which these chats must NOT be about or close to: {labels}.

Write {n} one-off chats this person opened with an AI assistant that belong to none of those
threads and share no topic with each other: a quick practical question, a word they cannot
remember, a message to draft, a fact to check, a one-time recipe, a form to fill, and so on.
Each is only the FIRST message they typed, in their own voice. Vary them: some one line, one or
two very short, one sloppy with typos.

"day" is any whole number from 0 to {span_days}.

Return this JSON:
{{"chats": [{{"day": 12, "text": "<the message>"}}, ...]}}"""


def persona_messages(hints: Sequence[str], n_threads: int) -> list[Message]:
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": PERSONA_PROMPT.format(hints="; ".join(hints), n_threads=n_threads),
        },
    ]


def chats_for_thread_messages(
    persona: str,
    label: str,
    description: str,
    mix: Sequence[str],
    span_months: int = 4,
) -> list[Message]:
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": CHATS_FOR_THREAD_PROMPT.format(
                persona=persona,
                label=label,
                description=description,
                n=len(mix),
                span_months=span_months,
                mix=", ".join(mix),
                numbered="; ".join(f"chat {i + 1} is {d}" for i, d in enumerate(mix)),
            ),
        },
    ]


def loose_chats_messages(
    persona: str,
    thread_labels: Sequence[str],
    n: int,
    span_days: int = 180,
) -> list[Message]:
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": LOOSE_CHATS_PROMPT.format(
                persona=persona,
                labels="; ".join(thread_labels),
                n=n,
                span_days=span_days,
            ),
        },
    ]


__all__ = [
    "PROMPT_VERSION",
    "ChatOut",
    "ChatsOut",
    "LooseChatOut",
    "LooseOut",
    "Message",
    "PersonaOut",
    "ThreadOut",
    "chats_for_thread_messages",
    "chats_schema",
    "coerce_day",
    "difficulty_mix",
    "loose_chats_messages",
    "loose_schema",
    "normalise_difficulty",
    "persona_hints",
    "persona_messages",
    "persona_schema",
]
