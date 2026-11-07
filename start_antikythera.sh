#!/bin/bash

# --- Configuration ---
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$ROOT_DIR/venv"
PYTHON_EXE="$VENV_PATH/bin/python3"
UI_DIR="$ROOT_DIR/ui"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Relative paths below (logs, scripts/, api.main) assume the repo root.
cd "$ROOT_DIR" || exit 1

# The project .env is sourced below and must exist. Check before anything is stopped or
# sourced (P5-3 C-check), so a missing file gives a clear message instead of a shell error.
if [ ! -f "$ROOT_DIR/.env" ]; then
  echo -e "${RED}Error: $ROOT_DIR/.env not found.${NC}"
  echo "Create it from the template: cp .env.example .env  (then set PORT and VITE_API_URL)."
  exit 1
fi

# Load env vars from user home first (if present), then from project .env (project overrides)
if [ -f "$HOME/.antikythera/.env" ]; then
  echo -e "${BLUE}Loading user env from $HOME/.antikythera/.env${NC}"
  set -a
  source "$HOME/.antikythera/.env"
  set +a
fi
# Extract VITE_API_URL from .env (project file overrides any previous value)
VITE_API_URL=$(grep '^VITE_API_URL=' "$ROOT_DIR/.env" | cut -d '=' -f2)
if [ -z "$VITE_API_URL" ]; then
  # Fallback to env var loaded earlier (user env)
  VITE_API_URL=${VITE_API_URL:-$VITE_API_URL}
  if [ -z "$VITE_API_URL" ]; then
    echo -e "${RED}Error: VITE_API_URL not set${NC}"
    exit 1
  fi
fi
echo -e "${BLUE}🚀 Preparing Antikythera environment...${NC}"

# 0. Pre-flight check: Ensure no old processes are running
echo "Running cleanup to prevent ghost processes..."
"$ROOT_DIR/stop_antikythera.sh"

# Log rotation (O6): keep one previous generation per log. A log above LOG_MAX_BYTES is
# moved to <name>.1 (replacing the previous .1), then appended to on this start.
LOG_MAX_BYTES=$((10 * 1024 * 1024))
rotate_log() {
  local log_file="$1"
  [ -f "$log_file" ] || return 0
  local size
  size=$(wc -c < "$log_file" | tr -d ' ')
  if [ "$size" -gt "$LOG_MAX_BYTES" ]; then
    mv -f "$log_file" "$log_file.1"
    echo "Rotated $log_file (${size} bytes) to $log_file.1"
  fi
}
rotate_log "$ROOT_DIR/backend.log"
rotate_log "$UI_DIR/ui.log"
rotate_log "$ROOT_DIR/orchestrator.log"

echo -e "\n${BLUE}🚀 Starting Antikythera Full Stack...${NC}"

# 1. Start Backend API
echo -e "Loading port from .env..."
# Extract PORT value using grep and cut
PORT=$(grep '^PORT=' "$ROOT_DIR/.env" | cut -d '=' -f2)
set -a
source "$ROOT_DIR/.env"
# Load API keys from .ai_env and export them
if [ -f "$HOME/.antikythera/.ai_env" ]; then
  set -a
  source "$HOME/.antikythera/.ai_env"
  set +a
fi
set +a
if [ -z "$PORT" ]; then
  echo -e "${RED}Error: PORT not found in .env file${NC}"
  exit 1
fi

echo -e "Starting Backend API on port $PORT..."
# Use PYTHONPATH to ensure the 'api' package is discoverable
PYTHONPATH=$ROOT_DIR $PYTHON_EXE -m uvicorn api.main:app --host 0.0.0.0 --port $PORT >> backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID) - logs: backend.log${NC}"

# 2. Start Frontend UI
echo -e "Starting Frontend UI..."
cd "$UI_DIR" || exit 1
npm run dev >> ui.log 2>&1 &
UI_PID=$!
cd "$ROOT_DIR" || exit 1
echo -e "${GREEN}✅ UI started (PID: $UI_PID) - logs: ui.log${NC}"

# 3. Start Orchestrator
echo -e "Starting Orchestrator Agent loop..."
$PYTHON_EXE scripts/run_orchestrator.py >> orchestrator.log 2>&1 &
ORCH_PID=$!
echo -e "${GREEN}✅ Orchestrator started (PID: $ORCH_PID) - logs: orchestrator.log${NC}"

echo -e "\n${BLUE}✨ Antikythera is now running!${NC}"
# The backend is served on PORT (from .env); VITE_API_URL is the URL the UI calls, which
# should point at the same place. Warn when they disagree instead of printing a wrong URL.
echo -e "Backend: http://localhost:$PORT"
if [ -n "$VITE_API_URL" ] && [ "$VITE_API_URL" != "http://localhost:$PORT" ]; then
  echo -e "${RED}Warning: VITE_API_URL=$VITE_API_URL does not match PORT=$PORT. Set VITE_API_URL=http://localhost:$PORT in .env.${NC}"
fi
echo -e "Frontend: http://localhost:5173"
echo -e "Use ./stop_antikythera.sh to shut down everything."
