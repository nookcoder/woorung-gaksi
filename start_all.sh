#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Starting Woorung-Gaksi Services...${NC}"

# Ensure cleanup on exit
cleanup() {
    echo -e "\n${RED}Shutting down services...${NC}"
    # Kill any processes started by this script
    kill -- -$$ 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Function to check and kill ports
check_and_kill_port() {
    PORT=$1
    NAME=$2
    PID=$(lsof -t -i:$PORT)
    if [ -n "$PID" ]; then
        echo -e "${RED}Port $PORT ($NAME) is in use by PID $PID. Killing...${NC}"
        kill -9 $PID 2>/dev/null || true
        sleep 1
    fi
}

echo -e "${BLUE}Checking ports...${NC}"
check_and_kill_port 8000 "PM Agent"
check_and_kill_port 8080 "Core Gateway"

echo -e "${BLUE}[PM Agent] Starting...${NC}"
(
    cd services/pm-agent || exit
    if [ ! -f "uv.lock" ]; then
        echo "Installing Python dependencies..."
        uv sync
    fi
    uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
) &
PM_PID=$!
echo -e "${GREEN}[PM Agent] Started (PID $PM_PID)${NC}"

# Short delay to let PM Agent init
sleep 2

echo -e "${BLUE}[Core Gateway] Starting...${NC}"
(
    cd services/core-gateway || exit
    echo "Downloading Go modules..."
    go mod download
    go run ./cmd/server/main.go
) &
GW_PID=$!
echo -e "${GREEN}[Core Gateway] Started (PID $GW_PID)${NC}"

echo -e "${GREEN}Services running. Press Ctrl+C to stop.${NC}"

# Wait for all processes to exit
wait

echo -e "${RED}A service exited unexpectedly.${NC}"
cleanup
