#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"

# Pick active virtualenv if present, otherwise auto-create backend/.venv
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  PYTHON_BIN="$VIRTUAL_ENV/bin/python"
else
  if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Creating Python virtual environment at backend/.venv ..."
    python3 -m venv "$VENV_DIR"
  fi
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

if ! "$PYTHON_BIN" -c "import fastapi, uvicorn, catboost, shap, vaderSentiment" >/dev/null 2>&1; then
  echo "Installing backend dependencies from backend/requirements.txt ..."
  "$PYTHON_BIN" -m pip install --upgrade pip -q
  "$PYTHON_BIN" -m pip install -r "$BACKEND_DIR/requirements.txt"
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies ..."
  (cd "$FRONTEND_DIR" && npm install)
fi

echo "Starting EventPulse AI Backend on http://localhost:8000 ..."
cd "$BACKEND_DIR"
"$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Starting EventPulse AI Frontend on http://localhost:5173 ..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait
