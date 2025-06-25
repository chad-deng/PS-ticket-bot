"""
Tests for queue functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.queue import QueueManager, get_queue_manager
from app.tasks.ticket_processor import process_ticket, assess_quality, generate_comment


client = TestClient(app)


class TestQueueManager:
    """Test cases for QueueManager."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('app.core.queue.get_settings') as mock_settings:
            mock_settings.return_value.redis.url = "redis://redis:6379"
            mock_settings.return_value.redis.db = 0
            mock_settings.return_value.redis.decode_responses = True
            mock_settings.return_value.redis.socket_timeout = 5
            mock_settings.return_value.redis.socket_connect_timeout = 5
            mock_settings.return_value.redis.retry_on_timeout = True
            mock_settings.return_value.redis.max_connections = 50
            yield mock_settings.return_value
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch('app.core.queue.redis.from_url') as mock_redis:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.llen.return_value = 5
            mock_redis.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def mock_celery(self):
        """Mock Celery app."""
        with patch('app.core.queue.create_celery_app') as mock_celery:
            mock_app = Mock()
            mock_app.control.inspect.return_value.active.return_value = {"worker1": []}
            mock_app.control.inspect.return_value.stats.return_value = {"worker1": {}}
            mock_celery.return_value = mock_app
            yield mock_app
    
    def test_queue_manager_initialization(self, mock_settings, mock_redis, mock_celery):
        """Test QueueManager initialization."""
        queue_manager = QueueManager()
        
        assert queue_manager.settings is not None
        assert queue_manager.redis_client is not None
        assert queue_manager.celery_app is not None
    
    @patch('app.tasks.ticket_processor.process_ticket.apply_async')
    def test_queue_ticket_processing(self, mock_apply_async, mock_settings, mock_redis, mock_celery):
        """Test queuing a ticket for processing."""
        # Setup mock
        mock_result = Mock()
        mock_result.id = "test-task-id-123"
        mock_apply_async.return_value = mock_result
        
        queue_manager = QueueManager()
        
        # Test queuing
        task_id = queue_manager.queue_ticket_processing("SUPPORT-123", "jira:issue_created", "high")
        
        assert task_id == "test-task-id-123"
        mock_apply_async.assert_called_once()
        
        # Check call arguments
        call_args = mock_apply_async.call_args
        assert call_args[1]["args"] == ["SUPPORT-123", "jira:issue_created"]
        assert call_args[1]["priority"] == 9  # High priority
        assert call_args[1]["queue"] == "ticket_processing"
    
    def test_get_queue_stats(self, mock_settings, mock_redis, mock_celery):
        """Test getting queue statistics."""
        queue_manager = QueueManager()
        
        stats = queue_manager.get_queue_stats()
        
        assert "queue_lengths" in stats
        assert "active_tasks" in stats
        assert "worker_count" in stats
        assert "redis_connected" in stats
        assert "celery_connected" in stats
        
        # Check Redis connection check
        assert stats["redis_connected"] is True
    
    def test_redis_connection_check(self, mock_settings, mock_redis, mock_celery):
        """Test Redis connection health check."""
        queue_manager = QueueManager()
        
        # Test successful connection
        assert queue_manager._check_redis_connection() is True
        
        # Test failed connection
        mock_redis.ping.side_effect = Exception("Connection failed")
        assert queue_manager._check_redis_connection() is False
    
    def test_purge_queues(self, mock_settings, mock_redis, mock_celery):
        """Test queue purging functionality."""
        queue_manager = QueueManager()
        
        # Setup mock
        mock_redis.llen.return_value = 10
        mock_redis.delete.return_value = True
        
        # Test purging
        result = queue_manager.purge_queues(["ticket_processing"])
        
        assert "ticket_processing" in result
        assert result["ticket_processing"] == 10
        
        # Verify Redis operations
        mock_redis.llen.assert_called()
        mock_redis.delete.assert_called()


