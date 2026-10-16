"""teacher: JSON extraction from messy text, and the client against a fake transport."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from bundle_pipeline.teacher import SEED_STEP, TeacherClient, TeacherError, extract_json

# --- extract_json ---------------------------------------------------------------


def test_extracts_fenced_json_with_prose_around() -> None:
    text = 'Sure! Here you go:\n```json\n{"a": 1, "b": [1, 2]}\n```\nHope that helps.'
    assert extract_json(text) == {"a": 1, "b": [1, 2]}


def test_extracts_first_object_from_plain_prose() -> None:
    text = 'the answer is {"chats": [{"day": 0, "text": "hi {there}"}]} and that is all {"x": 1}'
    assert extract_json(text) == {"chats": [{"day": 0, "text": "hi {there}"}]}


def test_handles_braces_and_escapes_inside_strings() -> None:
    text = '{"text": "a \\"quoted\\" } brace", "n": 2}'
    assert extract_json(text) == {"text": 'a "quoted" } brace', "n": 2}


def test_repairs_trailing_commas() -> None:
    assert extract_json('{"a": [1, 2,], "b": {"c": 3,},}') == {"a": [1, 2], "b": {"c": 3}}


def test_repairs_truncated_tail() -> None:
    text = '{"chats": [{"day": 0, "text": "one"}, {"day": 3, "text": "two'
    out = extract_json(text)
    assert out["chats"][0] == {"day": 0, "text": "one"}
    assert out["chats"][1]["day"] == 3


def test_strips_think_blocks_and_skips_non_json_braces() -> None:
    text = '<think>{not json at all</think> ok {oops} then {"k": "v"}'
    assert extract_json(text) == {"k": "v"}


def test_raises_when_nothing_parses() -> None:
    with pytest.raises(ValueError):
        extract_json("no json here, sorry")
    with pytest.raises(ValueError):
        extract_json("   ")
    with pytest.raises(ValueError):
        extract_json("[1, 2, 3]")  # a top-level array is not an object


# --- client ---------------------------------------------------------------------


class Answer(BaseModel):
    name: str
    count: int


def _completion(content: str, usage: dict | None = None, model: str = "fake-4b") -> httpx.Response:
    body = {
        "id": "cmpl-1",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return httpx.Response(200, json=body)


class FakeServer:
    """A scripted OpenAI-compatible server: pops one response per POST, records the bodies."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.posts: list[dict] = []
        self.paths: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(200, json={"object": "list", "data": [{"id": "fake-4b"}]})
        self.posts.append(json.loads(request.content))
        if not self.responses:
            raise AssertionError("more requests than scripted responses")
        return self.responses.pop(0)


def _client(server: FakeServer, **kw) -> TeacherClient:
    return TeacherClient(
        "http://teacher.test/v1",
        "fake-4b",
        transport=httpx.MockTransport(server),
        backoff_s=0.0,
        **kw,
    )


def test_health_lists_models() -> None:
    server = FakeServer([])
    with _client(server) as client:
        assert client.health() == ["fake-4b"]
    assert server.paths == ["/v1/models"]


def test_health_raises_when_unreachable() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = TeacherClient("http://teacher.test/v1", transport=httpx.MockTransport(down))
    with pytest.raises(TeacherError, match="unreachable"):
        client.health()


def test_chat_sends_seed_and_json_mode_and_returns_usage() -> None:
    server = FakeServer([_completion('{"name": "x", "count": 1}')])
    with _client(server) as client:
        result = client.chat([{"role": "user", "content": "hi"}], seed=42, max_tokens=99)
    body = server.posts[0]
    assert server.paths == ["/v1/chat/completions"]
    assert body["seed"] == 42
    assert body["max_tokens"] == 99
    assert body["response_format"] == {"type": "json_object"}
    assert body["model"] == "fake-4b"
    assert result.text == '{"name": "x", "count": 1}'
    assert result.usage is not None and result.usage.completion_tokens == 5
    assert result.model == "fake-4b"
    assert result.http_attempts == 1


def test_chat_json_retries_with_a_changed_seed_then_validates() -> None:
    server = FakeServer(
        [
            _completion("Sorry, here is some prose and no JSON."),
            _completion('{"name": "x", "count": "not a number"}'),
            _completion('Here: {"name": "ok", "count": 3}'),
        ]
    )
    with _client(server) as client:
        obj, result = client.chat_json([{"role": "user", "content": "go"}], Answer, seed=7)
    assert obj == Answer(name="ok", count=3)
    seeds = [p["seed"] for p in server.posts]
    assert seeds == [7, 7 + SEED_STEP, 7 + 2 * SEED_STEP]
    assert result.json_attempts == 3
    # the retry carries a nudge naming the problem
    assert server.posts[1]["messages"][-1]["role"] == "user"
    assert "not valid" in server.posts[1]["messages"][-1]["content"]
    # usage is summed over the completions it took
    assert result.usage is not None and result.usage.completion_tokens == 15


