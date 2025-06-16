"""
Tests for logging functionality.
"""

import pytest
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.logging_config import (
    TicketProcessingLogger,
    APILogger,
    JiraLogger,
    GeminiLogger,
    QueueLogger,
    setup_logging
)


client = TestClient(app)


class TestLoggingConfiguration:
    """Test cases for logging configuration."""
    
    def test_setup_logging(self):
        """Test logging setup."""
        # This should not raise any exceptions
        setup_logging()
        
        # Check that root logger is configured
        root_logger = logging.getLogger()
        assert root_logger.level <= logging.INFO
        assert len(root_logger.handlers) > 0
    
    def test_logger_levels(self):
        """Test that specific loggers have correct levels."""
        setup_logging()
        
        # Check application loggers
        app_logger = logging.getLogger("app")
        assert app_logger.level == logging.DEBUG
        
        # Check external library loggers are set to reduce noise
        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level == logging.WARNING


class TestTicketProcessingLogger:
    """Test cases for TicketProcessingLogger."""
    
    def test_initialization(self):
        """Test logger initialization."""
        logger = TicketProcessingLogger("TEST-123")
        
        assert logger.ticket_key == "TEST-123"
        assert logger.context["ticket_key"] == "TEST-123"
        assert logger.logger is not None
    
    def test_log_ingestion(self):
        """Test ingestion logging."""
        logger = TicketProcessingLogger("TEST-123")
        
        # This should not raise any exceptions
        logger.log_ingestion(True, source="webhook")
        logger.log_ingestion(False, error="API timeout")
    
    def test_log_quality_assessment(self):
        """Test quality assessment logging."""
        logger = TicketProcessingLogger("TEST-123")
        
        logger.log_quality_assessment("high", 95, 0)
        logger.log_quality_assessment("low", 30, 5, issues=["summary too short"])
    
    def test_log_ai_comment_generation(self):
        """Test AI comment generation logging."""
        logger = TicketProcessingLogger("TEST-123")
        
        logger.log_ai_comment_generation(True, "ai", response_time=2.5)
        logger.log_ai_comment_generation(False, "fallback", error="Rate limit")
    
    def test_log_comment_posting(self):
        """Test comment posting logging."""
        logger = TicketProcessingLogger("TEST-123")
        
        logger.log_comment_posting(True, "comment123")
        logger.log_comment_posting(False, error="Permission denied")
    
    def test_log_status_transition(self):
        """Test status transition logging."""
        logger = TicketProcessingLogger("TEST-123")
        
        logger.log_status_transition(True, "Open", "In Progress")
        logger.log_status_transition(False, error="Invalid transition")
    
    def test_log_processing_complete(self):
        """Test processing completion logging."""
        logger = TicketProcessingLogger("TEST-123")
        
        logger.log_processing_complete(True, 15.5, steps_completed=5)
        logger.log_processing_complete(False, 8.2, error="Quality assessment failed")
    
    def test_log_error(self):
        """Test error logging."""
        logger = TicketProcessingLogger("TEST-123")
        
        error = ValueError("Test error")
        logger.log_error(error, "quality_assessment", additional_info="test data")


class TestAPILogger:
    """Test cases for APILogger."""
    
    def test_initialization(self):
        """Test API logger initialization."""
        logger = APILogger("/api/test")
        
        assert logger.endpoint == "/api/test"
        assert logger.context["endpoint"] == "/api/test"
    
    def test_log_request(self):
        """Test request logging."""
        logger = APILogger("/api/test")
        
        logger.log_request("POST", user_id="user123", payload_size=1024)
    
    def test_log_response(self):
        """Test response logging."""
        logger = APILogger("/api/test")
        
        logger.log_response(200, 0.5, response_size=2048)
        logger.log_response(500, 1.2, error="Internal server error")
    
    def test_log_error(self):
        """Test API error logging."""
        logger = APILogger("/api/test")
        
        error = ConnectionError("Database connection failed")
        logger.log_error(error, request_id="req123")


class TestJiraLogger:
    """Test cases for JiraLogger."""
    
    def test_initialization(self):
        """Test JIRA logger initialization."""
        logger = JiraLogger()
        assert logger.logger is not None
    
    def test_log_api_call(self):
        """Test JIRA API call logging."""
        logger = JiraLogger()
        
        logger.log_api_call("get_issue", "TEST-123", True, response_time=1.5)
        logger.log_api_call("add_comment", "TEST-123", False, error="Permission denied")
    
    def test_log_webhook_received(self):
        """Test webhook logging."""
        logger = JiraLogger()
        
        logger.log_webhook_received("jira:issue_created", "TEST-123", user="test_user")
    
    def test_log_rate_limit(self):
        """Test rate limit logging."""
        logger = JiraLogger()
        
        logger.log_rate_limit(retry_after=60, endpoint="/rest/api/2/issue")


