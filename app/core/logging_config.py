"""
Logging configuration for PS Ticket Process Bot.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Dict, Any
import structlog

from app.core.config import get_settings


def setup_logging() -> None:
    """
    Set up comprehensive logging configuration for the application.
    """
    settings = get_settings()
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure standard logging
    _configure_standard_logging(settings)
    
    # Configure structured logging
    _configure_structured_logging(settings)
    
    # Log startup information
    logger = structlog.get_logger(__name__)
    logger.info(
        "Logging configured",
        environment=settings.app.environment,
        log_level=settings.app.log_level,
        debug_mode=settings.app.debug
    )


def _configure_standard_logging(settings) -> None:
    """Configure standard Python logging."""
    
    # Set root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.app.log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.app.log_level.upper()))
    
    if settings.app.debug:
        console_handler.setFormatter(detailed_formatter)
    else:
        console_handler.setFormatter(simple_formatter)
    
    root_logger.addHandler(console_handler)
    
    # File handler for general logs
    file_handler = logging.handlers.RotatingFileHandler(
        filename=f"logs/{settings.app.environment}.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        filename=f"logs/{settings.app.environment}_errors.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # Set specific logger levels
    _configure_logger_levels()


def _configure_structured_logging(settings) -> None:
    """Configure structured logging with structlog."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.app.environment == "production" else structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _configure_logger_levels() -> None:
    """Configure specific logger levels to reduce noise."""
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("redis").setLevel(logging.WARNING)
    
    # Set application logger levels
    logging.getLogger("app").setLevel(logging.DEBUG)
    logging.getLogger("app.services").setLevel(logging.INFO)
    logging.getLogger("app.tasks").setLevel(logging.INFO)
    logging.getLogger("app.api").setLevel(logging.INFO)


class TicketProcessingLogger:
    """Specialized logger for ticket processing operations."""
    
    def __init__(self, ticket_key: str):
        """
        Initialize ticket processing logger.
        
        Args:
            ticket_key: JIRA ticket key for context
        """
        self.ticket_key = ticket_key
        self.logger = structlog.get_logger("app.ticket_processing")
        self.context = {"ticket_key": ticket_key}
    
    def log_ingestion(self, success: bool, **kwargs) -> None:
        """Log ticket ingestion."""
        self.logger.info(
            "Ticket ingestion",
            success=success,
            **self.context,
            **kwargs
        )
    
    def log_quality_assessment(self, quality_level: str, score: int, issues_count: int, **kwargs) -> None:
        """Log quality assessment."""
        self.logger.info(
            "Quality assessment completed",
            quality_level=quality_level,
            score=score,
            issues_count=issues_count,
            **self.context,
            **kwargs
        )
    
    def log_ai_comment_generation(self, success: bool, generated_by: str, **kwargs) -> None:
        """Log AI comment generation."""
        self.logger.info(
            "AI comment generation",
            success=success,
            generated_by=generated_by,
            **self.context,
            **kwargs
        )
    
    def log_comment_posting(self, success: bool, comment_id: str = None, **kwargs) -> None:
        """Log comment posting to JIRA."""
        self.logger.info(
            "Comment posting",
            success=success,
            comment_id=comment_id,
            **self.context,
            **kwargs
        )
    
    def log_status_transition(self, success: bool, from_status: str = None, to_status: str = None, **kwargs) -> None:
        """Log status transition."""
        self.logger.info(
            "Status transition",
            success=success,
            from_status=from_status,
            to_status=to_status,
            **self.context,
            **kwargs
        )
    
    def log_processing_complete(self, success: bool, processing_time: float, **kwargs) -> None:
        """Log completion of ticket processing."""
        self.logger.info(
            "Ticket processing completed",
            success=success,
            processing_time_seconds=processing_time,
            **self.context,
            **kwargs
        )
    
    def log_error(self, error: Exception, step: str, **kwargs) -> None:
        """Log processing error."""
        self.logger.error(
            "Ticket processing error",
            error=str(error),
            error_type=type(error).__name__,
            step=step,
            **self.context,
            **kwargs,
            exc_info=True
        )


