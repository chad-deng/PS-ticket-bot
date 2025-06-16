"""
AI comment generation API endpoints for PS Ticket Process Bot.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.gemini_client import get_gemini_client, GeminiAPIError
from app.services.jira_client import get_jira_client, JiraAPIError
from app.core.quality_engine import get_quality_engine
from app.models.ticket import JiraTicket, QualityAssessment


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate/{issue_key}")
async def generate_comment_for_ticket(issue_key: str):
    """
    Generate an AI comment for a specific JIRA ticket.
    
    This endpoint fetches the ticket, assesses its quality, and generates
    an appropriate AI comment based on the assessment.
    
    Args:
        issue_key: JIRA issue key (e.g., SUPPORT-123)
        
    Returns:
        Generated comment with metadata about the generation process.
    """
    try:
        logger.info(f"Generating AI comment for ticket {issue_key}")
        
        # Fetch ticket from JIRA
        jira_client = get_jira_client()
        try:
            ticket = jira_client.get_issue_sync(issue_key)
        except JiraAPIError as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Ticket {issue_key} not found")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to fetch ticket: {e.message}")
        
        # Assess ticket quality
        quality_engine = get_quality_engine()
        assessment = quality_engine.assess_ticket_quality(ticket)
        
        # Generate AI comment
        gemini_client = get_gemini_client()
        try:
            comment = await gemini_client.generate_comment(ticket, assessment)
            generated_by = "ai"
            ai_error = None
        except GeminiAPIError as e:
            logger.warning(f"AI generation failed for {issue_key}: {e}")
            comment = gemini_client.generate_fallback_comment(ticket, assessment)
            generated_by = "fallback"
            ai_error = str(e)
        
        logger.info(f"Successfully generated comment for {issue_key} using {generated_by}")
        
        return JSONResponse(
            status_code=200,
            content={
                "ticket_key": issue_key,
                "comment": comment,
                "generated_by": generated_by,
                "ai_error": ai_error,
                "quality_assessment": {
                    "overall_quality": assessment.overall_quality.value,
                    "score": assessment.score,
                    "issues_found": assessment.issues_found
                },
                "ticket_info": {
                    "summary": ticket.summary,
                    "issue_type": ticket.issue_type.value,
                    "priority": ticket.priority.value,
                    "status": ticket.status.value
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comment generation failed for {issue_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Comment generation failed")


@router.post("/generate")
async def generate_comment_from_data(
    ticket_data: Dict[str, Any],
    quality_assessment: Dict[str, Any]
):
    """
    Generate an AI comment from provided ticket data and quality assessment.
    
    This endpoint allows testing comment generation without fetching from JIRA.
    
    Args:
        ticket_data: Ticket data in JiraTicket format
        quality_assessment: Quality assessment in QualityAssessment format
        
    Returns:
        Generated comment with metadata.
    """
    try:
        # Validate and create models
        try:
            ticket = JiraTicket(**ticket_data)
            assessment = QualityAssessment(**quality_assessment)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid data format: {e}")
        
        # Generate AI comment
        gemini_client = get_gemini_client()
        try:
            comment = await gemini_client.generate_comment(ticket, assessment)
            generated_by = "ai"
            ai_error = None
        except GeminiAPIError as e:
            logger.warning(f"AI generation failed for {ticket.key}: {e}")
            comment = gemini_client.generate_fallback_comment(ticket, assessment)
            generated_by = "fallback"
            ai_error = str(e)
        
        logger.info(f"Generated comment for {ticket.key} using {generated_by}")
        
        return JSONResponse(
            status_code=200,
            content={
                "comment": comment,
                "generated_by": generated_by,
                "ai_error": ai_error,
                "quality_level": assessment.overall_quality.value
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comment generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Comment generation failed")


@router.get("/test")
async def test_ai_generation():
    """
    Test AI comment generation with sample data.
    
    Returns:
        Test results showing AI generation functionality.
    """
    try:
        from app.models.ticket import JiraUser, IssueType, Priority, TicketStatus, QualityLevel
        from datetime import datetime
        
        # Create test ticket
        test_ticket = JiraTicket(
            key="TEST-AI-001",
            id="ai001",
            summary="Test ticket for AI comment generation",
            description="This is a test ticket to verify AI comment generation functionality.",
            issue_type=IssueType.BUG,
            priority=Priority.MEDIUM,
            status=TicketStatus.OPEN,
            reporter=JiraUser(account_id="test_user", display_name="Test User"),
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            steps_to_reproduce="1. Run test\n2. Observe behavior",
            affected_version="1.0.0",
            project_key="TEST",
            project_name="Test Project"
        )
        
        # Create test quality assessment
        test_assessment = QualityAssessment(
            ticket_key="TEST-AI-001",
            overall_quality=QualityLevel.MEDIUM,
            issues_found=["Description could be more detailed"],
            score=75,
            assessed_at=datetime.utcnow()
        )
        
        # Test AI generation
        gemini_client = get_gemini_client()
        
        # Test API connection first
        connection_test = await gemini_client.test_api_connection()
        
        if connection_test["success"]:
            # Generate comment
            try:
                ai_comment = await gemini_client.generate_comment(test_ticket, test_assessment)
                ai_success = True
                ai_error = None
            except Exception as e:
                ai_comment = None
                ai_success = False
                ai_error = str(e)
            
            # Generate fallback comment
            fallback_comment = gemini_client.generate_fallback_comment(test_ticket, test_assessment)
            
            return JSONResponse(
                status_code=200,
                content={
                    "api_connection": connection_test,
                    "ai_generation": {
                        "success": ai_success,
                        "comment": ai_comment,
                        "error": ai_error
                    },
                    "fallback_generation": {
                        "success": True,
                        "comment": fallback_comment
                    },
                    "test_data": {
                        "ticket_key": test_ticket.key,
                        "quality_level": test_assessment.overall_quality.value
                    }
                }
            )
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "api_connection": connection_test,
                    "message": "AI service unavailable, only fallback generation available"
                }
            )
        
    except Exception as e:
        logger.error(f"AI generation test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI generation test failed")


@router.get("/config")
async def get_ai_config():
    """
    Get AI comment generation configuration.
    
    Returns:
        Current AI generation configuration and settings.
    """
    try:
        from app.core.config import get_settings
        from app.utils.config_manager import get_config_manager
        
        settings = get_settings()
        config_manager = get_config_manager()
        
        # Get Gemini configuration
        gemini_config = {
            "model": settings.gemini.model,
            "temperature": settings.gemini.temperature,
            "top_p": settings.gemini.top_p,
            "top_k": settings.gemini.top_k,
            "max_output_tokens": settings.gemini.max_output_tokens,
            "timeout": settings.gemini.timeout,
            "max_retries": settings.gemini.max_retries
        }
        
        # Get comment templates
        templates = config_manager.get_comment_templates()
        
        # Get feature flags
        features = {
            "ai_comments_enabled": settings.features.enable_ai_comments,
            "fallback_enabled": True
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "gemini_config": gemini_config,
                "comment_templates": templates,
                "features": features
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get AI config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve AI configuration")


@router.get("/stats")
async def get_ai_stats():
    """
    Get AI comment generation statistics.
    
    Returns:
        Statistics about AI comment generation performance.
    """
    try:
        # TODO: Implement AI generation statistics tracking
        # For now, return placeholder data
        
        stats = {
            "total_comments_generated": 0,
            "ai_generation_success_rate": 0,
            "fallback_usage_rate": 0,
            "average_generation_time": 0,
            "generation_by_quality": {
                "high": 0,
                "medium": 0,
                "low": 0
            },
            "error_types": {
                "rate_limit": 0,
                "api_error": 0,
                "timeout": 0,
                "other": 0
            }
        }
        
        return JSONResponse(
            status_code=200,
            content=stats
        )
        
    except Exception as e:
        logger.error(f"Failed to get AI stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve AI statistics")
