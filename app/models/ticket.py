"""
Data models for JIRA tickets and related entities.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class IssueType(str, Enum):
    """JIRA issue types."""
    PROBLEM = "Problem"  # Default issue type
   


class Priority(str, Enum):
    """JIRA priority levels."""
    BLOCKER = "Blocker"  # Highest priority
    P1 = "P1"           # High priority
    P2 = "P2"           # Medium priority (default)
    P3 = "P3"           # Low priority
    P4 = "P4"           # Lowest priority


class TicketStatus(str, Enum):
    """JIRA ticket statuses."""
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    AWAITING_CUSTOMER_INFO = "Awaiting Customer Info"
    NEEDS_CLARIFICATION = "Needs Clarification"
    NEEDS_MORE_INFO = "Needs More Info (Reporter)"
    READY_FOR_DEVELOPMENT = "Ready for Development"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class QualityLevel(str, Enum):
    """Ticket quality assessment levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JiraUser(BaseModel):
    """JIRA user information."""
    account_id: str
    display_name: str
    email_address: Optional[str] = None
    active: bool = True


class JiraAttachment(BaseModel):
    """JIRA attachment information."""
    id: str
    filename: str
    size: int
    mime_type: str
    created: datetime
    author: JiraUser


class JiraTicket(BaseModel):
    """JIRA ticket data model."""
    
    # Basic ticket information
    key: str = Field(..., description="JIRA ticket key (e.g., SUPPORT-123)")
    id: str = Field(..., description="JIRA ticket ID")
    summary: str = Field(..., description="Ticket summary/title")
    description: Optional[str] = Field(None, description="Ticket description")
    
    # Ticket metadata
    issue_type: IssueType = Field(..., description="Type of issue")
    priority: Priority = Field(..., description="Priority level")
    status: TicketStatus = Field(..., description="Current status")
    
    # People
    reporter: JiraUser = Field(..., description="Ticket reporter")
    assignee: Optional[JiraUser] = Field(None, description="Ticket assignee")
    
    # Timestamps
    created: datetime = Field(..., description="Creation timestamp")
    updated: datetime = Field(..., description="Last update timestamp")
    
    # Custom fields
    steps_to_reproduce: Optional[str] = Field(None, description="Steps to reproduce the issue")
    affected_version: Optional[str] = Field(None, description="Affected version/environment")
    customer_impact: Optional[str] = Field(None, description="Customer impact description")
    
    # Attachments
    attachments: List[JiraAttachment] = Field(default_factory=list, description="Ticket attachments")
    
    # Project information
    project_key: str = Field(..., description="JIRA project key")
    project_name: str = Field(..., description="JIRA project name")
    
    # Raw JIRA data (for debugging/reference)
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw JIRA API response")
    
    @validator("key")
    def validate_key_format(cls, v):
        """Validate JIRA key format."""
        if not v or "-" not in v:
            raise ValueError("JIRA key must be in format PROJECT-NUMBER")
        return v
    
    @property
    def has_attachments(self) -> bool:
        """Check if ticket has attachments."""
        return len(self.attachments) > 0
    
    @property
    def is_high_priority(self) -> bool:
        """Check if ticket is high priority."""
        return self.priority in [Priority.BLOCKER, Priority.P1]

    @property
    def is_bug(self) -> bool:
        """Check if ticket is a bug or problem."""
        return self.issue_type in [IssueType.PROBLEM]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ticket to dictionary for processing."""
        return {
            "key": self.key,
            "id": self.id,
            "summary": self.summary,
            "description": self.description,
            "issue_type": self.issue_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "reporter": self.reporter.display_name,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "steps_to_reproduce": self.steps_to_reproduce,
            "affected_version": self.affected_version,
            "customer_impact": self.customer_impact,
            "has_attachments": self.has_attachments,
            "project_key": self.project_key,
            "project_name": self.project_name
        }


class QualityAssessment(BaseModel):
    """Quality assessment result for a ticket."""
    
    ticket_key: str = Field(..., description="JIRA ticket key")
    overall_quality: QualityLevel = Field(..., description="Overall quality level")
    issues_found: List[str] = Field(default_factory=list, description="List of quality issues")
    score: int = Field(..., description="Quality score (0-100)")
    
    # Individual rule results
    summary_valid: bool = Field(True, description="Summary meets requirements")
    description_valid: bool = Field(True, description="Description meets requirements")
    steps_valid: bool = Field(True, description="Steps to reproduce are valid")
    version_valid: bool = Field(True, description="Affected version is specified")
    attachments_valid: bool = Field(True, description="Attachments are appropriate")
    pic_valid: bool = Field(True, description="PIC (Person in Charge) is specified")
    customer_login_valid: bool = Field(True, description="Customer login details are provided")
    top_merchants_valid: bool = Field(True, description="Top 450 merchants impact is specified")
    product_valid: bool = Field(True, description="Product/System is specified")
    actual_result_valid: bool = Field(True, description="Actual result is provided")
    expected_result_valid: bool = Field(True, description="Expected result is provided")
    
    # Assessment metadata
    assessed_at: datetime = Field(default_factory=datetime.utcnow, description="Assessment timestamp")
    rules_version: str = Field("1.0", description="Quality rules version used")
    
    @property
    def is_high_quality(self) -> bool:
        """Check if ticket is high quality."""
        return self.overall_quality == QualityLevel.HIGH
    
    @property
    def is_medium_quality(self) -> bool:
        """Check if ticket is medium quality."""
        return self.overall_quality == QualityLevel.MEDIUM
    
    @property
    def is_low_quality(self) -> bool:
        """Check if ticket is low quality."""
        return self.overall_quality == QualityLevel.LOW


class WebhookEvent(BaseModel):
    """JIRA webhook event data model."""
    
    timestamp: datetime = Field(..., description="Event timestamp")
    webhook_event: str = Field(..., description="Type of webhook event")
    issue_event_type_name: Optional[str] = Field(None, description="Issue event type")
    
    # Issue data
    issue: Dict[str, Any] = Field(..., description="Issue data from webhook")
    
    # User who triggered the event
    user: Optional[Dict[str, Any]] = Field(None, description="User who triggered the event")
    
    # Changelog (for update events)
    changelog: Optional[Dict[str, Any]] = Field(None, description="Changelog for update events")
    
    @property
    def is_issue_created(self) -> bool:
        """Check if this is an issue created event."""
        return self.webhook_event == "jira:issue_created"
    
    @property
    def is_issue_updated(self) -> bool:
        """Check if this is an issue updated event."""
        return self.webhook_event == "jira:issue_updated"
    
    @property
    def issue_key(self) -> Optional[str]:
        """Get the issue key from the event."""
        return self.issue.get("key") if self.issue else None
    
    @property
    def issue_id(self) -> Optional[str]:
        """Get the issue ID from the event."""
        return self.issue.get("id") if self.issue else None


class ProcessingResult(BaseModel):
    """Result of ticket processing."""
    
    ticket_key: str = Field(..., description="JIRA ticket key")
    success: bool = Field(..., description="Whether processing was successful")
    
    # Processing steps completed
    ingested: bool = Field(False, description="Ticket was ingested")
    quality_assessed: bool = Field(False, description="Quality was assessed")
    comment_generated: bool = Field(False, description="AI comment was generated")
    comment_posted: bool = Field(False, description="Comment was posted to JIRA")
    status_transitioned: bool = Field(False, description="Status was transitioned")
    
    # Results
    quality_assessment: Optional[QualityAssessment] = Field(None, description="Quality assessment result")
    generated_comment: Optional[str] = Field(None, description="Generated AI comment")
    new_status: Optional[TicketStatus] = Field(None, description="New ticket status")
    
    # Error information
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    error_step: Optional[str] = Field(None, description="Step where error occurred")
    
    # Processing metadata
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    processing_time_seconds: Optional[float] = Field(None, description="Total processing time")
    
    @property
    def is_complete(self) -> bool:
        """Check if all processing steps were completed."""
        return all([
            self.ingested,
            self.quality_assessed,
            self.comment_generated,
            self.comment_posted
        ])
