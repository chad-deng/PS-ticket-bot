"""
Tests for AI comment generation functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.gemini_client import GeminiClient, GeminiAPIError, get_gemini_client
from app.models.ticket import JiraTicket, JiraUser, IssueType, Priority, TicketStatus, QualityAssessment, QualityLevel


client = TestClient(app)


class TestGeminiClient:
    """Test cases for GeminiClient."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('app.services.gemini_client.get_settings') as mock_settings:
            mock_settings.return_value.gemini.api_key = "test_api_key"
            mock_settings.return_value.gemini.model = "gemini-pro"
            mock_settings.return_value.gemini.temperature = 0.3
            mock_settings.return_value.gemini.top_p = 0.8
            mock_settings.return_value.gemini.top_k = 40
            mock_settings.return_value.gemini.max_output_tokens = 1024
            mock_settings.return_value.gemini.timeout = 30
            mock_settings.return_value.gemini.max_retries = 3
            mock_settings.return_value.gemini.retry_delay = 1
            yield mock_settings.return_value
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock config manager for testing."""
        with patch('app.services.gemini_client.get_config_manager') as mock_config:
            mock_config.return_value.settings.yaml_config = {
                "gemini": {
                    "comment_generation": {
                        "prompts": {
                            "system_prompt": "You are a helpful JIRA assistant.",
                            "user_prompt_template": "Analyze this ticket: {summary}"
                        }
                    }
                }
            }
            mock_config.return_value.get_comment_templates.return_value = {
                "high_quality": {
                    "greeting": "Thank you for the detailed ticket.",
                    "body": "We'll investigate this.",
                    "closing": "We'll keep you updated."
                },
                "medium_quality": {
                    "greeting": "Thank you for the ticket.",
                    "body": "Please provide more information:",
                    "closing": "We'll proceed once we have this."
                },
                "low_quality": {
                    "greeting": "Thank you for the ticket.",
                    "body": "We need additional information:",
                    "closing": "Please update the ticket."
                }
            }
            yield mock_config.return_value
    
    @pytest.fixture
    def sample_ticket(self):
        """Create a sample ticket for testing."""
        return JiraTicket(
            key="TEST-123",
            id="12345",
            summary="Test issue summary",
            description="Test issue description",
            issue_type=IssueType.BUG,
            priority=Priority.MEDIUM,
            status=TicketStatus.OPEN,
            reporter=JiraUser(account_id="user123", display_name="Test User"),
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            steps_to_reproduce="1. Do something\n2. See error",
            affected_version="1.0.0",
            project_key="TEST",
            project_name="Test Project"
        )
    
    @pytest.fixture
    def sample_assessment(self):
        """Create a sample quality assessment."""
        return QualityAssessment(
            ticket_key="TEST-123",
            overall_quality=QualityLevel.MEDIUM,
            issues_found=["Description could be more detailed"],
            score=75,
            assessed_at=datetime.utcnow()
        )
    
    def test_client_initialization(self, mock_settings, mock_config_manager):
        """Test GeminiClient initialization."""
        client = GeminiClient()
        
        assert client.api_key == "test_api_key"
        assert client.model == "gemini-pro"
        assert client.temperature == 0.3
        assert client.max_output_tokens == 1024
    
    def test_construct_prompt(self, mock_settings, mock_config_manager, sample_ticket, sample_assessment):
        """Test prompt construction."""
        client = GeminiClient()
        prompt = client._construct_prompt(sample_ticket, sample_assessment)
        
        assert "You are a helpful JIRA assistant." in prompt
        assert "TEST-123" in prompt
        assert "Test issue summary" in prompt
        assert "medium" in prompt.lower()
    
    @patch('httpx.AsyncClient')
    async def test_call_gemini_api_success(self, mock_client, mock_settings, mock_config_manager):
        """Test successful Gemini API call."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "Thank you for submitting this ticket. We'll investigate the issue."
                    }]
                }
            }]
        }
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        client = GeminiClient()
        response = await client._call_gemini_api("test prompt")
        
        assert "candidates" in response
        assert len(response["candidates"]) > 0
    
    @patch('httpx.AsyncClient')
    async def test_call_gemini_api_rate_limit(self, mock_client, mock_settings, mock_config_manager):
        """Test Gemini API rate limit handling."""
        # Setup mock response for rate limit
        mock_response = Mock()
        mock_response.status_code = 429
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        client = GeminiClient()
        
        with pytest.raises(GeminiAPIError) as exc_info:
            await client._call_gemini_api("test prompt")
        
        assert "Rate limit exceeded" in str(exc_info.value)
    
    def test_extract_comment_from_response(self, mock_settings, mock_config_manager):
        """Test comment extraction from API response."""
        client = GeminiClient()
        
        response = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "**Thank you** for submitting this *ticket*. We'll investigate."
                    }]
                }
            }]
        }
        
        comment = client._extract_comment_from_response(response)
        
        assert comment == "Thank you for submitting this ticket. We'll investigate."
        assert "**" not in comment  # Markdown removed
        assert "*" not in comment   # Markdown removed
    
    def test_extract_comment_invalid_response(self, mock_settings, mock_config_manager):
        """Test comment extraction with invalid response."""
        client = GeminiClient()
        
        invalid_response = {"candidates": []}
        
        with pytest.raises(GeminiAPIError):
            client._extract_comment_from_response(invalid_response)
    
    def test_generate_fallback_comment_high_quality(self, mock_settings, mock_config_manager, sample_ticket):
        """Test fallback comment generation for high quality ticket."""
        assessment = QualityAssessment(
            ticket_key="TEST-123",
            overall_quality=QualityLevel.HIGH,
            issues_found=[],
            score=95,
            assessed_at=datetime.utcnow()
        )
        
        client = GeminiClient()
        comment = client.generate_fallback_comment(sample_ticket, assessment)
        
        assert "Thank you for the detailed ticket." in comment
        assert "We'll investigate this." in comment
        assert "We'll keep you updated." in comment
    
    def test_generate_fallback_comment_low_quality(self, mock_settings, mock_config_manager, sample_ticket):
        """Test fallback comment generation for low quality ticket."""
        assessment = QualityAssessment(
            ticket_key="TEST-123",
            overall_quality=QualityLevel.LOW,
            issues_found=["Summary too short", "Missing steps"],
            score=30,
            assessed_at=datetime.utcnow()
        )
        
        client = GeminiClient()
        comment = client.generate_fallback_comment(sample_ticket, assessment)
        
        assert "Thank you for the ticket." in comment
        assert "We need additional information:" in comment
        assert "Summary too short" in comment
        assert "Missing steps" in comment
        assert "Please update the ticket." in comment
    
    @patch('httpx.AsyncClient')
    async def test_generate_comment_success(self, mock_client, mock_settings, mock_config_manager, sample_ticket, sample_assessment):
        """Test successful AI comment generation."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "Thank you for submitting this ticket. We'll investigate the issue and get back to you."
                    }]
                }
            }]
        }
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        client = GeminiClient()
        comment = await client.generate_comment(sample_ticket, sample_assessment)
        
        assert "Thank you for submitting this ticket" in comment
        assert len(comment) > 0
    
    @patch('httpx.AsyncClient')
    async def test_test_api_connection_success(self, mock_client, mock_settings, mock_config_manager):
        """Test API connection test."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "Test response from Gemini API"
                    }]
                }
            }]
        }
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        client = GeminiClient()
        result = await client.test_api_connection()
        
        assert result["success"] is True
        assert "response_time" in result
        assert "generated_text" in result
        assert result["model"] == "gemini-pro"
    
    @patch('httpx.AsyncClient')
    async def test_test_api_connection_failure(self, mock_client, mock_settings, mock_config_manager):
        """Test API connection test failure."""
        # Setup mock to raise exception
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("Connection failed"))
        
        client = GeminiClient()
        result = await client.test_api_connection()
        
        assert result["success"] is False
        assert "error" in result
        assert "Connection failed" in result["error"]


