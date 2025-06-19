"""
Celery Beat scheduler configuration for PS Ticket Process Bot.
"""

import logging
from typing import Dict, Any
from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.utils.search_config_manager import get_search_config_manager


logger = logging.getLogger(__name__)


def create_beat_schedule() -> Dict[str, Any]:
    """
    Create Celery Beat schedule from search configuration profiles.
    
    Returns:
        Dict: Celery Beat schedule configuration
    """
    logger.info("Creating Celery Beat schedule from search profiles")
    
    config_manager = get_search_config_manager()
    profiles = config_manager.list_profiles(enabled_only=True)
    
    beat_schedule = {}
    
    for profile in profiles:
        profile_name = profile['name']
        schedule_str = profile['schedule']
        
        # Skip manual profiles
        if schedule_str == 'manual':
            logger.debug(f"Skipping manual profile: {profile_name}")
            continue
        
        # Parse cron schedule
        try:
            cron_parts = schedule_str.split()
            if len(cron_parts) != 5:
                logger.warning(f"Invalid cron format for profile {profile_name}: {schedule_str}")
                continue
            
            minute, hour, day, month, day_of_week = cron_parts
            
            # Create crontab schedule
            schedule = crontab(
                minute=minute,
                hour=hour,
                day_of_month=day,
                month_of_year=month,
                day_of_week=day_of_week
            )
            
            # Get profile configuration
            profile_config = config_manager.get_profile_config(profile_name)
            if not profile_config:
                logger.warning(f"Could not get config for profile: {profile_name}")
                continue
            
            # Create beat schedule entry
            task_name = f"scheduled_search_{profile_name}"
            beat_schedule[task_name] = {
                'task': 'app.tasks.scheduled_search.scheduled_ticket_search',
                'schedule': schedule,
                'args': [profile_config],
                'kwargs': {
                    'priority': profile.get('priority', 'normal'),
                    'profile_name': profile_name
                },
                'options': {
                    'queue': 'scheduled_search',
                    'priority': _get_priority_value(profile.get('priority', 'normal'))
                }
            }
            
            logger.info(f"Added scheduled task: {task_name} with schedule: {schedule_str}")
            
        except Exception as e:
            logger.error(f"Failed to create schedule for profile {profile_name}: {e}")
            continue
    
    logger.info(f"Created {len(beat_schedule)} scheduled tasks")
    return beat_schedule


def _get_priority_value(priority: str) -> int:
    """Convert priority string to numeric value."""
    priority_map = {
        'low': 1,
        'normal': 5,
        'high': 9
    }
    return priority_map.get(priority.lower(), 5)


def setup_celery_beat(celery_app: Celery) -> None:
    """
    Setup Celery Beat with dynamic schedule from search profiles.
    
    Args:
        celery_app: Celery application instance
    """
    logger.info("Setting up Celery Beat scheduler")
    
    try:
        # Create beat schedule
        beat_schedule = create_beat_schedule()
        
        # Update Celery configuration
        celery_app.conf.update(
            beat_schedule=beat_schedule,
            timezone='UTC',
            enable_utc=True,
            beat_schedule_filename='celerybeat-schedule',
            beat_max_loop_interval=300,  # 5 minutes
        )
        
        logger.info("Celery Beat scheduler configured successfully")
        
    except Exception as e:
        logger.error(f"Failed to setup Celery Beat: {e}")
        raise


def reload_beat_schedule(celery_app: Celery) -> bool:
    """
    Reload the beat schedule from updated search profiles.
    
    Args:
        celery_app: Celery application instance
        
    Returns:
        bool: True if reload was successful
    """
    logger.info("Reloading Celery Beat schedule")
    
    try:
        # Reload search profiles
        config_manager = get_search_config_manager()
        config_manager.reload_profiles()
        
        # Create new beat schedule
        beat_schedule = create_beat_schedule()
        
        # Update Celery configuration
        celery_app.conf.beat_schedule = beat_schedule
        
        logger.info("Celery Beat schedule reloaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to reload beat schedule: {e}")
        return False


def get_scheduled_tasks() -> Dict[str, Any]:
    """
    Get information about currently scheduled tasks.
    
    Returns:
        Dict: Information about scheduled tasks
    """
    try:
        config_manager = get_search_config_manager()
        profiles = config_manager.list_profiles(enabled_only=True)
        
        scheduled_tasks = []
        manual_tasks = []
        
        for profile in profiles:
            task_info = {
                'profile_name': profile['name'],
                'display_name': profile['display_name'],
                'description': profile['description'],
                'schedule': profile['schedule'],
                'priority': profile['priority'],
                'enabled': profile['enabled']
            }
            
            if profile['schedule'] == 'manual':
                manual_tasks.append(task_info)
            else:
                scheduled_tasks.append(task_info)
        
        return {
            'scheduled_tasks': scheduled_tasks,
            'manual_tasks': manual_tasks,
            'total_scheduled': len(scheduled_tasks),
            'total_manual': len(manual_tasks),
            'total_enabled': len(profiles)
        }
        
    except Exception as e:
        logger.error(f"Failed to get scheduled tasks info: {e}")
        return {
            'error': str(e),
            'scheduled_tasks': [],
            'manual_tasks': []
        }


def validate_cron_schedule(cron_string: str) -> Dict[str, Any]:
    """
    Validate a cron schedule string.
    
    Args:
        cron_string: Cron schedule string (5 fields)
        
    Returns:
        Dict: Validation result
    """
    try:
        parts = cron_string.strip().split()
        
        if len(parts) != 5:
            return {
                'valid': False,
                'error': f'Cron string must have exactly 5 fields, got {len(parts)}'
            }
        
        minute, hour, day, month, day_of_week = parts
        
        # Try to create crontab to validate
        schedule = crontab(
            minute=minute,
            hour=hour,
            day_of_month=day,
            month_of_year=month,
            day_of_week=day_of_week
        )
        
        return {
            'valid': True,
            'schedule': str(schedule),
            'next_run_times': []  # Could add next run time calculation here
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }


# Common cron schedule examples
COMMON_SCHEDULES = {
    'every_minute': '* * * * *',
    'every_5_minutes': '*/5 * * * *',
    'every_10_minutes': '*/10 * * * *',
    'every_15_minutes': '*/15 * * * *',
    'every_30_minutes': '*/30 * * * *',
    'every_hour': '0 * * * *',
    'every_2_hours': '0 */2 * * *',
    'every_4_hours': '0 */4 * * *',
    'every_6_hours': '0 */6 * * *',
    'every_12_hours': '0 */12 * * *',
    'daily_at_midnight': '0 0 * * *',
    'daily_at_9am': '0 9 * * *',
    'daily_at_6pm': '0 18 * * *',
    'weekdays_at_9am': '0 9 * * 1-5',
    'weekends_only': '0 9 * * 6,0',
    'monday_9am': '0 9 * * 1',
    'friday_5pm': '0 17 * * 5',
    'first_of_month': '0 0 1 * *',
    'weekly_sunday': '0 0 * * 0'
}


def get_common_schedules() -> Dict[str, str]:
    """Get dictionary of common cron schedules."""
    return COMMON_SCHEDULES.copy()
