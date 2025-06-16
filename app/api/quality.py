"""
Quality assessment API endpoints for PS Ticket Process Bot.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.quality_engine import get_quality_engine
from app.services.jira_client import get_jira_client, JiraAPIError
from app.models.ticket import QualityAssessment


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/assess/{issue_key}")
async def assess_ticket_quality(issue_key: str):
    """
    Assess the quality of a specific JIRA ticket.
    
    Args:
        issue_key: JIRA issue key (e.g., SUPPORT-123)
        
    Returns:
        Quality assessment result with score, issues found, and recommendations.
    """
    try:
        logger.info(f"Assessing quality for ticket {issue_key}")
        
        # Fetch ticket from JIRA
        jira_client = get_jira_client()
        try:
            ticket = jira_client.get_issue_sync(issue_key)
        except JiraAPIError as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Ticket {issue_key} not found")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to fetch ticket: {e.message}")
        
        # Assess quality
        quality_engine = get_quality_engine()
        assessment = quality_engine.assess_ticket_quality(ticket)
        
        # Get improvement suggestions
        suggestions = quality_engine.get_quality_suggestions(assessment, ticket)
        
        logger.info(f"Quality assessment complete for {issue_key}: {assessment.overall_quality.value}")
        
        return JSONResponse(
            status_code=200,
            content={
                "ticket_key": issue_key,
                "assessment": assessment.dict(),
                "suggestions": suggestions,
                "ticket_info": {
                    "summary": ticket.summary,
                    "issue_type": ticket.issue_type.value,
                    "priority": ticket.priority.value,
                    "status": ticket.status.value,
                    "reporter": ticket.reporter.display_name
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quality assessment failed for {issue_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Quality assessment failed")


@router.post("/assess")
async def assess_ticket_data(ticket_data: Dict[str, Any]):
    """
    Assess quality of ticket data without fetching from JIRA.
    
    This endpoint allows testing quality assessment with custom ticket data.
    
    Args:
        ticket_data: Ticket data in JiraTicket format
        
    Returns:
        Quality assessment result.
    """
    try:
        from app.models.ticket import JiraTicket
        
        # Validate and create ticket model
        try:
            ticket = JiraTicket(**ticket_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid ticket data: {e}")
        
        # Assess quality
        quality_engine = get_quality_engine()
        assessment = quality_engine.assess_ticket_quality(ticket)
        
        # Get improvement suggestions
        suggestions = quality_engine.get_quality_suggestions(assessment, ticket)
        
        logger.info(f"Quality assessment complete for {ticket.key}: {assessment.overall_quality.value}")
        
        return JSONResponse(
            status_code=200,
            content={
                "assessment": assessment.dict(),
                "suggestions": suggestions
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quality assessment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Quality assessment failed")


@router.get("/rules")
async def get_quality_rules():
    """
    Get information about quality assessment rules.
    
    Returns:
        Documentation about quality rules, thresholds, and configuration.
    """
    try:
        quality_engine = get_quality_engine()
        documentation = quality_engine.get_rule_documentation()
        
        return JSONResponse(
            status_code=200,
            content=documentation
        )
        
    except Exception as e:
        logger.error(f"Failed to get quality rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve quality rules")


@router.get("/stats")
async def get_quality_stats():
    """
    Get quality assessment statistics.
    
    Returns:
        Statistics about quality assessments performed.
    """
    try:
        # TODO: Implement quality statistics tracking
        # For now, return placeholder data
        
        stats = {
            "total_assessments": 0,
            "quality_distribution": {
                "high": 0,
                "medium": 0,
                "low": 0
            },
            "common_issues": [
                "Description too short",
                "Missing steps to reproduce",
                "Affected version not specified"
            ],
            "average_score": 0,
            "assessment_trends": {
                "last_24h": 0,
                "last_7d": 0,
                "last_30d": 0
            }
        }
        
        return JSONResponse(
            status_code=200,
            content=stats
        )
        
    except Exception as e:
        logger.error(f"Failed to get quality stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve quality statistics")


@router.get("/test")
async def test_quality_engine():
    """
    Test the quality assessment engine with sample data.
    
    Returns:
        Test results showing quality assessment functionality.
    """
    try:
        from app.models.ticket import JiraTicket, JiraUser, IssueType, Priority, TicketStatus
        from datetime import datetime
        
        # Create test tickets with different quality levels
        test_tickets = []
        
        # High quality ticket
        high_quality_ticket = JiraTicket(
            key="TEST-001",
            id="1001",
            summary="Application crashes when clicking the submit button on the contact form",
            description="When users fill out the contact form and click the submit button, the application crashes with a null pointer exception. This affects all users trying to submit contact requests and prevents them from reaching our support team.",
            issue_type=IssueType.BUG,
            priority=Priority.HIGH,
            status=TicketStatus.OPEN,
            reporter=JiraUser(account_id="user1", display_name="Test User"),
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            steps_to_reproduce="1. Navigate to /contact page\n2. Fill out all required fields\n3. Click 'Submit' button\n4. Observe application crash",
            affected_version="2.1.0",
            project_key="TEST",
            project_name="Test Project"
        )
        
        # Low quality ticket
        low_quality_ticket = JiraTicket(
            key="TEST-002",
            id="1002",
            summary="Bug",
            description="It's broken",
            issue_type=IssueType.BUG,
            priority=Priority.MEDIUM,
            status=TicketStatus.OPEN,
            reporter=JiraUser(account_id="user2", display_name="Test User 2"),
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            project_key="TEST",
            project_name="Test Project"
        )
        
        test_tickets = [high_quality_ticket, low_quality_ticket]
        
        # Assess quality for each test ticket
        quality_engine = get_quality_engine()
        results = []
        
        for ticket in test_tickets:
            assessment = quality_engine.assess_ticket_quality(ticket)
            suggestions = quality_engine.get_quality_suggestions(assessment, ticket)
            
            results.append({
                "ticket_key": ticket.key,
                "ticket_summary": ticket.summary,
                "assessment": assessment.dict(),
                "suggestions": suggestions
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "test_results": results,
                "engine_info": {
                    "rules_count": len(quality_engine.rules),
                    "rules_version": "1.0"
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Quality engine test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Quality engine test failed")