class TestTicketProcessorTasks:
    """Test cases for ticket processor tasks."""
    
    @pytest.fixture
    def mock_ticket_data(self):
        """Mock ticket data for testing."""
        return {
            "key": "SUPPORT-123",
            "id": "12345",
            "summary": "Test issue summary",
            "description": "Test issue description with sufficient length to pass validation",
            "issue_type": "Bug",
            "priority": "High",
            "status": "Open",
            "steps_to_reproduce": "Step 1: Do something\nStep 2: See error",
            "affected_version": "1.0.0",
            "has_attachments": True
        }
    
    @patch('app.tasks.ticket_processor.get_jira_client')
    @patch('app.tasks.ticket_processor.get_config_manager')
    def test_process_ticket_success(self, mock_config_manager, mock_jira_client, mock_ticket_data):
        """Test successful ticket processing."""
        # Setup mocks
        mock_ticket = Mock()
        mock_ticket.issue_type.value = "Bug"
        mock_ticket.dict.return_value = mock_ticket_data
        
        mock_jira_client.return_value.get_issue_sync.return_value = mock_ticket
        mock_config_manager.return_value.should_process_issue_type.return_value = True
        mock_config_manager.return_value.settings.features.enable_ai_comments = True
        mock_config_manager.return_value.settings.features.enable_status_transitions = True
        
        # Mock task dependencies
        with patch('app.tasks.ticket_processor.assess_quality.delay') as mock_assess:
            with patch('app.tasks.ticket_processor.generate_comment.delay') as mock_generate:
                with patch('app.tasks.ticket_processor.post_comment.delay') as mock_post:
                    with patch('app.tasks.ticket_processor.transition_ticket.delay') as mock_transition:
                        
                        # Setup task results
                        mock_assess.return_value.get.return_value = {
                            "success": True,
                            "assessment": {"overall_quality": "high", "issues_found": []},
                            "quality_level": "high"
                        }
                        
                        mock_generate.return_value.get.return_value = {
                            "success": True,
                            "comment": "Test comment"
                        }
                        
                        mock_post.return_value.get.return_value = {
                            "success": True,
                            "comment_id": "comment123"
                        }
                        
                        mock_transition.return_value.get.return_value = {
                            "success": True,
                            "new_status": "In Progress"
                        }
                        
                        # Test the task
                        result = process_ticket("SUPPORT-123", "jira:issue_created")
                        
                        assert result["success"] is True
                        assert result["ticket_key"] == "SUPPORT-123"
                        assert result["ingested"] is True
                        assert result["quality_assessed"] is True
                        assert result["comment_generated"] is True
                        assert result["comment_posted"] is True
                        assert result["status_transitioned"] is True
    
    def test_assess_quality_high_quality(self, mock_ticket_data):
        """Test quality assessment for high-quality ticket."""
        # Modify ticket data to be high quality
        mock_ticket_data.update({
            "summary": "Clear and descriptive summary of the issue",
            "description": "Detailed description with all necessary information about the problem",
            "steps_to_reproduce": "1. Open application\n2. Click button\n3. Observe error",
            "affected_version": "2.1.0"
        })
        
        result = assess_quality(mock_ticket_data)
        
        assert result["success"] is True
        assert result["quality_level"] == "high"
        assert len(result["assessment"]["issues_found"]) <= 1
    
    def test_assess_quality_low_quality(self, mock_ticket_data):
        """Test quality assessment for low-quality ticket."""
        # Modify ticket data to be low quality
        mock_ticket_data.update({
            "summary": "Bug",  # Too short
            "description": "It's broken",  # Too short
            "steps_to_reproduce": "",  # Missing
            "affected_version": ""  # Missing
        })
        
        result = assess_quality(mock_ticket_data)
        
        assert result["success"] is True
        assert result["quality_level"] == "low"
        assert len(result["assessment"]["issues_found"]) >= 4
    
    def test_generate_comment_high_quality(self, mock_ticket_data):
        """Test comment generation for high-quality ticket."""
        quality_assessment = {
            "overall_quality": "high",
            "issues_found": []
        }
        
        result = generate_comment(mock_ticket_data, quality_assessment)
        
        assert result["success"] is True
        assert "well-detailed" in result["comment"]
        assert "begin working" in result["comment"]
    
    def test_generate_comment_low_quality(self, mock_ticket_data):
        """Test comment generation for low-quality ticket."""
        quality_assessment = {
            "overall_quality": "low",
            "issues_found": [
                "Summary is too short",
                "Description is missing",
                "Steps to reproduce are missing"
            ]
        }
        
        result = generate_comment(mock_ticket_data, quality_assessment)
        
        assert result["success"] is True
        assert "additional information" in result["comment"]
        assert "Summary is too short" in result["comment"]


