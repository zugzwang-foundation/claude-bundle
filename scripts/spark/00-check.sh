#!/usr/bin/env bash
# 00-check.sh — is this DGX Spark ready for Bundle's loop?
#
# WRITTEN IN BDL-3, NEVER RUN YET; VERIFY ON THE SPARK IN BDL-4.
#
# Read-only, except that CHECK_PULL=1 lets the GPU container smoke test pull the
# vLLM image (a large download). Never asks for input. Prints PASS / WARN / FAIL
# per check and exits 1 if anything FAILed.
#
# Sources: docs/research/dgx-spark.md (R6), "For Claude Code (commands, in order)"
# steps 1, 3, 6 and 8, plus its Findings on DGX OS 7.5.0 (kernel 6.17, driver
# 580.159.03, CUDA 13.0.2), compute capability 12.1, and NVIDIA's known issue that
# nvidia-smi shows "Memory-Usage: Not Supported" on this iGPU (checked 16 Oct 2026).
# Anything R6 did not document is marked NOT VERIFIED below.

set -uo pipefail   # deliberately no -e: every check runs; the summary decides.

# ---- parameters (override from the environment) ------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${BUNDLE_REPO_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
PIPELINE_DIR="${BUNDLE_PIPELINE_DIR:-$REPO_DIR/pipeline}"
VLLM_IMAGE="${VLLM_IMAGE:-nvcr.io/nvidia/vllm:26.04-py3}"   # R3's tag; R6 names 26.05-py3. Decide in BDL-4.
EXPECTED_TORCH="${EXPECTED_TORCH:-2.14.1+cu130}"             # R6 step 6
EXPECTED_CAPABILITY="${EXPECTED_CAPABILITY:-(12, 1)}"         # R6: GB10 is sm_121
EXPECTED_KERNEL_PREFIX="${EXPECTED_KERNEL_PREFIX:-6.17}"      # R6: DGX OS 7.5.0
EXPECTED_DRIVER="${EXPECTED_DRIVER:-580.159.03}"              # R6: DGX OS 7.5.0
MIN_FREE_GB="${MIN_FREE_GB:-150}"       # teacher checkpoints run 20-70 GB each (R6)
MIN_TOTAL_MEM_GB="${MIN_TOTAL_MEM_GB:-100}"  # a 64 GB Spark changes the plan (R6 point 7)
TEACHER_PORT="${TEACHER_PORT:-8081}"
CHECK_PULL="${CHECK_PULL:-0}"           # 1 = allow docker to pull VLLM_IMAGE for the smoke test
CHECK_TORCH="${CHECK_TORCH:-1}"         # 0 = skip the uv/torch check (slow before the first uv sync)

# ---- helpers -----------------------------------------------------------------
PASS=0; WARN=0; FAIL=0
pass() { PASS=$((PASS + 1)); printf 'PASS  %s\n' "$*"; }
warn() { WARN=$((WARN + 1)); printf 'WARN  %s\n' "$*"; }
fail() { FAIL=$((FAIL + 1)); printf 'FAIL  %s\n' "$*"; }
section() { printf '\n== %s ==\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

printf 'Bundle: DGX Spark readiness check\n'
printf 'date -u: %s\n' "$(date -u)"
printf 'host: %s   user: %s\n' "$(hostname)" "$(id -un)"
printf 'repository: %s\n' "$REPO_DIR"

# ---- 1. OS and kernel (R6 step 1) --------------------------------------------
section "OS and kernel"
if have lsb_release; then
  lsb_release -a 2>/dev/null | sed 's/^/      /'
  pass "lsb_release ran"
else
  warn "lsb_release missing; /etc/os-release follows"
  sed 's/^/      /' /etc/os-release 2>/dev/null || true
fi
KERNEL="$(uname -r)"
printf '      kernel: %s\n' "$KERNEL"
case "$KERNEL" in
  "$EXPECTED_KERNEL_PREFIX"*) pass "kernel $KERNEL matches DGX OS 7.5.0's $EXPECTED_KERNEL_PREFIX (R6)" ;;
  *) warn "kernel $KERNEL is not $EXPECTED_KERNEL_PREFIX.x; newer DGX OS or an unexpected image. Record it in docs/DECISIONS.md (R6 step 1)" ;;
esac
if [ "$(uname -m)" = "aarch64" ]; then
  pass "architecture aarch64 (Grace CPU)"
else
  fail "architecture $(uname -m): this is not a DGX Spark"
fi

