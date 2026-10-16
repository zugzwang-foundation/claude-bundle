# The toy teacher on the Mac (BDL-3, W3)

The toy teacher is a small instruct model served locally by llama.cpp's
`llama-server` as an OpenAI-compatible API. `bundle_pipeline.teacher` talks to it
exactly as it will talk to the Spark's vLLM server later; only the URL changes.

All facts below were checked on 2026-10-16 (UTC) on this Mac unless marked
NOT VERIFIED.

## Reaching it

| | |
|---|---|
| Base URL | `http://127.0.0.1:8081/v1` (override with `BUNDLE_TEACHER_URL`) |
| Endpoints used | `GET /v1/models`, `POST /v1/chat/completions` |
| JSON output | `response_format: {"type": "json_object"}` is honoured (grammar-constrained); `json_schema` is also supported by this server version |
| Model name in requests | anything; the server has one model loaded (`bundle_pipeline.config.TEACHER_MODEL` sends `local`) |
| Sampling the model card recommends | temperature 0.7, top_p 0.8, top_k 20, min_p 0 (non-thinking model; there is no thinking mode to switch off) |
| Start | `pipeline/scripts/teacher-mac.sh` (idempotent: exits 0 if the port already answers; otherwise starts the server with nohup and waits up to 180 s for `/v1/models`) |
| Stop | `pipeline/scripts/teacher-mac-stop.sh` |
| Smoke test | `cd pipeline && uv run python scripts/teacher_smoke.py --concurrency 4` |
| Log | `~/Developer/claude-bundle/models/teacher/server.log` (`models/` is gitignored) |
| PID file | `~/Developer/claude-bundle/models/teacher/server.pid` |

Exact server command (what the start script runs):

```sh
nohup /opt/homebrew/bin/llama-server \
  -m ~/Developer/claude-bundle/models/teacher/Qwen3-4B-Instruct-2507-Q4_K_M.gguf \
  --host 127.0.0.1 --port 8081 -c 16384 -np 4 --jinja -t 6 \
  > ~/Developer/claude-bundle/models/teacher/server.log 2>&1 &
```

`-c 16384 -np 4` gives four parallel slots of 4,096 tokens each (the log says
`n_slots = 4, n_ctx_slot = 4096, kv_unified = 'false'`). Every flag was accepted
by this llama-server version; `--jinja` is already the default here but is kept
so the command also works on older builds. The start script takes
`TEACHER_CTX`, `TEACHER_SLOTS`, `TEACHER_THREADS`, `TEACHER_PORT`,
`TEACHER_MODEL` overrides; `TEACHER_CTX=32768` (8,192 per slot) is the first
thing to try if a generation prompt plus answer does not fit in 4,096 tokens
(memory allows it: see below).

## Server

- `llama-server --version`: `version: 0.5.0 (build 11146, commit 7fe450e19)`,
  `built with AppleClang 17.0.0.17000604 for Darwin arm64`; Homebrew formula
  `llama.cpp 0.5.0`, binary `/opt/homebrew/bin/llama-server`.
- Devices (`llama-server --list-devices`): `BLAS: Accelerate`, `MTL0: Apple M4
  (16384 MiB)`. During generation the server process uses about 10% of one CPU,
  so the work runs on the Metal GPU, not the CPU threads.
- mlx_lm.server and Ollama are not installed and were not installed today (the
  relay's first choice, mlx-lm, was skipped for time; llama.cpp was already
  present).
