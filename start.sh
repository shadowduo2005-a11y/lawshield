#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# LawShield – Full-stack startup script
# Starts: AI Service (port 8000) · Backend (port 3000) · Frontend (port 5173)
# ─────────────────────────────────────────────────────────────────────────────

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        🛡️  LawShield – Starting Up           ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Helper: kill background jobs on CTRL-C ────────────────────────────────────
cleanup() {
  echo ""
  echo "🛑  Stopping all services..."
  kill 0 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM

# ── 1. AI Service (Python / FastAPI) ─────────────────────────────────────────
echo "▶  Starting AI Service on http://localhost:8000 ..."
cd "$ROOT/ai_service"
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
AI_PID=$!
deactivate

# ── 2. Backend (Node.js / Express) ───────────────────────────────────────────
echo "▶  Starting Backend on http://localhost:3000 ..."
cd "$ROOT/backend"
node server.js &
BACKEND_PID=$!

# ── 3. Frontend (Vite) ───────────────────────────────────────────────────────
echo "▶  Starting Frontend on http://localhost:5173 ..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅  All services started!"
echo "   • AI Service  → http://localhost:8000"
echo "   • Backend     → http://localhost:3000"
echo "   • Frontend    → http://localhost:5173"
echo ""
echo "Press CTRL+C to stop all services."
echo ""

# Wait for all background jobs
wait
