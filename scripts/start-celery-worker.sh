#!/bin/bash

# Start Celery Worker for PS Ticket Process Bot
# This script starts the Celery worker that processes tasks

set -e

# Configuration
CELERY_APP="app.core.queue"
LOG_LEVEL="info"
CONCURRENCY=4
QUEUES="ticket_processing,quality_assessment,ai_generation,jira_operations,scheduled_search"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Celery Worker for PS Ticket Process Bot${NC}"
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

# Start Celery worker
echo -e "${YELLOW}Starting Celery worker...${NC}"
echo "App: $CELERY_APP"
echo "Queues: $QUEUES"
echo "Concurrency: $CONCURRENCY"
echo "Log Level: $LOG_LEVEL"
echo ""

exec python -m celery -A "$CELERY_APP" worker \
    --loglevel="$LOG_LEVEL" \
    --concurrency="$CONCURRENCY" \
    --queues="$QUEUES" \
    --hostname="worker@%h" \
    --time-limit=300 \
    --soft-time-limit=240
