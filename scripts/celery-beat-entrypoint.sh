#!/bin/bash
"""
Entrypoint script for Celery Beat to ensure proper permissions.
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to setup directories and permissions
setup_directories() {
    log_info "Setting up Celery Beat directories and permissions..."
    
    # Create data directory if it doesn't exist
    if [ ! -d "/app/data" ]; then
        mkdir -p /app/data
        log_info "Created /app/data directory"
    fi
    
    # Create logs directory if it doesn't exist
    if [ ! -d "/app/logs" ]; then
        mkdir -p /app/logs
        log_info "Created /app/logs directory"
    fi
    
    # Ensure current user owns the directories
    if [ -w "/app/data" ]; then
        log_info "Write permission confirmed for /app/data"
    else
        log_error "No write permission for /app/data"
        exit 1
    fi
    
    # Remove any existing schedule files that might have permission issues
    if [ -f "/app/data/celerybeat-schedule" ]; then
        if [ -w "/app/data/celerybeat-schedule" ]; then
            log_info "Existing schedule file is writable"
        else
            log_warn "Removing non-writable schedule file"
            rm -f /app/data/celerybeat-schedule* 2>/dev/null || true
        fi
    fi
}

# Function to test Celery Beat configuration
test_celery_config() {
    log_info "Testing Celery configuration..."
    
    # Test if we can import the Celery app
    python -c "from app.core.celery import app; print(f'Celery app loaded: {app.main}')" || {
        log_error "Failed to import Celery app"
        exit 1
    }
    
    # Test if we can access the broker
    python -c "
from app.core.celery import app
try:
    inspect = app.control.inspect()
    stats = inspect.stats()
    print('Broker connection test passed')
except Exception as e:
    print(f'Broker connection test failed: {e}')
    exit(1)
" || {
        log_warn "Broker connection test failed (this is normal if Redis isn't ready yet)"
    }
}

# Function to start Celery Beat with proper error handling
start_celery_beat() {
    log_info "Starting Celery Beat scheduler..."
    
    # Set the schedule file path
    SCHEDULE_FILE="/app/data/celerybeat-schedule"
    
    # Additional Celery Beat options for better reliability
    CELERY_OPTS=(
        "--loglevel=info"
        "--schedule=${SCHEDULE_FILE}"
        "--pidfile=/app/data/celerybeat.pid"
        "--max-interval=60"
    )
    
    log_info "Schedule file: ${SCHEDULE_FILE}"
    log_info "Starting with options: ${CELERY_OPTS[*]}"
    
    # Start Celery Beat
    exec celery -A app.core.celery beat "${CELERY_OPTS[@]}"
}

# Function to handle cleanup on exit
cleanup() {
    log_info "Cleaning up Celery Beat..."
    
    # Remove PID file if it exists
    if [ -f "/app/data/celerybeat.pid" ]; then
        rm -f /app/data/celerybeat.pid
        log_info "Removed PID file"
    fi
}

# Set up signal handlers for graceful shutdown
trap cleanup EXIT INT TERM

# Main execution
main() {
    log_info "Celery Beat entrypoint starting..."
    log_info "User: $(whoami)"
    log_info "Working directory: $(pwd)"
    log_info "Python path: $(which python)"
    
    # Setup directories and permissions
    setup_directories
    
    # Test configuration
    test_celery_config
    
    # Start Celery Beat
    start_celery_beat
}

# Run main function
main "$@"
