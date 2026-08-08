#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT/backend"
source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > "$ROOT/backend/backend.log" 2>&1 &
echo "Backend started on http://localhost:8000 (PID $!)"

cd "$ROOT/frontend"
nohup npm run dev > "$ROOT/frontend/frontend.log" 2>&1 &
echo "Frontend started on http://localhost:5173 (PID $!)"

echo ""
echo "Logs:"
echo "  backend:  $ROOT/backend/backend.log"
echo "  frontend: $ROOT/frontend/frontend.log"
