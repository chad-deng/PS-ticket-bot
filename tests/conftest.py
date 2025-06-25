"""
Shared test configuration and fixtures.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.ticket import JiraTicket, JiraUser, IssueType, Priority, TicketStatus, QualityAssessment, QualityLevel


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_jira_user():
    """Create a sample JIRA user for testing."""
    return JiraUser(
        account_id="user123",
        display_name="Test User",
        email_address="test@example.com",
        active=True
    )


@pytest.fixture
def sample_ticket(sample_jira_user):
    """Create a sample ticket for testing."""
    return JiraTicket(
        key="TEST-123",
        id="12345",
        summary="Test issue summary with sufficient length",
        description="This is a detailed description of the test issue that meets the minimum length requirements for quality assessment.",
        issue_type=IssueType.BUG,
        priority=Priority.MEDIUM,
        status=TicketStatus.OPEN,
        reporter=sample_jira_user,
        created=datetime.utcnow(),
        updated=datetime.utcnow(),
        steps_to_reproduce="1. Open application\n2. Click button\n3. Observe error",
        affected_version="1.0.0",
        project_key="TEST",
        project_name="Test Project"
    )


@pytest.fixture
def high_quality_ticket(sample_jira_user):
    """Create a high-quality ticket for testing."""
    return JiraTicket(
        key="TEST-456",
        id="45678",
        summary="Critical production issue with detailed information",
        description="This is a comprehensive description of a critical production issue that includes all necessary details for proper investigation and resolution.",
        issue_type=IssueType.BUG,
        priority=Priority.HIGH,
        status=TicketStatus.OPEN,
        reporter=sample_jira_user,
        created=datetime.utcnow(),
        updated=datetime.utcnow(),
        steps_to_reproduce="1. Access production environment\n2. Navigate to user dashboard\n3. Click on reports section\n4. System throws 500 error",
        affected_version="2.1.0",
        project_key="TEST",
        project_name="Test Project"
    )


@pytest.fixture
def low_quality_ticket(sample_jira_user):
    """Create a low-quality ticket for testing."""
    return JiraTicket(
        key="TEST-789",
        id="78901",
        summary="Bug",  # Too short
        description="It's broken",  # Too short
        issue_type=IssueType.BUG,
        priority=Priority.MEDIUM,
        status=TicketStatus.OPEN,
        reporter=sample_jira_user,
        created=datetime.utcnow(),
        updated=datetime.utcnow(),
        steps_to_reproduce="",  # Missing
        affected_version="",  # Missing
        project_key="TEST",
        project_name="Test Project"
    )


@pytest.fixture
def sample_quality_assessment():
    """Create a sample quality assessment."""
    return QualityAssessment(
        ticket_key="TEST-123",
        overall_quality=QualityLevel.MEDIUM,
        issues_found=["Description could be more detailed"],
        score=75,
        assessed_at=datetime.utcnow()
    )


@pytest.fixture
def mock_jira_response():
    """Mock JIRA API response data."""
    return {
        "key": "TEST-123",
        "id": "12345",
        "fields": {
            "summary": "Test issue summary",
            "description": "Test issue description",
            "issuetype": {"name": "Bug"},
            "priority": {"name": "Medium"},
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
                "key": "TEST",
                "name": "Test Project"
            },
            "attachment": []
        }
    }


@pytest.fixture
def mock_settings():
    """Mock application settings."""
    with patch('app.core.config.get_settings') as mock_settings:
        # JIRA settings
        mock_settings.return_value.jira.base_url = "https://test.atlassian.net"
        mock_settings.return_value.jira.username = "test_user"
        mock_settings.return_value.jira.api_token = "test_token"
        mock_settings.return_value.jira.timeout = 30
        mock_settings.return_value.jira.max_retries = 3
        mock_settings.return_value.jira.retry_delay = 1
        
        # Gemini settings
        mock_settings.return_value.gemini.api_key = "test_api_key"
        mock_settings.return_value.gemini.model = "gemini-pro"
        mock_settings.return_value.gemini.temperature = 0.3
        mock_settings.return_value.gemini.max_output_tokens = 1024
        mock_settings.return_value.gemini.timeout = 30
        mock_settings.return_value.gemini.max_retries = 3
        mock_settings.return_value.gemini.retry_delay = 1
        
        # Quality rules settings
        mock_settings.return_value.quality_rules.summary_min_length = 10
        mock_settings.return_value.quality_rules.summary_max_length = 255
        mock_settings.return_value.quality_rules.description_min_length = 50
        mock_settings.return_value.quality_rules.description_max_length = 32767
        mock_settings.return_value.quality_rules.steps_min_length = 20
        mock_settings.return_value.quality_rules.steps_required_for_bugs = True
        mock_settings.return_value.quality_rules.affected_version_required = True
        mock_settings.return_value.quality_rules.high_priority_enforce_all_rules = True
        mock_settings.return_value.quality_rules.high_priority_levels = ["Highest", "High"]
        mock_settings.return_value.quality_rules.high_quality_max_issues = 1
        mock_settings.return_value.quality_rules.medium_quality_max_issues = 3
        mock_settings.return_value.quality_rules.low_quality_min_issues = 4
        
        # App settings
        mock_settings.return_value.app.environment = "test"
        mock_settings.return_value.app.debug = True
        
        yield mock_settings.return_value


@pytest.fixture
def mock_config_manager():
    """Mock configuration manager."""
    with patch('app.utils.config_manager.get_config_manager') as mock_config:
        mock_config.return_value.get_jira_field_mappings.return_value = {
            "summary": "summary",
            "description": "description",
            "steps_to_reproduce": "customfield_10001",
            "affected_version": "customfield_10002"
        }
        mock_config.return_value.should_process_issue_type.return_value = True
        mock_config.return_value.settings.features.enable_ai_comments = True
        mock_config.return_value.settings.features.enable_status_transitions = True
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


# Test markers for categorizing tests
pytestmark = [
    pytest.mark.unit,  # Mark all tests as unit tests by default
]
