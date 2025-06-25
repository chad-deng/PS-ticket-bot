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
        
        # Steps to reproduce rule (for bugs and problems)
        rules.append(QualityRule(
            name="steps_to_reproduce",
            description="Steps to reproduce must be provided for bugs and problems",
            required=True,
            weight=15,
            applies_to_issue_types=["Bug", "Problem"],
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
        
        # PIC (Person in Charge) rule
        rules.append(QualityRule(
            name="pic_field",
            description="PIC (Person in Charge) must be specified",
            required=True,
            weight=10,
            applies_to_issue_types=["Support Request", "Problem", "Bug"],
            applies_to_priorities=["*"]
        ))

        # Customer login details rule
        rules.append(QualityRule(
            name="customer_login_details",
            description="Customer login details should be provided for support tickets",
            required=True,
            weight=10,
            applies_to_issue_types=["Support Request", "Problem", "Bug"],
            applies_to_priorities=["*"]
        ))

        # Top 450 merchants impact rule
        rules.append(QualityRule(
            name="top_merchants_impact",
            description="Impact on top 450 merchants must be specified",
            required=True,
            weight=10,
            applies_to_issue_types=["Support Request", "Problem", "Bug"],
            applies_to_priorities=["*"]
        ))

        # Product field rule
        rules.append(QualityRule(
            name="product_field",
            description="Product must be specified",
            required=True,
            weight=10,
            applies_to_issue_types=["Support Request", "Problem", "Bug"],
            applies_to_priorities=["*"]
        ))

        # Actual result rule
        rules.append(QualityRule(
            name="actual_result",
            description="Actual result must be provided",
            required=True,
            weight=15,
            applies_to_issue_types=["Problem", "Bug"],
            applies_to_priorities=["*"]
        ))

        # Expected result rule
        rules.append(QualityRule(
            name="expected_result",
            description="Expected result must be provided",
            required=True,
            weight=15,
            applies_to_issue_types=["Problem", "Bug"],
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
            pic_valid=rule_results.get("pic_field", {}).get("passed", True),
            customer_login_valid=rule_results.get("customer_login_details", {}).get("passed", True),
            top_merchants_valid=rule_results.get("top_merchants_impact", {}).get("passed", True),
            product_valid=rule_results.get("product_field", {}).get("passed", True),
            actual_result_valid=rule_results.get("actual_result", {}).get("passed", True),
            expected_result_valid=rule_results.get("expected_result", {}).get("passed", True),
            assessed_at=datetime.utcnow(),
            rules_version="2.0"
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
        elif rule.name == "pic_field":
            return self._evaluate_pic_field(ticket)
        elif rule.name == "customer_login_details":
            return self._evaluate_customer_login_details(ticket)
        elif rule.name == "top_merchants_impact":
            return self._evaluate_top_merchants_impact(ticket)
        elif rule.name == "product_field":
            return self._evaluate_product_field(ticket)
        elif rule.name == "actual_result":
            return self._evaluate_actual_result(ticket)
        elif rule.name == "expected_result":
            return self._evaluate_expected_result(ticket)
        elif rule.name == "high_priority_completeness":
            return self._evaluate_high_priority_completeness(ticket)
        else:
            logger.warning(f"Unknown rule: {rule.name}")
            return {"passed": True, "message": ""}
    
    def _evaluate_summary_length(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate summary quality rule.

        Rules:
        1. More than 10 characters
        2. Don't include quotation marks (")
        3. Make sure it has clarity (meaningful content)
        """
        summary = ticket.summary or ""

        # Rule 1: Check minimum length (more than 10 characters)
        if len(summary.strip()) <= 10:
            return {
                "passed": False,
                "message": "Summary is too short (minimum 10 characters required)"
            }

        # Rule 2: Check for quotation marks
        if '"' in summary:
            return {
                "passed": False,
                "message": "Summary should not contain quotation marks"
            }

        # Rule 3: Check for clarity (meaningful content)
        if not self._has_clear_description(summary):
            return {
                "passed": False,
                "message": "Summary should be clear and meaningful"
            }

        # Check maximum length (keep existing max limit)
        max_length = self.settings.quality_rules.summary_max_length
        if len(summary) > max_length:
            return {
                "passed": False,
                "message": f"Summary is too long (maximum {max_length} characters allowed)"
            }

        return {"passed": True, "message": ""}
    
    def _evaluate_description_length(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate description rule.

        Only check description when labels contain 'Unreproducible_bug'.
        """
        # Check if we should validate description for this ticket
        if not self._should_validate_description(ticket):
            return {"passed": True, "message": ""}

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

    def _should_validate_description(self, ticket: JiraTicket) -> bool:
        """Check if description should be validated for this ticket.

        Only validate description when issue type is 'Unreproducible Bug'.
        """
        return ticket.issue_type.value == "Unreproducible Bug"

    def _has_clear_description(self, description: str) -> bool:
        """Check if description has clarity and meaningful content."""
        if not description or not description.strip():
            return False

        # Remove whitespace and check actual content
        clean_description = description.strip()

        # Check for very short or unclear descriptions
        unclear_patterns = [
            "test", "testing", "issue", "problem", "error", "bug", "help",
            "not working", "broken", "fix", "please help", "urgent"
        ]

        # If description is just one of these unclear words, it's not clear
        if clean_description.lower() in unclear_patterns:
            return False

        # Check for meaningful content (should have some descriptive words)
        words = clean_description.split()
        if len(words) < 3:  # At least 3 words for clarity
            return False

        # Check if it contains some action words or descriptive content
        meaningful_indicators = [
            "when", "after", "before", "during", "while", "because", "since",
            "unable", "cannot", "can't", "doesn't", "won't", "fails", "failed",
            "expected", "actual", "should", "would", "could", "trying", "attempt",
            "click", "select", "enter", "submit", "load", "save", "delete",
            "user", "customer", "system", "application", "page", "screen",
            "message", "notification", "response", "result", "output"
        ]

        description_lower = clean_description.lower()
        has_meaningful_content = any(indicator in description_lower for indicator in meaningful_indicators)

        return has_meaningful_content

    def _evaluate_steps_to_reproduce(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate steps to reproduce rule."""
        # First check if the dedicated steps_to_reproduce field is populated
        if ticket.steps_to_reproduce and ticket.steps_to_reproduce.strip():
            # Check if the steps field has meaningful content (not just whitespace)
            steps_content = ticket.steps_to_reproduce.strip()
            if len(steps_content) >= 20:  # Minimum meaningful length
                return {"passed": True, "message": ""}

        # If steps field is empty, check summary and description for steps-related information
        text_to_check = f"{ticket.summary or ''} {ticket.description or ''}".lower()

        # Keywords that indicate steps to reproduce are provided
        steps_keywords = [
            "steps", "step", "reproduce", "reproduction", "step by step", "step-by-step",
            "how to", "procedure", "process", "instructions", "to reproduce",
            "1.", "2.", "3.", "first", "second", "third", "then", "next",
            "follow these", "do this", "click", "navigate", "go to"
        ]

        # Check if any steps-related keywords are present
        has_steps_info = any(keyword in text_to_check for keyword in steps_keywords)

        # Also check for numbered lists or structured content
        import re
        # Look for numbered steps like "1.", "2.", etc.
        numbered_pattern = r'\b\d+\.\s'
        has_numbered_steps = bool(re.search(numbered_pattern, text_to_check))

        if has_steps_info or has_numbered_steps:
            return {"passed": True, "message": ""}
        else:
            return {
                "passed": False,
                "message": "Steps to reproduce should be provided"
            }
    
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

    def _evaluate_customer_login_details(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate customer login details rule."""
        # Debug logging
        logger.debug(f"Customer login validation for {ticket.key}:")
        logger.debug(f"  - Customer login field: '{ticket.customer_login_details or 'None'}'")
        logger.debug(f"  - Summary: '{ticket.summary or 'None'}'")
        logger.debug(f"  - Description: '{(ticket.description or 'None')[:100]}...'")

        # Check dedicated customer login field first
        if ticket.customer_login_details and ticket.customer_login_details.strip():
            logger.info(f"  - Dedicated field has content, checking: '{ticket.customer_login_details}'")
            logger.info(f"  - Field type: {type(ticket.customer_login_details)}")
            logger.info(f"  - Field length: {len(ticket.customer_login_details)}")
            if self._validate_customer_login_text(ticket.customer_login_details):
                logger.info(f"  - PASSED: Valid customer login found in dedicated field")
                return {"passed": True, "message": ""}
            else:
                logger.warning(f"  - Dedicated field content not recognized as valid login details")
        else:
            logger.info(f"  - Dedicated field is empty or None, checking summary and description")
            logger.info(f"  - Field value: {repr(ticket.customer_login_details)}")

        # If dedicated field is empty or invalid, check summary and description
        fallback_text = f"{ticket.summary or ''} {ticket.description or ''}"
        logger.debug(f"  - Checking fallback text: '{fallback_text[:200]}...'")

        if self._validate_customer_login_text(fallback_text):
            logger.debug(f"  - PASSED: Valid customer login found in summary/description")
            return {"passed": True, "message": ""}

        logger.debug(f"  - FAILED: No valid customer login details found")
        return {
            "passed": False,
            "message": "Customer login details should be provided. Please include customer email address."
        }

    def _validate_customer_login_text(self, text: str) -> bool:
        """Validate if text contains valid customer login details.

        Simple validation: check if text is not empty and contains an email address.
        """
        if not text or not text.strip():
            logger.debug(f"    - Invalid: Text is empty")
            return False

        # Simple email pattern check
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails_found = re.findall(email_pattern, text)

        logger.debug(f"    - Text length: {len(text.strip())} characters")
        logger.debug(f"    - Emails found: {emails_found}")

        if emails_found:
            logger.debug(f"    - Valid: Email address found")
            return True
        else:
            logger.debug(f"    - Invalid: No email address found")
            return False

    def _evaluate_pic_field(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate PIC (Person in Charge) field rule."""
        # First check if PIC field is populated
        if ticket.pic and ticket.pic.strip():
            return {"passed": True, "message": ""}

        # If PIC field is empty, check summary and description for PIC information
        text_to_check = f"{ticket.summary or ''} {ticket.description or ''}".lower()

        # Keywords that indicate PIC is mentioned
        pic_keywords = [
            "pic", "person in charge", "contact person", "responsible person",
            "assigned to", "handled by", "owner", "point of contact", "poc"
        ]

        # Check if any PIC-related keywords are present
        has_pic_info = any(keyword in text_to_check for keyword in pic_keywords)

        if has_pic_info:
            return {"passed": True, "message": ""}
        else:
            return {
                "passed": False,
                "message": "PIC (Person in Charge) should be specified"
            }

    def _evaluate_top_merchants_impact(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate top 450 merchants impact rule."""
        # First check if the dedicated top_450_merchants field is populated
        if ticket.top_450_merchants and ticket.top_450_merchants.strip():
            # Field is populated, consider it valid regardless of value (Yes/No)
            return {"passed": True, "message": ""}

        # If field is empty, check summary and description for merchant impact information
        text_to_check = f"{ticket.summary or ''} {ticket.description or ''}".lower()

        # Keywords that indicate merchant impact is mentioned
        merchant_keywords = [
            "top 450", "top merchants", "merchant", "affecting merchants",
            "merchant impact", "450 merchants", "top 450 merchants",
            "merchant affected", "merchant list", "high value merchants"
        ]

        # Check if any merchant impact keywords are present
        has_merchant_info = any(keyword in text_to_check for keyword in merchant_keywords)

        if has_merchant_info:
            return {"passed": True, "message": ""}
        else:
            return {
                "passed": False,
                "message": "Impact on top 450 merchants should be specified"
            }

    def _evaluate_product_field(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate product field rule."""
        # First check if the dedicated product field is populated
        if ticket.product and ticket.product.strip():
            return {"passed": True, "message": ""}

        # If product field is empty, check summary and description for product information
        text_to_check = f"{ticket.summary or ''} {ticket.description or ''}".lower()

        # Keywords that indicate product is mentioned
        product_keywords = [
            "product", "application", "system", "platform", "service",
            "module", "feature", "component", "app", "website", "portal"
        ]

        # Check if any product keywords are present
        has_product_info = any(keyword in text_to_check for keyword in product_keywords)

        if has_product_info:
            return {"passed": True, "message": ""}
        else:
            return {
                "passed": False,
                "message": "Product/System should be specified"
            }

    def _evaluate_actual_result(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate actual result rule."""
        # First check if the dedicated actual_result field is populated
        if ticket.actual_result and ticket.actual_result.strip():
            # Check if the field has meaningful content (not just whitespace)
            actual_content = ticket.actual_result.strip()
            if len(actual_content) >= 3:  # Minimum meaningful length (reduced from 10 to 3)
                return {"passed": True, "message": ""}

        # If actual result field is empty, check summary and description for actual result information
        text_to_check = f"{ticket.summary or ''} {ticket.description or ''}".lower()

        # Keywords that indicate actual result is mentioned
        actual_keywords = [
            "actual result", "actual", "what happened", "current behavior",
            "observed", "seeing", "getting", "result", "outcome", "behavior"
        ]

        # Check if any actual result keywords are present
        has_actual_info = any(keyword in text_to_check for keyword in actual_keywords)

        if has_actual_info:
            return {"passed": True, "message": ""}
        else:
            return {
                "passed": False,
                "message": "Actual result should be provided (what actually happened)"
            }

    def _evaluate_expected_result(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Evaluate expected result rule."""
        # First check if the dedicated expected_result field is populated
        if ticket.expected_result and ticket.expected_result.strip():
            # Check if the field has meaningful content (not just whitespace)
            expected_content = ticket.expected_result.strip()
            if len(expected_content) >= 3:  # Minimum meaningful length (reduced from 10 to 3)
                return {"passed": True, "message": ""}

        # If expected result field is empty, check summary and description for expected result information
        text_to_check = f"{ticket.summary or ''} {ticket.description or ''}".lower()

        # Keywords that indicate expected result is mentioned
        expected_keywords = [
            "expected result", "expected", "should", "supposed to", "intended",
            "expected behavior", "should be", "should have", "expectation"
        ]

        # Check if any expected result keywords are present
        has_expected_info = any(keyword in text_to_check for keyword in expected_keywords)

        if has_expected_info:
            return {"passed": True, "message": ""}
        else:
            return {
                "passed": False,
                "message": "Expected result should be provided (what should have happened)"
            }
    
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
            # Use the same logic as _evaluate_steps_to_reproduce
            text_to_check = f"{ticket.summary or ''} {ticket.description or ''}".lower()
            steps_keywords = [
                "steps", "step", "reproduce", "reproduction", "step by step", "step-by-step",
                "how to", "procedure", "process", "instructions", "to reproduce",
                "1.", "2.", "3.", "first", "second", "third", "then", "next",
                "follow these", "do this", "click", "navigate", "go to"
            ]
            has_steps_info = any(keyword in text_to_check for keyword in steps_keywords)
            import re
            numbered_pattern = r'\b\d+\.\s'
            has_numbered_steps = bool(re.search(numbered_pattern, text_to_check))

            if not (has_steps_info or has_numbered_steps):
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
            suggestions.append("Provide a clear summary (more than 10 characters, no quotes, meaningful content)")
        
        if not assessment.description_valid:
            if ticket.issue_type.value == "Unreproducible Bug":
                suggestions.append("Provide a detailed description (required for Unreproducible Bug tickets)")
            else:
                suggestions.append("Provide a clear description")
        
        if not assessment.steps_valid and (ticket.is_bug or ticket.issue_type.value == "Problem"):
            suggestions.append("Include step-by-step instructions to reproduce the issue")
        
        if not assessment.version_valid:
            suggestions.append("Specify the affected version, environment, or system where the issue occurs")
        
        if not assessment.attachments_valid and ticket.is_bug:
            suggestions.append("Attach relevant screenshots, error logs, or other supporting files")

        if not assessment.pic_valid:
            suggestions.append("Specify PIC (Person in Charge) or responsible person for this issue")

        if not assessment.customer_login_valid:
            suggestions.append("Provide customer login details. Please include customer email address.")

        if not assessment.top_merchants_valid:
            suggestions.append("Specify if this issue affects top 450 merchants or high-value customers")

        if not assessment.product_valid:
            suggestions.append("Specify the product, system, or application where the issue occurs")

        if not assessment.actual_result_valid and ticket.is_bug:
            suggestions.append("Describe the actual result - what actually happened or what you observed")

        if not assessment.expected_result_valid and ticket.is_bug:
            suggestions.append("Describe the expected result - what should have happened or what you expected to see")

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
