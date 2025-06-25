"""
Celery application entry point for PS Ticket Process Bot.

This module provides the Celery app instance that Docker Compose expects.
The actual Celery configuration is in app.core.queue.
"""

import logging
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import the configured Celery app from queue module
from app.core.queue import celery_app

# Configure logging for Celery
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Export the Celery app for Docker Compose
app = celery_app

# Log startup information
logger.info("Celery application loaded from app.core.celery")
logger.info(f"Celery app name: {app.main}")
logger.info(f"Broker URL: {app.conf.broker_url}")
logger.info(f"Result backend: {app.conf.result_backend}")

# Ensure all tasks are imported and registered
try:
    from app.tasks import ticket_processor, scheduled_search
    logger.info("All task modules imported successfully")
except ImportError as e:
    logger.error(f"Failed to import task modules: {e}")

# Export for compatibility
__all__ = ['app', 'celery_app']
