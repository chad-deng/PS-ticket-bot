"""
Tests for JIRA operations API endpoints.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.jira_client import JiraAPIError


client = TestClient(app)


class TestJiraOperationsAPI:
    """Test cases for JIRA operations API endpoints."""
    
    @patch('app.api.jira_operations.get_jira_client')
    async def test_add_comment_success(self, mock_get_client):
        """Test successful comment addition."""
        # Setup mock
        mock_client = Mock()
        mock_client.add_comment = AsyncMock(return_value={
            "id": "comment123",
            "created": "2024-01-01T10:00:00.000+0000",
            "author": {"displayName": "PS Bot"}
        })
        mock_get_client.return_value = mock_client
        
        # Test the endpoint
        response = client.post(
            "/jira/comment/TEST-123",
            json="This is a test comment"
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["comment_id"] == "comment123"
        assert data["issue_key"] == "TEST-123"
    
    def test_add_comment_empty_body(self):
        """Test comment addition with empty body."""
        response = client.post(
            "/jira/comment/TEST-123",
            json=""
        )
        
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]
    
    def test_add_comment_too_long(self):
        """Test comment addition with body too long."""
        long_comment = "x" * 32768  # Exceeds JIRA limit
        
        response = client.post(
            "/jira/comment/TEST-123",
            json=long_comment
        )
        
        assert response.status_code == 400
        assert "exceeds maximum length" in response.json()["detail"]
    
    @patch('app.api.jira_operations.get_jira_client')
    async def test_add_comment_not_found(self, mock_get_client):
        """Test comment addition for non-existent ticket."""
        # Setup mock to raise 404 error
        mock_client = Mock()
        mock_client.add_comment = AsyncMock(side_effect=JiraAPIError("Not found", 404))
        mock_get_client.return_value = mock_client
        
        response = client.post(
            "/jira/comment/NONEXISTENT-123",
            json="Test comment"
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.api.jira_operations.get_jira_client')
    async def test_transition_ticket_success(self, mock_get_client):
        """Test successful ticket transition."""
        # Setup mocks
        mock_ticket = Mock()
        mock_ticket.status.value = "In Progress"
        
        mock_client = Mock()
        mock_client.transition_issue = AsyncMock(return_value={"success": True})
        mock_client.get_issue_sync.return_value = mock_ticket
        mock_get_client.return_value = mock_client
        
        # Test the endpoint
        response = client.post(
            "/jira/transition/TEST-123",
            json={"transition_id": "11"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["issue_key"] == "TEST-123"
        assert data["new_status"] == "In Progress"
    
    @patch('app.api.jira_operations.get_jira_client')
    async def test_transition_ticket_with_comment(self, mock_get_client):
        """Test ticket transition with comment."""
        # Setup mocks
        mock_ticket = Mock()
        mock_ticket.status.value = "In Progress"
        
        mock_client = Mock()
        mock_client.add_comment = AsyncMock(return_value={"id": "comment456"})
        mock_client.transition_issue = AsyncMock(return_value={"success": True})
        mock_client.get_issue_sync.return_value = mock_ticket
        mock_get_client.return_value = mock_client
        
        # Test the endpoint
        response = client.post(
            "/jira/transition/TEST-123",
            json={
                "transition_id": "11",
                "comment": "Transitioning to In Progress"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["comment_id"] == "comment456"
    
    def test_transition_ticket_empty_id(self):
        """Test transition with empty transition ID."""
        response = client.post(
            "/jira/transition/TEST-123",
            json={"transition_id": ""}
        )
        
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]
    
    @patch('app.api.jira_operations.get_jira_client')
    async def test_get_available_transitions(self, mock_get_client):
        """Test getting available transitions."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_available_transitions = AsyncMock(return_value=[
            {
                "id": "11",
                "name": "Start Progress",
                "to": {"id": "3", "name": "In Progress"}
            },
            {
                "id": "21",
                "name": "Resolve Issue",
                "to": {"id": "5", "name": "Resolved"}
            }
        ])
        mock_get_client.return_value = mock_client
        
        # Test the endpoint
        response = client.get("/jira/transitions/TEST-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["issue_key"] == "TEST-123"
        assert data["count"] == 2
        assert len(data["transitions"]) == 2
        assert data["transitions"][0]["id"] == "11"
        assert data["transitions"][0]["name"] == "Start Progress"
        assert data["transitions"][0]["to_status"] == "In Progress"
    
    @patch('app.api.jira_operations.get_jira_client')
    def test_get_ticket_info(self, mock_get_client):
        """Test getting ticket information."""
        # Setup mock
        mock_ticket = Mock()
        mock_ticket.to_dict.return_value = {
            "key": "TEST-123",
            "summary": "Test issue",
            "issue_type": "Bug",
            "priority": "High"
        }
        mock_ticket.has_attachments = True
        mock_ticket.is_high_priority = True
        mock_ticket.is_bug = True
        mock_ticket.attachments = [Mock(), Mock()]  # 2 attachments
        
        mock_client = Mock()
        mock_client.get_issue_sync.return_value = mock_ticket
        mock_get_client.return_value = mock_client
        
        # Test the endpoint
        response = client.get("/jira/ticket/TEST-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ticket"]["key"] == "TEST-123"
        assert data["metadata"]["has_attachments"] is True
        assert data["metadata"]["is_high_priority"] is True
        assert data["metadata"]["attachment_count"] == 2
    
    @patch('app.api.jira_operations.get_jira_client')
    @patch('app.api.jira_operations.get_config_manager')
    @patch('app.api.jira_operations.get_queue_manager')
    def test_process_ticket_manually(self, mock_get_queue, mock_get_config, mock_get_jira):
        """Test manual ticket processing."""
        # Setup mocks
        mock_ticket = Mock()
        mock_ticket.issue_type.value = "Bug"
        mock_ticket.summary = "Test issue"
        mock_ticket.priority.value = "High"
        mock_ticket.status.value = "Open"
        
        mock_jira = Mock()
        mock_jira.get_issue_sync.return_value = mock_ticket
        mock_get_jira.return_value = mock_jira
        
        mock_config = Mock()
        mock_config.should_process_issue_type.return_value = True
        mock_get_config.return_value = mock_config
        
        mock_queue = Mock()
        mock_queue.queue_ticket_processing.return_value = "task-123"
        mock_get_queue.return_value = mock_queue
        
        # Test the endpoint
        response = client.post("/jira/process/TEST-123")
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["issue_key"] == "TEST-123"
        assert data["task_id"] == "task-123"
    
    def test_process_ticket_invalid_issue_type(self):
        """Test manual processing with invalid issue type."""
        with patch('app.api.jira_operations.get_jira_client') as mock_get_jira:
            with patch('app.api.jira_operations.get_config_manager') as mock_get_config:
                # Setup mocks
                mock_ticket = Mock()
                mock_ticket.issue_type.value = "Epic"
                
                mock_jira = Mock()
                mock_jira.get_issue_sync.return_value = mock_ticket
                mock_get_jira.return_value = mock_jira
                
                mock_config = Mock()
                mock_config.should_process_issue_type.return_value = False
                mock_get_config.return_value = mock_config
                
                # Test the endpoint
                response = client.post("/jira/process/TEST-123")
                
                assert response.status_code == 400
                assert "not configured for processing" in response.json()["detail"]
    
    @patch('httpx.AsyncClient')
    async def test_jira_connection_success(self, mock_client):
        """Test successful JIRA connection test."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "displayName": "PS Bot",
            "accountId": "bot123",
            "emailAddress": "bot@company.com"
        }
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        # Test the endpoint
        response = client.get("/jira/test/connection")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["test_results"]["connection"] is True
        assert data["test_results"]["authentication"] is True
    
    @patch('httpx.AsyncClient')
    async def test_jira_connection_auth_failure(self, mock_client):
        """Test JIRA connection test with authentication failure."""
        # Setup mock response for auth failure
        mock_response = Mock()
        mock_response.status_code = 401
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        # Test the endpoint
        response = client.get("/jira/test/connection")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["test_results"]["connection"] is True
        assert data["test_results"]["authentication"] is False
    
    @patch('httpx.AsyncClient')
    async def test_jira_connection_network_failure(self, mock_client):
        """Test JIRA connection test with network failure."""
        # Setup mock to raise exception
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("Connection timeout")
        )
        
        # Test the endpoint
        response = client.get("/jira/test/connection")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "Connection timeout" in str(data["test_results"]["errors"])
