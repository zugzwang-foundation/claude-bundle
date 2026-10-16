# scripts/spark — running Bundle's loop on the DGX Spark

> **WRITTEN IN BDL-3, NEVER RUN YET. VERIFY ON THE SPARK IN BDL-4.**
> No Spark was available when these files were written. Every command below was
> taken from the two research notes named under *Sources*, not from a run. Each
> script is `bash -n` clean and nothing more. Treat the first night as a test of
> the scripts, not of the model.

Status: DRAFT (BDL-3). Bundle is a working name.

## What is here, in the order it runs

| file | what it does | run it |
|---|---|---|
| `00-check.sh` | Read-only health check: OS, kernel, `nvidia-smi`, CUDA, memory, disk, Docker and its NVIDIA runtime, sleep targets, tmux, uv and the CUDA build of torch, a GPU container smoke test. Exits non-zero on any FAIL. | by hand, first, and whenever something looks wrong |
| `10-serve-teacher.sh` | Starts the teacher: vLLM in NVIDIA's NGC container serving the model R3 picked, bound to `127.0.0.1:8081`, with an OpenAI-compatible API. Idempotent (exits 0 if the port already answers). Health-check loop. | by hand or from `20-run-loop.sh` |
| `20-run-loop.sh` | One night: `generate -> validate -> split -> tasks -> baseline -> train -> calibrate -> exam -> export -> scoreboard`, each via `uv run bundle-pipeline <command>`, with `BUNDLE_TEACHER_URL` set, per-stage time budgets, logs under `runs/<run-id>/`, and a stop on the first failure. | by hand in tmux first; then from the timer |
| `30-nightly.service` | systemd **user** unit that runs `20-run-loop.sh` with `Restart=on-failure`. **Not enabled.** | install by hand when the loop has worked once |
| `30-nightly.timer` | systemd **user** timer that starts the service at 01:00 local time, catching up after a missed night. **Not enabled.** | same |
| `ssh.md` | How to reach the Spark from the Mac: key-based SSH on the LAN, optional Tailscale, tmux for long runs, tunnels, getting the data back. Placeholders only. | read |

Order on the first night (from R6's BDL-4 checklist and R3's first task):

1. `./00-check.sh` and fix every FAIL.
2. `./10-serve-teacher.sh`, then `curl -s http://127.0.0.1:8081/v1/models`.
3. A ten-minute throughput test at sixteen concurrent requests, using the pipeline
   itself: `cd pipeline && BUNDLE_TEACHER_URL=http://127.0.0.1:8081/v1 BUNDLE_TEACHER_MODEL=nvidia/Qwen3.6-35B-A3B-NVFP4 uv run bundle-pipeline generate --people 16 --workers 16 --time-budget-min 10 --seed 1 --data-root data/throughput`.
   `--data-root` keeps the test people out of the real data tree. `generate` prints
   tok/s per person and, at the end, an aggregate "tok/s while busy" (generate.py,
   checked 16 Oct 2026). R3's rule: under 200 tok/s aggregate, switch to Fallback A
   (see *Teacher choices* below).
4. `./20-run-loop.sh` inside tmux, with small numbers first (`PEOPLE=20 GEN_TIME_BUDGET_MIN=30`).
5. Only when 4 has finished once: install the units (instructions at the top of
   `30-nightly.service`) and let the timer run a night.
6. The morning after: `journalctl --user -u 30-nightly --since yesterday | tail`,
   `last -x reboot | head`, the `runs/<run-id>/status.tsv` and the new
   `scoreboard/runs/<run-id>.json`. A reboot in the night means the stability
   mitigations R6 lists (airflow and dust, firmware with a cold drain, then the
   clock cap `nvidia-smi -lgc 300,2100`), in that order.

## What must be true before running anything

From R6's checklist (docs/research/dgx-spark.md, "BDL-4 setup checklist"):