# ---- 2. GPU driver (R6 step 1 and known issues) ------------------------------
section "nvidia-smi"
if have nvidia-smi; then
  if nvidia-smi >/tmp/bundle-nvidia-smi.$$ 2>&1; then
    sed 's/^/      /' /tmp/bundle-nvidia-smi.$$
    pass "nvidia-smi ran"
    if command grep -q "Not Supported" /tmp/bundle-nvidia-smi.$$; then
      pass "\"Memory-Usage: Not Supported\" is expected on this iGPU (NVIDIA known issue, R6); not a fault"
    fi
    # Driver and compute capability as fields. NOT VERIFIED: the `compute_cap`
    # query field on DGX OS's nvidia-smi; R6 cites the capability (12.1) from
    # NVIDIA's CUDA GPUs page, not from this command.
    DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 | tr -d ' ')"
    CAP="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -1 | tr -d ' ')"
    printf '      driver: %s   compute capability: %s\n' "${DRIVER:-unknown}" "${CAP:-unknown}"
    if [ "$DRIVER" = "$EXPECTED_DRIVER" ]; then
      pass "driver $DRIVER matches DGX OS 7.5.0 (R6)"
    else
      warn "driver ${DRIVER:-unknown}, R6 recorded $EXPECTED_DRIVER for DGX OS 7.5.0; a newer driver is fine, record it"
    fi
    if [ "$CAP" = "12.1" ]; then
      pass "compute capability 12.1 (sm_121), as R6 states"
    elif [ -n "$CAP" ]; then
      fail "compute capability $CAP is not 12.1: generic Blackwell builds for 12.0 miss GB10 (R6)"
    else
      warn "compute capability not reported by nvidia-smi; check torch.cuda.get_device_capability() below"
    fi
  else
    fail "nvidia-smi failed:"; sed 's/^/      /' /tmp/bundle-nvidia-smi.$$
  fi
  rm -f /tmp/bundle-nvidia-smi.$$
  # Temperature, power and clocks: the three things that go wrong overnight (R6 step 10).
  printf '      --- temperature, power, clocks (nvidia-smi -q) ---\n'
  nvidia-smi -q -d TEMPERATURE,POWER,CLOCK 2>/dev/null | command grep -E "GPU Current Temp|Power Draw|Graphics *:|SM *:|Memory *:" | head -8 | sed 's/^/      /' || true
else
  fail "nvidia-smi not found"
fi

# ---- 3. CUDA toolkit (R6 step 1) ---------------------------------------------
section "CUDA"
NVCC=""
if have nvcc; then NVCC="$(command -v nvcc)";
elif [ -x /usr/local/cuda/bin/nvcc ]; then NVCC=/usr/local/cuda/bin/nvcc;   # NOT VERIFIED: nvcc's path on DGX OS
fi
if [ -n "$NVCC" ]; then
  "$NVCC" --version | tail -2 | sed 's/^/      /'
  pass "nvcc found at $NVCC (R6 recorded CUDA 13.0.2 for DGX OS 7.5.0; newest CUDA arrives via NGC containers, not the base OS)"
else
  warn "nvcc not on PATH or in /usr/local/cuda/bin; the base OS may still carry the driver's CUDA. Containers bring their own (R6)"
fi

# ---- 4. Memory (R6: 128 GB unified) ------------------------------------------
section "memory"
free -g | sed 's/^/      /'
TOTAL_GB="$(free -g | awk '/^Mem:/ {print $2}')"
if [ -n "$TOTAL_GB" ] && [ "$TOTAL_GB" -ge "$MIN_TOTAL_MEM_GB" ]; then
  pass "total memory ${TOTAL_GB} GB (128 GB unified expected)"
else
  fail "total memory ${TOTAL_GB:-unknown} GB: under ${MIN_TOTAL_MEM_GB} GB this is the 64 GB variant and the teacher plan changes (R6 point 7)"
fi
# Unified memory lies to allocators (R6 point 5). Not a check, a reminder.
printf '      note: expect "out of memory" with free RAM; 10-serve-teacher.sh drops caches first (R6)\n'

# ---- 5. Disk (R6 step 1, 13) -------------------------------------------------
section "disk"
df -h / "$HOME" 2>/dev/null | sed 's/^/      /'
FREE_GB="$(df -BG --output=avail "$HOME" 2>/dev/null | tail -1 | tr -dc '0-9')"
if [ -n "$FREE_GB" ] && [ "$FREE_GB" -ge "$MIN_FREE_GB" ]; then
  pass "free space under \$HOME: ${FREE_GB} GB (>= ${MIN_FREE_GB})"