class TestAICommentsAPI:
    """Test cases for AI comments API endpoints."""
    
    @patch('app.api.ai_comments.get_jira_client')
    @patch('app.api.ai_comments.get_quality_engine')
    @patch('app.api.ai_comments.get_gemini_client')
    async def test_generate_comment_for_ticket_success(self, mock_get_gemini, mock_get_quality, mock_get_jira):
        """Test successful comment generation for ticket."""
        # Setup mocks
        mock_ticket = Mock()
        mock_ticket.summary = "Test issue"
        mock_ticket.issue_type.value = "Bug"
        mock_ticket.priority.value = "Medium"
        mock_ticket.status.value = "Open"
        
        mock_jira = Mock()
        mock_jira.get_issue_sync.return_value = mock_ticket
        mock_get_jira.return_value = mock_jira
        
        mock_assessment = Mock()
        mock_assessment.overall_quality.value = "medium"
        mock_assessment.score = 75
        mock_assessment.issues_found = ["Need more details"]
        
        mock_quality = Mock()
        mock_quality.assess_ticket_quality.return_value = mock_assessment
        mock_get_quality.return_value = mock_quality
        
        mock_gemini = Mock()
        mock_gemini.generate_comment = AsyncMock(return_value="Generated AI comment")
        mock_get_gemini.return_value = mock_gemini
        
        # Test the endpoint
        response = client.post("/ai/generate/TEST-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ticket_key"] == "TEST-123"
        assert data["comment"] == "Generated AI comment"
        assert data["generated_by"] == "ai"
    
    def test_ai_config_endpoint(self):
        """Test AI configuration endpoint."""
        response = client.get("/ai/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "gemini_config" in data
        assert "comment_templates" in data
        assert "features" in data
    
    def test_ai_stats_endpoint(self):
        """Test AI statistics endpoint."""
        response = client.get("/ai/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_comments_generated" in data
        assert "ai_generation_success_rate" in data
        assert "fallback_usage_rate" in data
    
    def test_ai_test_endpoint(self):
        """Test AI generation test endpoint."""
        response = client.get("/ai/test")
        
        assert response.status_code in [200, 503]  # 503 if API unavailable
        data = response.json()
        assert "api_connection" in data