- A **128 GB** Spark, not the 64 GB variant: a 64 GB unit changes the teacher plan (R6, point 7).
- DGX OS 7.5.0 or later as R6 records it (kernel 6.17, driver 580.159.03, CUDA 13.0.2); `00-check.sh` prints what it finds and compares softly.
- Wired to the router by Ethernet; the supplied 240 W adapter only; standing where air moves (R6).
- One account with a non-personal username (R6 suggests `bundle`); SSH keys copied once (`ssh.md`).
- Sleep, suspend, hibernate and hybrid-sleep targets masked (R6; `00-check.sh` checks).
- uv installed from a pinned installer URL, the repository cloned over HTTPS into `~/bundle` (the scripts find the repository root from their own location, so another path works too).
- `pipeline/pyproject.toml` carries the explicit `pytorch-cu130` index block, `uv sync` has run, and
  `uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_capability())"`
  prints `2.14.1+cu130 True (12, 1)`. A `+cpu` means stop and fix the index (R6, point 4). **As of BDL-3 the pyproject does not yet carry that block**: adding it is BDL-4 work.
- `docker pull` of the vLLM image works. If it demands a login, that is an NGC account: log it under *Needs Hrishikesh* and fall back to PyPI vLLM 0.30.0 in uv (R6, step 8).
- Enough disk: teacher checkpoints run 20–70 GB each (R6); `00-check.sh` warns under `MIN_FREE_GB` (default 150).
- No Hugging Face token is needed: every model named here is ungated (R3, source 79; R6). If one is ever added it lives in `~/.config/bundle/env` on the Spark, mode 600, never in the repository.
- Nobody clicks *Update* in the DGX Dashboard during a run: it reboots the box (R6).

## Teacher choices baked into `10-serve-teacher.sh`

All parameters sit at the top of the file and can be overridden from the environment.

| parameter | default | why |
|---|---|---|
| `VLLM_IMAGE` | `nvcr.io/nvidia/vllm:26.04-py3` | R3: vLLM 0.19.0, the Qwen3.6 card's minimum, and the tag the community measurement used; R3 asks this folder to pin it. **R6 names `26.05-py3`** (the playbook's tag) and says to start there. Both appear in NVIDIA's release index per R6 (source 61). Open point for BDL-4: confirm with `docker pull` before the first night (R6, point 8) and pick one. |
| `TEACHER_MODEL_ID` | `nvidia/Qwen3.6-35B-A3B-NVFP4` | R3's pick: Qwen3.6-35B-A3B, Apache-2.0, not gated, in NVIDIA's official NVFP4 checkpoint (also Apache-2.0, not gated), whose card carries a DGX Spark section. |
| flags | `--kv-cache-dtype fp8 --attention-backend flashinfer --moe-backend marlin --language-model-only` | from the NVFP4 card's Spark section and the Qwen3.6 card, as R3 records them. |
| `GPU_MEMORY_UTILIZATION` | `0.7` | R6's recommendation for unified memory; NVIDIA's own notes say vLLM over-allocates on it. Budget 100–110 GB for teacher plus KV cache, never 128 (R6, point 5). |
| `MAX_NUM_SEQS` / `MAX_MODEL_LEN` | `64` / `8192` | R6's serve example (step 9). Decode is memory-bound; only batching makes the Spark a data factory (R6). Lower `MAX_NUM_SEQS` if the server reports out of memory. |
| port | `127.0.0.1:8081 -> 8000` | the pipeline's default `BUNDLE_TEACHER_URL` is `http://127.0.0.1:8081/v1`; vLLM listens on 8000 inside the container (R6). Bound to localhost only, reached over SSH or the tailnet (R6). |

Fallbacks R3 names, as one-line overrides:

