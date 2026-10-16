"""prompts: version, answer shapes, difficulty mix, rendered messages."""

from __future__ import annotations

import random

import pytest
from pydantic import ValidationError

from bundle_pipeline import config
from bundle_pipeline.prompts import (
    PROMPT_VERSION,
    ChatsOut,
    LooseOut,
    PersonaOut,
    chats_for_thread_messages,
    difficulty_mix,
    loose_chats_messages,
    normalise_difficulty,
    persona_hints,
    persona_messages,
)
from bundle_pipeline.schema import DIFFICULTIES


def test_prompt_version_is_v0_1_and_matches_config() -> None:
    assert PROMPT_VERSION == "v0.2"
    assert config.PROMPT_VERSION == PROMPT_VERSION


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Very Short", "very_short"),
        ("very-short", "very_short"),
        ("typo", "typos"),
        ("Long gap", "long_gap"),
        ("new", "new_thread"),
        ("normal", "plain"),
        ("plain", "plain"),
        ("overlap", "overlap"),
    ],
)
def test_difficulty_synonyms(raw: str, expected: str) -> None:
    assert normalise_difficulty(raw) == expected


def test_chats_out_rejects_unknown_difficulty_but_coerces_days() -> None:
    out = ChatsOut.model_validate({"chats": [{"day": "3", "text": " hi ", "difficulty": "Typo"}]})
    assert out.chats[0].day == 3 and out.chats[0].text == "hi"
    assert out.chats[0].difficulty == "typos"
    with pytest.raises(ValidationError):
        ChatsOut.model_validate({"chats": [{"day": 0, "text": "x", "difficulty": "impossible"}]})
    with pytest.raises(ValidationError):
        ChatsOut.model_validate({"chats": []})


def test_persona_out_bounds() -> None:
    good = {
        "persona": "A fictional person who types quickly and asks about their garden.",
        "interests": ["a", "b", "c"],
        "threads": [{"label": "L", "description": "D"}] * 3,
    }
    assert len(PersonaOut.model_validate(good).threads) == 3
    with pytest.raises(ValidationError):
        PersonaOut.model_validate({**good, "threads": good["threads"][:2]})
    with pytest.raises(ValidationError):
        PersonaOut.model_validate({**good, "interests": ["only two", "here"]})
    assert LooseOut.model_validate({"chats": [{"day": 1, "text": "x"}]}).chats[0].day == 1


def test_difficulty_mix_shape() -> None:
    rng = random.Random(0)
    for n in (1, 2, 5, 8, 10, 13, 15):
        mix = difficulty_mix(rng, n)
        assert len(mix) == n
        assert mix[0] == "new_thread"
        assert "new_thread" not in mix[1:]
        assert "nowhere" not in mix
        assert set(mix) <= set(DIFFICULTIES)
        if n >= 6:
            assert {"overlap", "vague", "typos", "very_short", "long_gap"} <= set(mix)


def test_messages_render_with_persona_and_mix() -> None:
    rng = random.Random(1)
    hints = persona_hints(rng)
    assert len(hints) == 4
    msgs = persona_messages(hints, 4)
    assert msgs[0]["role"] == "system" and "fiction" in msgs[0]["content"]
    assert "exactly 4 threads" in msgs[1]["content"]
    assert hints[0] in msgs[1]["content"]

    mix = ["new_thread", "plain", "very_short"]
    msgs = chats_for_thread_messages("A runner.", "Half marathon", "Training.", mix)
    user = msgs[1]["content"]
    assert "A runner." in user and "Half marathon" in user and "Write 3 chats" in user
    assert "new_thread, plain, very_short" in user

    msgs = loose_chats_messages("A runner.", ["Half marathon", "Sourdough"], 6)
    assert "Half marathon; Sourdough" in msgs[1]["content"]
    assert "Write 6 one-off chats" in msgs[1]["content"]
    for m in (msgs[0], msgs[1]):
        assert (
            "{" not in m["content"].replace("{{", "").replace("}}", "") or '"chats"' in m["content"]
        )


def test_strict_schemas_pin_counts_keys_and_difficulties() -> None:
    from bundle_pipeline.prompts import chats_schema, loose_schema, persona_schema
    from bundle_pipeline.schema import DIFFICULTIES

    chats = chats_schema(7)
    arr = chats["properties"]["chats"]
    assert arr["minItems"] == 7 and arr["maxItems"] == 7
    item = arr["items"]
    assert item["required"] == ["day", "text", "difficulty"]
    assert item["additionalProperties"] is False
    assert item["properties"]["difficulty"]["enum"] == list(DIFFICULTIES)
    assert item["properties"]["day"] == {"type": "integer", "minimum": 0}
    assert item["properties"]["text"]["minLength"] == 1

    loose = loose_schema(6)["properties"]["chats"]
    assert loose["minItems"] == 6 and loose["maxItems"] == 6
    assert loose["items"]["required"] == ["day", "text"]

    persona = persona_schema(4)
    assert persona["required"] == ["persona", "interests", "threads"]
    threads = persona["properties"]["threads"]
    assert threads["minItems"] == 4 and threads["maxItems"] == 4
    assert threads["items"]["required"] == ["label", "description"]
    interests = persona["properties"]["interests"]
    assert (interests["minItems"], interests["maxItems"]) == (3, 6)


def test_chats_prompt_numbers_the_mix() -> None:
    from bundle_pipeline.prompts import chats_for_thread_messages

    mix = ["new_thread", "typos", "plain"]
    user = chats_for_thread_messages("p", "lbl", "desc", mix)[1]["content"]
    assert "Use exactly this mix, in this order: new_thread, typos, plain" in user
    assert "chat 1 is new_thread; chat 2 is typos; chat 3 is plain" in user
    assert "exactly 3 chats" in user
    assert 'never leave out "text"' in user
