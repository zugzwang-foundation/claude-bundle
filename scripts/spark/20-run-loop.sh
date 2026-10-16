#!/usr/bin/env bash
# 20-run-loop.sh — one night of Bundle's learning loop on the DGX Spark.
#
# WRITTEN IN BDL-3, NEVER RUN YET; VERIFY ON THE SPARK IN BDL-4.
#
# Order (docs/ARCHITECTURE.md section 5; pipeline/README.md):
#   generate -> validate -> split -> tasks -> baseline -> train -> calibrate -> exam -> export -> scoreboard
# Each stage is `uv run bundle-pipeline <command>` run from pipeline/, with
# BUNDLE_TEACHER_URL set, a per-stage time budget (coreutils `timeout`), its own log
# under runs/<run-id>/, and a line in runs/<run-id>/status.tsv. The first failure
# stops the night (set -e, and an explicit exit with the stage's code).
#
# Resumable, as R6 asks: `generate` skips people already on disk, and the run id and
# seed come from the LOCAL date, so a restart in the same night (systemd
# Restart=on-failure, or a reboot after a power-off) continues the same run.
# Never asks for input. No secrets: the teacher is ungated (R3, R6).
#
# Sources (checked 16 Oct 2026): docs/research/dgx-spark.md (R6) for the torch
# check, resumability, nvidia-smi monitoring and systemd; docs/research/
# teacher-and-data.md (R3) for the teacher id and the 16-concurrent sizing;
# pipeline/src/bundle_pipeline/cli.py for every flag used below.

set -euo pipefail

# ---- parameters (override from the environment or ~/.config/bundle/env) ------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${BUNDLE_REPO_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
PIPELINE_DIR="${BUNDLE_PIPELINE_DIR:-$REPO_DIR/pipeline}"
RUNS_DIR="${BUNDLE_RUNS_DIR:-$REPO_DIR/runs}"      # logs; a .gitignore with "*" is written there

# The night. Local date on purpose (see header). CLAUDE.md's UTC rule is kept for
# every timestamp written to the logs.
NIGHT="${NIGHT:-$(date +%Y-%m-%d)}"
RUN_ID="${RUN_ID:-${NIGHT}-spark-v0}"                # "v0": release numbering is BDL-4's (README)
SEED="${SEED:-$(date +%Y%m%d)}"                      # person ids are p<seed>-<index>; a new seed per night means new people

# Teacher (D9: one OpenAI-compatible URL, the same client as on the Mac).
export BUNDLE_TEACHER_URL="${BUNDLE_TEACHER_URL:-http://127.0.0.1:8081/v1}"
export BUNDLE_TEACHER_MODEL="${BUNDLE_TEACHER_MODEL:-nvidia/Qwen3.6-35B-A3B-NVFP4}"   # must equal the id in /v1/models
export BUNDLE_TEACHER_TIMEOUT="${BUNDLE_TEACHER_TIMEOUT:-300}"                       # seconds per request; 180 on the Mac
# Data root: config.py reads BUNDLE_DATA_ROOT first and BUNDLE_DATA_DIR as the older
# spelling; the CLI's --data-root wins over both (checked 16 Oct 2026). Gitignored (data/).
export BUNDLE_DATA_ROOT="${BUNDLE_DATA_ROOT:-${BUNDLE_DATA_DIR:-$PIPELINE_DIR/data}}"
BUNDLE_DATA_DIR="$BUNDLE_DATA_ROOT"
START_TEACHER="${START_TEACHER:-1}"                  # run 10-serve-teacher.sh first (idempotent)
STOP_TEACHER_AFTER_GENERATE="${STOP_TEACHER_AFTER_GENERATE:-0}"   # free unified memory before training
TEACHER_CONTAINER="${CONTAINER_NAME:-bundle-teacher}"

# Generation. R3's whole budget is 2,000 people x 60 chats, about 15M tokens: 10 hours at
# 400 tok/s aggregate or 42 at 100, so it spans nights. Start small.
PEOPLE="${PEOPLE:-200}"
CHATS_PER_PERSON="${CHATS_PER_PERSON:-60}"
WORKERS="${WORKERS:-16}"                             # R3's throughput test uses 16 concurrent; R6 says measure 16/32/64
GEN_TIME_BUDGET_MIN="${GEN_TIME_BUDGET_MIN:-360}"    # generate stops starting people after this
GEN_GRACE_MIN="${GEN_GRACE_MIN:-10}"                 # and abandons people still in flight after this much more