- **Fallback A** (if Gated DeltaNet kernels are slow on GB10, or aggregate decode is under 200 tok/s):
  `TEACHER_MODEL_ID=Qwen/Qwen3-30B-A3B-Instruct-2507 MOE_BACKEND= LANGUAGE_MODEL_ONLY=0 ./10-serve-teacher.sh`
  (plain attention, best checked writing scores; not an FP4 checkpoint, so the marlin backend that FP4 MoE needs per R3 (source 48 and the NVFP4 card) is left off, and the vision-skipping flag too since R3's table lists it as text-only. NOT VERIFIED that either flag would be harmless if kept).
- **Fallback B**: gpt-oss-120b on llama-server (harmony chat format). Not scripted here.
- A second teacher for one person in five, Gemma 4 26B-A4B-it (Apache-2.0, not gated), is R3's recipe but not scripted: the loop talks to one URL.

Sampling R3 takes from the Qwen3.6 card (temperature 0.7, top-p 0.8, top-k 20, presence penalty 1.5) and the `chat_template_kwargs: {"enable_thinking": false}` switch belong in the request body, which is the pipeline's job, not the server's. See the next section.

## Pipeline changes BDL-4 must make before the loop is honest on the Spark

Read from `pipeline/src/bundle_pipeline/` as it stands at the end of BDL-3 (checked 16 Oct 2026):

1. **CUDA device.** `encoder.resolve_device("auto")` returns `mps` or `cpu`; the CLI's `--device` offers only `auto|cpu|mps`. On the Spark `auto` means **CPU**. Add `cuda` to the choices and to `resolve_device`, then set `DEVICE=cuda` in `20-run-loop.sh`. The loop warns about this on every run until it is fixed.
2. **No thinking tokens.** `teacher.py` sends no `chat_template_kwargs`. R3 says Qwen3.6 needs `chat_template_kwargs: {"enable_thinking": false}` (the `/no_think` soft switch is not supported). `extract_json` strips `<think>` blocks today, so the loop works, but every thought is paid for in tokens. Structured output is already as R3 asks: `teacher.py` sends a strict `response_format: json_schema` for the v0.2 prompts and steps down to `json_object`, then to plain JSON in the prompt, when a server answers 400.
3. **Sampling.** `teacher.py` sends `temperature` 0.7, which matches the Qwen3.6 card; top-p 0.8, top-k 20 and presence penalty 1.5 (above) are not sent, so the server's defaults apply to them.
4. **Sealed exam across nights.** `split` ranks people by `sha256(person_id + salt)` and refuses to change `exam.jsonl` (exit 2) unless `--force`. Adding people on night two changes the ranks, so the loop will stop at `split`. Whether the exam is fixed across runs or re-split per major version is R3's open question (docs/ARCHITECTURE.md, section 6). The loop leaves `SPLIT_FORCE=0` and stops rather than guess.
5. **Run ids.** The default is `<date>-toy-v0`. The loop passes `--run-id <local-date>-spark-v0`; the `v0` suffix is a placeholder for the release numbering BDL-4 settles.
6. **Web calibration copy.** `calibrate` writes `web/src/sorter/calibration.json` by default. On the Spark the loop passes `--no-web`: shipping is decided on the Mac under D7, after the exam, never by the night job.

## systemd: user units, and when a system unit is better

The task asked for user units, and that is what `30-nightly.*` are. Two things R6 did not confirm, so both are NOT VERIFIED on DGX OS:

- A user manager only runs while that user has a session unless lingering is on: `loginctl enable-linger <user>`. Without it the 01:00 timer never fires on a headless box.
- User units cannot order themselves after the system's `docker.service`. The loop copes by waiting for the teacher's health check instead.

R6's own path is a **system** unit (`sudo systemctl enable --now bundle-gen`, `WorkingDirectory=/home/bundle/bundle`, `Restart=on-failure`, `RestartSec=30`). To use the same files that way: copy them to `/etc/systemd/system/`, add `User=<user>` under `[Service]`, replace every `%h` with the home directory, change `WantedBy=default.target` to `multi-user.target`, then `sudo systemctl daemon-reload && sudo systemctl enable --now 30-nightly.timer`. Logs: `journalctl -u 30-nightly -f`.

Why systemd and not cron: R6 wants every long job to survive the hard power-offs users report, so it must be resumable and restart on failure under systemd with journald logs. `generate` already skips people already on disk, so a restart resumes.

## Licences of what these scripts run

- vLLM: Apache-2.0 (R3, source 83; R6).
- The NGC vLLM container: NVIDIA's EULA and AI product terms, **not** an open licence (R3, source 80). It is a tool run on our own machine, not a dependency we ship; R3 asks for it to be recorded in a licences file. The upstream `vllm/vllm-openai:cu130-nightly` image is the fallback if that matters (R3).
- Teacher `nvidia/Qwen3.6-35B-A3B-NVFP4` and `Qwen/Qwen3.6-35B-A3B`: Apache-2.0, not gated (R3, sources 7, 84, 79).
- torch cu130 wheels: BSD-style (R6). Tailscale client: BSD-3-Clause (R6). tmux and the rest are Ubuntu packages.

## NOT VERIFIED, by file

Marked in comments where they occur. Collected here so BDL-4 can tick them off:

- `00-check.sh`: `nvidia-smi --query-gpu=...,compute_cap` field name on DGX OS; `timedatectl show -p Timezone`; `nvcc` location when not on PATH; that `docker info` lists the runtime as `nvidia`.
- `10-serve-teacher.sh`: the image tag (26.04 vs 26.05); `docker run --restart unless-stopped` as the right policy next to a systemd-driven loop; the exact flag for MTP speculative decoding (left out; add through `EXTRA_VLLM_ARGS`); `--env-file` for an optional token file; whether the model id vLLM reports in `/v1/models` is exactly `TEACHER_MODEL_ID` (the loop assumes it is).
- `20-run-loop.sh`: `timeout` from coreutils on DGX OS; that a local-date run id survives a restart in the same night; that `--device auto` means CPU until the pipeline learns `cuda` (confirmed in the code, not yet on the box).
- `30-nightly.*`: `loginctl enable-linger`; `Type=simple` with `Restart=on-failure` under a timer; `StartLimitIntervalSec`/`StartLimitBurst`; `EnvironmentFile=-` tolerating a missing file; `%h` in `ExecStart` and `Environment=`; `TimeoutStopSec`, `KillMode=mixed` and `Nice` are standard systemd directives chosen here, not from R6. The loop exits with the failed stage's code, so a deliberate stop (`split` exit 2) is retried up to `StartLimitBurst` times; each retry is short because `generate` skips people on disk.
- `ssh.md`: the exact apt lines for Tailscale (pointed at the playbook, not copied); `ssh-copy-id` present on macOS (it is on recent macOS; not checked today); `ServerAliveCountMax` and `IdentitiesOnly` are ordinary OpenSSH options added here, not from R6 (R6 names only `ServerAliveInterval 60`).

## Sources

- docs/research/dgx-spark.md (R6): hardware, DGX OS, NGC images, serving flags, the uv/torch index pitfall, SSH and Tailscale, overnight stability, the BDL-4 checklist. Everything cited to R6 was checked there on 16 Oct 2026.
- docs/research/teacher-and-data.md (R3): the teacher pick, its checkpoint and flags, fallbacks, sampling, the throughput test and the data recipe. Checked 16 Oct 2026.
- docs/ARCHITECTURE.md section 5 (the nightly loop) and section 6 (open questions); docs/DECISIONS.md D3, D7, D9, D10.
- pipeline/README.md and pipeline/src/bundle_pipeline/{cli,config,encoder,teacher,generate,split,scoreboard}.py for the subcommands, flags, paths, exit codes and environment variables the loop uses. Read on 16 Oct 2026 from the W3 pipeline worktree before its pull request merged, so the flags below match that state; re-check `uv run bundle-pipeline <command> --help` on the Spark.
