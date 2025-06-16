"""
Celery tasks for ticket processing pipeline.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from app.core.queue import celery_app
from app.models.ticket import ProcessingResult, QualityLevel
from app.services.jira_client import get_jira_client, JiraAPIError
from app.utils.config_manager import get_config_manager


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_ticket(self, issue_key: str, webhook_event: str) -> Dict[str, Any]:
    """
    Main ticket processing task that orchestrates the entire pipeline.
    
    Args:
        issue_key: JIRA issue key
        webhook_event: Type of webhook event that triggered processing
        
    Returns:
        Dict: Processing result
    """
    start_time = time.time()
    logger.info(f"Starting ticket processing for {issue_key} (event: {webhook_event})")
    
    # Initialize processing result
    result = ProcessingResult(
        ticket_key=issue_key,
        success=False
    )
    
    try:
        # Step 1: Fetch ticket from JIRA
        logger.info(f"Fetching ticket {issue_key} from JIRA")
        jira_client = get_jira_client()
        
        try:
            ticket = jira_client.get_issue_sync(issue_key)
            result.ingested = True
            logger.info(f"Successfully fetched ticket {issue_key}")
        except JiraAPIError as e:
            logger.error(f"Failed to fetch ticket {issue_key}: {e}")
            result.error_message = f"Failed to fetch ticket: {e.message}"
            result.error_step = "ingestion"
            return result.dict()
        
        # Step 2: Check if ticket should be processed
        config_manager = get_config_manager()
        if not config_manager.should_process_issue_type(ticket.issue_type.value):
            logger.info(f"Skipping ticket {issue_key} - issue type {ticket.issue_type.value} not configured for processing")
            result.success = True
            result.error_message = f"Issue type {ticket.issue_type.value} not configured for processing"
            return result.dict()
        
        # Step 3: Quality assessment
        logger.info(f"Assessing quality for ticket {issue_key}")
        quality_task = assess_quality.delay(ticket.dict())
        quality_result = quality_task.get(timeout=300)  # 5 minute timeout
        
        if not quality_result.get("success"):
            logger.error(f"Quality assessment failed for {issue_key}")
            result.error_message = quality_result.get("error", "Quality assessment failed")
            result.error_step = "quality_assessment"
            return result.dict()
        
        result.quality_assessed = True
        result.quality_assessment = quality_result.get("assessment")
        quality_level = quality_result.get("quality_level")
        
        # Step 4: Generate AI comment (if enabled)
        if config_manager.settings.features.enable_ai_comments:
            logger.info(f"Generating AI comment for ticket {issue_key}")
            comment_task = generate_comment.delay(ticket.dict(), quality_result.get("assessment"))
            comment_result = comment_task.get(timeout=300)
            
            if not comment_result.get("success"):
                logger.error(f"Comment generation failed for {issue_key}")
                result.error_message = comment_result.get("error", "Comment generation failed")
                result.error_step = "comment_generation"
                return result.dict()
            
            result.comment_generated = True
            result.generated_comment = comment_result.get("comment")
            
            # Step 5: Post comment to JIRA
            logger.info(f"Posting comment to ticket {issue_key}")
            post_task = post_comment.delay(issue_key, comment_result.get("comment"))
            post_result = post_task.get(timeout=300)
            
            if not post_result.get("success"):
                logger.error(f"Failed to post comment to {issue_key}")
                result.error_message = post_result.get("error", "Failed to post comment")
                result.error_step = "comment_posting"
                return result.dict()
            
            result.comment_posted = True
        
        # Step 6: Transition ticket status (if enabled)
        if config_manager.settings.features.enable_status_transitions:
            logger.info(f"Transitioning ticket {issue_key} based on quality level: {quality_level}")
            transition_task = transition_ticket.delay(issue_key, quality_level)
            transition_result = transition_task.get(timeout=300)
            
            if not transition_result.get("success"):
                logger.warning(f"Failed to transition ticket {issue_key}: {transition_result.get('error')}")
                # Don't fail the entire process for transition failures
            else:
                result.status_transitioned = True
                result.new_status = transition_result.get("new_status")
        
        # Success!
        result.success = True
        processing_time = time.time() - start_time
        result.processing_time_seconds = processing_time
        
        logger.info(f"Successfully processed ticket {issue_key} in {processing_time:.2f} seconds")
        return result.dict()
        
    except Exception as e:
        logger.error(f"Unexpected error processing ticket {issue_key}: {e}", exc_info=True)
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying ticket processing for {issue_key} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # Exponential backoff
        
        result.error_message = f"Unexpected error: {str(e)}"
        result.error_step = "unknown"
        return result.dict()


@celery_app.task(bind=True, max_retries=2)
def assess_quality(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess ticket quality based on configured rules.

    Args:
        ticket_data: Ticket data dictionary

    Returns:
        Dict: Quality assessment result
    """
    logger.info(f"Assessing quality for ticket {ticket_data.get('key')}")

    try:
        from app.core.quality_engine import get_quality_engine
        from app.models.ticket import JiraTicket

        # Convert ticket data back to JiraTicket model
        # Note: This is a simplified conversion for the task
        # In a real implementation, you might want to store the full ticket object
        ticket = JiraTicket(**ticket_data)

        # Get quality engine and assess ticket
        quality_engine = get_quality_engine()
        assessment = quality_engine.assess_ticket_quality(ticket)

        logger.info(f"Quality assessment complete for {ticket_data.get('key')}: {assessment.overall_quality.value}")

        return {
            "success": True,
            "assessment": assessment.dict(),
            "quality_level": assessment.overall_quality.value
        }

    except Exception as e:
        logger.error(f"Quality assessment failed for {ticket_data.get('key')}: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(bind=True, max_retries=2)
def generate_comment(self, ticket_data: Dict[str, Any], quality_assessment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate AI comment based on ticket data and quality assessment.

    Args:
        ticket_data: Ticket data dictionary
        quality_assessment: Quality assessment result

    Returns:
        Dict: Comment generation result
    """
    logger.info(f"Generating AI comment for ticket {ticket_data.get('key')}")

    try:
        from app.services.gemini_client import get_gemini_client
        from app.models.ticket import JiraTicket, QualityAssessment

        # Convert data back to models
        ticket = JiraTicket(**ticket_data)
        assessment = QualityAssessment(**quality_assessment)

        # Get Gemini client
        gemini_client = get_gemini_client()

        # Try to generate AI comment
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                comment = loop.run_until_complete(
                    gemini_client.generate_comment(ticket, assessment)
                )
                logger.info(f"Generated AI comment for ticket {ticket_data.get('key')}")

                return {
                    "success": True,
                    "comment": comment,
                    "generated_by": "ai"
                }
            finally:
                loop.close()

        except Exception as ai_error:
            logger.warning(f"AI comment generation failed for {ticket_data.get('key')}: {ai_error}")
            logger.info(f"Falling back to template comment for {ticket_data.get('key')}")

            # Fall back to template-based comment
            fallback_comment = gemini_client.generate_fallback_comment(ticket, assessment)

            return {
                "success": True,
                "comment": fallback_comment,
                "generated_by": "fallback",
                "ai_error": str(ai_error)
            }

    except Exception as e:
        logger.error(f"Comment generation failed for {ticket_data.get('key')}: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(bind=True, max_retries=3)
def post_comment(self, issue_key: str, comment_body: str) -> Dict[str, Any]:
    """
    Post a comment to a JIRA ticket.
    
    Args:
        issue_key: JIRA issue key
        comment_body: Comment text to post
        
    Returns:
        Dict: Comment posting result
    """
    logger.info(f"Posting comment to ticket {issue_key}")
    
    try:
        jira_client = get_jira_client()
        
        # Use sync version for Celery tasks
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(jira_client.add_comment(issue_key, comment_body))
            logger.info(f"Successfully posted comment to {issue_key}")
            
            return {
                "success": True,
                "comment_id": result.get("id")
            }
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Failed to post comment to {issue_key}: {e}", exc_info=True)
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying comment posting for {issue_key}")
            raise self.retry(countdown=30 * (2 ** self.request.retries))
        
        return {
            "success": False,
            "error": str(e)
        }


@celery_app.task(bind=True, max_retries=3)
def transition_ticket(self, issue_key: str, quality_level: str) -> Dict[str, Any]:
    """
    Transition a ticket based on its quality level.
    
    Args:
        issue_key: JIRA issue key
        quality_level: Quality level (high, medium, low)
        
    Returns:
        Dict: Transition result
    """
    logger.info(f"Transitioning ticket {issue_key} for quality level: {quality_level}")
    
    try:
        config_manager = get_config_manager()
        
        # Get appropriate transition for quality level
        transition_config = config_manager.get_transition_for_quality(quality_level)
        if not transition_config:
            logger.warning(f"No transition configured for quality level: {quality_level}")
            return {
                "success": False,
                "error": f"No transition configured for quality level: {quality_level}"
            }
        
        transition_id = transition_config.get("transition_id")
        target_status = transition_config.get("target_status")
        
        if not transition_id:
            logger.warning(f"Transition ID not configured for quality level: {quality_level}")
            return {
                "success": False,
                "error": f"Transition ID not configured for quality level: {quality_level}"
            }
        
        # Execute transition
        jira_client = get_jira_client()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(jira_client.transition_issue(issue_key, transition_id))
            logger.info(f"Successfully transitioned {issue_key} to {target_status}")
            
            return {
                "success": True,
                "new_status": target_status,
                "transition_id": transition_id
            }
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Failed to transition ticket {issue_key}: {e}", exc_info=True)
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying transition for {issue_key}")
            raise self.retry(countdown=30 * (2 ** self.request.retries))
        
        return {
            "success": False,
            "error": str(e)
        }