# Student. The CLI's --device offers auto|cpu|mps today; auto resolves to CPU on
# Linux (encoder.resolve_device, checked 16 Oct 2026). Set DEVICE=cuda once BDL-4
# adds it to the pipeline; until then training runs on the Grace CPU.
DEVICE="${DEVICE:-auto}"
EPOCHS="${EPOCHS:-1}"
BATCH_SIZE="${BATCH_SIZE:-32}"
RUN_BASELINE="${RUN_BASELINE:-1}"
SPLIT_FORCE="${SPLIT_FORCE:-0}"                      # 1 lets the sealed exam change: only for a new major version (R3, D7)
UV_SYNC="${UV_SYNC:-0}"                              # 1 runs `uv sync --frozen` first

# Per-stage budgets in minutes. The worst case is their sum; printed at the start.
T_GENERATE="${T_GENERATE:-$((GEN_TIME_BUDGET_MIN + GEN_GRACE_MIN + 15))}"
T_VALIDATE="${T_VALIDATE:-30}"
T_SPLIT="${T_SPLIT:-10}"
T_TASKS="${T_TASKS:-30}"
T_BASELINE="${T_BASELINE:-60}"
T_TRAIN="${T_TRAIN:-180}"
T_CALIBRATE="${T_CALIBRATE:-60}"
T_EXAM="${T_EXAM:-90}"
T_EXPORT="${T_EXPORT:-30}"
T_SCOREBOARD="${T_SCOREBOARD:-5}"

# ---- helpers -----------------------------------------------------------------
RUN_DIR="$RUNS_DIR/$RUN_ID"
STATUS="$RUN_DIR/status.tsv"
log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
# NOT VERIFIED on DGX OS: coreutils `timeout`; the loop runs without budgets if it is missing.
TIMEOUT_BIN="$(command -v timeout || true)"
MONITOR_PID=""
cleanup() {
  local rc=$?
  [ -n "$MONITOR_PID" ] && kill "$MONITOR_PID" 2>/dev/null || true
  log "loop ended with exit $rc; status: $STATUS"
}
trap cleanup EXIT

# run_stage NN name budget_min command...
run_stage() {
  local nn="$1" name="$2" tmin="$3"; shift 3
  local logf="$RUN_DIR/${nn}-${name}.log" start end rc t0
  start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; t0=$SECONDS
  log "stage $nn $name (budget ${tmin} min): $*"
  set +e
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" --kill-after=60 "${tmin}m" "$@" 2>&1 | tee "$logf"
  else
    "$@" 2>&1 | tee "$logf"
  fi
  rc=${PIPESTATUS[0]}
  set -e
  end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$nn" "$name" "$start" "$end" "$rc" "$((SECONDS - t0))" >> "$STATUS"
  if [ "$rc" -ne 0 ]; then
    [ "$rc" -eq 124 ] && log "stage $name hit its ${tmin}-minute budget (timeout exit 124)"
    if [ "$name" = split ] && [ "$rc" -eq 2 ]; then
      log "split refused to change the sealed exam (exit 2). New people change the hash ranks; whether the exam is fixed across nights or re-split per major version is R3's open question (ARCHITECTURE section 6). Not guessing: stopping. SPLIT_FORCE=1 only for a new major version."
    fi
    if [ "$name" = generate ] && [ "$rc" -eq 2 ]; then
      log "generate could not reach the teacher at $BUNDLE_TEACHER_URL (exit 2); see 10-serve-teacher.sh"
    fi
    log "stage $name failed with exit $rc; the first failure stops the night. Last lines of $logf:"
    tail -20 "$logf" | sed 's/^/    /'
    exit "$rc"
  fi
  log "stage $name ok in $((SECONDS - t0)) s"
}

