#!/bin/bash

# --- Configuration ---
ROOT_DIR="$(pwd)"
VENV_PATH="$ROOT_DIR/venv"
PYTHON_EXE="$VENV_PATH/bin/python3"
UI_DIR="$ROOT_DIR/ui"

# Extract VITE_API_URL from .env
VITE_API_URL=$(grep '^VITE_API_URL=' .env | cut -d '=' -f2)
if [ -z "$VITE_API_URL" ]; then
  echo -e "${RED}Error: VITE_API_URL not found in .env file${NC}"
  exit 1
fi
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Preparing Antikythera environment...${NC}"

# 0. Pre-flight check: Ensure no old processes are running
echo "Running cleanup to prevent ghost processes..."
./stop_antikythera.sh

echo -e "\n${BLUE}🚀 Starting Antikythera Full Stack...${NC}"

# 1. Start Backend API
echo -e "Loading port from .env..."
# Extract PORT value using grep and cut
PORT=$(grep '^PORT=' .env | cut -d '=' -f2)
if [ -z "$PORT" ]; then
  echo -e "${RED}Error: PORT not found in .env file${NC}"
  exit 1
fi

echo -e "Starting Backend API on port $PORT..."
# Use PYTHONPATH to ensure the 'api' package is discoverable
PYTHONPATH=$ROOT_DIR $PYTHON_EXE -m uvicorn api.main:app --host 0.0.0.0 --port $PORT > backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID) - logs: backend.log${NC}"

# 2. Start Frontend UI
echo -e "Starting Frontend UI..."
cd $UI_DIR
npm run dev > ui.log 2>&1 &
UI_PID=$!
cd $ROOT_DIR
echo -e "${GREEN}✅ UI started (PID: $UI_PID) - logs: ui.log${NC}"

# 3. Start Orchestrator
echo -e "Starting Orchestrator Agent loop..."
$PYTHON_EXE scripts/run_orchestrator.py > orchestrator.log 2>&1 &
ORCH_PID=$!
echo -e "${GREEN}✅ Orchestrator started (PID: $ORCH_PID) - logs: orchestrator.log${NC}"

echo -e "\n${BLUE}✨ Antikythera is now running!${NC}"
echo -e "Backend: $VITE_API_URL"
echo -e "Frontend: http://localhost:5173"
echo -e "Use ./stop_antikythera.sh to shut down everything."
