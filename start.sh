#!/usr/bin/env bash
# ── Smart Recipe Substitute — start beide servers ────────────────────────────
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# Kleur-helpers
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

cleanup() {
  echo -e "\n${YELLOW}Servers stoppen…${NC}"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  echo -e "${GREEN}Klaar.${NC}"
}
trap cleanup INT TERM

# ── Backend ──────────────────────────────────────────────────────────────────
echo -e "${GREEN}▶ Backend starten (FastAPI op :8000)…${NC}"

if [ ! -d "$BACKEND/.venv" ]; then
  echo "  Virtualenv aanmaken…"
  python3 -m venv "$BACKEND/.venv"
fi

source "$BACKEND/.venv/bin/activate"
pip install -q -r "$BACKEND/requirements.txt"

uvicorn main:app --reload --app-dir "$BACKEND" --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# ── Frontend ─────────────────────────────────────────────────────────────────
echo -e "${GREEN}▶ Frontend starten (React/Vite op :5173)…${NC}"

if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "  Dependencies installeren…"
  npm --prefix "$FRONTEND" install
fi

npm --prefix "$FRONTEND" run dev &
FRONTEND_PID=$!

# ── Klaar ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${GREEN}✔ Backend:  http://localhost:8000${NC}"
echo -e "  ${GREEN}✔ Frontend: http://localhost:5173${NC}"
echo -e "  ${YELLOW}Druk op Ctrl+C om beide servers te stoppen.${NC}"
echo ""

wait "$BACKEND_PID" "$FRONTEND_PID"
