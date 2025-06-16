"""
Celery worker process for PS Ticket Process Bot.
"""

import logging
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.queue import celery_app
from app.core.config import get_settings


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main worker process entry point."""
    settings = get_settings()
    
    logger.info("Starting PS Ticket Process Bot worker")
    logger.info(f"Environment: {settings.app.environment}")
    logger.info(f"Redis URL: {settings.redis.url}")
    logger.info(f"Features enabled: {settings.features.__dict__}")
    
    # Configure worker options
    worker_options = [
        "worker",
        "--loglevel=info",
        "--concurrency=4",
        "--queues=ticket_processing,quality_assessment,ai_generation,jira_operations",
        "--hostname=ps-ticket-bot-worker@%h",
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat"
    ]
    
    # Add environment-specific options
    if settings.app.environment == "development":
        worker_options.extend([
            "--pool=solo",  # Single-threaded for debugging
            "--loglevel=debug"
        ])
    elif settings.app.environment == "production":
        worker_options.extend([
            "--optimization=fair",
            "--prefetch-multiplier=1",
            "--max-tasks-per-child=1000"
        ])
    
    # Start the worker
    try:
        celery_app.worker_main(worker_options)
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
