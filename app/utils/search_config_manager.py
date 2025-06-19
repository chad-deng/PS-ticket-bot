"""
Search configuration management for PS Ticket Process Bot.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.config import get_settings


logger = logging.getLogger(__name__)


class SearchConfigManager:
    """Manager for search configuration profiles."""
    
    def __init__(self):
        """Initialize the search configuration manager."""
        self.settings = get_settings()
        self.config_file = Path("config/search-profiles.yaml")
        self._profiles = None
        self._load_profiles()
    
    def _load_profiles(self) -> None:
        """Load search profiles from configuration file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self._profiles = yaml.safe_load(f) or {}
                logger.info(f"Loaded {len(self._profiles)} search profiles")
            else:
                logger.warning(f"Search profiles file not found: {self.config_file}")
                self._profiles = {}
        except Exception as e:
            logger.error(f"Failed to load search profiles: {e}")
            self._profiles = {}
    
    def get_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific search profile.
        
        Args:
            profile_name: Name of the profile to retrieve
            
        Returns:
            Dict: Profile configuration or None if not found
        """
        if self._profiles is None:
            self._load_profiles()
        
        profile = self._profiles.get(profile_name)
        if profile:
            logger.debug(f"Retrieved profile: {profile_name}")
            return profile.copy()
        else:
            logger.warning(f"Profile not found: {profile_name}")
            return None
    
    def list_profiles(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        List all available search profiles.
        
        Args:
            enabled_only: If True, only return enabled profiles
            
        Returns:
            List: List of profile summaries
        """
        if self._profiles is None:
            self._load_profiles()
        
        profiles = []
        for name, config in self._profiles.items():
            if enabled_only and not config.get('enabled', False):
                continue
                
            profiles.append({
                'name': name,
                'display_name': config.get('name', name),
                'description': config.get('description', ''),
                'enabled': config.get('enabled', False),
                'schedule': config.get('schedule', 'manual'),
                'priority': config.get('priority', 'normal')
            })
        
        return profiles
    
    def get_profile_config(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the search configuration from a profile.
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            Dict: Search configuration suitable for scheduled_ticket_search
        """
        profile = self.get_profile(profile_name)
        if not profile:
            return None
        
        config = profile.get('config', {}).copy()
        
        # Add processing options if specified
        processing_options = profile.get('processing_options', {})
        config.update(processing_options)
        
        return config
    
    def validate_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Validate a search profile configuration.
        
        Args:
            profile_name: Name of the profile to validate
            
        Returns:
            Dict: Validation results
        """
        profile = self.get_profile(profile_name)
        if not profile:
            return {
                'valid': False,
                'errors': [f'Profile "{profile_name}" not found']
            }
        
        errors = []
        warnings = []
        
        # Validate required fields
        config = profile.get('config', {})
        required_fields = ['projects', 'issue_types', 'statuses', 'time_range_hours', 'batch_size']
        
        for field in required_fields:
            if field not in config:
                errors.append(f'Missing required field: {field}')
            elif not config[field]:
                errors.append(f'Empty value for required field: {field}')
        
        # Validate field values
        if 'time_range_hours' in config:
            if not isinstance(config['time_range_hours'], int) or config['time_range_hours'] <= 0:
                errors.append('time_range_hours must be a positive integer')
            elif config['time_range_hours'] > 168:
                warnings.append('time_range_hours > 168 (1 week) may impact performance')
        
        if 'batch_size' in config:
            if not isinstance(config['batch_size'], int) or config['batch_size'] <= 0:
                errors.append('batch_size must be a positive integer')
            elif config['batch_size'] > 100:
                warnings.append('batch_size > 100 may impact JIRA API performance')
        
        # Validate schedule format (basic check)
        schedule = profile.get('schedule', '')
        if schedule and schedule != 'manual':
            # Basic cron validation (5 fields)
            parts = schedule.split()
            if len(parts) != 5:
                warnings.append('Schedule format may be invalid (should be cron format)')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'profile_name': profile_name
        }
    
    def create_jql_query(self, profile_name: str) -> Optional[str]:
        """
        Create a JQL query from a profile configuration.
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            str: JQL query string or None if profile not found
        """
        config = self.get_profile_config(profile_name)
        if not config:
            return None
        
        from app.tasks.scheduled_search import _build_jql_query
        
        # Build base JQL
        jql = _build_jql_query(config)
        
        # Add additional JQL if specified
        additional_jql = config.get('additional_jql', '')
        if additional_jql:
            jql += f' {additional_jql}'
        
        # Handle custom time field
        time_field = config.get('time_field', 'updated')
        if time_field != 'updated':
            # Replace 'updated >=' with custom field
            time_range = config.get('time_range_hours', 24)
            jql = jql.replace(f'updated >= -{time_range}h', f'{time_field} >= -{time_range}h')
        
        return jql
    
    def get_enabled_profiles(self) -> List[str]:
        """
        Get list of enabled profile names.
        
        Returns:
            List: List of enabled profile names
        """
        if self._profiles is None:
            self._load_profiles()
        
        enabled = []
        for name, config in self._profiles.items():
            if config.get('enabled', False):
                enabled.append(name)
        
        return enabled
    
    def reload_profiles(self) -> bool:
        """
        Reload profiles from configuration file.
        
        Returns:
            bool: True if reload was successful
        """
        try:
            self._load_profiles()
            logger.info("Search profiles reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload search profiles: {e}")
            return False
    
    def get_profile_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about configured profiles.
        
        Returns:
            Dict: Profile statistics
        """
        if self._profiles is None:
            self._load_profiles()
        
        total_profiles = len(self._profiles)
        enabled_profiles = len([p for p in self._profiles.values() if p.get('enabled', False)])
        
        # Count by priority
        priority_counts = {}
        for profile in self._profiles.values():
            priority = profile.get('priority', 'normal')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        # Count by schedule type
        schedule_types = {}
        for profile in self._profiles.values():
            schedule = profile.get('schedule', 'manual')
            if schedule == 'manual':
                schedule_type = 'manual'
            else:
                schedule_type = 'scheduled'
            schedule_types[schedule_type] = schedule_types.get(schedule_type, 0) + 1
        
        return {
            'total_profiles': total_profiles,
            'enabled_profiles': enabled_profiles,
            'disabled_profiles': total_profiles - enabled_profiles,
            'priority_distribution': priority_counts,
            'schedule_distribution': schedule_types,
            'last_loaded': datetime.utcnow().isoformat()
        }


# Global search config manager instance
_search_config_manager: Optional[SearchConfigManager] = None


def get_search_config_manager() -> SearchConfigManager:
    """Get the global search configuration manager instance."""
    global _search_config_manager
    if _search_config_manager is None:
        _search_config_manager = SearchConfigManager()
    return _search_config_manager


def clear_search_config_cache():
    """Clear the search configuration manager cache."""
    global _search_config_manager
    _search_config_manager = None
