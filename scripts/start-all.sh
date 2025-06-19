#!/bin/bash

# Start all components of PS Ticket Process Bot
# This script starts the API server, Celery worker, and Celery Beat scheduler

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting PS Ticket Process Bot - All Components${NC}"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Function to check if a process is running
check_process() {
    local process_name=$1
    local port=$2
    
    if [ -n "$port" ]; then
        if lsof -i :$port > /dev/null 2>&1; then
            echo -e "${YELLOW}Warning: Port $port is already in use${NC}"
            return 1
        fi
    fi
    return 0
}

# Function to start a process in the background
start_process() {
    local name=$1
    local script=$2
    local log_file=$3
    
    echo -e "${BLUE}Starting $name...${NC}"
    
    if [ -f "$script" ]; then
        chmod +x "$script"
        nohup "$script" > "$log_file" 2>&1 &
        local pid=$!
        echo "$pid" > "${name,,}.pid"
        echo -e "${GREEN}✓ $name started (PID: $pid)${NC}"
        echo "  Log file: $log_file"
        echo "  PID file: ${name,,}.pid"
    else
        echo -e "${RED}Error: Script not found: $script${NC}"
        return 1
    fi
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Redis
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}Error: Redis is not running. Starting Redis...${NC}"
    brew services start redis
    sleep 2
    if ! redis-cli ping > /dev/null 2>&1; then
        echo -e "${RED}Error: Failed to start Redis${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ Redis is running${NC}"

# Check Python environment
if ! python -c "import app.main" > /dev/null 2>&1; then
    echo -e "${RED}Error: Cannot import app. Please check your Python environment.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python environment is ready${NC}"

# Check configuration files
if [ ! -f "config/search-profiles.yaml" ]; then
    echo -e "${RED}Error: Search profiles configuration not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Configuration files found${NC}"

# Check ports
check_process "API Server" 8000

# Create logs directory
mkdir -p logs

# Start components
echo ""
echo -e "${YELLOW}Starting components...${NC}"

# 1. Start API Server
echo -e "${BLUE}Starting API Server...${NC}"
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > logs/api-server.log 2>&1 &
API_PID=$!
echo "$API_PID" > api-server.pid
echo -e "${GREEN}✓ API Server started (PID: $API_PID)${NC}"
echo "  URL: http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo "  Log file: logs/api-server.log"

# Wait a moment for API server to start
sleep 3

# 2. Start Celery Worker
start_process "Celery Worker" "scripts/start-celery-worker.sh" "logs/celery-worker.log"

# Wait a moment for worker to start
sleep 2

# 3. Start Celery Beat
start_process "Celery Beat" "scripts/start-celery-beat.sh" "logs/celery-beat.log"

# Summary
echo ""
echo -e "${GREEN}All components started successfully!${NC}"
echo "=================================="
echo -e "${BLUE}Components:${NC}"
echo "  • API Server: http://localhost:8000 (PID: $API_PID)"
echo "  • Celery Worker: $(cat celery-worker.pid 2>/dev/null || echo 'Unknown')"
echo "  • Celery Beat: $(cat celery-beat.pid 2>/dev/null || echo 'Unknown')"
echo ""
echo -e "${BLUE}Log files:${NC}"
echo "  • API Server: logs/api-server.log"
echo "  • Celery Worker: logs/celery-worker.log"
echo "  • Celery Beat: logs/celery-beat.log"
echo ""
echo -e "${BLUE}Management:${NC}"
echo "  • Stop all: ./scripts/stop-all.sh"
echo "  • View logs: tail -f logs/*.log"
echo "  • API docs: http://localhost:8000/docs"
echo "  • Scheduler status: curl http://localhost:8000/scheduler/status"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop monitoring (components will continue running)${NC}"

# Monitor processes
while true; do
    sleep 5
    
    # Check if API server is still running
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo -e "${RED}API Server stopped unexpectedly${NC}"
        break
    fi
    
    # Check if worker is still running
    if [ -f "celery-worker.pid" ]; then
        WORKER_PID=$(cat celery-worker.pid)
        if ! kill -0 "$WORKER_PID" 2>/dev/null; then
            echo -e "${RED}Celery Worker stopped unexpectedly${NC}"
            break
        fi
    fi
    
    # Check if beat is still running
    if [ -f "celery-beat.pid" ]; then
        BEAT_PID=$(cat celery-beat.pid)
        if ! kill -0 "$BEAT_PID" 2>/dev/null; then
            echo -e "${RED}Celery Beat stopped unexpectedly${NC}"
            break
        fi
    fi
done
