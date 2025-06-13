"""
Configuration management utilities for PS Ticket Process Bot.
"""

import os
import yaml
import json
from typing import Dict, Any, Optional, Union
from pathlib import Path
from app.core.config import get_settings


class ConfigManager:
    """Utility class for managing configuration at runtime."""
    
    def __init__(self):
        """Initialize the configuration manager."""
        self.settings = get_settings()
    
    def get_jira_project_config(self, project_key: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific JIRA project."""
        projects = self.settings.yaml_config.get("jira", {}).get("projects", {})
        
        for project_type, project_config in projects.items():
            if project_config.get("key") == project_key:
                return project_config
                
        return None
    
    def get_issue_type_config(self, issue_type_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific issue type."""
        issue_types = self.settings.yaml_config.get("jira", {}).get("issue_types", [])
        
        for issue_type in issue_types:
            if issue_type.get("name") == issue_type_name:
                return issue_type
                
        return None
    
    def should_process_issue_type(self, issue_type_name: str) -> bool:
        """Check if an issue type should be processed by the bot."""
        issue_type_config = self.get_issue_type_config(issue_type_name)
        return issue_type_config.get("process", False) if issue_type_config else False
    
    def get_transition_for_quality(self, quality_level: str) -> Optional[Dict[str, Any]]:
        """Get the appropriate transition for a quality level."""
        transitions = self.settings.get_jira_transitions()
        quality_transitions = transitions.get(f"{quality_level}_quality", [])
        
        # Return the first available transition for the quality level
        return quality_transitions[0] if quality_transitions else None
    
    def get_quality_rule_config(self, rule_name: str) -> Any:
        """Get configuration for a specific quality rule."""
        quality_rules = self.settings.get_quality_rules()
        return quality_rules.get(rule_name)
    
    def get_comment_template(self, template_type: str) -> Optional[Dict[str, str]]:
        """Get a comment template by type."""
        templates = self.settings.get_comment_templates()
        return templates.get(template_type)
    
    def get_field_mapping(self, field_name: str) -> Optional[str]:
        """Get JIRA field mapping for a logical field name."""
        mappings = self.settings.get_jira_field_mappings()
        return mappings.get(field_name)
    
    def is_high_priority(self, priority_name: str) -> bool:
        """Check if a priority level is considered high priority."""
        high_priority_levels = self.settings.quality_rules.high_priority_levels
        return priority_name in high_priority_levels
    
    def get_rate_limit_config(self, service: str) -> Dict[str, Any]:
        """Get rate limiting configuration for a service."""
        if service == "jira":
            return {
                "max_retries": self.settings.jira.max_retries,
                "retry_delay": self.settings.jira.retry_delay,
                "timeout": self.settings.jira.timeout
            }
        elif service == "gemini":
            return {
                "max_retries": self.settings.gemini.max_retries,
                "retry_delay": self.settings.gemini.retry_delay,
                "timeout": self.settings.gemini.timeout
            }
        else:
            return {}
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring and alerting configuration."""
        return {
            "enable_prometheus": self.settings.monitoring.enable_prometheus,
            "prometheus_port": self.settings.monitoring.prometheus_port,
            "health_check_interval": self.settings.monitoring.health_check_interval,
            "metrics_prefix": self.settings.monitoring.metrics_prefix,
            "thresholds": {
                "error_rate": self.settings.monitoring.error_rate_threshold,
                "response_time_p95": self.settings.monitoring.response_time_p95_threshold,
                "queue_depth": self.settings.monitoring.queue_depth_threshold
            }
        }
    
    def export_config(self, format: str = "yaml", include_secrets: bool = False) -> str:
        """Export current configuration in specified format."""
        config_data = {
            "app": {
                "name": self.settings.app.name,
                "version": self.settings.app.version,
                "environment": self.settings.app.environment,
                "debug": self.settings.app.debug
            },
            "features": {
                "enable_webhooks": self.settings.features.enable_webhooks,
                "enable_polling": self.settings.features.enable_polling,
                "enable_ai_comments": self.settings.features.enable_ai_comments,
                "enable_status_transitions": self.settings.features.enable_status_transitions,
                "enable_notifications": self.settings.features.enable_notifications,
                "enable_metrics": self.settings.features.enable_metrics
            },
            "quality_rules": {
                "summary_min_length": self.settings.quality_rules.summary_min_length,
                "description_min_length": self.settings.quality_rules.description_min_length,
                "steps_min_length": self.settings.quality_rules.steps_min_length,
                "high_quality_max_issues": self.settings.quality_rules.high_quality_max_issues,
                "medium_quality_max_issues": self.settings.quality_rules.medium_quality_max_issues,
                "low_quality_min_issues": self.settings.quality_rules.low_quality_min_issues
            }
        }
        
        if include_secrets:
            config_data["jira"] = {
                "base_url": self.settings.jira.base_url,
                "username": self.settings.jira.username,
                "timeout": self.settings.jira.timeout,
                "max_retries": self.settings.jira.max_retries
            }
            config_data["gemini"] = {
                "model": self.settings.gemini.model,
                "temperature": self.settings.gemini.temperature,
                "top_p": self.settings.gemini.top_p,
                "max_output_tokens": self.settings.gemini.max_output_tokens
            }
        
        if format.lower() == "json":
            return json.dumps(config_data, indent=2)
        else:  # Default to YAML
            return yaml.dump(config_data, default_flow_style=False, indent=2)
    
    def validate_runtime_config(self) -> Dict[str, Any]:
        """Validate configuration at runtime and return status."""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required field mappings
        required_fields = ["summary", "description", "issue_type", "priority"]
        mappings = self.settings.get_jira_field_mappings()
        
        for field in required_fields:
            if field not in mappings or not mappings[field]:
                validation_results["errors"].append(f"Missing field mapping: {field}")
                validation_results["valid"] = False
        
        # Check feature flag consistency
        if self.settings.features.enable_ai_comments and not self.settings.gemini.api_key:
            validation_results["errors"].append("AI comments enabled but no Gemini API key configured")
            validation_results["valid"] = False
        
        if self.settings.features.enable_webhooks and self.settings.features.enable_polling:
            validation_results["warnings"].append("Both webhooks and polling are enabled")
        
        # Check quality rule thresholds
        if self.settings.quality_rules.high_quality_max_issues >= self.settings.quality_rules.medium_quality_max_issues:
            validation_results["warnings"].append("High quality threshold should be lower than medium quality threshold")
        
        return validation_results
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Get information about the current environment."""
        return {
            "environment": self.settings.app.environment,
            "debug_mode": self.settings.app.debug,
            "config_file": self.settings.config_path,
            "features_enabled": {
                name: getattr(self.settings.features, f"enable_{name}")
                for name in ["webhooks", "polling", "ai_comments", "status_transitions", "notifications", "metrics"]
            },
            "external_services": {
                "jira_url": self.settings.jira.base_url,
                "gemini_model": self.settings.gemini.model,
                "redis_url": self.settings.redis.url.split("@")[-1] if "@" in self.settings.redis.url else self.settings.redis.url
            }
        }


# Global config manager instance
config_manager = ConfigManager()


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    return config_manager
