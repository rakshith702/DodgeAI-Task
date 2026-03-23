#!/bin/bash
# start.sh — runs backend + frontend together for local development

set -e
ROOT=$(cd "$(dirname "$0")" && pwd)

echo "=== SAP O2C Graph Explorer ==="

# Check for .env
if [ ! -f "$ROOT/backend/.env" ]; then
  echo "ERROR: backend/.env not found."
  echo "Run: cp backend/.env.example backend/.env  then add your ANTHROPIC_API_KEY"
  exit 1
fi

# Check if DB exists, if not run ingest
if [ ! -f "$ROOT/backend/o2c.db" ]; then
  echo "[1/3] Building database and graph (first run)..."
  cd "$ROOT/backend"
  python3 ingest.py
else
  echo "[1/3] Database already exists, skipping ingest."
fi

# Start backend
echo "[2/3] Starting FastAPI backend on http://localhost:8000 ..."
cd "$ROOT/backend"
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "[3/3] Starting React frontend on http://localhost:3000 ..."
cd "$ROOT/frontend"
npm start &
FRONTEND_PID=$!

echo ""
echo "App running at http://localhost:3000"
echo "API docs at  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" INT TERM
wait
