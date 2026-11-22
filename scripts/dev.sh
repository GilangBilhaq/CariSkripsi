#!/usr/bin/env bash
# Menjalankan backend (FastAPI, port 8000) dan frontend (Next.js, port 3000) sekaligus.
# Pemakaian: bash scripts/dev.sh   (Ctrl+C menghentikan keduanya)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -x "$ROOT/backend/.venv/bin/python" ]; then PY="$ROOT/backend/.venv/bin/python"
else PY="$ROOT/backend/.venv/Scripts/python.exe"; fi

export HF_HUB_OFFLINE=1
(cd "$ROOT/backend" && "$PY" -m uvicorn app.main:app --port 8000) &
BACKEND=$!
(cd "$ROOT/frontend" && npm run dev) &
FRONTEND=$!

trap 'kill $BACKEND $FRONTEND 2>/dev/null' EXIT INT TERM
echo "Buka http://localhost:3000 (Ctrl+C untuk berhenti)"
wait
