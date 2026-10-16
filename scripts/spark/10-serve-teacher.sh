#!/usr/bin/env bash
# 10-serve-teacher.sh — start Bundle's teacher on the DGX Spark.
#
# WRITTEN IN BDL-3, NEVER RUN YET; VERIFY ON THE SPARK IN BDL-4.
#
# What it does: runs vLLM inside NVIDIA's NGC container, serving the teacher model
# R3 picked as an OpenAI-compatible API on 127.0.0.1:${TEACHER_PORT} (default 8081,
# the pipeline's default BUNDLE_TEACHER_URL). Idempotent: exits 0 if the port already
# answers. Bound to localhost only; reach it over SSH or the tailnet (R6). Never asks
# for input; no token is needed because every model named here is ungated (R3, R6).
#
# Sources (checked 16 Oct 2026):
#   docs/research/teacher-and-data.md (R3): the model, its NVFP4 checkpoint and the
#     card's DGX Spark flags, --language-model-only, fallbacks, the 26.04-py3 tag.
#   docs/research/dgx-spark.md (R6): the docker run shape (--gpus all --ipc=host,
#     HF cache mount, --gpu-memory-utilization 0.7, --max-num-seqs, --max-model-len),
#     dropping caches first, the 26.05-py3 tag, "confirm the tag with docker pull".
# Anything neither note confirms is marked NOT VERIFIED.

set -euo pipefail

# ---- parameters (override from the environment) ------------------------------
# Image. R3 pins 26.04-py3 (vLLM 0.19.0, the Qwen3.6 card's minimum, the tag the
# community measurement used). R6 names 26.05-py3 (the playbook's tag) and says to
# start there. Both are in NVIDIA's release index per R6. Decide in BDL-4 after
# `docker pull` of each (R6 point 8). The container is under NVIDIA's EULA, not an
# open licence; the vLLM inside is Apache-2.0 (R3).
VLLM_IMAGE="${VLLM_IMAGE:-nvcr.io/nvidia/vllm:26.04-py3}"

# Model: R3's pick, NVIDIA's official NVFP4 checkpoint of Qwen3.6-35B-A3B
# (Apache-2.0, not gated; three safetensors shards; card has a DGX Spark section).
TEACHER_MODEL_ID="${TEACHER_MODEL_ID:-nvidia/Qwen3.6-35B-A3B-NVFP4}"

# Where it listens. 8081 on the host maps to vLLM's 8000 inside the container (R6).
TEACHER_HOST="${TEACHER_HOST:-127.0.0.1}"
TEACHER_PORT="${TEACHER_PORT:-8081}"
CONTAINER_PORT="${CONTAINER_PORT:-8000}"

# Context and parallelism (R6 step 9 example). Lower MAX_NUM_SEQS on out-of-memory.
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
# Unified memory: NVIDIA's notes say vLLM over-allocates; 0.7 is R6's recommendation.
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.7}"

# Flags from the NVFP4 card's Spark section and the Qwen3.6 card, as R3 records them.
# Empty = flag omitted. Fallback A is not an FP4 checkpoint and R3's table lists it as
# text-only, so it runs with MOE_BACKEND= and LANGUAGE_MODEL_ONLY=0 (NOT VERIFIED that
# keeping either flag would be harmless).
KV_CACHE_DTYPE="${KV_CACHE_DTYPE:-fp8}"
ATTENTION_BACKEND="${ATTENTION_BACKEND:-flashinfer}"
MOE_BACKEND="${MOE_BACKEND:-marlin}"           # FP4 MoE needs marlin (R3, citing the community measurement and the NVFP4 card)
LANGUAGE_MODEL_ONLY="${LANGUAGE_MODEL_ONLY:-1}" # skip the vision encoder, free memory for KV cache (R3)
# MTP speculative decoding: the card carries a config (R3) but neither note records
# the exact vLLM flag: NOT VERIFIED. Add it here after reading the card in BDL-4.
EXTRA_VLLM_ARGS="${EXTRA_VLLM_ARGS:-}"

CONTAINER_NAME="${CONTAINER_NAME:-bundle-teacher}"
HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"   # mounted as in R6 step 9
# NOT VERIFIED against R6: docker's own restart policy. unless-stopped brings the
# teacher back after a reboot without systemd; set to "no" if that fights the loop.
RESTART_POLICY="${RESTART_POLICY:-unless-stopped}"
DROP_CACHES="${DROP_CACHES:-1}"          # R6 step 9 and NVIDIA's known issue: drop caches before a big load
HEALTH_TIMEOUT_S="${HEALTH_TIMEOUT_S:-2400}"   # first start downloads 20-35 GB (R3); later starts are minutes
HEALTH_EVERY_S="${HEALTH_EVERY_S:-10}"
SMOKE_REQUEST="${SMOKE_REQUEST:-1}"      # one tiny chat completion after the API answers
# Optional env file for a token, mode 600, never in the repository (R6). Only passed
# if it exists. NOT VERIFIED against R6: docker's --env-file flag.
TOKEN_ENV_FILE="${TOKEN_ENV_FILE:-$HOME/.config/bundle/env}"

BASE_URL="http://${TEACHER_HOST}:${TEACHER_PORT}"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }

# ---- 0. already up? ----------------------------------------------------------
# Captured into a variable, not piped to head: under set -e -o pipefail a head that
# closes early would kill this script with SIGPIPE before the exit 0.
if MODELS_JSON="$(curl -sf --max-time 3 "${BASE_URL}/v1/models" 2>/dev/null)"; then
  log "teacher already answering at ${BASE_URL}/v1:"
  printf '%.600s\n' "$MODELS_JSON"
  exit 0
fi

# ---- 1. preconditions --------------------------------------------------------
command -v docker >/dev/null 2>&1 || { log "docker not found (R6 says it is preinstalled)"; exit 1; }
docker info >/dev/null 2>&1 || { log "docker daemon not reachable as $(id -un); docker group? (00-check.sh)"; exit 1; }
mkdir -p "$HF_CACHE"

# A container of that name that is not running (crashed, stopped, left from a reboot) is removed.
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  STATE="$(docker container inspect --format '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo unknown)"
  if [ "$STATE" = "running" ]; then
    log "container $CONTAINER_NAME is running but ${BASE_URL}/v1/models does not answer yet; waiting for it"
    SKIP_START=1
  else
    log "removing stale container $CONTAINER_NAME (state: $STATE)"
    docker rm -f "$CONTAINER_NAME" >/dev/null
    SKIP_START=0
  fi
else
  SKIP_START=0
fi

if [ "$SKIP_START" = 0 ]; then
  # ---- 2. image present? (R6 point 8: a bad tag fails the first pull of the night)
  if ! docker image inspect "$VLLM_IMAGE" >/dev/null 2>&1; then
    log "pulling $VLLM_IMAGE (first time only; large)"
    if ! docker pull "$VLLM_IMAGE"; then
      log "pull failed. If it asked for a login that is an NGC account -> Needs Hrishikesh; fallback: PyPI vLLM 0.30.0 in uv (R6 step 8). If the tag is unknown, try VLLM_IMAGE=nvcr.io/nvidia/vllm:26.05-py3 (R6)"
      exit 1
    fi
  fi

  # ---- 3. drop page caches (R6 step 9; NVIDIA known issue on unified memory) ----
  if [ "$DROP_CACHES" = 1 ]; then
    if sudo -n sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null; then
      log "dropped page caches"
    else
      log "could not drop caches without a password (sudo -n); continuing. Unified memory may look full when it is not (R6)"
    fi
  fi

  # ---- 4. assemble the command -----------------------------------------------
  # No --host, as in R6 step 9 (which passes none and then curls the mapped port). The
  # -p 127.0.0.1:... mapping confines the API to localhost on the host. NOT VERIFIED:
  # that vLLM's default bind inside the container is reachable through that mapping.
  VLLM_ARGS=(
    vllm serve "$TEACHER_MODEL_ID"
    --port "$CONTAINER_PORT"
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION"
    --max-num-seqs "$MAX_NUM_SEQS"
    --max-model-len "$MAX_MODEL_LEN"
  )
  [ -n "$KV_CACHE_DTYPE" ]    && VLLM_ARGS+=(--kv-cache-dtype "$KV_CACHE_DTYPE")
  [ -n "$ATTENTION_BACKEND" ] && VLLM_ARGS+=(--attention-backend "$ATTENTION_BACKEND")
  [ -n "$MOE_BACKEND" ]       && VLLM_ARGS+=(--moe-backend "$MOE_BACKEND")
  [ "$LANGUAGE_MODEL_ONLY" = 1 ] && VLLM_ARGS+=(--language-model-only)
  if [ -n "$EXTRA_VLLM_ARGS" ]; then
    # shellcheck disable=SC2206  # word-splitting of EXTRA_VLLM_ARGS is intended
    VLLM_ARGS+=($EXTRA_VLLM_ARGS)
  fi

  DOCKER_ARGS=(
    run -d --name "$CONTAINER_NAME"
    --gpus all --ipc=host
    --restart "$RESTART_POLICY"
    -p "${TEACHER_HOST}:${TEACHER_PORT}:${CONTAINER_PORT}"
    -v "${HF_CACHE}:/root/.cache/huggingface"
  )
  if [ -f "$TOKEN_ENV_FILE" ]; then
    log "passing $TOKEN_ENV_FILE to the container (contents never printed)"
    DOCKER_ARGS+=(--env-file "$TOKEN_ENV_FILE")
  fi

  log "starting: docker ${DOCKER_ARGS[*]} $VLLM_IMAGE ${VLLM_ARGS[*]}"
  docker "${DOCKER_ARGS[@]}" "$VLLM_IMAGE" "${VLLM_ARGS[@]}" >/dev/null
