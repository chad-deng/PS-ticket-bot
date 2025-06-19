"""
Configuration management for PS Ticket Process Bot.
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from pathlib import Path


class JiraConfig(BaseSettings):
    """JIRA configuration settings."""

    base_url: str = Field("https://example.atlassian.net", env="JIRA_BASE_URL")
    username: str = Field("dev@example.com", env="JIRA_USERNAME")
    api_token: str = Field("placeholder-token", env="JIRA_API_TOKEN")
    timeout: int = Field(30, env="JIRA_TIMEOUT")
    max_retries: int = Field(3, env="JIRA_MAX_RETRIES")
    retry_delay: float = Field(1.0, env="JIRA_RETRY_DELAY")
    verify_ssl: bool = Field(True, env="JIRA_VERIFY_SSL")

    model_config = {
        "extra": "ignore",
        "env_file": ".env",
        "case_sensitive": False,
        "env_file_encoding": "utf-8"
    }
    
    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("JIRA base URL must start with http:// or https://")
        return v.rstrip("/")


class GeminiConfig(BaseSettings):
    """Google Gemini API configuration settings."""

    api_key: str = Field("placeholder-gemini-key", env="GEMINI_API_KEY")
    model: str = Field("gemini-pro", env="GEMINI_MODEL")
    timeout: int = Field(30, env="GEMINI_TIMEOUT")
    max_retries: int = Field(3, env="GEMINI_MAX_RETRIES")
    retry_delay: float = Field(1.0, env="GEMINI_RETRY_DELAY")

    # Generation parameters
    temperature: float = Field(0.3, env="GEMINI_TEMPERATURE")
    top_p: float = Field(0.8, env="GEMINI_TOP_P")
    top_k: int = Field(40, env="GEMINI_TOP_K")
    max_output_tokens: int = Field(1024, env="GEMINI_MAX_OUTPUT_TOKENS")

    model_config = {"extra": "ignore", "env_file": ".env", "case_sensitive": False, "env_file_encoding": "utf-8"}
    
    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Temperature must be between 0.0 and 1.0")
        return v

    @field_validator("top_p")
    @classmethod
    def validate_top_p(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Top P must be between 0.0 and 1.0")
        return v


class QualityRulesConfig(BaseSettings):
    """Quality assessment rules configuration."""

    # Summary rules
    summary_min_length: int = Field(10, env="QUALITY_SUMMARY_MIN_LENGTH")
    summary_max_length: int = Field(255, env="QUALITY_SUMMARY_MAX_LENGTH")

    # Description rules
    description_min_length: int = Field(50, env="QUALITY_DESCRIPTION_MIN_LENGTH")
    description_max_length: int = Field(32767, env="QUALITY_DESCRIPTION_MAX_LENGTH")

    # Steps to reproduce rules
    steps_min_length: int = Field(20, env="QUALITY_STEPS_MIN_LENGTH")
    steps_required_for_bugs: bool = Field(True, env="QUALITY_STEPS_REQUIRED_FOR_BUGS")

    # Affected version rules
    affected_version_required: bool = Field(True, env="QUALITY_AFFECTED_VERSION_REQUIRED")

    # Attachment rules
    attachments_recommended_for_bugs: bool = Field(True, env="QUALITY_ATTACHMENTS_RECOMMENDED_FOR_BUGS")

    # High priority validation
    high_priority_enforce_all_rules: bool = Field(True, env="QUALITY_HIGH_PRIORITY_ENFORCE_ALL")
    high_priority_levels: List[str] = Field(["Blocker", "P1"], env="QUALITY_HIGH_PRIORITY_LEVELS")

    # Quality scoring thresholds
    high_quality_max_issues: int = Field(1, env="QUALITY_HIGH_MAX_ISSUES")
    medium_quality_max_issues: int = Field(3, env="QUALITY_MEDIUM_MAX_ISSUES")
    low_quality_min_issues: int = Field(4, env="QUALITY_LOW_MIN_ISSUES")

    model_config = {"extra": "ignore"}


class DatabaseConfig(BaseSettings):
    """Database configuration settings."""

    url: str = Field("sqlite:///./ps_ticket_bot.db", env="DATABASE_URL")
    echo: bool = Field(False, env="DATABASE_ECHO")
    pool_size: int = Field(5, env="DATABASE_POOL_SIZE")
    max_overflow: int = Field(10, env="DATABASE_MAX_OVERFLOW")
    pool_pre_ping: bool = Field(True, env="DATABASE_POOL_PRE_PING")
    pool_recycle: int = Field(3600, env="DATABASE_POOL_RECYCLE")

    model_config = {"extra": "ignore"}


class RedisConfig(BaseSettings):
    """Redis configuration settings."""

    url: str = Field("redis://localhost:6379", env="REDIS_URL")
    db: int = Field(0, env="REDIS_DB")
    decode_responses: bool = Field(True, env="REDIS_DECODE_RESPONSES")
    socket_timeout: int = Field(5, env="REDIS_SOCKET_TIMEOUT")
    socket_connect_timeout: int = Field(5, env="REDIS_SOCKET_CONNECT_TIMEOUT")
    retry_on_timeout: bool = Field(True, env="REDIS_RETRY_ON_TIMEOUT")
    max_connections: int = Field(50, env="REDIS_MAX_CONNECTIONS")

    model_config = {"extra": "ignore"}


class WebhookConfig(BaseSettings):
    """Webhook configuration settings."""

    secret: str = Field("dev-webhook-secret", env="JIRA_WEBHOOK_SECRET")
    verify_signature: bool = Field(True, env="WEBHOOK_VERIFY_SIGNATURE")
    timeout: int = Field(30, env="WEBHOOK_TIMEOUT")

    model_config = {"extra": "ignore"}


class SecurityConfig(BaseSettings):
    """Security configuration settings."""

    secret_key: str = Field("dev-secret-key", env="SECRET_KEY")
    algorithm: str = Field("HS256", env="SECURITY_ALGORITHM")
    access_token_expire_minutes: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    model_config = {"extra": "ignore"}


class FeatureFlagsConfig(BaseSettings):
    """Feature flags configuration."""

    enable_webhooks: bool = Field(True, env="ENABLE_WEBHOOKS")
    enable_polling: bool = Field(False, env="ENABLE_POLLING")
    enable_ai_comments: bool = Field(True, env="ENABLE_AI_COMMENTS")
    enable_status_transitions: bool = Field(True, env="ENABLE_STATUS_TRANSITIONS")
    enable_notifications: bool = Field(True, env="ENABLE_NOTIFICATIONS")
    enable_metrics: bool = Field(True, env="ENABLE_METRICS")
    enable_health_checks: bool = Field(True, env="ENABLE_HEALTH_CHECKS")

    model_config = {"extra": "ignore"}


class MonitoringConfig(BaseSettings):
    """Monitoring and observability configuration."""

    enable_prometheus: bool = Field(True, env="MONITORING_ENABLE_PROMETHEUS")
    prometheus_port: int = Field(8001, env="MONITORING_PROMETHEUS_PORT")
    health_check_interval: int = Field(30, env="MONITORING_HEALTH_CHECK_INTERVAL")
    metrics_prefix: str = Field("ps_ticket_bot", env="MONITORING_METRICS_PREFIX")

    # Alert thresholds
    error_rate_threshold: float = Field(0.05, env="MONITORING_ERROR_RATE_THRESHOLD")
    response_time_p95_threshold: float = Field(5.0, env="MONITORING_RESPONSE_TIME_P95_THRESHOLD")
    queue_depth_threshold: int = Field(1000, env="MONITORING_QUEUE_DEPTH_THRESHOLD")

    model_config = {"extra": "ignore"}


class AppConfig(BaseSettings):
    """Main application configuration."""

    name: str = Field("PS Ticket Process Bot", env="APP_NAME")
    version: str = Field("0.1.0", env="APP_VERSION")
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    reload: bool = Field(False, env="RELOAD")

    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT")

    model_config = {"extra": "ignore", "env_file": ".env", "case_sensitive": False}


class Settings:
    """Main settings class that loads all configurations."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize settings with optional config file path."""
        self.config_path = config_path or self._get_default_config_path()
        self._load_configurations()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path based on environment."""
        environment = os.getenv("ENVIRONMENT", "development")
        return f"config/environments/{environment}.yaml"
    
    def _load_configurations(self):
        """Load all configuration objects."""
        # Load environment variables from .env file FIRST
        from dotenv import load_dotenv
        load_dotenv(override=True)

        # Load environment-specific YAML config
        self.yaml_config = self._load_yaml_config()

        # Initialize Pydantic settings
        self.app = AppConfig()
        self.jira = JiraConfig()
        self.gemini = GeminiConfig()
        self.quality_rules = QualityRulesConfig()
        self.database = DatabaseConfig()
        self.redis = RedisConfig()
        self.webhook = WebhookConfig()
        self.security = SecurityConfig()
        self.features = FeatureFlagsConfig()
        self.monitoring = MonitoringConfig()
    
    def _load_yaml_config(self) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    return yaml.safe_load(f) or {}
            else:
                print(f"Warning: Configuration file {self.config_path} not found")
                return {}
        except Exception as e:
            print(f"Error loading configuration file {self.config_path}: {e}")
            return {}
    
    def get_jira_field_mappings(self) -> Dict[str, str]:
        """Get JIRA field mappings from YAML config."""
        jira_config = self.yaml_config.get("jira", {})
        fields = jira_config.get("fields", {})
        
        mappings = {}
        mappings.update(fields.get("standard", {}))
        mappings.update(fields.get("custom", {}))
        
        return mappings
    
    def get_jira_transitions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get JIRA transition mappings from YAML config."""
        jira_config = self.yaml_config.get("jira", {})
        return jira_config.get("transitions", {})
    
    def get_quality_rules(self) -> Dict[str, Any]:
        """Get quality rules from YAML config."""
        return self.yaml_config.get("quality_rules", {})
    
    def get_comment_templates(self) -> Dict[str, Any]:
        """Get comment generation templates from YAML config."""
        gemini_config = self.yaml_config.get("gemini", {})
        comment_config = gemini_config.get("comment_generation", {})
        return comment_config.get("templates", {})
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled."""
        return getattr(self.features, f"enable_{feature_name}", False)
    
    def get_environment_config(self, key: str, default: Any = None) -> Any:
        """Get environment-specific configuration value."""
        return self.yaml_config.get(key, default)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        # Load environment variables from .env file FIRST
        from dotenv import load_dotenv
        load_dotenv(override=True)  # Override existing env vars
        _settings = Settings()
    return _settings


def reload_settings(config_path: Optional[str] = None):
    """Reload settings with optional new config path."""
    global _settings
    _settings = None  # Clear the cache
    return get_settings()  # Force reload


def clear_settings_cache():
    """Clear the global settings cache to force reload."""
    global _settings
    _settings = None
