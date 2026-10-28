#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${KOLHOZ_BACKEND_PORT:-8001}"
FRONTEND_PORT="${KOLHOZ_FRONTEND_PORT:-5173}"
export KOLHOZ_BACKEND_PORT="$BACKEND_PORT"
python3 - "$BACKEND_PORT" "$FRONTEND_PORT" <<'PY'
import socket, sys
for port in map(int, sys.argv[1:]):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'Порт {port} занят. Выберите свободные порты: KOLHOZ_BACKEND_PORT=8011 KOLHOZ_FRONTEND_PORT=5180 ./start.sh')
PY
if [ ! -d "$PROJECT_DIR/backend/venv" ]; then
  python3 -m venv "$PROJECT_DIR/backend/venv"
  "$PROJECT_DIR/backend/venv/bin/pip" install -r "$PROJECT_DIR/backend/requirements.txt"
fi
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
  (cd "$PROJECT_DIR/frontend" && npm ci)
fi
BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
  if [ -n "$BACKEND_PID" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [ -n "$FRONTEND_PID" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM
(cd "$PROJECT_DIR/backend" && exec venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT") &
BACKEND_PID=$!
(cd "$PROJECT_DIR/frontend" && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort) &
FRONTEND_PID=$!
printf '\nРегул: http://localhost:%s\nAPI: http://localhost:%s/docs\nДля остановки нажмите Ctrl+C.\n\n' "$FRONTEND_PORT" "$BACKEND_PORT"
wait -n "$BACKEND_PID" "$FRONTEND_PID"