elif [ -n "$FREE_GB" ]; then
  warn "free space under \$HOME: ${FREE_GB} GB (< ${MIN_FREE_GB}); teacher checkpoints run 20-70 GB each and data grows nightly (R6). Back data up off the box"
else
  warn "could not read free space (df --output unsupported?)"
fi

# ---- 6. Docker and the NVIDIA runtime (R6: preinstalled) ---------------------
section "docker"
if have docker; then
  docker --version | sed 's/^/      /'
  if docker info >/dev/null 2>&1; then
    pass "docker daemon reachable as $(id -un)"
    # NOT VERIFIED: that DGX OS registers the runtime under the name "nvidia".
    RUNTIMES="$(docker info --format '{{range $k, $v := .Runtimes}}{{$k}} {{end}}' 2>/dev/null)"
    printf '      runtimes: %s\n' "${RUNTIMES:-unknown}"
    case " $RUNTIMES " in
      *" nvidia "*) pass "NVIDIA container runtime registered" ;;
      *) warn "no runtime named nvidia in docker info; --gpus all may still work (R6 says the runtime is preinstalled)" ;;
    esac
  else
    fail "docker daemon not reachable; is $(id -un) in the docker group? (NVIDIA Sync adds it, R6; or: sudo usermod -aG docker <user>, then log in again)"
  fi
else
  fail "docker not found (R6 says it is preinstalled on DGX OS)"
fi

# ---- 7. GPU container smoke test (R6 step 8) ---------------------------------
section "GPU container smoke test"
if have docker && docker info >/dev/null 2>&1; then
  if docker image inspect "$VLLM_IMAGE" >/dev/null 2>&1; then
    HAVE_IMAGE=1
  else
    HAVE_IMAGE=0
  fi
  if [ "$HAVE_IMAGE" = 1 ] || [ "$CHECK_PULL" = 1 ]; then
    if [ "$HAVE_IMAGE" = 0 ]; then
      printf '      pulling %s (large download; R6 point 8: confirm the tag exists before relying on it)\n' "$VLLM_IMAGE"
      if ! docker pull "$VLLM_IMAGE" >/tmp/bundle-pull.$$ 2>&1; then
        tail -5 /tmp/bundle-pull.$$ | sed 's/^/      /'
        if command grep -qi "unauthorized\|login\|denied" /tmp/bundle-pull.$$; then
          fail "docker pull wants a login: that is an NGC account -> Needs Hrishikesh; fallback is PyPI vLLM 0.30.0 in uv (R6 step 8)"
        else
          fail "docker pull $VLLM_IMAGE failed; wrong tag? R6 lists 25.09-26.09 in NVIDIA's index"
        fi
      fi
      rm -f /tmp/bundle-pull.$$
    fi
    if docker image inspect "$VLLM_IMAGE" >/dev/null 2>&1; then
      if OUT="$(docker run --rm --gpus all "$VLLM_IMAGE" vllm --version 2>&1)"; then
        printf '      %s\n' "$OUT" | tail -3
        pass "GPU container ran: $VLLM_IMAGE vllm --version (R6 step 8)"
      else
        printf '%s\n' "$OUT" | tail -10 | sed 's/^/      /'
        fail "docker run --gpus all $VLLM_IMAGE failed; driver/runtime mismatch? (R6: whether a CUDA 13.4 image runs on the 580 driver is unknown)"
      fi
    fi
  else
    warn "image $VLLM_IMAGE not present; rerun with CHECK_PULL=1 to pull it and run the smoke test"
  fi
else
  warn "skipped: docker unavailable"
fi

# ---- 8. Headless hardening (R6 step 3) ---------------------------------------
section "sleep targets"
ALL_MASKED=1
for t in sleep.target suspend.target hibernate.target hybrid-sleep.target; do
  STATE="$(systemctl is-enabled "$t" 2>/dev/null || true)"
  printf '      %-22s %s\n' "$t" "${STATE:-unknown}"
  [ "$STATE" = "masked" ] || ALL_MASKED=0
done
if [ "$ALL_MASKED" = 1 ]; then
  pass "sleep, suspend, hibernate and hybrid-sleep are masked (R6)"
else
  fail "not all masked. Headless Sparks have suspended after ~20 min (R6). Fix: sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target"
