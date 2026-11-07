#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}🛑 Stopping Antikythera Full Stack...${NC}"

# Resolve the repo root so the Vite match is limited to THIS checkout's UI (P5-3 C7).
# A bare `pkill -f vite` also killed unrelated processes (other projects' vite servers,
# editors, any command line containing the word "vite").
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="$ROOT_DIR/ui"

# Escape a path for use inside an extended regex (pgrep/pkill -f take a regex).
regex_escape() {
    printf '%s' "$1" | sed 's/[][\\.^$*+?(){}|]/\\&/g'
}
UI_RE="$(regex_escape "$UI_DIR")"
# npm runs the local vite binary: ui/node_modules/.bin/vite (a symlink) and the real
# ui/node_modules/vite/bin/vite.js are the two command lines a repo-local dev server shows.
VITE_PATTERN="$UI_RE/node_modules/(\\.bin/vite|vite/bin/vite\\.js)( |\$)"

# 1. Kill known processes by name
echo "Stopping Uvicorn (Backend)..."
pkill -f "uvicorn api.main:app" || echo "No Uvicorn process found."

echo "Stopping Vite (Frontend)..."
pkill -f "$VITE_PATTERN" || echo "No Vite process found."

echo "Stopping Orchestrator..."
pkill -f "scripts/run_orchestrator.py" || echo "No Orchestrator process found."

# 2. Aggressive cleanup: Kill anything else running on your known ports
# This is the "nuclear option" to ensure no ghost processes remain.
echo "Cleaning up orphaned processes on ports 18006 and 15173..."
for port in 18006 15173; do
    PID=$(lsof -t -i:$port)
    if [ -n "$PID" ]; then
        echo "Killing process $PID on port $port..."
        kill -9 $PID
    else
        echo "Port $port is already clean."
    fi
done

echo -e "\n${GREEN}✅ All processes stopped and ports cleared.${NC}"