- Machine: Apple M4, 10 cores (4 performance + 6 efficiency), 24 GB memory.
- Server memory: RSS 4.9-5.2 GB with the model loaded and 16k of KV cache
  (about 20% of RAM; the relay's ceiling is 40%, about 9.6 GiB).
- The server warns at start that no API key is set and CORS allows all
  origins. It listens on 127.0.0.1 only, so this is fine for a local toy.

## Model

| | |
|---|---|
| Model | Qwen3-4B-Instruct-2507 (4.0 B parameters, 3.6 B non-embedding; context 262,144 natively; non-thinking) |
| Licence | **Apache-2.0**. Model card tag `license: apache-2.0`; the card's `LICENSE` file is the standard Apache License 2.0 text (fetched from `https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/raw/main/LICENSE`). Apache-2.0 places no restriction on training other models on the outputs and no restriction on commercial use; the model card adds no extra terms. Verdict: PASS. |
| Base repo | https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507 (not gated; last modified 2025-09-17) |
| GGUF repo used | https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF (not gated, not private; licence tag apache-2.0 with `license_link` to the Qwen LICENSE above; last modified 2025-08-20) |
| Why not Qwen's own GGUF | `https://huggingface.co/api/models/Qwen/Qwen3-4B-Instruct-2507-GGUF` answers 401: no public repo under that name. bartowski's `Qwen_Qwen3-4B-Instruct-2507-GGUF` is also ungated with a Q4_K_M of 2,497,280,736 bytes and would do as a mirror. |
| File | `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| Size | 2,497,281,120 bytes (2.50 GB, 2.33 GiB); the server reports `ftype: Q4_K - Medium`, `n_params: 4,022,468,096` |
| SHA-256 | `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` (matches the Hub's LFS record for the file) |
| Download URL | `https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| Download command | `curl -L -C - --retry 5 -o ~/Developer/claude-bundle/models/teacher/Qwen3-4B-Instruct-2507-Q4_K_M.gguf <URL>` (resumable) |
| Local path | `~/Developer/claude-bundle/models/teacher/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (gitignored under `models/`) |
| Checked on | 2026-10-16, via the Hub API (`/api/models/...?blobs=true`) and the model-card pages |

Disk: `df -h ~` showed 16 GiB free before the download and 13 GiB after
(the 2.3 GiB file plus other agents' work in the same minutes). The download took
about 8 minutes.

Fallbacks considered and not needed: Qwen2.5-3B-Instruct is under the Qwen
research licence (skip); Qwen2.5-7B-Instruct Q4_K_M (~4.7 GB, Apache-2.0) was
too large for the 20 GB disk budget; Qwen3-1.7B would have been the small
fallback.

## Measured throughput (2026-10-16, 17:49-17:53 IST)

Measured with `scripts/teacher_smoke.py` (httpx from the project's venv) while
other BDL-3 agents were running on the same Mac: the load average was 7-11 on
10 cores and 39% of memory was free. Idle-Mac numbers would likely be higher:
NOT VERIFIED.

| Measurement | Result |
|---|---|
| Single stream, short JSON (59 prompt tokens, 36 output tokens) | 15.6 tokens/s generation; 2.4 s wall |
| Single stream, 400-token JSON answer (`max_tokens` 400, 116 prompt tokens) | **26.3 s wall**: 0.83 s prompt (113 tokens/s) + 25.5 s generation (**15.7 tokens/s**) |
| Single stream, 572-token complete JSON (20-item list, `max_tokens` 700) | 33.3 s wall, 17.2 tokens/s generation; prompt served from cache (`cached_tokens: 115`) |
| 4 concurrent 400-token JSON answers (`-np 4`) | 74.9 s wall for all four; 5.56 tokens/s per slot; **21.4 tokens/s aggregate** (1,600 tokens / 74.9 s) |
| Prompt processing | 113-156 tokens/s single stream on 59-93-token prompts; 38 tokens/s per slot with four slots busy (about 150 tokens/s aggregate) |
| JSON validity | the short answer and the 572-token answer parsed as JSON; the 400-token answers did not only because `max_tokens` cut the 20-item list short (`finish_reason: length`). Grammar-constrained `json_object` mode works. |

Four slots give only 1.4x the single-stream rate on this GPU, so parallelism
helps a little, not a lot. Prompt caching across requests works (slot reuse by
longest common prefix), so prompts that share a long fixed prefix are cheap.

Raw numbers: `~/Developer/claude-bundle/models/teacher/smoke-4.json` and the
`print_timing` lines in `server.log`.

## Time estimate for the toy generation

Assumptions: 24 people x 60 chats = 1,440 chats at about 80 output tokens each
(115,000 tokens), plus a persona (about 250 tokens) and three or four thread
labels and descriptions (about 240 tokens) per person: about 127,000 output
tokens in all. Prompt side: if the generator asks for about ten chats per
request, that is about 250 requests of roughly 600 prompt tokens (150,000
tokens).

| | At measured rates (4 slots, loaded Mac) |
|---|---|
| Output, 127,000 tokens at 21.4 tokens/s | 99 min |
| Prompts, 150,000 tokens at about 150 tokens/s | 17 min |
| 24 people x 60 chats, total | **about 2 hours** (before retries) |
| Per person (60 chats) | about 4.6 min |

Recommended `--people` for a 55-minute budget: **10** (600 chats, about 46 min
of generation at the measured aggregate rate, leaving about 9 minutes for
retries, validation and the slower per-slot rate when all four slots are busy).
If the generator keeps answers to about 80 tokens per chat and batches ten chats
per request, 12 people fit on an idle Mac; 24 people need about two hours and
should run with `nohup` while W4-W6 continue, as the relay allows ("size down if
throughput is lower").

Two design notes for `generate.py` that follow from the numbers:

1. One request per chat would cost about 1,440 prompts of 600+ tokens each
   (about 1.5 hours of prompt processing alone). Ask for a thread's chats, or
   about ten chats, per request instead.
2. Keep the fixed instructions and the persona at the front of every prompt for
   that person so the slot's prefix cache is hit.

Open point: with ten people the deterministic 80/10/10 split by person gives an
exam of one person. 12 people x 50 chats (600 chats, same cost) gives a slightly
better split and the same number of decisions; the generate agent should choose.

## Server state at hand-over

Left RUNNING: `llama-server` pid in `~/Developer/claude-bundle/models/teacher/server.pid`,
started 2026-10-16 17:48 IST (12:18 UTC). `pipeline/scripts/teacher-mac.sh`
re-attaches to it or restarts it after a reboot.
