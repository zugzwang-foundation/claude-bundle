"""Smoke-test the toy teacher: JSON output, single-stream and aggregate tokens/s.

Run with the project's runtime:
    cd pipeline && uv run python scripts/teacher_smoke.py [--concurrency 4] [--json-out path]

Reads BUNDLE_TEACHER_URL (default http://127.0.0.1:8081/v1). Uses only httpx, which
the package already pins. Prints a small report and optionally writes it as JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE_URL = os.environ.get("BUNDLE_TEACHER_URL", "http://127.0.0.1:8081/v1").rstrip("/")

SHORT_PROMPT = (
    "Return a JSON object with keys 'label' (a two-word bundle name for chats about "
    "training for a first half marathon) and 'description' (one sentence). JSON only."
)
LONG_PROMPT = (
    "Return a JSON object with a key 'chats' holding a list of exactly 20 objects. "
    "Each object has 'day' (an integer), 'text' (one casual opening question a runner "
    "might type into an AI assistant while training for a half marathon, 10 to 20 words) "
    "and 'difficulty' (one of plain, overlap, vague, typos, very_short). Vary the topics. "
    "JSON only, no prose."
)

FIRST_JSON = re.compile(r"\{.*\}", re.DOTALL)


def chat(
    client: httpx.Client, prompt: str, max_tokens: int, seed: int, json_mode: bool = True
) -> dict:
    body = {
        "model": "teacher",
        "messages": [
            {"role": "system", "content": "You answer with one JSON object and nothing else."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 0.8,
        "seed": seed,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/chat/completions", json=body, timeout=600)
    wall = time.perf_counter() - t0
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"] or ""
    usage = data.get("usage", {})
    timings = data.get("timings", {})
    parsed_ok = False
    try:
        json.loads(content)
        parsed_ok = True
    except json.JSONDecodeError:
        m = FIRST_JSON.search(content)
        if m:
            try:
                json.loads(m.group(0))
                parsed_ok = True
            except json.JSONDecodeError:
                parsed_ok = False
    return {
        "wall_s": round(wall, 3),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "finish_reason": data["choices"][0].get("finish_reason"),
        "server_predicted_per_second": timings.get("predicted_per_second"),
        "server_prompt_per_second": timings.get("prompt_per_second"),
        "server_predicted_ms": timings.get("predicted_ms"),
        "server_prompt_ms": timings.get("prompt_ms"),
        "json_parsed": parsed_ok,
        "content_head": content[:160],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    report: dict = {"base_url": BASE_URL, "model": None}
    with httpx.Client() as client:
        models = client.get(f"{BASE_URL}/models", timeout=30).json()
        report["model"] = [m.get("id") for m in models.get("data", [])]
        print("models:", report["model"])

        # Warm-up (loads Metal kernels, fills nothing we keep).
        chat(client, SHORT_PROMPT, 64, seed=1)

        print("\n== single stream, short JSON (max 128 tokens)")
        s = chat(client, SHORT_PROMPT, 128, seed=7)
        print(json.dumps(s, indent=1))
        report["single_short"] = s

        print("\n== single stream, ~400-token JSON answer (max 400 tokens)")
        long = chat(client, LONG_PROMPT, 400, seed=11)
        print(json.dumps(long, indent=1))
        report["single_long_400"] = long

        print(f"\n== {args.concurrency} concurrent ~400-token JSON answers")
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            with httpx.Client() as c2:
                results = list(
                    ex.map(
                        lambda i: chat(c2, LONG_PROMPT, 400, seed=100 + i),
                        range(args.concurrency),
                    )
                )
        wall = time.perf_counter() - t0
        total_tokens = sum(r["completion_tokens"] or 0 for r in results)
        agg = {
            "concurrency": args.concurrency,
            "wall_s": round(wall, 3),
            "total_completion_tokens": total_tokens,
            "aggregate_tokens_per_s": round(total_tokens / wall, 1) if wall else None,
            "per_request_wall_s": [r["wall_s"] for r in results],
            "per_request_server_tps": [r["server_predicted_per_second"] for r in results],
            "all_json_parsed": all(r["json_parsed"] for r in results),
        }
        print(json.dumps(agg, indent=1))
        report["concurrent"] = agg

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
        print("wrote", args.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
