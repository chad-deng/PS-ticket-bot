#!/bin/bash

# Stop all components of PS Ticket Process Bot

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Stopping PS Ticket Process Bot - All Components${NC}"
echo "=============================================="

# Function to stop a process by PID file
stop_process() {
    local name=$1
    local pid_file=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        echo -e "${YELLOW}Stopping $name (PID: $pid)...${NC}"
        
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            
            # Wait for process to stop
            local count=0
            while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "${YELLOW}Force killing $name...${NC}"
                kill -9 "$pid" 2>/dev/null || true
            fi
            
            echo -e "${GREEN}✓ $name stopped${NC}"
        else
            echo -e "${YELLOW}$name was not running${NC}"
        fi
        
        rm -f "$pid_file"
    else
        echo -e "${YELLOW}No PID file found for $name${NC}"
    fi
}

# Stop Celery Beat first
stop_process "Celery Beat" "celery-beat.pid"

# Stop Celery Worker
stop_process "Celery Worker" "celery-worker.pid"

# Stop API Server
stop_process "API Server" "api-server.pid"

# Clean up any remaining Celery processes
echo -e "${YELLOW}Cleaning up remaining Celery processes...${NC}"
pkill -f "celery.*worker" 2>/dev/null || true
pkill -f "celery.*beat" 2>/dev/null || true

# Clean up schedule files
if [ -f "celerybeat-schedule" ]; then
    echo -e "${YELLOW}Removing Celery Beat schedule file...${NC}"
    rm -f celerybeat-schedule
fi

if [ -f "celerybeat.pid" ]; then
    rm -f celerybeat.pid
fi

# Check for any remaining processes on port 8000
if lsof -i :8000 > /dev/null 2>&1; then
    echo -e "${YELLOW}Killing processes on port 8000...${NC}"
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}All components stopped successfully!${NC}"
echo ""
echo -e "${YELLOW}To restart:${NC}"
echo "  ./scripts/start-all.sh"
