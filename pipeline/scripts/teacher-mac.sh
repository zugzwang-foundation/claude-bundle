#!/bin/sh
# Start the toy teacher on this Mac: llama-server (llama.cpp, Homebrew) serving
# Qwen3-4B-Instruct-2507 Q4_K_M as an OpenAI-compatible API at
# http://127.0.0.1:8081/v1 . Idempotent: exits 0 if the port already answers.
# See pipeline/docs/toy-teacher.md for the model's provenance and measurements.
#
# Environment overrides:
#   TEACHER_MODEL   path to the .gguf (default below)
#   TEACHER_PORT    default 8081
#   TEACHER_CTX     total context shared by the slots (default 16384 = 4096 per slot)
#   TEACHER_SLOTS   parallel slots (default 4)
#   TEACHER_THREADS CPU threads for generation (default 6; the Mac has 10 cores)
#   TEACHER_LOG     server log file
set -eu

MODELS_DIR="${TEACHER_MODELS_DIR:-$HOME/Developer/claude-bundle/models/teacher}"
TEACHER_MODEL="${TEACHER_MODEL:-$MODELS_DIR/Qwen3-4B-Instruct-2507-Q4_K_M.gguf}"
TEACHER_PORT="${TEACHER_PORT:-8081}"
TEACHER_CTX="${TEACHER_CTX:-16384}"
TEACHER_SLOTS="${TEACHER_SLOTS:-4}"
TEACHER_THREADS="${TEACHER_THREADS:-6}"
TEACHER_LOG="${TEACHER_LOG:-$MODELS_DIR/server.log}"
LLAMA_SERVER="${LLAMA_SERVER:-/opt/homebrew/bin/llama-server}"
BASE_URL="http://127.0.0.1:${TEACHER_PORT}"

if curl -sf --max-time 2 "${BASE_URL}/v1/models" >/dev/null 2>&1; then
  echo "teacher already answering at ${BASE_URL}/v1 (pid $(lsof -tnP -iTCP:"${TEACHER_PORT}" -sTCP:LISTEN | head -1))"
  exit 0
fi

if [ ! -x "$LLAMA_SERVER" ]; then
  echo "llama-server not found at $LLAMA_SERVER (brew install llama.cpp)" >&2
  exit 1
fi
if [ ! -f "$TEACHER_MODEL" ]; then
  echo "model file missing: $TEACHER_MODEL" >&2
  echo "download: curl -L -C - -o \"$TEACHER_MODEL\" https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf" >&2
  exit 1
fi

mkdir -p "$(dirname "$TEACHER_LOG")"
nohup "$LLAMA_SERVER" -m "$TEACHER_MODEL" \
  --host 127.0.0.1 --port "$TEACHER_PORT" \
  -c "$TEACHER_CTX" -np "$TEACHER_SLOTS" --jinja -t "$TEACHER_THREADS" \
  > "$TEACHER_LOG" 2>&1 &
PID=$!
echo "$PID" > "$MODELS_DIR/server.pid"
echo "started llama-server pid $PID, log $TEACHER_LOG"

# Wait up to 180 s for the API to answer.
i=0
while [ "$i" -lt 180 ]; do
  if curl -sf --max-time 2 "${BASE_URL}/v1/models" >/dev/null 2>&1; then
    echo "teacher ready at ${BASE_URL}/v1 after ${i} s"
    exit 0
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "llama-server exited early; last log lines:" >&2
    tail -20 "$TEACHER_LOG" >&2
    exit 1
  fi
  i=$((i + 1))
  sleep 1
done
echo "teacher did not answer within 180 s; see $TEACHER_LOG" >&2
exit 1
