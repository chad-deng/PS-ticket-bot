"""
Scheduled search API endpoints for PS Ticket Process Bot.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.tasks.scheduled_search import scheduled_ticket_search
from app.core.queue import get_queue_manager
from app.utils.search_config_manager import get_search_config_manager


logger = logging.getLogger(__name__)
router = APIRouter()


class SearchConfig(BaseModel):
    """Search configuration model."""
    projects: list[str] = Field(default=["PS"], description="JIRA project keys to search")
    issue_types: list[str] = Field(default=["Problem", "Bug", "Support Request"], description="Issue types to include")
    statuses: list[str] = Field(default=["Open", "In Progress", "Reopened"], description="Statuses to include")
    time_range_hours: int = Field(default=24, ge=1, le=168, description="Hours to look back (1-168)")
    batch_size: int = Field(default=50, ge=1, le=100, description="Batch size for processing (1-100)")
    exclude_processed_within_hours: int = Field(default=6, ge=0, le=48, description="Skip tickets processed within hours")


class SearchTriggerRequest(BaseModel):
    """Request model for triggering a search."""
    config: Optional[SearchConfig] = Field(default=None, description="Optional search configuration override")
    priority: str = Field(default="normal", description="Task priority (high, normal, low)")


@router.post("/trigger")
async def trigger_search(
    request: SearchTriggerRequest,
    background_tasks: BackgroundTasks
):
    """
    Manually trigger a scheduled search for JIRA tickets.
    
    This endpoint allows manual triggering of the scheduled search process
    for testing or immediate processing needs.
    """
    logger.info("Manual search trigger requested")
    
    try:
        # Get queue manager
        queue_manager = get_queue_manager()
        
        # Prepare search configuration
        search_config = request.config.dict() if request.config else None
        
        # Determine task priority
        task_priority = 5  # Default
        if request.priority == "high":
            task_priority = 9
        elif request.priority == "low":
            task_priority = 1
        
        # Queue the search task
        result = scheduled_ticket_search.apply_async(
            args=[search_config],
            priority=task_priority,
            queue="ticket_processing"
        )
        
        logger.info(f"Scheduled search queued with task ID {result.id}")
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "task_id": result.id,
                "message": "Scheduled search has been queued",
                "config": search_config or "default",
                "priority": request.priority
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to trigger scheduled search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger search: {str(e)}")


@router.get("/config/default")
async def get_default_config():
    """
    Get the default search configuration.
    
    Returns the default configuration used for scheduled searches
    when no custom configuration is provided.
    """
    from app.tasks.scheduled_search import _get_default_search_config
    
    try:
        default_config = _get_default_search_config()
        
        return JSONResponse(
            status_code=200,
            content={
                "default_config": default_config,
                "description": "Default configuration for scheduled JIRA searches"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get default config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get default configuration")


@router.post("/config/validate")
async def validate_config(config: SearchConfig):
    """
    Validate a search configuration and preview the JQL query.
    
    This endpoint validates the provided configuration and shows
    what JQL query would be generated for the search.
    """
    try:
        from app.tasks.scheduled_search import _build_jql_query
        
        # Convert to dict and build JQL
        config_dict = config.dict()
        jql_query = _build_jql_query(config_dict)
        
        # Estimate potential results (this is just a preview)
        estimated_scope = {
            "projects": len(config.projects),
            "issue_types": len(config.issue_types),
            "statuses": len(config.statuses),
            "time_range": f"{config.time_range_hours} hours",
            "batch_size": config.batch_size
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "valid": True,
                "config": config_dict,
                "generated_jql": jql_query,
                "estimated_scope": estimated_scope,
                "message": "Configuration is valid"
            }
        )
        
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        return JSONResponse(
            status_code=400,
            content={
                "valid": False,
                "error": str(e),
                "message": "Configuration validation failed"
            }
        )


@router.get("/status/{task_id}")
async def get_search_status(task_id: str):
    """
    Get the status of a scheduled search task.
    
    Args:
        task_id: Celery task ID from the trigger response
    """
    try:
        from celery.result import AsyncResult
        from app.core.queue import celery_app
        
        # Get task result
        task_result = AsyncResult(task_id, app=celery_app)
        
        response_data = {
            "task_id": task_id,
            "status": task_result.status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if task_result.ready():
            if task_result.successful():
                result = task_result.result
                response_data.update({
                    "completed": True,
                    "success": result.get("success", False),
                    "tickets_found": result.get("tickets_found", 0),
                    "tickets_queued": result.get("tickets_queued", 0),
                    "tickets_skipped": result.get("tickets_skipped", 0),
                    "errors": result.get("errors", []),
                    "duration_seconds": result.get("duration_seconds"),
                    "search_started_at": result.get("search_started_at"),
                    "search_completed_at": result.get("search_completed_at")
                })
            else:
                response_data.update({
                    "completed": True,
                    "success": False,
                    "error": str(task_result.result) if task_result.result else "Task failed"
                })
        else:
            response_data.update({
                "completed": False,
                "message": "Task is still running"
            })
        
        return JSONResponse(status_code=200, content=response_data)
        
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@router.get("/history")
async def get_search_history(
    limit: int = Query(default=10, ge=1, le=100, description="Number of recent searches to return")
):
    """
    Get history of recent scheduled searches.
    
    Note: This is a placeholder implementation. In production, you would
    store search history in a database or Redis.
    """
    try:
        # This is a placeholder - in production you'd query a database
        # For now, return a sample response
        sample_history = [
            {
                "task_id": "sample-task-1",
                "started_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                "completed_at": (datetime.utcnow() - timedelta(hours=2, minutes=-5)).isoformat(),
                "status": "SUCCESS",
                "tickets_found": 15,
                "tickets_queued": 12,
                "tickets_skipped": 3,
                "duration_seconds": 45.2
            },
            {
                "task_id": "sample-task-2", 
                "started_at": (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                "completed_at": (datetime.utcnow() - timedelta(hours=6, minutes=-3)).isoformat(),
                "status": "SUCCESS",
                "tickets_found": 8,
                "tickets_queued": 8,
                "tickets_skipped": 0,
                "duration_seconds": 32.1
            }
        ]
        
        return JSONResponse(
            status_code=200,
            content={
                "history": sample_history[:limit],
                "total_count": len(sample_history),
                "note": "This is sample data. In production, this would show real search history."
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get search history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get search history")


@router.post("/test")
async def test_search_query(config: SearchConfig):
    """
    Test a search configuration without actually processing tickets.
    
    This endpoint executes the search query and returns the found tickets
    without queuing them for processing. Useful for testing configurations.
    """
    try:
        from app.services.jira_client import get_jira_client
        from app.tasks.scheduled_search import _build_jql_query
        
        # Build JQL query
        config_dict = config.dict()
        jql_query = _build_jql_query(config_dict)
        
        # Execute search (limited to first batch only)
        jira_client = get_jira_client()
        search_results = jira_client.search_issues_sync(
            jql=jql_query,
            start_at=0,
            max_results=min(config.batch_size, 10),  # Limit test results
            expand=["attachment"]
        )
        
        issues = search_results.get("issues", [])
        total_found = search_results.get("total", 0)
        
        # Extract basic info from found issues
        issue_summaries = []
        for issue in issues:
            issue_summaries.append({
                "key": issue.get("key"),
                "summary": issue.get("fields", {}).get("summary", ""),
                "issue_type": issue.get("fields", {}).get("issuetype", {}).get("name", ""),
                "priority": issue.get("fields", {}).get("priority", {}).get("name", ""),
                "status": issue.get("fields", {}).get("status", {}).get("name", ""),
                "updated": issue.get("fields", {}).get("updated", "")
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "test_successful": True,
                "jql_query": jql_query,
                "total_found": total_found,
                "sample_issues": issue_summaries,
                "config_used": config_dict,
                "note": f"Showing first {len(issue_summaries)} of {total_found} total results"
            }
        )
        
    except Exception as e:
        logger.error(f"Search test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search test failed: {str(e)}")
