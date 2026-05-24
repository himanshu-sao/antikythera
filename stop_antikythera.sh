#!/bin/bash

RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${RED}🛑 Stopping Antikythera Full Stack...${NC}"

# Kill Uvicorn (Backend)
pkill -f "uvicorn api.main:app"
# Kill Vite (Frontend)
pkill -f "vite"
# Kill Orchestrator
pkill -f "scripts/run_orchestrator.py"

echo -e "\n${RED}✅ All processes stopped.${NC}"
