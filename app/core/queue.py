"""
Message queue configuration and setup for PS Ticket Process Bot.
"""

import logging
from typing import Optional, Dict, Any
from celery import Celery
from kombu import Queue
import redis

from app.core.config import get_settings


logger = logging.getLogger(__name__)


def create_celery_app() -> Celery:
    """
    Create and configure Celery application.
    
    Returns:
        Celery: Configured Celery application
    """
    settings = get_settings()
    
    # Create Celery app
    celery_app = Celery(
        "ps_ticket_bot",
        broker=settings.redis.url,
        backend=settings.redis.url,
        include=["app.tasks.ticket_processor"]
    )
    
    # Configure Celery
    celery_app.conf.update(
        # Task serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        
        # Timezone settings
        timezone="UTC",
        enable_utc=True,
        
        # Task routing
        task_routes={
            "app.tasks.ticket_processor.process_ticket": {"queue": "ticket_processing"},
            "app.tasks.ticket_processor.assess_quality": {"queue": "quality_assessment"},
            "app.tasks.ticket_processor.generate_comment": {"queue": "ai_generation"},
            "app.tasks.ticket_processor.post_comment": {"queue": "jira_operations"},
            "app.tasks.ticket_processor.transition_ticket": {"queue": "jira_operations"},
            "app.tasks.scheduled_search.scheduled_ticket_search": {"queue": "scheduled_search"},
        },
        
        # Queue definitions
        task_queues=(
            Queue("ticket_processing", routing_key="ticket_processing"),
            Queue("quality_assessment", routing_key="quality_assessment"),
            Queue("ai_generation", routing_key="ai_generation"),
            Queue("jira_operations", routing_key="jira_operations"),
            Queue("scheduled_search", routing_key="scheduled_search"),
        ),
        
        # Worker settings
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_disable_rate_limits=False,
        
        # Task execution settings
        task_always_eager=False,  # Set to True for testing
        task_eager_propagates=True,
        task_ignore_result=False,
        
        # Result backend settings
        result_expires=3600,  # 1 hour
        result_persistent=True,
        
        # Error handling
        task_reject_on_worker_lost=True,
        task_acks_on_failure_or_timeout=True,
        
        # Monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,
    )
    
    logger.info("Celery application configured")
    return celery_app


def get_redis_client() -> redis.Redis:
    """
    Get Redis client for direct queue operations.
    
    Returns:
        redis.Redis: Redis client instance
    """
    settings = get_settings()
    
    client = redis.from_url(
        settings.redis.url,
        db=settings.redis.db,
        decode_responses=settings.redis.decode_responses,
        socket_timeout=settings.redis.socket_timeout,
        socket_connect_timeout=settings.redis.socket_connect_timeout,
        retry_on_timeout=settings.redis.retry_on_timeout,
        max_connections=settings.redis.max_connections
    )
    
    return client