# ---- 0. run directory and record ---------------------------------------------
mkdir -p "$RUN_DIR"
[ -f "$RUNS_DIR/.gitignore" ] || printf '*\n' > "$RUNS_DIR/.gitignore"
[ -f "$STATUS" ] || printf 'stage\tname\tstart_utc\tend_utc\texit\tseconds\n' > "$STATUS"
{
  printf 'date_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'run_id\t%s\nnight_local\t%s\nseed\t%s\n' "$RUN_ID" "$NIGHT" "$SEED"
  printf 'repo\t%s\ngit\t%s\n' "$REPO_DIR" "$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  printf 'kernel\t%s\ndriver\t%s\n' "$(uname -r)" "$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || echo unknown)"
  printf 'teacher_url\t%s\nteacher_model\t%s\n' "$BUNDLE_TEACHER_URL" "$BUNDLE_TEACHER_MODEL"
  printf 'people\t%s\nchats_per_person\t%s\nworkers\t%s\ngen_budget_min\t%s\ngen_grace_min\t%s\n' "$PEOPLE" "$CHATS_PER_PERSON" "$WORKERS" "$GEN_TIME_BUDGET_MIN" "$GEN_GRACE_MIN"
  printf 'device\t%s\nepochs\t%s\nbatch_size\t%s\nsplit_force\t%s\n' "$DEVICE" "$EPOCHS" "$BATCH_SIZE" "$SPLIT_FORCE"
  printf 'data_dir\t%s\n' "$BUNDLE_DATA_DIR"
} >> "$RUN_DIR/env.txt"
log "run $RUN_ID; logs in $RUN_DIR; parameters in env.txt"
log "worst case $((T_GENERATE + T_VALIDATE + T_SPLIT + T_TASKS + T_BASELINE + T_TRAIN + T_CALIBRATE + T_EXAM + T_EXPORT + T_SCOREBOARD)) min if every stage uses its whole budget"

# ---- 1. preconditions --------------------------------------------------------
command -v uv >/dev/null 2>&1 || { log "uv not found on PATH ($PATH); R6 step 5"; exit 1; }
[ -f "$PIPELINE_DIR/pyproject.toml" ] || { log "no pipeline at $PIPELINE_DIR"; exit 1; }
cd "$PIPELINE_DIR"
if [ "$UV_SYNC" = 1 ]; then
  log "uv sync --frozen"
  uv sync --frozen 2>&1 | tee "$RUN_DIR/00-uv-sync.log"
fi
# R6 step 6: a +cpu torch means the cu130 index is missing; stop, do not train on it unknowingly.
# `|| true`: under set -e a failing probe (no torch yet) would otherwise end the script silently.
TORCH_LINE="$(uv run python -c 'import torch; print(torch.__version__, torch.cuda.is_available())' 2>&1 | tail -1 || true)"
log "torch: $TORCH_LINE"
case "$TORCH_LINE" in
  *"+cpu"*) log "torch is a CPU-only build: fix pipeline/pyproject.toml's pytorch-cu130 index first (R6 point 4, step 6)"; exit 1 ;;
  *"+cu130 True"*) : ;;
  *) log "warning: torch is not 2.14.1+cu130 with CUDA available; continuing, but check 00-check.sh" ;;
esac
if ! command grep -q '"cuda"' "$PIPELINE_DIR/src/bundle_pipeline/encoder.py" 2>/dev/null; then
  log "warning: the pipeline's --device does not know cuda yet; DEVICE=$DEVICE means CPU on this box (README, pipeline change 1)"
fi