fi

# ---- 5. health check loop ----------------------------------------------------
log "waiting up to ${HEALTH_TIMEOUT_S} s for ${BASE_URL}/v1/models (first start includes the model download)"
WAITED=0
while [ "$WAITED" -lt "$HEALTH_TIMEOUT_S" ]; do
  if MODELS_JSON="$(curl -sf --max-time 5 "${BASE_URL}/v1/models" 2>/dev/null)"; then
    log "teacher ready at ${BASE_URL}/v1 after ${WAITED} s"
    printf '%.600s\n' "$MODELS_JSON"
    break
  fi
  STATE="$(docker container inspect --format '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo gone)"
  if [ "$STATE" != "running" ]; then
    log "container $CONTAINER_NAME is $STATE; last log lines:"
    docker logs --tail 60 "$CONTAINER_NAME" 2>&1 | sed 's/^/    /' || true
    log "common causes (R6, R3): out of memory on unified memory (lower MAX_NUM_SEQS or GPU_MEMORY_UTILIZATION, drop caches), a tag that does not exist, Gated DeltaNet kernels on GB10 (try Fallback A: TEACHER_MODEL_ID=Qwen/Qwen3-30B-A3B-Instruct-2507 MOE_BACKEND= LANGUAGE_MODEL_ONLY=0)"
    exit 1
  fi
  if [ $((WAITED % 120)) -eq 0 ] && [ "$WAITED" -gt 0 ]; then
    log "still loading (${WAITED} s); last container line: $(docker logs --tail 1 "$CONTAINER_NAME" 2>&1 | tail -1 | cut -c1-160)"
  fi
  sleep "$HEALTH_EVERY_S"
  WAITED=$((WAITED + HEALTH_EVERY_S))
done
if [ "$WAITED" -ge "$HEALTH_TIMEOUT_S" ]; then
  log "no answer after ${HEALTH_TIMEOUT_S} s; see: docker logs -f $CONTAINER_NAME"
  exit 1
fi

# ---- 6. one tiny request ----------------------------------------------------
# chat_template_kwargs.enable_thinking=false is the Qwen3.6 card's switch (R3); the
# pipeline's teacher client does not send it yet (see README). max_tokens keeps it cheap.
if [ "$SMOKE_REQUEST" = 1 ]; then
  BODY=$(printf '{"model":"%s","messages":[{"role":"user","content":"Reply with the single word: ready"}],"max_tokens":8,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}' "$TEACHER_MODEL_ID")
  if RESP="$(curl -sf --max-time 120 -H 'Content-Type: application/json' -d "$BODY" "${BASE_URL}/v1/chat/completions" 2>&1)"; then
    log "smoke request ok: $(printf '%s' "$RESP" | head -c 400)"
  else
    log "smoke request failed (the API answers /v1/models but not /v1/chat/completions): $RESP"
    log "if the error names the model, the served id differs from TEACHER_MODEL_ID; read /v1/models above and set BUNDLE_TEACHER_MODEL to it"
    exit 1
  fi
fi

log "done. Stop with: docker stop $CONTAINER_NAME   Logs: docker logs -f $CONTAINER_NAME"
log "next (R3's first task): a 10-minute throughput test at 16 concurrent requests; under 200 tok/s aggregate, use Fallback A. See README.md"
