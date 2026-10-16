"""OpenAI-compatible chat client for the teacher server.

Today the server is llama.cpp's `llama-server` on this Mac; later it is vLLM on
the Spark. Both speak the OpenAI chat-completions dialect, so one client drives
both:

    client = TeacherClient()                        # URL from BUNDLE_TEACHER_URL
    client.health()                                 # GET /models -> model ids
    obj, result = client.chat_json(messages, SomeModel, seed=7)

`chat` runs one completion with transport-level retries (connection errors,
HTTP 429 and 5xx). It asks for JSON through `response_format`: a strict
`json_schema` when the caller passes one (llama-server compiles it to a grammar,
so every key and the item count are guaranteed), else `json_object`. If the
server rejects either with a 400 it remembers to step down a level. `chat_json`
pulls the first {...} block out of whatever text came back, validates it with
pydantic and, on failure, asks again with a changed seed, up to `max_retries`
completions in total.

Nothing here imports torch; the module is cheap to load and easy to test with
`httpx.MockTransport`.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from bundle_pipeline import config

Message = dict[str, str]

SEED_STEP = 1_000_003
"""Added to the seed on each JSON retry so the server does not replay the same sample."""

RETRY_NUDGE = (
    "Your previous answer was not valid for the required JSON shape ({error}). "
    "Answer again with exactly one JSON object and nothing else."
)


class TeacherError(RuntimeError):
    """The teacher could not be reached, or gave up after the configured retries."""


class BudgetExceeded(TeacherError):
    """Raised by a caller-supplied `before_call` hook when the time budget is spent."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: Usage | None) -> None:
        if other is None:
            return
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Usage | None:
        raw = data.get("usage")
        if not isinstance(raw, dict):
            return None

        def _int(key: str) -> int:
            value = raw.get(key, 0)
            return int(value) if isinstance(value, int | float) else 0

        return cls(_int("prompt_tokens"), _int("completion_tokens"), _int("total_tokens"))


@dataclass
class ChatResult:
    """What one successful `chat` call returned, plus how much it cost."""

    text: str
    seed: int
    http_attempts: int
    """HTTP requests this completion needed (transport retries included)."""
    elapsed_s: float
    """Wall time of the successful request, as seen by the client."""
    usage: Usage | None
    model: str | None
    json_attempts: int = 1
    """Set by `chat_json`: how many completions it took to get valid JSON."""


# --- JSON extraction ----------------------------------------------------------

