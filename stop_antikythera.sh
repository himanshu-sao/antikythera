#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}🛑 Stopping Antikythera Full Stack...${NC}"

# 1. Kill known processes by name
echo "Stopping Uvicorn (Backend)..."
pkill -f "uvicorn api.main:app" || echo "No Uvicorn process found."

echo "Stopping Vite (Frontend)..."
pkill -f "vite" || echo "No Vite process found."

echo "Stopping Orchestrator..."
pkill -f "scripts/run_orchestrator.py" || echo "No Orchestrator process found."

# 2. Aggressive cleanup: Kill anything else running on your known ports
# This is the "nuclear option" to ensure no ghost processes remain.
echo "Cleaning up orphaned processes on ports 8006 and 5173..."
for port in 8006 5173; do
    PID=$(lsof -t -i:$port)
    if [ -n "$PID" ]; then
        echo "Killing process $PID on port $port..."
        kill -9 $PID
    else
        echo "Port $port is already clean."
    fi
done

echo -e "\n${GREEN}✅ All processes stopped and ports cleared.${NC}"
