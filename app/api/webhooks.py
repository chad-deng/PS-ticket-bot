"""
JIRA webhook endpoints for PS Ticket Process Bot.
"""

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.models.ticket import WebhookEvent
from app.services.jira_client import get_jira_client
from app.utils.config_manager import get_config_manager


logger = logging.getLogger(__name__)
router = APIRouter()


def verify_webhook_signature(request: Request, body: bytes) -> bool:
    """
    Verify JIRA webhook signature for security.
    
    Args:
        request: FastAPI request object
        body: Raw request body
        
    Returns:
        bool: True if signature is valid
    """
    settings = get_settings()
    
    if not settings.webhook.verify_signature:
        logger.debug("Webhook signature verification disabled")
        return True
    
    # Get signature from header
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        logger.warning("Missing webhook signature header")
        return False
    
    # Extract signature
    try:
        signature = signature_header.split("=")[1]
    except (IndexError, AttributeError):
        logger.warning("Invalid signature header format")
        return False
    
    # Calculate expected signature
    secret = settings.webhook.secret.encode()
    expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    # Compare signatures
    is_valid = hmac.compare_digest(signature, expected_signature)
    
    if not is_valid:
        logger.warning("Invalid webhook signature")
    
    return is_valid


async def should_process_webhook(webhook_data: Dict[str, Any]) -> bool:
    """
    Determine if a webhook event should be processed.
    
    Args:
        webhook_data: Webhook payload
        
    Returns:
        bool: True if event should be processed
    """
    config_manager = get_config_manager()
    
    # Check if webhooks are enabled
    if not config_manager.settings.features.enable_webhooks:
        logger.debug("Webhooks are disabled")
        return False
    
    # Get issue data
    issue = webhook_data.get("issue", {})
    if not issue:
        logger.debug("No issue data in webhook")
        return False
    
    # Check project
    project = issue.get("fields", {}).get("project", {})
    project_key = project.get("key")
    
    project_config = config_manager.get_jira_project_config(project_key)
    if not project_config:
        logger.debug(f"Project {project_key} not configured for processing")
        return False
    
    # Check issue type
    issue_type = issue.get("fields", {}).get("issuetype", {})
    issue_type_name = issue_type.get("name")
    
    if not config_manager.should_process_issue_type(issue_type_name):
        logger.debug(f"Issue type {issue_type_name} not configured for processing")
        return False
    
    logger.info(f"Webhook event should be processed: {project_key} - {issue_type_name}")
    return True


async def queue_ticket_processing(issue_key: str, webhook_event: str):
    """
    Queue a ticket for processing.

    Args:
        issue_key: JIRA issue key
        webhook_event: Type of webhook event
    """
    from app.core.queue import get_queue_manager

    logger.info(f"Queuing ticket {issue_key} for processing (event: {webhook_event})")

    try:
        queue_manager = get_queue_manager()

        # Determine priority based on webhook event
        priority = "high" if webhook_event == "jira:issue_created" else "normal"

        # Queue the ticket
        task_id = queue_manager.queue_ticket_processing(issue_key, webhook_event, priority)

        logger.info(f"Successfully queued ticket {issue_key} with task ID {task_id}")

    except Exception as e:
        logger.error(f"Failed to queue ticket {issue_key}: {e}", exc_info=True)
        # Don't fail the webhook for queue errors
        pass


@router.post("/jira")
async def jira_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle JIRA webhook events.
    
    This endpoint receives webhook events from JIRA when issues are created or updated.
    It validates the webhook signature, filters relevant events, and queues them for processing.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify webhook signature
        if not verify_webhook_signature(request, body):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse JSON payload
        try:
            webhook_data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse webhook JSON: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Create webhook event model
        try:
            webhook_event = WebhookEvent(
                timestamp=datetime.utcnow(),
                webhook_event=webhook_data.get("webhookEvent", ""),
                issue_event_type_name=webhook_data.get("issue_event_type_name"),
                issue=webhook_data.get("issue", {}),
                user=webhook_data.get("user"),
                changelog=webhook_data.get("changelog")
            )
        except Exception as e:
            logger.error(f"Failed to create webhook event model: {e}")
            raise HTTPException(status_code=400, detail="Invalid webhook data")
        
        logger.info(f"Received webhook: {webhook_event.webhook_event} for issue {webhook_event.issue_key}")
        
        # Check if we should process this event
        if not await should_process_webhook(webhook_data):
            logger.debug(f"Skipping webhook event for {webhook_event.issue_key}")
            return JSONResponse(
                status_code=200,
                content={"status": "ignored", "reason": "Event not configured for processing"}
            )
        
        # Validate event type
        if not (webhook_event.is_issue_created or webhook_event.is_issue_updated):
            logger.debug(f"Ignoring webhook event type: {webhook_event.webhook_event}")
            return JSONResponse(
                status_code=200,
                content={"status": "ignored", "reason": "Event type not supported"}
            )
        
        # Queue the ticket for processing
        background_tasks.add_task(
            queue_ticket_processing,
            webhook_event.issue_key,
            webhook_event.webhook_event
        )
        
        logger.info(f"Successfully queued {webhook_event.issue_key} for processing")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "accepted",
                "issue_key": webhook_event.issue_key,
                "event_type": webhook_event.webhook_event,
                "timestamp": webhook_event.timestamp.isoformat()
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jira/test")
async def test_webhook():
    """
    Test endpoint for webhook functionality.
    
    This endpoint can be used to test webhook processing without actual JIRA events.
    """
    settings = get_settings()
    config_manager = get_config_manager()
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "webhook_config": {
                "verify_signature": settings.webhook.verify_signature,
                "webhooks_enabled": settings.features.enable_webhooks,
                "timeout": settings.webhook.timeout
            },
            "jira_config": {
                "base_url": settings.jira.base_url,
                "username": settings.jira.username,
                "projects": list(config_manager.settings.yaml_config.get("jira", {}).get("projects", {}).keys())
            }
        }
    )


@router.post("/jira/manual")
async def manual_process_ticket(
    issue_key: str,
    background_tasks: BackgroundTasks
):
    """
    Manually trigger ticket processing.
    
    This endpoint allows manual triggering of ticket processing for testing
    or reprocessing existing tickets.
    
    Args:
        issue_key: JIRA issue key to process
    """
    logger.info(f"Manual processing requested for {issue_key}")
    
    try:
        # Validate issue key format
        if not issue_key or "-" not in issue_key:
            raise HTTPException(status_code=400, detail="Invalid issue key format")
        
        # Check if the issue exists
        jira_client = get_jira_client()
        try:
            ticket = jira_client.get_issue_sync(issue_key)
        except Exception as e:
            logger.error(f"Failed to fetch issue {issue_key}: {e}")
            raise HTTPException(status_code=404, detail=f"Issue not found: {issue_key}")
        
        # Check if issue should be processed
        config_manager = get_config_manager()
        if not config_manager.should_process_issue_type(ticket.issue_type.value):
            raise HTTPException(
                status_code=400,
                detail=f"Issue type {ticket.issue_type.value} not configured for processing"
            )
        
        # Queue for processing
        background_tasks.add_task(
            queue_ticket_processing,
            issue_key,
            "manual_trigger"
        )
        
        logger.info(f"Successfully queued {issue_key} for manual processing")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "accepted",
                "issue_key": issue_key,
                "event_type": "manual_trigger",
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
        logger.error(f"Unexpected error in manual processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
