#!/bin/bash

# Start Celery Beat Scheduler for PS Ticket Process Bot
# This script starts the Celery Beat scheduler that triggers scheduled searches

set -e

# Configuration
CELERY_APP="app.core.queue"
LOG_LEVEL="info"
SCHEDULE_FILE="celerybeat-schedule"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Celery Beat Scheduler for PS Ticket Process Bot${NC}"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check if Redis is running
echo -e "${YELLOW}Checking Redis connection...${NC}"
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}Error: Redis is not running. Please start Redis first:${NC}"
    echo "  brew services start redis"
    exit 1
fi
echo -e "${GREEN}✓ Redis is running${NC}"

# Check Python environment
echo -e "${YELLOW}Checking Python environment...${NC}"
if ! python -c "import app.core.queue" > /dev/null 2>&1; then
    echo -e "${RED}Error: Cannot import Celery app. Please check your Python environment.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python environment is ready${NC}"

# Check search profiles configuration
echo -e "${YELLOW}Checking search profiles...${NC}"
if [ ! -f "config/search-profiles.yaml" ]; then
    echo -e "${RED}Error: Search profiles configuration not found at config/search-profiles.yaml${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Search profiles configuration found${NC}"

# Remove old schedule file if it exists
if [ -f "$SCHEDULE_FILE" ]; then
    echo -e "${YELLOW}Removing old schedule file...${NC}"
    rm "$SCHEDULE_FILE"
fi

# Start Celery Beat
echo -e "${YELLOW}Starting Celery Beat scheduler...${NC}"
echo "App: $CELERY_APP"
echo "Schedule File: $SCHEDULE_FILE"
echo "Log Level: $LOG_LEVEL"
echo ""

exec python -m celery -A "$CELERY_APP" beat \
    --loglevel="$LOG_LEVEL" \
    --schedule="$SCHEDULE_FILE" \
    --pidfile="celerybeat.pid"