class TestGeminiLogger:
    """Test cases for GeminiLogger."""
    
    def test_initialization(self):
        """Test Gemini logger initialization."""
        logger = GeminiLogger()
        assert logger.logger is not None
    
    def test_log_api_call(self):
        """Test Gemini API call logging."""
        logger = GeminiLogger()
        
        logger.log_api_call("generate_comment", True, 3.2, tokens_used=150)
        logger.log_api_call("generate_comment", False, error="Rate limit exceeded")
    
    def test_log_fallback_used(self):
        """Test fallback logging."""
        logger = GeminiLogger()
        
        logger.log_fallback_used("API timeout", ticket_key="TEST-123")
    
    def test_log_rate_limit(self):
        """Test rate limit logging."""
        logger = GeminiLogger()
        
        logger.log_rate_limit(retry_after=120, quota_exceeded=True)


class TestQueueLogger:
    """Test cases for QueueLogger."""
    
    def test_initialization(self):
        """Test queue logger initialization."""
        logger = QueueLogger()
        assert logger.logger is not None
    
    def test_log_task_queued(self):
        """Test task queued logging."""
        logger = QueueLogger()
        
        logger.log_task_queued("process_ticket", "task123", "high", ticket_key="TEST-123")
    
    def test_log_task_started(self):
        """Test task started logging."""
        logger = QueueLogger()
        
        logger.log_task_started("process_ticket", "task123", worker="worker1")
    
    def test_log_task_completed(self):
        """Test task completed logging."""
        logger = QueueLogger()
        
        logger.log_task_completed("process_ticket", "task123", True, 15.5, result="success")
        logger.log_task_completed("process_ticket", "task456", False, 8.2, error="Timeout")
    
    def test_log_task_retry(self):
        """Test task retry logging."""
        logger = QueueLogger()
        
        logger.log_task_retry("process_ticket", "task123", 2, reason="API error")


class TestLoggingAPI:
    """Test cases for logging API endpoints."""
    
    @patch('app.api.logging_api.Path')
    def test_get_log_files_no_directory(self, mock_path):
        """Test getting log files when directory doesn't exist."""
        mock_path.return_value.exists.return_value = False
        
        response = client.get("/logs/logs")
        
        assert response.status_code == 200
        data = response.json()
        assert data["log_files"] == []
        assert "No logs directory found" in data["message"]
    
    @patch('app.api.logging_api.Path')
    def test_get_log_files_with_files(self, mock_path):
        """Test getting log files when files exist."""
        # Setup mock
        mock_log_file = Mock()
        mock_log_file.name = "development.log"
        mock_log_file.stat.return_value.st_size = 1024 * 1024  # 1MB
        mock_log_file.stat.return_value.st_mtime = 1640995200  # 2022-01-01
        
        mock_path.return_value.exists.return_value = True
        mock_path.return_value.glob.return_value = [mock_log_file]
        
        response = client.get("/logs/logs")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["log_files"]) == 1
        assert data["log_files"][0]["name"] == "development.log"
        assert data["log_files"][0]["size_mb"] == 1.0
    
    def test_get_log_content_not_found(self):
        """Test getting content from non-existent log file."""
        response = client.get("/logs/logs/nonexistent.log")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_get_log_content_invalid_path(self):
        """Test getting content with invalid path."""
        response = client.get("/logs/logs/../../../etc/passwd")
        
        assert response.status_code == 400
        assert "Invalid log file path" in response.json()["detail"]
    
    @patch('builtins.open')
    @patch('app.api.logging_api.Path')
    def test_get_log_content_success(self, mock_path, mock_open):
        """Test successful log content retrieval."""
        # Setup mocks
        mock_path.return_value.exists.return_value = True
        mock_path.return_value.resolve.return_value = Path("/app/logs/test.log")
        mock_path.return_value.__truediv__.return_value.resolve.return_value = Path("/app/logs/test.log")
        
        mock_open.return_value.__enter__.return_value.readlines.return_value = [
            "2024-01-01 10:00:00 - INFO - Test log line 1\n",
            "2024-01-01 10:01:00 - ERROR - Test log line 2\n",
            "2024-01-01 10:02:00 - INFO - Test log line 3\n"
        ]
        
        response = client.get("/logs/logs/test.log?lines=2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["log_file"] == "test.log"
        assert data["total_lines"] == 3
        assert data["returned_lines"] == 2
        assert len(data["content"]) == 2
    
    def test_get_logging_config(self):
        """Test getting logging configuration."""
        response = client.get("/logs/logging/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "app_config" in data
        assert "loggers" in data
        assert "root_logger" in data
    
    def test_set_log_level_invalid(self):
        """Test setting invalid log level."""
        response = client.post("/logs/logging/level?logger_name=app&level=INVALID")
        
        assert response.status_code == 400
        assert "Invalid log level" in response.json()["detail"]
    
    def test_set_log_level_valid(self):
        """Test setting valid log level."""
        response = client.post("/logs/logging/level?logger_name=app.test&level=DEBUG")
        
        assert response.status_code == 200
        data = response.json()
        assert data["logger_name"] == "app.test"
        assert data["new_level"] == "DEBUG"
    
    def test_get_logging_stats(self):
        """Test getting logging statistics."""
        response = client.get("/logs/logging/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "total_log_files" in data["stats"]
