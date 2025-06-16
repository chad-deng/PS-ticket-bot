"""
Tests for JIRA integration functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.ticket import JiraTicket, JiraUser, IssueType, Priority, TicketStatus, WebhookEvent
from app.services.jira_client import JiraClient, JiraAPIError


client = TestClient(app)


class TestJiraClient:
    """Test cases for JiraClient."""
    
    @pytest.fixture
    def mock_jira_response(self):
        """Mock JIRA API response data."""
        return {
            "key": "SUPPORT-123",
            "id": "12345",
            "fields": {
                "summary": "Test issue summary",
                "description": "Test issue description",
                "issuetype": {"name": "Bug"},
                "priority": {"name": "High"},
                "status": {"name": "Open"},
                "reporter": {
                    "accountId": "user123",
                    "displayName": "Test User",
                    "emailAddress": "test@example.com",
                    "active": True
                },
                "assignee": None,
                "created": "2024-01-01T10:00:00.000+0000",
                "updated": "2024-01-01T10:00:00.000+0000",
                "project": {
                    "key": "SUPPORT",
                    "name": "Product Support"
                },
                "attachment": []
            }
        }
    
    @pytest.fixture
    def jira_client(self):
        """Create JiraClient instance for testing."""
        with patch('app.services.jira_client.get_settings') as mock_settings:
            mock_settings.return_value.jira.base_url = "https://test.atlassian.net"
            mock_settings.return_value.jira.username = "test_user"
            mock_settings.return_value.jira.api_token = "test_token"
            mock_settings.return_value.jira.timeout = 30
            mock_settings.return_value.jira.max_retries = 3
            mock_settings.return_value.jira.retry_delay = 1
            
            with patch('app.services.jira_client.get_config_manager') as mock_config:
                mock_config.return_value.get_jira_field_mappings.return_value = {
                    "summary": "summary",
                    "description": "description",
                    "steps_to_reproduce": "customfield_10001",
                    "affected_version": "customfield_10002"
                }
                
                return JiraClient()
    
    def test_parse_issue_data(self, jira_client, mock_jira_response):
        """Test parsing JIRA API response into JiraTicket model."""
        ticket = jira_client._parse_issue_data(mock_jira_response)
        
        assert isinstance(ticket, JiraTicket)
        assert ticket.key == "SUPPORT-123"
        assert ticket.id == "12345"
        assert ticket.summary == "Test issue summary"
        assert ticket.description == "Test issue description"
        assert ticket.issue_type == IssueType.BUG
        assert ticket.priority == Priority.HIGH
        assert ticket.status == TicketStatus.OPEN
        assert ticket.reporter.display_name == "Test User"
        assert ticket.assignee is None
        assert ticket.project_key == "SUPPORT"
        assert ticket.project_name == "Product Support"
        assert not ticket.has_attachments
    
    @patch('httpx.AsyncClient')
    async def test_get_issue_success(self, mock_client, jira_client, mock_jira_response):
        """Test successful issue retrieval."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_jira_response
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        # Test
        ticket = await jira_client.get_issue("SUPPORT-123")
        
        assert isinstance(ticket, JiraTicket)
        assert ticket.key == "SUPPORT-123"
    
    @patch('httpx.AsyncClient')
    async def test_get_issue_not_found(self, mock_client, jira_client):
        """Test issue not found error."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 404
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        # Test
        with pytest.raises(JiraAPIError) as exc_info:
            await jira_client.get_issue("SUPPORT-999")
        
        assert "not found" in str(exc_info.value)
        assert exc_info.value.status_code == 404
    
    @patch('requests.get')
    def test_get_issue_sync(self, mock_get, jira_client, mock_jira_response):
        """Test synchronous issue retrieval."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_jira_response
        
        mock_get.return_value = mock_response
        
        # Test
        ticket = jira_client.get_issue_sync("SUPPORT-123")
        
        assert isinstance(ticket, JiraTicket)
        assert ticket.key == "SUPPORT-123"
    
    @patch('httpx.AsyncClient')
    async def test_add_comment_success(self, mock_client, jira_client):
        """Test successful comment addition."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "comment123"}
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        # Test
        result = await jira_client.add_comment("SUPPORT-123", "Test comment")
        
        assert result["id"] == "comment123"
    
    @patch('httpx.AsyncClient')
    async def test_transition_issue_success(self, mock_client, jira_client):
        """Test successful issue transition."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 204
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        # Test
        result = await jira_client.transition_issue("SUPPORT-123", "11")
        
        assert result["success"] is True