# Temperature, power and clocks once a minute (R6 step 10), in the background.
if command -v nvidia-smi >/dev/null 2>&1; then
  (
    while true; do
      { printf '### %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"; nvidia-smi -q -d TEMPERATURE,POWER,CLOCK 2>/dev/null | command grep -E "GPU Current Temp|Power Draw|Graphics *:|SM *:" | head -6; } >> "$RUN_DIR/nvidia-smi.log" 2>/dev/null || true
      sleep 60
    done
  ) &
  MONITOR_PID=$!
fi

# ---- 2. teacher --------------------------------------------------------------
if [ "$START_TEACHER" = 1 ]; then
  log "starting or confirming the teacher (10-serve-teacher.sh; TEACHER_PORT must match BUNDLE_TEACHER_URL)"
  if ! "$SCRIPT_DIR/10-serve-teacher.sh" 2>&1 | tee "$RUN_DIR/00-teacher.log"; then
    log "10-serve-teacher.sh failed; see $RUN_DIR/00-teacher.log. Stopping"; exit 1
  fi
fi
if ! MODELS="$(curl -sf --max-time 10 "${BUNDLE_TEACHER_URL}/models" 2>&1)"; then
  log "teacher not answering at ${BUNDLE_TEACHER_URL}/models; stopping"; exit 1
fi
if ! printf '%s' "$MODELS" | command grep -q "\"$BUNDLE_TEACHER_MODEL\""; then
  log "warning: /v1/models does not list \"$BUNDLE_TEACHER_MODEL\"; requests may be refused. Served: $(printf '%s' "$MODELS" | head -c 300)"
fi

# ---- 3. the ten stages -------------------------------------------------------
run_stage 01 generate "$T_GENERATE" uv run bundle-pipeline generate \
  --people "$PEOPLE" --chats-per-person "$CHATS_PER_PERSON" --seed "$SEED" --workers "$WORKERS" \
  --time-budget-min "$GEN_TIME_BUDGET_MIN" --grace-min "$GEN_GRACE_MIN" \
  --teacher-url "$BUNDLE_TEACHER_URL" --model "$BUNDLE_TEACHER_MODEL"

if [ "$STOP_TEACHER_AFTER_GENERATE" = 1 ]; then
  log "stopping the teacher container $TEACHER_CONTAINER to free unified memory"
  docker stop "$TEACHER_CONTAINER" >/dev/null 2>&1 || log "warning: could not stop $TEACHER_CONTAINER"
fi

run_stage 02 validate "$T_VALIDATE" uv run bundle-pipeline validate --seed "$SEED"

SPLIT_ARGS=()
[ "$SPLIT_FORCE" = 1 ] && SPLIT_ARGS+=(--force)
if [ -f "$BUNDLE_DATA_DIR/splits/exam.sha256" ] && [ "$SPLIT_FORCE" != 1 ]; then
  log "note: a sealed exam exists ($BUNDLE_DATA_DIR/splits/exam.sha256); split will refuse (exit 2) if tonight's people would change it"
fi
run_stage 03 split "$T_SPLIT" uv run bundle-pipeline split --seed "$SEED" ${SPLIT_ARGS[@]+"${SPLIT_ARGS[@]}"}

run_stage 04 tasks "$T_TASKS" uv run bundle-pipeline tasks --seed "$SEED"

if [ "$RUN_BASELINE" = 1 ]; then
  run_stage 05 baseline "$T_BASELINE" uv run bundle-pipeline baseline --split practice --device "$DEVICE" --seed "$SEED"
else
  log "stage 05 baseline skipped (RUN_BASELINE=$RUN_BASELINE)"
fi

STUDENT_DIR="$BUNDLE_DATA_DIR/models/student-$RUN_ID"
run_stage 06 train "$T_TRAIN" uv run bundle-pipeline train \
  --epochs "$EPOCHS" --batch-size "$BATCH_SIZE" --device "$DEVICE" --seed "$SEED" --out "$STUDENT_DIR"

# --no-web: the Spark never writes web/src/sorter/calibration.json; shipping is the
# Mac's decision under D7 after the exam.
run_stage 07 calibrate "$T_CALIBRATE" uv run bundle-pipeline calibrate \
  --model "$STUDENT_DIR" --device "$DEVICE" --seed "$SEED" --out "$STUDENT_DIR/calibration.json" --no-web

run_stage 08 exam "$T_EXAM" uv run bundle-pipeline exam \
  --model "$STUDENT_DIR" --calibration "$STUDENT_DIR/calibration.json" --device "$DEVICE" --seed "$SEED" --run-id "$RUN_ID"

run_stage 09 export "$T_EXPORT" uv run bundle-pipeline export \
  --model "$STUDENT_DIR" --student-id "student-$RUN_ID" --run-id "$RUN_ID" --seed "$SEED" --out "${STUDENT_DIR}-onnx"

run_stage 10 scoreboard "$T_SCOREBOARD" uv run bundle-pipeline scoreboard \
  --source "$BUNDLE_DATA_DIR/runs/exam-${RUN_ID}.json" --run-id "$RUN_ID" --seed "$SEED" \
  --notes "DGX Spark nightly via scripts/spark (first written in BDL-3)" \
  --notes "teacher $BUNDLE_TEACHER_MODEL over vLLM at $BUNDLE_TEACHER_URL" \
  --notes "seed $SEED, people requested $PEOPLE x $CHATS_PER_PERSON chats, workers $WORKERS, device $DEVICE"

# ---- 4. summary --------------------------------------------------------------
log "night complete. Stages:"
column -t -s $'\t' "$STATUS" 2>/dev/null || cat "$STATUS"
BOARD="$REPO_DIR/scoreboard/runs/${RUN_ID}.json"
if [ -f "$BOARD" ]; then
  log "scoreboard run: $BOARD (ships only if it beats the last release, D7; the Mac decides)"
else
  log "warning: expected $BOARD; check $RUN_DIR/10-scoreboard.log"
fi
log "student: $STUDENT_DIR   export: ${STUDENT_DIR}-onnx   exam metrics: $BUNDLE_DATA_DIR/runs/exam-${RUN_ID}.json"
log "rsync the data to the Mac (R6 step 13; ssh.md). The data is the product."
