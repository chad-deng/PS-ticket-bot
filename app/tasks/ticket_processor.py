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
def process_ticket(self, issue_key: str, webhook_event: str, processing_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Main ticket processing task that orchestrates the entire pipeline.

    Updated Process Flow:
    1. Fetch JIRA ticket based on schedule and search conditions
    2. Check required fields are filled
    3. Search for duplicate tickets in JIRA
    4. AI assess ticket quality
    5. AI add comment and transition status

    Args:
        issue_key: JIRA issue key
        webhook_event: Type of webhook event that triggered processing
        processing_options: Optional processing options (force_reprocess, skip_quality_check, etc.)

    Returns:
        Dict: Processing result
    """
    start_time = time.time()
    logger.info(f"Starting ticket processing for {issue_key} (event: {webhook_event})")

    # Parse processing options
    if processing_options is None:
        processing_options = {}

    force_reprocess = processing_options.get("force_reprocess", False)
    skip_quality_check = processing_options.get("skip_quality_check", False)
    skip_ai_comment = processing_options.get("skip_ai_comment", False)
    skip_transition = processing_options.get("skip_transition", False)

    logger.info(f"Processing options for {issue_key}: force_reprocess={force_reprocess}, skip_quality_check={skip_quality_check}, skip_ai_comment={skip_ai_comment}, skip_transition={skip_transition}")

    # Initialize processing result
    result = ProcessingResult(
        ticket_key=issue_key,
        success=False
    )
    
    try:
        # Step 1: Fetch JIRA ticket based on schedule and search conditions
        logger.info(f"Step 1: Fetching ticket {issue_key} from JIRA")
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

        # Check if ticket should be processed
        config_manager = get_config_manager()
        if not config_manager.should_process_issue_type(ticket.issue_type.value):
            logger.info(f"Skipping ticket {issue_key} - issue type {ticket.issue_type.value} not configured for processing")
            result.success = True
            result.error_message = f"Issue type {ticket.issue_type.value} not configured for processing"
            return result.dict()

        # Step 2: Check required fields are filled
        logger.info(f"Step 2: Checking required fields for ticket {issue_key}")
        required_fields_result = _check_required_fields_sync(ticket)

        if not required_fields_result.get("success"):
            logger.warning(f"Required fields check failed for {issue_key}: {required_fields_result.get('message')}")
            # Continue processing but note the missing fields

        # Step 3: Search for duplicate tickets in JIRA
        logger.info(f"Step 3: Searching for duplicate tickets for {issue_key}")
        duplicate_search_result = _search_duplicate_tickets_sync(ticket, jira_client)

        if duplicate_search_result.get("duplicates_found", 0) > 0:
            logger.warning(f"Found {duplicate_search_result.get('duplicates_found')} potential duplicates for {issue_key}")
            # Continue processing but note the duplicates

        # Step 4: AI assess ticket quality (unless skipped)
        if skip_quality_check:
            logger.info(f"Step 4: Skipping quality assessment for ticket {issue_key} (skip_quality_check=True)")
            # Use default quality level for skipped assessment
            quality_level = "medium"
            result.quality_assessed = False
            quality_result = {
                "success": True,
                "assessment": {"overall_quality": {"value": "medium"}, "score": 50},
                "quality_level": "medium"
            }
        else:
            logger.info(f"Step 4: AI assessing quality for ticket {issue_key}")
            quality_result = _assess_quality_sync(ticket.dict())

            if not quality_result.get("success"):
                logger.error(f"Quality assessment failed for {issue_key}")
                result.error_message = quality_result.get("error", "Quality assessment failed")
                result.error_step = "quality_assessment"
                return result.dict()

            result.quality_assessed = True
            result.quality_assessment = quality_result.get("assessment")
            quality_level = quality_result.get("quality_level")

        # Step 5: AI add comment and transition status
        logger.info(f"Step 5: AI adding comment and transitioning status for ticket {issue_key}")

        # Generate and post AI comment (if enabled and not skipped)
        if skip_ai_comment:
            logger.info(f"Skipping AI comment generation for ticket {issue_key} (skip_ai_comment=True)")
            result.comment_generated = False
            result.comment_posted = False
        elif config_manager.settings.features.enable_ai_comments:
            logger.info(f"Generating AI comment for ticket {issue_key}")
            comment_result = _generate_comment_sync(ticket.dict(), quality_result.get("assessment"))

            if comment_result.get("success"):
                result.comment_generated = True
                result.generated_comment = comment_result.get("comment")

                # Post comment to JIRA
                logger.info(f"Posting AI comment to ticket {issue_key}")
                post_result = _post_comment_sync(issue_key, comment_result.get("comment"))

                if post_result.get("success"):
                    result.comment_posted = True
                    logger.info(f"Successfully posted AI comment to {issue_key}")
                else:
                    logger.warning(f"Failed to post comment to {issue_key}: {post_result.get('error')}")
            else:
                logger.warning(f"Comment generation failed for {issue_key}: {comment_result.get('error')}")
        else:
            logger.info(f"AI comments disabled in configuration for ticket {issue_key}")

        # Transition ticket status based on quality (if enabled and not skipped)
        if skip_transition:
            logger.info(f"Skipping status transition for ticket {issue_key} (skip_transition=True)")
            result.status_transitioned = False
        elif config_manager.settings.features.enable_status_transitions:
            logger.info(f"Transitioning ticket {issue_key} based on quality level: {quality_level}")
            transition_result = _transition_ticket_sync(issue_key, quality_level)

            if transition_result.get("success"):
                result.status_transitioned = True
                result.new_status = transition_result.get("new_status")
                logger.info(f"Successfully transitioned {issue_key} to {result.new_status}")
            else:
                logger.warning(f"Failed to transition ticket {issue_key}: {transition_result.get('error')}")
                # Don't fail the entire process for transition failures
        else:
            logger.info(f"Status transitions disabled in configuration for ticket {issue_key}")
        
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


# Synchronous helper functions to avoid Celery anti-patterns

def _assess_quality_sync(ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous quality assessment function.

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
        ticket = JiraTicket(**ticket_data)

        # Get quality engine and assess ticket
        quality_engine = get_quality_engine()
        logger.info(f"Initialized quality assessment engine with {len(quality_engine.rules)} rules")
        assessment = quality_engine.assess_ticket_quality(ticket)

        logger.info(f"Quality assessment complete for {ticket_data.get('key')}: {assessment.overall_quality.value} ({assessment.score}/100)")

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


def _generate_comment_sync(ticket_data: Dict[str, Any], quality_assessment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous comment generation function.

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


def _post_comment_sync(issue_key: str, comment_body: str) -> Dict[str, Any]:
    """
    Synchronous comment posting function.

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
        return {
            "success": False,
            "error": str(e)
        }


def _transition_ticket_sync(issue_key: str, quality_level: str) -> Dict[str, Any]:
    """
    Synchronous ticket transition function.

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
        return {
            "success": False,
            "error": str(e)
        }


def _check_required_fields_sync(ticket) -> Dict[str, Any]:
    """
    Check if required fields are filled in the ticket.

    Args:
        ticket: JiraTicket instance

    Returns:
        Dict: Required fields check result
    """
    logger.info(f"Checking required fields for ticket {ticket.key}")

    missing_fields = []
    warnings = []

    # Check basic required fields
    if not ticket.summary or len(ticket.summary.strip()) < 5:
        missing_fields.append("Summary is too short or empty")

    if not ticket.description or len(ticket.description.strip()) < 10:
        missing_fields.append("Description is too short or empty")

    # Check issue type specific requirements
    if ticket.issue_type.value in ["Problem", "Bug"]:
        if not ticket.steps_to_reproduce:
            missing_fields.append("Steps to reproduce are missing for Problem/Bug tickets")
        elif len(ticket.steps_to_reproduce.strip()) < 20:
            warnings.append("Steps to reproduce are very brief")

        if not ticket.affected_version:
            missing_fields.append("Affected version is missing for Problem/Bug tickets")

    # Check priority
    if not ticket.priority:
        missing_fields.append("Priority is not set")

    # Check reporter
    if not ticket.reporter:
        missing_fields.append("Reporter is not set")

    success = len(missing_fields) == 0
    message = f"Required fields check: {len(missing_fields)} missing, {len(warnings)} warnings"

    if missing_fields:
        message += f" - Missing: {', '.join(missing_fields)}"
    if warnings:
        message += f" - Warnings: {', '.join(warnings)}"

    logger.info(f"Required fields check for {ticket.key}: {message}")

    return {
        "success": success,
        "missing_fields": missing_fields,
        "warnings": warnings,
        "message": message
    }


def _search_duplicate_tickets_sync(ticket, jira_client) -> Dict[str, Any]:
    """
    Search for potential duplicate tickets in JIRA.

    Args:
        ticket: JiraTicket instance
        jira_client: JIRA client instance

    Returns:
        Dict: Duplicate search result
    """
    logger.info(f"Searching for duplicate tickets for {ticket.key}")

    try:
        # Build search query for potential duplicates
        # Search for tickets with similar summary in the same project
        summary_words = ticket.summary.split()
        if len(summary_words) < 2:
            logger.info(f"Summary too short for duplicate search: {ticket.key}")
            return {
                "success": True,
                "duplicates_found": 0,
                "duplicates": [],
                "message": "Summary too short for meaningful duplicate search"
            }

        # Use key words from summary for search
        key_words = [word for word in summary_words if len(word) > 3][:3]  # Take first 3 meaningful words
        if not key_words:
            key_words = summary_words[:2]  # Fallback to first 2 words

        # Build JQL query to find similar tickets
        search_terms = " AND ".join([f'summary ~ "{word}"' for word in key_words])
        jql_query = f'project = "{ticket.project_key}" AND {search_terms} AND key != "{ticket.key}" AND status != "Closed"'

        logger.debug(f"Duplicate search JQL: {jql_query}")

        # Execute search
        search_results = jira_client.search_issues_sync(
            jql=jql_query,
            start_at=0,
            max_results=10  # Limit to 10 potential duplicates
        )

        duplicates = []
        for issue in search_results.get("issues", []):
            duplicates.append({
                "key": issue.get("key"),
                "summary": issue.get("fields", {}).get("summary", ""),
                "status": issue.get("fields", {}).get("status", {}).get("name", ""),
                "created": issue.get("fields", {}).get("created", "")
            })

        duplicates_found = len(duplicates)
        message = f"Found {duplicates_found} potential duplicates for {ticket.key}"

        if duplicates_found > 0:
            logger.warning(f"{message}: {[d['key'] for d in duplicates]}")
        else:
            logger.info(f"No duplicates found for {ticket.key}")

        return {
            "success": True,
            "duplicates_found": duplicates_found,
            "duplicates": duplicates,
            "message": message,
            "search_query": jql_query
        }

    except Exception as e:
        logger.error(f"Duplicate search failed for {ticket.key}: {e}")
        return {
            "success": False,
            "duplicates_found": 0,
            "duplicates": [],
            "error": str(e),
            "message": f"Duplicate search failed: {str(e)}"
        }