_THINK = re.compile(r"<think>.*?</think>", re.S)
_FENCE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)```", re.S)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _balanced_object(text: str, start: int) -> tuple[str, bool]:
    """The {...} block starting at `start`, and whether it closed."""
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1], True
    return text[start:], False


def _repair(block: str, closed: bool) -> str:
    """Cheap fixes for the two mistakes small models make most: trailing commas, truncation."""
    fixed = _TRAILING_COMMA.sub(r"\1", block)
    if not closed:
        # Close an unterminated string, then any open brackets, innermost first.
        if fixed.count('"') % 2 == 1:
            fixed += '"'
        stack: list[str] = []
        in_string = False
        escaped = False
        for ch in fixed:
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]" and stack:
                stack.pop()
        fixed = _TRAILING_COMMA.sub(r"\1", fixed.rstrip().rstrip(","))
        fixed += "".join(reversed(stack))
    return fixed


def extract_json(text: str, max_scan: int = 50) -> dict[str, Any]:
    """Return the first JSON object found in messy model output.

    Handles reasoning blocks, ```json fences, prose before and after, braces
    inside strings, trailing commas and a truncated tail. Raises ValueError
    when nothing parses.
    """
    if not text or not text.strip():
        raise ValueError("empty response")
    cleaned = _THINK.sub("", text)
    chunks: list[str] = [m.group(1) for m in _FENCE.finditer(cleaned)]
    chunks.append(cleaned)
    for chunk in chunks:
        pos = 0
        for _ in range(max_scan):
            start = chunk.find("{", pos)
            if start < 0:
                break
            block, closed = _balanced_object(chunk, start)
            for candidate in (block, _repair(block, closed)):
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed
            pos = start + 1
    raise ValueError("no JSON object found in response")


def _content(data: dict[str, Any]) -> str:
    try:
        choice = data["choices"][0]
    except (KeyError, IndexError, TypeError) as e:
        raise TeacherError(f"malformed completion: {str(data)[:200]}") from e
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if content is None and isinstance(choice, dict):
        content = choice.get("text")  # legacy /completions shape
    if not isinstance(content, str):
        raise TeacherError("completion has no text content")
    return content


# --- Client -------------------------------------------------------------------


class TeacherClient:
    """A thin, synchronous client over httpx. Safe to share across threads."""

    def __init__(
        self,
        base_url: str = config.TEACHER_URL,
        model: str = config.TEACHER_MODEL,
        *,
        timeout_s: float = config.TEACHER_TIMEOUT_S,
        max_retries: int = config.TEACHER_MAX_RETRIES,
        backoff_s: float = 2.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max(1, max_retries)
        self.backoff_s = backoff_s
        self.json_mode: bool | None = None
        """None until a request is made; False once the server rejected response_format."""
        self.schema_mode: bool | None = None
        """None until a schema is sent; False once the server rejected json_schema."""
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_s, connect=10.0),
            transport=transport,
            headers={"Content-Type": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> TeacherClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- health --

    def health(self) -> list[str]:
        """GET /models; returns the model ids the server offers. Raises TeacherError."""
        try:
            response = self._client.get("/models")
        except httpx.HTTPError as e:
            raise TeacherError(f"teacher unreachable at {self.base_url}: {e}") from e
        if response.status_code != 200:
            raise TeacherError(f"teacher /models returned HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as e:
            raise TeacherError("teacher /models did not return JSON") from e
        rows = data.get("data", []) if isinstance(data, dict) else []
        return [
            row["id"] for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)
        ]

    # -- one completion --

    def chat(
        self,
        messages: Sequence[Message],
        *,
        seed: int,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json: bool = True,
        schema: dict[str, Any] | None = None,
        schema_name: str = "answer",
    ) -> ChatResult:
        """One chat completion with transport retries. Returns the raw text.

        `schema` (a JSON schema) asks for grammar-constrained output through
        `response_format: json_schema`; without one, `json=True` asks for
        `json_object`. Either steps down when the server answers 400.
        """
        body: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "seed": seed,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        use_schema = json and schema is not None and self.schema_mode is not False
        use_json = json and self.json_mode is not False

        def set_format() -> None:
            if use_schema:
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "strict": True, "schema": schema},
                }
            elif use_json:
                body["response_format"] = {"type": "json_object"}
            else:
                body.pop("response_format", None)

        set_format()

        attempts = 0
        last_error = "no attempt made"
        while attempts < self.max_retries:
            attempts += 1
            started = time.monotonic()
            try:
                response = self._client.post("/chat/completions", json=body)
            except httpx.HTTPError as e:
                last_error = f"{type(e).__name__}: {e}"
                self._sleep(attempts)
                continue
            elapsed = time.monotonic() - started

            if response.status_code == 400 and (use_schema or use_json):
                # Step down: json_schema -> json_object -> JSON instructed in the prompt only.
                if use_schema:
                    self.schema_mode = False
                    use_schema = False
                else:
                    self.json_mode = False
                    use_json = False
                set_format()
                attempts -= 1  # the probe does not count as a failed try
                continue
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                self._sleep(attempts)
                continue
            if response.status_code != 200:
                raise TeacherError(f"teacher HTTP {response.status_code}: {response.text[:500]}")

            try:
                data = response.json()
            except ValueError as e:
                raise TeacherError("teacher returned a non-JSON completion body") from e
            if use_schema and self.schema_mode is None:
                self.schema_mode = True
            if use_json and not use_schema and self.json_mode is None:
                self.json_mode = True
            return ChatResult(
                text=_content(data),
                seed=seed,
                http_attempts=attempts,
                elapsed_s=elapsed,
                usage=Usage.from_response(data),
                model=data.get("model") if isinstance(data.get("model"), str) else None,
            )
        raise TeacherError(f"teacher failed after {attempts} attempts: {last_error}")

    # -- JSON with validation and seed retries --

    def chat_json[T: BaseModel](
        self,
        messages: Sequence[Message],
        model_cls: type[T],
        *,
        seed: int,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        schema: dict[str, Any] | None = None,
        schema_name: str = "answer",
    ) -> tuple[T, ChatResult]:
        """Ask for JSON matching `model_cls`; retry with a changed seed on bad output.

        `schema` is forwarded to `chat` for grammar-constrained decoding.

        Each retry appends a short nudge naming the validation error. Returns
        the validated object and the ChatResult of the completion that worked
        (its usage covers that completion only; `total_usage` on the client is
        not kept, callers sum `result.usage` themselves).
        """
        errors: list[str] = []
        convo = list(messages)
        last_usage = Usage()
        for attempt in range(self.max_retries):
            use_seed = seed + attempt * SEED_STEP
            result = self.chat(
                convo,
                seed=use_seed,
                temperature=temperature,
                max_tokens=max_tokens,
                json=True,
                schema=schema,
                schema_name=schema_name,
            )
            last_usage.add(result.usage)
            try:
                payload = extract_json(result.text)
                obj = model_cls.model_validate(payload)
            except (ValueError, ValidationError) as e:
                short = str(e).splitlines()[0][:200]
                errors.append(f"seed {use_seed}: {short}")
                convo = [
                    *list(messages),
                    {"role": "assistant", "content": result.text[:2000]},
                    {"role": "user", "content": RETRY_NUDGE.format(error=short)},
                ]
                continue
            result.json_attempts = attempt + 1
            result.usage = last_usage if result.usage is not None else None
            return obj, result
        raise TeacherError(
            f"no valid {model_cls.__name__} after {self.max_retries} completions: "
            + " | ".join(errors)
        )

    def _sleep(self, attempt: int) -> None:
        if self.backoff_s > 0:
            time.sleep(min(self.backoff_s * attempt, 10.0))


__all__ = [
    "SEED_STEP",
    "BudgetExceeded",
    "ChatResult",
    "Message",
    "TeacherClient",
    "TeacherError",
    "Usage",
    "extract_json",
]
