"""
Tests for quality assessment engine.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from app.core.quality_engine import QualityAssessmentEngine, QualityRule
from app.models.ticket import QualityLevel


class TestQualityRule:
    """Test cases for QualityRule dataclass."""
    
    def test_quality_rule_creation(self):
        """Test QualityRule creation."""
        rule = QualityRule(
            name="test_rule",
            description="Test rule description",
            required=True,
            weight=20,
            applies_to_issue_types=["Bug"],
            applies_to_priorities=["High"]
        )
        
        assert rule.name == "test_rule"
        assert rule.description == "Test rule description"
        assert rule.required is True
        assert rule.weight == 20
        assert rule.applies_to_issue_types == ["Bug"]
        assert rule.applies_to_priorities == ["High"]


class TestQualityAssessmentEngine:
    """Test cases for QualityAssessmentEngine."""
    
    def test_engine_initialization(self, mock_settings, mock_config_manager):
        """Test quality engine initialization."""
        engine = QualityAssessmentEngine()

        assert engine.settings is not None
        assert len(engine.rules) > 0
        assert any(rule.name == "summary_length" for rule in engine.rules)
        assert any(rule.name == "description_length" for rule in engine.rules)

    def test_high_quality_assessment(self, mock_settings, mock_config_manager, high_quality_ticket):
        """Test assessment of high-quality ticket."""
        engine = QualityAssessmentEngine()
        assessment = engine.assess_ticket_quality(high_quality_ticket)

        assert assessment.ticket_key == "TEST-456"
        assert assessment.overall_quality == QualityLevel.HIGH
        assert assessment.score >= 80
        assert len(assessment.issues_found) <= 1
    
    def test_low_quality_assessment(self, mock_settings):
        """Test assessment of low-quality ticket."""
        # Create a low-quality ticket
        low_quality_ticket = JiraTicket(
            key="TEST-456",
            id="45678",
            summary="Bug",  # Too short
            description="It's broken",  # Too short
            issue_type=IssueType.BUG,
            priority=Priority.MEDIUM,
            status=TicketStatus.OPEN,
            reporter=JiraUser(account_id="user456", display_name="Test User"),
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            steps_to_reproduce="",  # Missing
            affected_version="",  # Missing
            project_key="TEST",
            project_name="Test Project"
        )
        
        with patch('app.core.quality_engine.get_config_manager'):
            engine = QualityAssessmentEngine()
            assessment = engine.assess_ticket_quality(low_quality_ticket)
            
            assert assessment.ticket_key == "TEST-456"
            assert assessment.overall_quality == QualityLevel.LOW
            assert assessment.score < 50
            assert len(assessment.issues_found) >= 4
    
    def test_high_priority_ticket_assessment(self, mock_settings):
        """Test assessment of high-priority ticket with special rules."""
        high_priority_ticket = JiraTicket(
            key="TEST-789",
            id="78901",
            summary="Critical production issue",
            description="This is a critical issue affecting production systems with detailed information.",
            issue_type=IssueType.BUG,
            priority=Priority.HIGH,  # High priority
            status=TicketStatus.OPEN,
            reporter=JiraUser(account_id="user789", display_name="Test User"),
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            steps_to_reproduce="1. Access production\n2. Perform action\n3. System fails",
            affected_version="2.0.0",
            project_key="TEST",
            project_name="Test Project"
        )
        
        with patch('app.core.quality_engine.get_config_manager'):
            engine = QualityAssessmentEngine()
            assessment = engine.assess_ticket_quality(high_priority_ticket)
            
            assert assessment.ticket_key == "TEST-789"
            assert assessment.overall_quality == QualityLevel.HIGH
            assert assessment.summary_valid is True
            assert assessment.description_valid is True
            assert assessment.steps_valid is True
            assert assessment.version_valid is True
    
    def test_rule_applicability(self, mock_settings, sample_ticket):
        """Test rule applicability logic."""
        with patch('app.core.quality_engine.get_config_manager'):
            engine = QualityAssessmentEngine()
            
            # Test rule that applies to all issue types
            summary_rule = next(rule for rule in engine.rules if rule.name == "summary_length")
            assert engine._rule_applies_to_ticket(summary_rule, sample_ticket) is True
            
            # Test rule that applies only to bugs
            steps_rule = next(rule for rule in engine.rules if rule.name == "steps_to_reproduce")
            assert engine._rule_applies_to_ticket(steps_rule, sample_ticket) is True
            
            # Change ticket to non-bug type
            sample_ticket.issue_type = IssueType.FEATURE_REQUEST
            assert engine._rule_applies_to_ticket(steps_rule, sample_ticket) is False
    
    def test_summary_length_evaluation(self, mock_settings, sample_ticket):
        """Test summary length rule evaluation."""
        with patch('app.core.quality_engine.get_config_manager'):
            engine = QualityAssessmentEngine()
            
            # Test valid summary
            result = engine._evaluate_summary_length(sample_ticket)
            assert result["passed"] is True
            
            # Test too short summary
            sample_ticket.summary = "Bug"
            result = engine._evaluate_summary_length(sample_ticket)
            assert result["passed"] is False
            assert "too short" in result["message"]
    
    def test_description_length_evaluation(self, mock_settings, sample_ticket):
        """Test description length rule evaluation."""
        with patch('app.core.quality_engine.get_config_manager'):
            engine = QualityAssessmentEngine()
            
            # Test valid description
            result = engine._evaluate_description_length(sample_ticket)
            assert result["passed"] is True
            
            # Test too short description
            sample_ticket.description = "Broken"
            result = engine._evaluate_description_length(sample_ticket)
            assert result["passed"] is False
            assert "too short" in result["message"]
    
    def test_steps_to_reproduce_evaluation(self, mock_settings, sample_ticket):
        """Test steps to reproduce rule evaluation."""
        with patch('app.core.quality_engine.get_config_manager'):
            engine = QualityAssessmentEngine()
            
            # Test valid steps
            result = engine._evaluate_steps_to_reproduce(sample_ticket)
            assert result["passed"] is True
            
            # Test missing steps
            sample_ticket.steps_to_reproduce = ""
            result = engine._evaluate_steps_to_reproduce(sample_ticket)
            assert result["passed"] is False
            assert "missing" in result["message"].lower()
    
    def test_affected_version_evaluation(self, mock_settings, sample_ticket):
        """Test affected version rule evaluation."""
        with patch('app.core.quality_engine.get_config_manager'):
            engine = QualityAssessmentEngine()
            
            # Test valid version
            result = engine._evaluate_affected_version(sample_ticket)
            assert result["passed"] is True
            
            # Test missing version
            sample_ticket.affected_version = ""
            result = engine._evaluate_affected_version(sample_ticket)
            assert result["passed"] is False
            assert "not specified" in result["message"]
    
    def test_quality_suggestions(self, mock_settings):
        """Test quality improvement suggestions."""
        # Create ticket with multiple issues
        problematic_ticket = JiraTicket(
            key="TEST-999",
            id="99999",
            summary="Bug",  # Too short
            description="Broken",  # Too short
            issue_type=IssueType.BUG,
            priority=Priority.MEDIUM,
            status=TicketStatus.OPEN,
            reporter=JiraUser(account_id="user999", display_name="Test User"),
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            steps_to_reproduce="",  # Missing
            affected_version="",  # Missing
            project_key="TEST",
            project_name="Test Project"
        )
        
        with patch('app.core.quality_engine.get_config_manager'):
            engine = QualityAssessmentEngine()
            assessment = engine.assess_ticket_quality(problematic_ticket)
            suggestions = engine.get_quality_suggestions(assessment, problematic_ticket)
            
            assert len(suggestions) > 0
            assert any("summary" in suggestion.lower() for suggestion in suggestions)
            assert any("description" in suggestion.lower() for suggestion in suggestions)
            assert any("steps" in suggestion.lower() for suggestion in suggestions)
            assert any("version" in suggestion.lower() for suggestion in suggestions)
    
    def test_rule_documentation(self, mock_settings):
        """Test rule documentation generation."""
        with patch('app.core.quality_engine.get_config_manager'):
            engine = QualityAssessmentEngine()
            documentation = engine.get_rule_documentation()
            
            assert "rules" in documentation
            assert "thresholds" in documentation
            assert "configuration" in documentation
            assert len(documentation["rules"]) > 0
            
            # Check that each rule has required fields
            for rule_doc in documentation["rules"]:
                assert "name" in rule_doc
                assert "description" in rule_doc
                assert "required" in rule_doc
                assert "weight" in rule_doc


class TestQualityAPI:
    """Test cases for quality API endpoints."""
    
    @patch('app.api.quality.get_jira_client')
    @patch('app.api.quality.get_quality_engine')
    def test_assess_ticket_endpoint(self, mock_get_engine, mock_get_client):
        """Test ticket quality assessment endpoint."""
        # Setup mocks
        mock_ticket = Mock()
        mock_ticket.summary = "Test issue"
        mock_ticket.issue_type.value = "Bug"
        mock_ticket.priority.value = "High"
        mock_ticket.status.value = "Open"
        mock_ticket.reporter.display_name = "Test User"
        
        mock_client = Mock()
        mock_client.get_issue_sync.return_value = mock_ticket
        mock_get_client.return_value = mock_client
        
        mock_assessment = Mock()
        mock_assessment.overall_quality.value = "high"
        mock_assessment.dict.return_value = {"overall_quality": "high", "score": 95}
        
        mock_engine = Mock()
        mock_engine.assess_ticket_quality.return_value = mock_assessment
        mock_engine.get_quality_suggestions.return_value = ["Great ticket!"]
        mock_get_engine.return_value = mock_engine
        
        # Test the endpoint
        response = client.get("/quality/assess/TEST-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ticket_key"] == "TEST-123"
        assert "assessment" in data
        assert "suggestions" in data
        assert "ticket_info" in data
    
    def test_get_quality_rules_endpoint(self):
        """Test quality rules endpoint."""
        response = client.get("/quality/rules")
        
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "thresholds" in data
        assert "configuration" in data
    
    def test_quality_stats_endpoint(self):
        """Test quality statistics endpoint."""
        response = client.get("/quality/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_assessments" in data
        assert "quality_distribution" in data
        assert "common_issues" in data
    
    def test_quality_test_endpoint(self):
        """Test quality engine test endpoint."""
        response = client.get("/quality/test")
        
        assert response.status_code == 200
        data = response.json()
        assert "test_results" in data
        assert "engine_info" in data
        assert len(data["test_results"]) == 2  # High and low quality test tickets