class TestAdminAPI:
    """Test cases for admin API endpoints."""
    
    @patch('app.api.admin.get_queue_manager')
    def test_queue_stats_endpoint(self, mock_get_queue_manager):
        """Test queue statistics endpoint."""
        # Setup mock
        mock_queue_manager = Mock()
        mock_queue_manager.get_queue_stats.return_value = {
            "queue_lengths": {"ticket_processing": 5},
            "active_tasks": 2,
            "worker_count": 1,
            "redis_connected": True,
            "celery_connected": True
        }
        mock_get_queue_manager.return_value = mock_queue_manager
        
        response = client.get("/admin/queue/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "stats" in data
        assert data["stats"]["queue_lengths"]["ticket_processing"] == 5
    
    @patch('app.api.admin.get_queue_manager')
    def test_queue_health_endpoint_healthy(self, mock_get_queue_manager):
        """Test queue health endpoint when healthy."""
        # Setup mock
        mock_queue_manager = Mock()
        mock_queue_manager.get_queue_stats.return_value = {
            "redis_connected": True,
            "celery_connected": True,
            "queue_lengths": {},
            "active_tasks": 0,
            "worker_count": 1
        }
        mock_get_queue_manager.return_value = mock_queue_manager
        
        response = client.get("/admin/queue/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis_connected"] is True
        assert data["celery_connected"] is True
    
    @patch('app.api.admin.get_queue_manager')
    def test_queue_health_endpoint_unhealthy(self, mock_get_queue_manager):
        """Test queue health endpoint when unhealthy."""
        # Setup mock
        mock_queue_manager = Mock()
        mock_queue_manager.get_queue_stats.return_value = {
            "redis_connected": False,
            "celery_connected": False,
            "queue_lengths": {},
            "active_tasks": 0,
            "worker_count": 0
        }
        mock_get_queue_manager.return_value = mock_queue_manager
        
        response = client.get("/admin/queue/health")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["redis_connected"] is False
        assert data["celery_connected"] is False
    
    def test_get_configuration_endpoint(self):
        """Test configuration endpoint."""
        response = client.get("/admin/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "features" in data
        assert "jira" in data
        assert "gemini" in data
        assert "queue" in data
    
    @patch('app.api.admin.get_settings')
    @patch('app.api.admin.get_queue_manager')
    def test_purge_queues_development(self, mock_get_queue_manager, mock_get_settings):
        """Test queue purging in development environment."""
        # Setup mocks
        mock_settings = Mock()
        mock_settings.app.environment = "development"
        mock_get_settings.return_value = mock_settings
        
        mock_queue_manager = Mock()
        mock_queue_manager.purge_queues.return_value = {"ticket_processing": 5}
        mock_get_queue_manager.return_value = mock_queue_manager
        
        response = client.post("/admin/queue/purge")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["purged_queues"]["ticket_processing"] == 5
    
    @patch('app.api.admin.get_settings')
    def test_purge_queues_production_forbidden(self, mock_get_settings):
        """Test queue purging forbidden in production."""
        # Setup mock
        mock_settings = Mock()
        mock_settings.app.environment = "production"
        mock_get_settings.return_value = mock_settings
        
        response = client.post("/admin/queue/purge")
        
        assert response.status_code == 403
        assert "not allowed in production" in response.json()["detail"]
