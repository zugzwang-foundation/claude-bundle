#!/bin/sh
# Stop the toy teacher started by teacher-mac.sh. Safe to run when nothing is running.
set -u
TEACHER_PORT="${TEACHER_PORT:-8081}"
MODELS_DIR="${TEACHER_MODELS_DIR:-$HOME/Developer/claude-bundle/models/teacher}"

PIDS="$(lsof -tnP -iTCP:"${TEACHER_PORT}" -sTCP:LISTEN 2>/dev/null || true)"
if [ -z "$PIDS" ] && [ -f "$MODELS_DIR/server.pid" ]; then
  PIDS="$(cat "$MODELS_DIR/server.pid")"
fi
if [ -z "$PIDS" ]; then
  echo "no teacher listening on port ${TEACHER_PORT}"
  rm -f "$MODELS_DIR/server.pid"
  exit 0
fi
for p in $PIDS; do
  if kill -0 "$p" 2>/dev/null; then
    kill -TERM "$p" && echo "sent TERM to $p"
  fi
done
i=0
while [ "$i" -lt 20 ]; do
  alive=0
  for p in $PIDS; do kill -0 "$p" 2>/dev/null && alive=1; done
  [ "$alive" -eq 0 ] && break
  i=$((i + 1)); sleep 1
done
for p in $PIDS; do kill -0 "$p" 2>/dev/null && kill -KILL "$p" && echo "killed $p"; done
rm -f "$MODELS_DIR/server.pid"
echo "teacher stopped"
