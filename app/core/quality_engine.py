"""
Quality assessment engine for PS Ticket Process Bot.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from app.models.ticket import JiraTicket, QualityAssessment, QualityLevel, IssueType, Priority
from app.core.config import get_settings
from app.utils.config_manager import get_config_manager


logger = logging.getLogger(__name__)


@dataclass
class QualityRule:
    """Represents a quality assessment rule."""
    name: str
    description: str
    required: bool
    weight: int
    applies_to_issue_types: List[str]
    applies_to_priorities: List[str]


class QualityAssessmentEngine:
    """Engine for assessing ticket quality based on configurable rules."""
    
    def __init__(self):
        """Initialize the quality assessment engine."""
        self.settings = get_settings()
        self.config_manager = get_config_manager()
        self.rules = self._load_quality_rules()
        
        logger.info(f"Initialized quality assessment engine with {len(self.rules)} rules")
    
    def _load_quality_rules(self) -> List[QualityRule]:
        """Load quality rules from configuration."""
        rules = []
        
        # Summary validation rule
        rules.append(QualityRule(
            name="summary_length",
            description="Summary must be between minimum and maximum length",
            required=True,
            weight=20,
            applies_to_issue_types=["*"],  # All issue types
            applies_to_priorities=["*"]    # All priorities
        ))
        
        # Description validation rule
        rules.append(QualityRule(
            name="description_length",
            description="Description must meet minimum length requirements",
            required=True,
            weight=25,
            applies_to_issue_types=["*"],
            applies_to_priorities=["*"]
        ))
        
        # Steps to reproduce rule (for bugs)
        rules.append(QualityRule(
            name="steps_to_reproduce",
            description="Steps to reproduce must be provided for bugs",
            required=self.settings.quality_rules.steps_required_for_bugs,
            weight=30,
            applies_to_issue_types=["Bug"],
            applies_to_priorities=["*"]
        ))
        
        # Affected version rule
        rules.append(QualityRule(
            name="affected_version",
            description="Affected version must be specified",
            required=self.settings.quality_rules.affected_version_required,
            weight=15,
            applies_to_issue_types=["Bug", "Support Request"],
            applies_to_priorities=["*"]
        ))
        
        # Attachments rule (recommended for bugs)
        rules.append(QualityRule(
            name="attachments",
            description="Attachments are recommended for bug reports",
            required=False,
            weight=10,
            applies_to_issue_types=["Bug"],
            applies_to_priorities=["*"]
        ))
        
        # High priority validation rule
        rules.append(QualityRule(
            name="high_priority_completeness",
            description="High priority tickets must meet all quality criteria",
            required=self.settings.quality_rules.high_priority_enforce_all_rules,
            weight=50,
            applies_to_issue_types=["*"],
            applies_to_priorities=self.settings.quality_rules.high_priority_levels
        ))
        
        return rules
    
    def assess_ticket_quality(self, ticket: JiraTicket) -> QualityAssessment:
        """
        Assess the quality of a JIRA ticket.
        
        Args:
            ticket: JiraTicket to assess
            
        Returns:
            QualityAssessment: Assessment result
        """
        logger.info(f"Assessing quality for ticket {ticket.key}")
        
        issues_found = []
        rule_results = {}
        total_score = 100
        
        # Evaluate each applicable rule
        for rule in self.rules:
            if self._rule_applies_to_ticket(rule, ticket):
                result = self._evaluate_rule(rule, ticket)
                rule_results[rule.name] = result
                
                if not result["passed"]:
                    issues_found.append(result["message"])
                    if rule.required:
                        total_score -= rule.weight
                    else:
                        total_score -= rule.weight // 2  # Half penalty for optional rules
        
        # Ensure score doesn't go below 0
        total_score = max(0, total_score)
        
        # Determine overall quality level
        overall_quality = self._determine_quality_level(len(issues_found), ticket)
        
        # Create assessment result
        assessment = QualityAssessment(
            ticket_key=ticket.key,
            overall_quality=overall_quality,
            issues_found=issues_found,
            score=total_score,
            summary_valid=rule_results.get("summary_length", {}).get("passed", True),
            description_valid=rule_results.get("description_length", {}).get("passed", True),
            steps_valid=rule_results.get("steps_to_reproduce", {}).get("passed", True),
            version_valid=rule_results.get("affected_version", {}).get("passed", True),
            attachments_valid=rule_results.get("attachments", {}).get("passed", True),
            assessed_at=datetime.utcnow(),
            rules_version="1.0"
        )
        
        logger.info(f"Quality assessment complete for {ticket.key}: {overall_quality.value} ({total_score}/100)")
        return assessment
    
    def _rule_applies_to_ticket(self, rule: QualityRule, ticket: JiraTicket) -> bool:
        """Check if a rule applies to a specific ticket."""
        # Check issue type
        if "*" not in rule.applies_to_issue_types:
            if ticket.issue_type.value not in rule.applies_to_issue_types:
                return False
        
        # Check priority
        if "*" not in rule.applies_to_priorities:
            if ticket.priority.value not in rule.applies_to_priorities:
                return False
        
        return True
    
    def _evaluate_rule(self, rule: QualityRule, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate a specific rule against a ticket."""
        if rule.name == "summary_length":
            return self._evaluate_summary_length(ticket)
        elif rule.name == "description_length":
            return self._evaluate_description_length(ticket)
        elif rule.name == "steps_to_reproduce":
            return self._evaluate_steps_to_reproduce(ticket)
        elif rule.name == "affected_version":
            return self._evaluate_affected_version(ticket)
        elif rule.name == "attachments":
            return self._evaluate_attachments(ticket)
        elif rule.name == "high_priority_completeness":
            return self._evaluate_high_priority_completeness(ticket)
        else:
            logger.warning(f"Unknown rule: {rule.name}")
            return {"passed": True, "message": ""}
    
    def _evaluate_summary_length(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate summary length rule."""
        summary = ticket.summary or ""
        min_length = self.settings.quality_rules.summary_min_length
        max_length = self.settings.quality_rules.summary_max_length
        
        if len(summary) < min_length:
            return {
                "passed": False,
                "message": f"Summary is too short (minimum {min_length} characters required)"
            }
        elif len(summary) > max_length:
            return {
                "passed": False,
                "message": f"Summary is too long (maximum {max_length} characters allowed)"
            }
        else:
            return {"passed": True, "message": ""}
    
    def _evaluate_description_length(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate description length rule."""
        description = ticket.description or ""
        min_length = self.settings.quality_rules.description_min_length
        max_length = self.settings.quality_rules.description_max_length
        
        if len(description) < min_length:
            return {
                "passed": False,
                "message": f"Description is too short (minimum {min_length} characters required)"
            }
        elif len(description) > max_length:
            return {
                "passed": False,
                "message": f"Description is too long (maximum {max_length} characters allowed)"
            }
        else:
            return {"passed": True, "message": ""}
    
    def _evaluate_steps_to_reproduce(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate steps to reproduce rule."""
        steps = ticket.steps_to_reproduce or ""
        min_length = self.settings.quality_rules.steps_min_length
        
        if len(steps) < min_length:
            return {
                "passed": False,
                "message": f"Steps to reproduce are missing or too short (minimum {min_length} characters required)"
            }
        else:
            return {"passed": True, "message": ""}
    
    def _evaluate_affected_version(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate affected version rule."""
        version = ticket.affected_version or ""
        
        if not version.strip():
            return {
                "passed": False,
                "message": "Affected version is not specified"
            }
        else:
            return {"passed": True, "message": ""}
    
    def _evaluate_attachments(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate attachments rule."""
        if not ticket.has_attachments:
            return {
                "passed": False,
                "message": "Attachments are recommended for bug reports (screenshots, logs, etc.)"
            }
        else:
            return {"passed": True, "message": ""}
    
    def _evaluate_high_priority_completeness(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate high priority completeness rule."""
        if not ticket.is_high_priority:
            return {"passed": True, "message": ""}  # Rule doesn't apply
        
        # For high priority tickets, check if any other rules failed
        issues = []
        
        # Check all basic rules for high priority tickets
        if not ticket.summary or len(ticket.summary) < self.settings.quality_rules.summary_min_length:
            issues.append("summary")
        
        if not ticket.description or len(ticket.description) < self.settings.quality_rules.description_min_length:
            issues.append("description")
        
        if ticket.is_bug:
            if not ticket.steps_to_reproduce or len(ticket.steps_to_reproduce) < self.settings.quality_rules.steps_min_length:
                issues.append("steps to reproduce")
        
        if not ticket.affected_version:
            issues.append("affected version")
        
        if issues:
            return {
                "passed": False,
                "message": f"High priority tickets must have complete information. Missing: {', '.join(issues)}"
            }
        else:
            return {"passed": True, "message": ""}
    
    def _determine_quality_level(self, issue_count: int, ticket: JiraTicket) -> QualityLevel:
        """Determine overall quality level based on issues found."""
        # Use configured thresholds
        high_threshold = self.settings.quality_rules.high_quality_max_issues
        medium_threshold = self.settings.quality_rules.medium_quality_max_issues
        
        # Special handling for high priority tickets
        if ticket.is_high_priority and self.settings.quality_rules.high_priority_enforce_all_rules:
            if issue_count == 0:
                return QualityLevel.HIGH
            elif issue_count <= 1:
                return QualityLevel.MEDIUM
            else:
                return QualityLevel.LOW
        
        # Standard quality assessment
        if issue_count <= high_threshold:
            return QualityLevel.HIGH
        elif issue_count <= medium_threshold:
            return QualityLevel.MEDIUM
        else:
            return QualityLevel.LOW
    
    def get_quality_suggestions(self, assessment: QualityAssessment, ticket: JiraTicket) -> List[str]:
        """
        Get suggestions for improving ticket quality.
        
        Args:
            assessment: Quality assessment result
            ticket: Original ticket
            
        Returns:
            List[str]: List of improvement suggestions
        """
        suggestions = []
        
        if not assessment.summary_valid:
            suggestions.append("Provide a clear, descriptive summary that explains the issue concisely")
        
        if not assessment.description_valid:
            suggestions.append("Add a detailed description explaining what happened, what was expected, and the impact")
        
        if not assessment.steps_valid and ticket.is_bug:
            suggestions.append("Include step-by-step instructions to reproduce the issue")
        
        if not assessment.version_valid:
            suggestions.append("Specify the affected version, environment, or system where the issue occurs")
        
        if not assessment.attachments_valid and ticket.is_bug:
            suggestions.append("Attach relevant screenshots, error logs, or other supporting files")
        
        # Add priority-specific suggestions
        if ticket.is_high_priority:
            suggestions.append("High priority tickets require complete information for immediate attention")
        
        return suggestions
    
    def get_rule_documentation(self) -> Dict[str, Any]:
        """Get documentation about quality rules."""
        return {
            "rules": [
                {
                    "name": rule.name,
                    "description": rule.description,
                    "required": rule.required,
                    "weight": rule.weight,
                    "applies_to_issue_types": rule.applies_to_issue_types,
                    "applies_to_priorities": rule.applies_to_priorities
                }
                for rule in self.rules
            ],
            "thresholds": {
                "high_quality_max_issues": self.settings.quality_rules.high_quality_max_issues,
                "medium_quality_max_issues": self.settings.quality_rules.medium_quality_max_issues,
                "low_quality_min_issues": self.settings.quality_rules.low_quality_min_issues
            },
            "configuration": {
                "summary_min_length": self.settings.quality_rules.summary_min_length,
                "description_min_length": self.settings.quality_rules.description_min_length,
                "steps_min_length": self.settings.quality_rules.steps_min_length,
                "high_priority_enforce_all_rules": self.settings.quality_rules.high_priority_enforce_all_rules
            }
        }


# Global quality engine instance
_quality_engine: Optional[QualityAssessmentEngine] = None


def get_quality_engine() -> QualityAssessmentEngine:
    """Get the global quality assessment engine instance."""
    global _quality_engine
    if _quality_engine is None:
        _quality_engine = QualityAssessmentEngine()
    return _quality_engine
