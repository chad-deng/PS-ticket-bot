"""
Admin API endpoints for PS Ticket Process Bot.
"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.queue import get_queue_manager
from app.core.config import get_settings


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/queue/stats")
async def get_queue_stats():
    """
    Get queue statistics and health information.
    
    Returns queue lengths, active tasks, worker information, and connection status.
    """
    try:
        queue_manager = get_queue_manager()
        stats = queue_manager.get_queue_stats()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "timestamp": "2024-01-01T00:00:00Z",  # TODO: Use actual timestamp
                "stats": stats
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve queue statistics")


@router.get("/queue/health")
async def queue_health_check():
    """
    Check queue system health.
    
    Returns health status of Redis, Celery, and individual queues.
    """
    try:
        queue_manager = get_queue_manager()
        stats = queue_manager.get_queue_stats()
        
        # Determine overall health
        redis_ok = stats.get("redis_connected", False)
        celery_ok = stats.get("celery_connected", False)
        
        health_status = "healthy" if (redis_ok and celery_ok) else "unhealthy"
        status_code = 200 if health_status == "healthy" else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": health_status,
                "redis_connected": redis_ok,
                "celery_connected": celery_ok,
                "queue_lengths": stats.get("queue_lengths", {}),
                "active_tasks": stats.get("active_tasks", 0),
                "worker_count": stats.get("worker_count", 0)
            }
        )
        
    except Exception as e:
        logger.error(f"Queue health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Get status of a specific task.
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Task status information including state, result, and progress.
    """
    try:
        queue_manager = get_queue_manager()
        task_status = queue_manager.get_task_status(task_id)
        
        if "error" in task_status:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        
        return JSONResponse(
            status_code=200,
            content=task_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve task status")


@router.post("/queue/purge")
async def purge_queues(
    queues: Optional[List[str]] = Query(None, description="Queue names to purge (all if not specified)")
):
    """
    Purge specified queues (for testing/maintenance).
    
    Args:
        queues: List of queue names to purge
        
    Returns:
        Number of messages purged per queue.
    """
    try:
        settings = get_settings()
        
        # Only allow purging in development/staging
        if settings.app.environment == "production":
            raise HTTPException(
                status_code=403,
                detail="Queue purging is not allowed in production environment"
            )
        
        queue_manager = get_queue_manager()
        purged = queue_manager.purge_queues(queues)
        
        logger.warning(f"Purged queues: {purged}")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "purged_queues": purged,
                "total_messages_purged": sum(count for count in purged.values() if count > 0)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to purge queues: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to purge queues")


@router.post("/task/retry")
async def retry_failed_tasks(
    max_retries: int = Query(3, description="Maximum number of retries per task")
):
    """
    Retry failed tasks in the queue.
    
    Args:
        max_retries: Maximum number of retries per task
        
    Returns:
        Retry operation results.
    """
    try:
        queue_manager = get_queue_manager()
        result = queue_manager.retry_failed_tasks(max_retries)
        
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except Exception as e:
        logger.error(f"Failed to retry failed tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retry failed tasks")


@router.get("/config")
async def get_configuration():
    """
    Get current bot configuration (non-sensitive information).
    
    Returns:
        Current configuration settings for monitoring and debugging.
    """
    try:
        settings = get_settings()
        
        config_info = {
            "app": {
                "name": settings.app.name,
                "version": settings.app.version,
                "environment": settings.app.environment,
                "debug": settings.app.debug
            },
            "features": {
                "webhooks_enabled": settings.features.enable_webhooks,
                "polling_enabled": settings.features.enable_polling,
                "ai_comments_enabled": settings.features.enable_ai_comments,
                "status_transitions_enabled": settings.features.enable_status_transitions,
                "notifications_enabled": settings.features.enable_notifications,
                "metrics_enabled": settings.features.enable_metrics
            },
            "jira": {
                "base_url": settings.jira.base_url,
                "username": settings.jira.username,
                "timeout": settings.jira.timeout,
                "max_retries": settings.jira.max_retries
            },
            "gemini": {
                "model": settings.gemini.model,
                "temperature": settings.gemini.temperature,
                "max_output_tokens": settings.gemini.max_output_tokens
            },
            "queue": {
                "redis_url": settings.redis.url.split("@")[-1] if "@" in settings.redis.url else settings.redis.url,
                "redis_db": settings.redis.db
            }
        }
        
        return JSONResponse(
            status_code=200,
            content=config_info
        )
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration")


@router.get("/metrics")
async def get_metrics():
    """
    Get bot metrics and performance information.
    
    Returns:
        Performance metrics, processing statistics, and system health.
    """
    try:
        # TODO: Implement comprehensive metrics collection
        # For now, return basic queue stats
        
        queue_manager = get_queue_manager()
        queue_stats = queue_manager.get_queue_stats()
        
        metrics = {
            "queue_metrics": queue_stats,
            "processing_metrics": {
                "total_tickets_processed": 0,  # TODO: Implement counter
                "average_processing_time": 0,  # TODO: Implement timing
                "success_rate": 0,  # TODO: Implement success tracking
                "error_rate": 0  # TODO: Implement error tracking
            },
            "system_metrics": {
                "uptime_seconds": 0,  # TODO: Implement uptime tracking
                "memory_usage_mb": 0,  # TODO: Implement memory monitoring
                "cpu_usage_percent": 0  # TODO: Implement CPU monitoring
            }
        }
        
        return JSONResponse(
            status_code=200,
            content=metrics
        )
        
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.post("/test/queue")
async def test_queue_processing(
    issue_key: str = Query(..., description="JIRA issue key to test"),
    priority: str = Query("normal", description="Task priority (high, normal, low)")
):
    """
    Test queue processing with a specific ticket.
    
    Args:
        issue_key: JIRA issue key to process
        priority: Task priority level
        
    Returns:
        Task ID and status for testing.
    """
    try:
        settings = get_settings()
        
        # Only allow testing in development/staging
        if settings.app.environment == "production":
            raise HTTPException(
                status_code=403,
                detail="Queue testing is not allowed in production environment"
            )
        
        queue_manager = get_queue_manager()
        task_id = queue_manager.queue_ticket_processing(issue_key, "test_event", priority)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "queued",
                "task_id": task_id,
                "issue_key": issue_key,
                "priority": priority,
                "message": f"Ticket {issue_key} queued for testing with task ID {task_id}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test queue processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to test queue processing")