class APILogger:
    """Specialized logger for API operations."""
    
    def __init__(self, endpoint: str):
        """
        Initialize API logger.
        
        Args:
            endpoint: API endpoint being called
        """
        self.endpoint = endpoint
        self.logger = structlog.get_logger("app.api")
        self.context = {"endpoint": endpoint}
    
    def log_request(self, method: str, **kwargs) -> None:
        """Log API request."""
        self.logger.info(
            "API request",
            method=method,
            **self.context,
            **kwargs
        )
    
    def log_response(self, status_code: int, response_time: float, **kwargs) -> None:
        """Log API response."""
        self.logger.info(
            "API response",
            status_code=status_code,
            response_time_ms=response_time * 1000,
            **self.context,
            **kwargs
        )
    
    def log_error(self, error: Exception, **kwargs) -> None:
        """Log API error."""
        self.logger.error(
            "API error",
            error=str(error),
            error_type=type(error).__name__,
            **self.context,
            **kwargs,
            exc_info=True
        )


class JiraLogger:
    """Specialized logger for JIRA operations."""
    
    def __init__(self):
        """Initialize JIRA logger."""
        self.logger = structlog.get_logger("app.services.jira")
    
    def log_api_call(self, operation: str, issue_key: str = None, success: bool = True, **kwargs) -> None:
        """Log JIRA API call."""
        self.logger.info(
            "JIRA API call",
            operation=operation,
            issue_key=issue_key,
            success=success,
            **kwargs
        )
    
    def log_webhook_received(self, event_type: str, issue_key: str, **kwargs) -> None:
        """Log webhook received."""
        self.logger.info(
            "JIRA webhook received",
            event_type=event_type,
            issue_key=issue_key,
            **kwargs
        )
    
    def log_rate_limit(self, retry_after: int = None, **kwargs) -> None:
        """Log rate limiting."""
        self.logger.warning(
            "JIRA rate limit encountered",
            retry_after=retry_after,
            **kwargs
        )


class GeminiLogger:
    """Specialized logger for Gemini API operations."""
    
    def __init__(self):
        """Initialize Gemini logger."""
        self.logger = structlog.get_logger("app.services.gemini")
    
    def log_api_call(self, operation: str, success: bool, response_time: float = None, **kwargs) -> None:
        """Log Gemini API call."""
        self.logger.info(
            "Gemini API call",
            operation=operation,
            success=success,
            response_time_seconds=response_time,
            **kwargs
        )
    
    def log_fallback_used(self, reason: str, **kwargs) -> None:
        """Log fallback comment generation."""
        self.logger.warning(
            "Gemini fallback used",
            reason=reason,
            **kwargs
        )
    
    def log_rate_limit(self, retry_after: int = None, **kwargs) -> None:
        """Log rate limiting."""
        self.logger.warning(
            "Gemini rate limit encountered",
            retry_after=retry_after,
            **kwargs
        )


class QueueLogger:
    """Specialized logger for queue operations."""
    
    def __init__(self):
        """Initialize queue logger."""
        self.logger = structlog.get_logger("app.queue")
    
    def log_task_queued(self, task_name: str, task_id: str, priority: str = None, **kwargs) -> None:
        """Log task queued."""
        self.logger.info(
            "Task queued",
            task_name=task_name,
            task_id=task_id,
            priority=priority,
            **kwargs
        )
    
    def log_task_started(self, task_name: str, task_id: str, **kwargs) -> None:
        """Log task started."""
        self.logger.info(
            "Task started",
            task_name=task_name,
            task_id=task_id,
            **kwargs
        )
    
    def log_task_completed(self, task_name: str, task_id: str, success: bool, duration: float, **kwargs) -> None:
        """Log task completed."""
        self.logger.info(
            "Task completed",
            task_name=task_name,
            task_id=task_id,
            success=success,
            duration_seconds=duration,
            **kwargs
        )
    
    def log_task_retry(self, task_name: str, task_id: str, attempt: int, **kwargs) -> None:
        """Log task retry."""
        self.logger.warning(
            "Task retry",
            task_name=task_name,
            task_id=task_id,
            attempt=attempt,
            **kwargs
        )


def get_ticket_logger(ticket_key: str) -> TicketProcessingLogger:
    """Get a ticket processing logger instance."""
    return TicketProcessingLogger(ticket_key)


def get_api_logger(endpoint: str) -> APILogger:
    """Get an API logger instance."""
    return APILogger(endpoint)


def get_jira_logger() -> JiraLogger:
    """Get a JIRA logger instance."""
    return JiraLogger()


def get_gemini_logger() -> GeminiLogger:
    """Get a Gemini logger instance."""
    return GeminiLogger()


def get_queue_logger() -> QueueLogger:
    """Get a queue logger instance."""
    return QueueLogger()


# Initialize logging when module is imported
setup_logging()
