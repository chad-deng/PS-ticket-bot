"""
Scheduler management API endpoints.
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.scheduler import (
    get_scheduled_tasks,
    reload_beat_schedule,
    validate_cron_schedule,
    get_common_schedules
)
from app.utils.search_config_manager import get_search_config_manager
from app.core.queue import celery_app


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class ScheduleValidationRequest(BaseModel):
    """Request model for schedule validation."""
    cron_schedule: str


class ScheduleValidationResponse(BaseModel):
    """Response model for schedule validation."""
    valid: bool
    error: str = None
    schedule: str = None


@router.get("/status")
async def get_scheduler_status() -> Dict[str, Any]:
    """
    Get current scheduler status and information.
    
    Returns:
        Dict: Scheduler status information
    """
    logger.info("Getting scheduler status")
    
    try:
        # Get scheduled tasks info
        tasks_info = get_scheduled_tasks()
        
        # Get Celery Beat status (if available)
        beat_status = "unknown"
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            if active_tasks is not None:
                beat_status = "running"
            else:
                beat_status = "not_running"
        except Exception:
            beat_status = "unavailable"
        
        return {
            "scheduler_type": "celery_beat",
            "beat_status": beat_status,
            "tasks_info": tasks_info,
            "configuration": {
                "timezone": "UTC",
                "beat_schedule_file": "celerybeat-schedule",
                "max_loop_interval": 300
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")


@router.get("/tasks")
async def list_scheduled_tasks() -> Dict[str, Any]:
    """
    List all scheduled and manual tasks.
    
    Returns:
        Dict: List of scheduled tasks
    """
    logger.info("Listing scheduled tasks")
    
    try:
        tasks_info = get_scheduled_tasks()
        return tasks_info
        
    except Exception as e:
        logger.error(f"Failed to list scheduled tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


@router.post("/reload")
async def reload_scheduler() -> Dict[str, Any]:
    """
    Reload the scheduler configuration from search profiles.
    
    Returns:
        Dict: Reload operation result
    """
    logger.info("Reloading scheduler configuration")
    
    try:
        success = reload_beat_schedule(celery_app)
        
        if success:
            tasks_info = get_scheduled_tasks()
            return {
                "success": True,
                "message": "Scheduler configuration reloaded successfully",
                "tasks_info": tasks_info
            }
        else:
            return {
                "success": False,
                "message": "Failed to reload scheduler configuration"
            }
        
    except Exception as e:
        logger.error(f"Failed to reload scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload scheduler: {str(e)}")


@router.post("/validate-schedule")
async def validate_schedule(request: ScheduleValidationRequest) -> ScheduleValidationResponse:
    """
    Validate a cron schedule string.
    
    Args:
        request: Schedule validation request
        
    Returns:
        ScheduleValidationResponse: Validation result
    """
    logger.info(f"Validating cron schedule: {request.cron_schedule}")
    
    try:
        result = validate_cron_schedule(request.cron_schedule)
        
        return ScheduleValidationResponse(
            valid=result['valid'],
            error=result.get('error'),
            schedule=result.get('schedule')
        )
        
    except Exception as e:
        logger.error(f"Failed to validate schedule: {e}")
        return ScheduleValidationResponse(
            valid=False,
            error=f"Validation failed: {str(e)}"
        )


@router.get("/common-schedules")
async def get_common_schedule_examples() -> Dict[str, str]:
    """
    Get common cron schedule examples.
    
    Returns:
        Dict: Common cron schedule patterns
    """
    logger.info("Getting common schedule examples")
    
    try:
        return get_common_schedules()
        
    except Exception as e:
        logger.error(f"Failed to get common schedules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get schedules: {str(e)}")


@router.get("/profiles/{profile_name}/schedule")
async def get_profile_schedule(profile_name: str) -> Dict[str, Any]:
    """
    Get schedule information for a specific profile.
    
    Args:
        profile_name: Name of the search profile
        
    Returns:
        Dict: Profile schedule information
    """
    logger.info(f"Getting schedule for profile: {profile_name}")
    
    try:
        config_manager = get_search_config_manager()
        profile = config_manager.get_profile(profile_name)
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' not found")
        
        schedule_str = profile.get('schedule', 'manual')
        
        # Validate schedule if it's not manual
        schedule_info = {
            'profile_name': profile_name,
            'schedule': schedule_str,
            'enabled': profile.get('enabled', False),
            'priority': profile.get('priority', 'normal')
        }
        
        if schedule_str != 'manual':
            validation = validate_cron_schedule(schedule_str)
            schedule_info['validation'] = validation
        
        return schedule_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get profile schedule: {str(e)}")


@router.put("/profiles/{profile_name}/enable")
async def enable_profile_schedule(profile_name: str) -> Dict[str, Any]:
    """
    Enable scheduling for a specific profile.
    
    Args:
        profile_name: Name of the search profile
        
    Returns:
        Dict: Operation result
    """
    logger.info(f"Enabling schedule for profile: {profile_name}")
    
    try:
        config_manager = get_search_config_manager()
        profile = config_manager.get_profile(profile_name)
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' not found")
        
        # Note: This would require updating the YAML file
        # For now, return information about how to enable it
        return {
            "message": f"To enable profile '{profile_name}', set 'enabled: true' in config/search-profiles.yaml",
            "profile_name": profile_name,
            "current_status": profile.get('enabled', False),
            "schedule": profile.get('schedule', 'manual'),
            "action_required": "Manual configuration file update required"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable profile schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enable profile: {str(e)}")


@router.put("/profiles/{profile_name}/disable")
async def disable_profile_schedule(profile_name: str) -> Dict[str, Any]:
    """
    Disable scheduling for a specific profile.
    
    Args:
        profile_name: Name of the search profile
        
    Returns:
        Dict: Operation result
    """
    logger.info(f"Disabling schedule for profile: {profile_name}")
    
    try:
        config_manager = get_search_config_manager()
        profile = config_manager.get_profile(profile_name)
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' not found")
        
        # Note: This would require updating the YAML file
        # For now, return information about how to disable it
        return {
            "message": f"To disable profile '{profile_name}', set 'enabled: false' in config/search-profiles.yaml",
            "profile_name": profile_name,
            "current_status": profile.get('enabled', False),
            "schedule": profile.get('schedule', 'manual'),
            "action_required": "Manual configuration file update required"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable profile schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disable profile: {str(e)}")


@router.get("/next-runs")
async def get_next_scheduled_runs(
    limit: int = Query(default=10, ge=1, le=50, description="Number of next runs to show")
) -> Dict[str, Any]:
    """
    Get information about next scheduled runs.
    
    Args:
        limit: Maximum number of next runs to show
        
    Returns:
        Dict: Next scheduled runs information
    """
    logger.info(f"Getting next {limit} scheduled runs")
    
    try:
        # This would require more complex implementation to calculate next run times
        # For now, return basic information
        tasks_info = get_scheduled_tasks()
        
        return {
            "message": "Next run calculation not yet implemented",
            "scheduled_tasks_count": tasks_info.get('total_scheduled', 0),
            "note": "Use 'celery -A app.core.queue inspect scheduled' to see pending tasks"
        }
        
    except Exception as e:
        logger.error(f"Failed to get next runs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get next runs: {str(e)}")