class QueueManager:
    """Manager for queue operations and monitoring."""
    
    def __init__(self):
        """Initialize the queue manager."""
        self.settings = get_settings()
        self.redis_client = get_redis_client()
        self.celery_app = create_celery_app()
        
    def queue_ticket_processing(
        self,
        issue_key: str,
        webhook_event: str,
        priority: str = "normal",
        processing_options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Queue a ticket for processing.

        Args:
            issue_key: JIRA issue key
            webhook_event: Type of webhook event
            priority: Task priority (high, normal, low)
            processing_options: Optional processing options (force_reprocess, skip_quality_check, etc.)

        Returns:
            str: Task ID
        """
        from app.tasks.ticket_processor import process_ticket

        logger.info(f"Queuing ticket {issue_key} for processing (event: {webhook_event})")

        # Set task priority
        task_priority = 5  # Default priority
        if priority == "high":
            task_priority = 9
        elif priority == "low":
            task_priority = 1

        # Prepare task arguments
        task_args = [issue_key, webhook_event]
        if processing_options:
            task_args.append(processing_options)
            logger.info(f"Processing options for {issue_key}: {processing_options}")

        # Queue the task
        result = process_ticket.apply_async(
            args=task_args,
            priority=task_priority,
            queue="ticket_processing"
        )

        logger.info(f"Queued ticket {issue_key} with task ID {result.id}")
        return result.id
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics and health information.
        
        Returns:
            Dict: Queue statistics
        """
        try:
            # Get Celery inspect instance
            inspect = self.celery_app.control.inspect()
            
            # Get active tasks
            active_tasks = inspect.active()
            
            # Get queue lengths from Redis
            queue_lengths = {}
            queue_names = ["ticket_processing", "quality_assessment", "ai_generation", "jira_operations"]
            
            for queue_name in queue_names:
                try:
                    length = self.redis_client.llen(f"celery:{queue_name}")
                    queue_lengths[queue_name] = length
                except Exception as e:
                    logger.warning(f"Failed to get length for queue {queue_name}: {e}")
                    queue_lengths[queue_name] = -1
            
            # Get worker stats
            worker_stats = inspect.stats() or {}
            
            return {
                "queue_lengths": queue_lengths,
                "active_tasks": len(active_tasks) if active_tasks else 0,
                "worker_count": len(worker_stats),
                "redis_connected": self._check_redis_connection(),
                "celery_connected": self._check_celery_connection()
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {
                "error": str(e),
                "redis_connected": self._check_redis_connection(),
                "celery_connected": False
            }
    
    def _check_redis_connection(self) -> bool:
        """Check Redis connection health."""
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
    
    def _check_celery_connection(self) -> bool:
        """Check Celery connection health."""
        try:
            inspect = self.celery_app.control.inspect()
            stats = inspect.stats()
            return stats is not None
        except Exception:
            return False
    
    def purge_queues(self, queue_names: Optional[list] = None) -> Dict[str, int]:
        """
        Purge specified queues (for testing/maintenance).
        
        Args:
            queue_names: List of queue names to purge, or None for all
            
        Returns:
            Dict: Number of messages purged per queue
        """
        if queue_names is None:
            queue_names = ["ticket_processing", "quality_assessment", "ai_generation", "jira_operations"]
        
        purged = {}
        
        for queue_name in queue_names:
            try:
                # Purge Celery queue
                self.celery_app.control.purge()
                
                # Also clear Redis list directly
                redis_key = f"celery:{queue_name}"
                count = self.redis_client.llen(redis_key)
                self.redis_client.delete(redis_key)
                
                purged[queue_name] = count
                logger.info(f"Purged {count} messages from queue {queue_name}")
                
            except Exception as e:
                logger.error(f"Failed to purge queue {queue_name}: {e}")
                purged[queue_name] = -1
        
        return purged
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a specific task.
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Dict: Task status information
        """
        try:
            result = self.celery_app.AsyncResult(task_id)
            
            return {
                "task_id": task_id,
                "status": result.status,
                "result": result.result,
                "traceback": result.traceback,
                "successful": result.successful(),
                "failed": result.failed(),
                "ready": result.ready()
            }
            
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return {
                "task_id": task_id,
                "error": str(e)
            }
    
    def retry_failed_tasks(self, max_retries: int = 3) -> Dict[str, Any]:
        """
        Retry failed tasks in the queue.
        
        Args:
            max_retries: Maximum number of retries per task
            
        Returns:
            Dict: Retry operation results
        """
        # This is a simplified implementation
        # In production, you might want to use Celery's built-in retry mechanisms
        logger.info("Retry failed tasks functionality not fully implemented")
        return {"message": "Retry functionality requires additional implementation"}


# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager() -> QueueManager:
    """Get the global queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager()
    return _queue_manager


# Create Celery app instance for worker
celery_app = create_celery_app()

# Import tasks to register them with Celery
from app.tasks import ticket_processor, scheduled_search

# Setup Celery Beat scheduler
try:
    from app.core.scheduler import setup_celery_beat
    setup_celery_beat(celery_app)
    logger.info("Celery Beat scheduler configured")
except Exception as e:
    logger.warning(f"Failed to setup Celery Beat: {e}")