class TestWebhookEndpoints:
    """Test cases for webhook endpoints."""
    
    def test_webhook_test_endpoint(self):
        """Test webhook test endpoint."""
        response = client.get("/webhook/jira/test")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "webhook_config" in data
        assert "jira_config" in data
    
    @patch('app.api.webhooks.verify_webhook_signature')
    @patch('app.api.webhooks.should_process_webhook')
    def test_jira_webhook_success(self, mock_should_process, mock_verify_sig):
        """Test successful webhook processing."""
        # Setup mocks
        mock_verify_sig.return_value = True
        mock_should_process.return_value = True
        
        # Webhook payload
        webhook_payload = {
            "webhookEvent": "jira:issue_created",
            "issue_event_type_name": "issue_created",
            "issue": {
                "key": "SUPPORT-123",
                "id": "12345",
                "fields": {
                    "project": {"key": "SUPPORT"},
                    "issuetype": {"name": "Bug"}
                }
            },
            "user": {
                "accountId": "user123",
                "displayName": "Test User"
            }
        }
        
        response = client.post("/webhook/jira", json=webhook_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["issue_key"] == "SUPPORT-123"
    
    @patch('app.api.webhooks.verify_webhook_signature')
    def test_jira_webhook_invalid_signature(self, mock_verify_sig):
        """Test webhook with invalid signature."""
        mock_verify_sig.return_value = False
        
        webhook_payload = {
            "webhookEvent": "jira:issue_created",
            "issue": {"key": "SUPPORT-123"}
        }
        
        response = client.post("/webhook/jira", json=webhook_payload)
        
        assert response.status_code == 401
    
    @patch('app.api.webhooks.verify_webhook_signature')
    @patch('app.api.webhooks.should_process_webhook')
    def test_jira_webhook_ignored_event(self, mock_should_process, mock_verify_sig):
        """Test webhook event that should be ignored."""
        mock_verify_sig.return_value = True
        mock_should_process.return_value = False
        
        webhook_payload = {
            "webhookEvent": "jira:issue_created",
            "issue": {"key": "OTHER-123"}
        }
        
        response = client.post("/webhook/jira", json=webhook_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
    
    def test_jira_webhook_invalid_json(self):
        """Test webhook with invalid JSON."""
        response = client.post(
            "/webhook/jira",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
    
    @patch('app.services.jira_client.JiraClient.get_issue_sync')
    def test_manual_process_ticket_success(self, mock_get_issue):
        """Test manual ticket processing endpoint."""
        # Setup mock
        mock_ticket = Mock()
        mock_ticket.issue_type.value = "Bug"
        mock_ticket.summary = "Test issue"
        mock_ticket.priority.value = "High"
        mock_ticket.status.value = "Open"
        mock_get_issue.return_value = mock_ticket
        
        with patch('app.utils.config_manager.get_config_manager') as mock_config:
            mock_config.return_value.should_process_issue_type.return_value = True
            
            response = client.post("/webhook/jira/manual?issue_key=SUPPORT-123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "accepted"
            assert data["issue_key"] == "SUPPORT-123"
    
    def test_manual_process_ticket_invalid_key(self):
        """Test manual processing with invalid issue key."""
        response = client.post("/webhook/jira/manual?issue_key=invalid")
        
        assert response.status_code == 400


class TestWebhookEvent:
    """Test cases for WebhookEvent model."""
    
    def test_webhook_event_creation(self):
        """Test WebhookEvent model creation."""
        event_data = {
            "timestamp": datetime.utcnow(),
            "webhook_event": "jira:issue_created",
            "issue_event_type_name": "issue_created",
            "issue": {
                "key": "SUPPORT-123",
                "id": "12345"
            }
        }
        
        event = WebhookEvent(**event_data)
        
        assert event.webhook_event == "jira:issue_created"
        assert event.issue_key == "SUPPORT-123"
        assert event.issue_id == "12345"
        assert event.is_issue_created is True
        assert event.is_issue_updated is False
    
    def test_webhook_event_properties(self):
        """Test WebhookEvent properties."""
        event = WebhookEvent(
            timestamp=datetime.utcnow(),
            webhook_event="jira:issue_updated",
            issue={"key": "SUPPORT-456", "id": "67890"}
        )
        
        assert event.is_issue_created is False
        assert event.is_issue_updated is True
        assert event.issue_key == "SUPPORT-456"
        assert event.issue_id == "67890"