def test_chat_json_gives_up_after_max_retries() -> None:
    server = FakeServer([_completion("nope")] * 3)
    with _client(server, max_retries=3) as client:
        with pytest.raises(TeacherError, match="no valid Answer after 3"):
            client.chat_json([{"role": "user", "content": "go"}], Answer, seed=1)
    assert len(server.posts) == 3


def test_falls_back_when_server_rejects_response_format() -> None:
    server = FakeServer(
        [
            httpx.Response(400, json={"error": {"message": "unknown field response_format"}}),
            _completion('{"name": "y", "count": 2}'),
            _completion('{"name": "z", "count": 4}'),
        ]
    )
    with _client(server) as client:
        obj, _ = client.chat_json([{"role": "user", "content": "go"}], Answer, seed=1)
        assert obj.name == "y"
        assert client.json_mode is False
        client.chat([{"role": "user", "content": "again"}], seed=2)
    assert "response_format" in server.posts[0]
    assert "response_format" not in server.posts[1]
    assert "response_format" not in server.posts[2]


def test_retries_on_5xx_and_connection_errors() -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("slow", request=request)
        if calls["n"] == 2:
            return httpx.Response(503, text="busy")
        return _completion('{"name": "late", "count": 9}')

    client = TeacherClient(
        "http://teacher.test/v1", transport=httpx.MockTransport(flaky), backoff_s=0.0
    )
    result = client.chat([{"role": "user", "content": "go"}], seed=1)
    assert result.http_attempts == 3
    assert result.text == '{"name": "late", "count": 9}'


def test_non_retryable_http_error_raises() -> None:
    server = FakeServer([httpx.Response(404, text="no such route")])
    with _client(server) as client:
        with pytest.raises(TeacherError, match="HTTP 404"):
            client.chat([{"role": "user", "content": "go"}], seed=1)


SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "count": {"type": "integer"}},
    "required": ["name", "count"],
    "additionalProperties": False,
}


def test_chat_sends_json_schema_when_given() -> None:
    server = FakeServer([_completion('{"name": "x", "count": 1}')])
    with _client(server) as client:
        obj, result = client.chat_json(
            [{"role": "user", "content": "go"}], Answer, seed=5, schema=SCHEMA, schema_name="ans"
        )
        assert client.schema_mode is True
        assert client.json_mode is None  # json_object was never probed
    assert obj.count == 1 and result.json_attempts == 1
    assert server.posts[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "ans", "strict": True, "schema": SCHEMA},
    }


def test_steps_down_from_json_schema_to_json_object_to_plain() -> None:
    server = FakeServer(
        [
            httpx.Response(400, json={"error": {"message": "json_schema is not supported"}}),
            httpx.Response(400, json={"error": {"message": "unknown field response_format"}}),
            _completion('{"name": "y", "count": 2}'),
            _completion('{"name": "z", "count": 4}'),
        ]
    )
    with _client(server) as client:
        obj, result = client.chat_json(
            [{"role": "user", "content": "go"}], Answer, seed=1, schema=SCHEMA
        )
        assert obj.name == "y"
        assert result.http_attempts == 1  # the two probes do not count as failed tries
        assert client.schema_mode is False and client.json_mode is False
        client.chat([{"role": "user", "content": "again"}], seed=2, schema=SCHEMA)
    assert server.posts[0]["response_format"]["type"] == "json_schema"
    assert server.posts[1]["response_format"] == {"type": "json_object"}
    assert "response_format" not in server.posts[2]
    assert "response_format" not in server.posts[3]


def test_json_schema_rejected_but_json_object_accepted() -> None:
    server = FakeServer(
        [
            httpx.Response(400, json={"error": {"message": "json_schema is not supported"}}),
            _completion('{"name": "y", "count": 2}'),
        ]
    )
    with _client(server) as client:
        client.chat([{"role": "user", "content": "go"}], seed=1, schema=SCHEMA)
        assert client.schema_mode is False and client.json_mode is True
    assert server.posts[1]["response_format"] == {"type": "json_object"}