fi
DEFAULT_TARGET="$(systemctl get-default 2>/dev/null || echo unknown)"
printf '      default target: %s\n' "$DEFAULT_TARGET"
[ "$DEFAULT_TARGET" = "multi-user.target" ] && pass "desktop dropped (multi-user.target)" || warn "default target is $DEFAULT_TARGET; optional: sudo systemctl set-default multi-user.target (R6 step 3)"

# ---- 9. tmux (R6 step 3) -----------------------------------------------------
section "tmux"
if have tmux; then pass "tmux $(tmux -V 2>/dev/null)"; else warn "tmux missing: sudo apt install -y tmux (R6)"; fi

# ---- 10. Time zone (for the 01:00 local timer) -------------------------------
section "time zone"
# NOT VERIFIED: `timedatectl show -p Timezone --value` on DGX OS; falls back to date.
TZ_NAME="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
printf '      time zone: %s   local now: %s   UTC now: %s\n' "${TZ_NAME:-$(date +%Z)}" "$(date +%H:%M)" "$(date -u +%H:%M)"
pass "30-nightly.timer's 01:00 is in this zone"

# ---- 11. uv and the CUDA build of torch (R6 steps 5, 6) ----------------------
section "uv and torch"
if ! have uv; then
  fail "uv not found; install from a pinned installer URL (R6 step 5), then uv sync in $PIPELINE_DIR"
elif [ ! -f "$PIPELINE_DIR/pyproject.toml" ]; then
  fail "no pyproject.toml at $PIPELINE_DIR; clone the repository over HTTPS first (R6 step 5)"
else
  pass "uv $(uv --version 2>/dev/null) and $PIPELINE_DIR/pyproject.toml present"
  if command grep -q "pytorch-cu130" "$PIPELINE_DIR/pyproject.toml"; then
    pass "pyproject carries the explicit pytorch-cu130 index (R6 step 6)"
  else
    fail "pyproject has no pytorch-cu130 index block: a plain uv sync installs CPU-only torch on aarch64 (R6 point 4). BDL-4 must add it"
  fi
  if [ "$CHECK_TORCH" = 1 ] && [ -d "$PIPELINE_DIR/.venv" ]; then
    # NOT VERIFIED: `uv run --no-sync` (skip re-resolving) is uv's flag, not in R6; drop it if uv rejects it.
    TORCH_OUT="$(cd "$PIPELINE_DIR" && uv run --no-sync python -c 'import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_capability() if torch.cuda.is_available() else None)' 2>&1 | tail -1)"
    printf '      %s\n' "$TORCH_OUT"
    case "$TORCH_OUT" in
      "$EXPECTED_TORCH True $EXPECTED_CAPABILITY") pass "torch $EXPECTED_TORCH sees the GPU at $EXPECTED_CAPABILITY (R6 step 6)" ;;
      *"+cpu"*) fail "torch is a +cpu build: stop and fix the index (R6 step 6)" ;;
      *" False "*) fail "torch cannot see CUDA; driver, runtime or wheel mismatch" ;;
      *) warn "unexpected torch report; R6 expects '$EXPECTED_TORCH True $EXPECTED_CAPABILITY'" ;;
    esac
    # The pipeline's own device switch (checked 16 Oct 2026): auto -> mps or cpu, never cuda.
    if command grep -q '"cuda"' "$PIPELINE_DIR/src/bundle_pipeline/encoder.py" 2>/dev/null; then
      pass "encoder.py knows cuda"
    else
      warn "encoder.resolve_device knows only mps and cpu: --device auto means CPU on this box until BDL-4 adds cuda (see README)"
    fi
  elif [ "$CHECK_TORCH" = 1 ]; then
    warn "no .venv under $PIPELINE_DIR yet; run uv sync, then rerun this check"
  fi
fi

# ---- 12. Teacher port --------------------------------------------------------
section "teacher port $TEACHER_PORT"
if curl -sf --max-time 2 "http://127.0.0.1:${TEACHER_PORT}/v1/models" >/dev/null 2>&1; then
  pass "something answers /v1/models on 127.0.0.1:${TEACHER_PORT} (a teacher is up)"
else
  pass "port ${TEACHER_PORT} is quiet; 10-serve-teacher.sh will start the teacher"
fi

# ---- summary -----------------------------------------------------------------
section "summary"
printf 'PASS %d   WARN %d   FAIL %d\n' "$PASS" "$WARN" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf 'Not ready: fix the FAIL lines above before 10-serve-teacher.sh and 20-run-loop.sh.\n'
  exit 1
fi
printf 'Ready enough to try 10-serve-teacher.sh. Remember: written in BDL-3, never run yet.\n'
exit 0
