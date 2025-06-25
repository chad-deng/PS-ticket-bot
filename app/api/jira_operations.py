"""
JIRA operations API endpoints for PS Ticket Process Bot.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse

from app.services.jira_client import get_jira_client, JiraAPIError
from app.core.config import get_settings
from app.utils.config_manager import get_config_manager


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/comment/{issue_key}")
async def add_comment_to_ticket(
    issue_key: str,
    comment_body: str = Body(..., description="Comment text to add")
):
    """
    Add a comment to a JIRA ticket.
    
    Args:
        issue_key: JIRA issue key (e.g., SUPPORT-123)
        comment_body: Comment text to add
        
    Returns:
        Comment creation result with comment ID and metadata.
    """
    try:
        logger.info(f"Adding comment to ticket {issue_key}")
        
        # Validate inputs
        if not comment_body or not comment_body.strip():
            raise HTTPException(status_code=400, detail="Comment body cannot be empty")
        
        if len(comment_body) > 32767:  # JIRA comment limit
            raise HTTPException(status_code=400, detail="Comment body exceeds maximum length (32767 characters)")
        
        # Get JIRA client and add comment
        jira_client = get_jira_client()
        
        try:
            result = await jira_client.add_comment(issue_key, comment_body.strip())
            
            logger.info(f"Successfully added comment to {issue_key}: {result.get('id')}")
            
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "comment_id": result.get("id"),
                    "issue_key": issue_key,
                    "comment_length": len(comment_body.strip()),
                    "created": result.get("created"),
                    "author": result.get("author", {}).get("displayName"),
                    "message": f"Comment successfully added to {issue_key}"
                }
            )
            
        except JiraAPIError as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Ticket {issue_key} not found")
            elif e.status_code == 403:
                raise HTTPException(status_code=403, detail="Insufficient permissions to add comment")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to add comment: {e.message}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comment addition failed for {issue_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Comment addition failed")


@router.post("/transition/{issue_key}")
async def transition_ticket(
    issue_key: str,
    transition_id: str = Body(..., description="ID of the transition to execute"),
    comment: Optional[str] = Body(None, description="Optional comment to add with transition")
):
    """
    Transition a JIRA ticket to a new status.
    
    Args:
        issue_key: JIRA issue key
        transition_id: ID of the transition to execute
        comment: Optional comment to add with the transition
        
    Returns:
        Transition result with new status information.
    """
    try:
        logger.info(f"Transitioning ticket {issue_key} with transition {transition_id}")
        
        # Validate inputs
        if not transition_id or not transition_id.strip():
            raise HTTPException(status_code=400, detail="Transition ID cannot be empty")
        
        jira_client = get_jira_client()
        
        # Add comment first if provided
        comment_id = None
        if comment and comment.strip():
            try:
                comment_result = await jira_client.add_comment(issue_key, comment.strip())
                comment_id = comment_result.get("id")
                logger.info(f"Added comment {comment_id} before transition")
            except Exception as e:
                logger.warning(f"Failed to add comment before transition: {e}")
                # Continue with transition even if comment fails
        
        # Execute transition
        try:
            result = await jira_client.transition_issue(issue_key, transition_id.strip())
            
            # Get updated ticket info
            updated_ticket = jira_client.get_issue_sync(issue_key)
            
            logger.info(f"Successfully transitioned {issue_key} to {updated_ticket.status.value}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "issue_key": issue_key,
                    "transition_id": transition_id,
                    "new_status": updated_ticket.status.value,
                    "comment_id": comment_id,
                    "message": f"Ticket {issue_key} successfully transitioned to {updated_ticket.status.value}"
                }
            )
            
        except JiraAPIError as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Ticket {issue_key} not found")
            elif e.status_code == 400:
                raise HTTPException(status_code=400, detail=f"Invalid transition ID: {transition_id}")
            elif e.status_code == 403:
                raise HTTPException(status_code=403, detail="Insufficient permissions to transition ticket")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to transition ticket: {e.message}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transition failed for {issue_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ticket transition failed")


@router.get("/transitions/{issue_key}")
async def get_available_transitions(issue_key: str):
    """
    Get available transitions for a JIRA ticket.
    
    Args:
        issue_key: JIRA issue key
        
    Returns:
        List of available transitions with IDs and target statuses.
    """
    try:
        logger.info(f"Getting available transitions for {issue_key}")
        
        jira_client = get_jira_client()
        
        try:
            transitions = await jira_client.get_available_transitions(issue_key)
            
            # Format transitions for easier use
            formatted_transitions = []
            for transition in transitions:
                formatted_transitions.append({
                    "id": transition.get("id"),
                    "name": transition.get("name"),
                    "to_status": transition.get("to", {}).get("name"),
                    "to_status_id": transition.get("to", {}).get("id")
                })
            
            logger.info(f"Found {len(formatted_transitions)} transitions for {issue_key}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "issue_key": issue_key,
                    "transitions": formatted_transitions,
                    "count": len(formatted_transitions)
                }
            )
            
        except JiraAPIError as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Ticket {issue_key} not found")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to get transitions: {e.message}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get transitions for {issue_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve transitions")


@router.get("/ticket/{issue_key}")
async def get_ticket_info(issue_key: str):
    """
    Get detailed information about a JIRA ticket.
    
    Args:
        issue_key: JIRA issue key
        
    Returns:
        Detailed ticket information.
    """
    try:
        logger.info(f"Getting ticket info for {issue_key}")
        
        jira_client = get_jira_client()
        
        try:
            ticket = jira_client.get_issue_sync(issue_key)
            
            return JSONResponse(
                status_code=200,
                content={
                    "ticket": ticket.to_dict(),
                    "metadata": {
                        "has_attachments": ticket.has_attachments,
                        "is_high_priority": ticket.is_high_priority,
                        "is_bug": ticket.is_bug,
                        "attachment_count": len(ticket.attachments)
                    }
                }
            )
            
        except JiraAPIError as e:
            if e.status_code == 404:
                logger.warning(f"Ticket {issue_key} not found")
                raise HTTPException(status_code=404, detail=f"Ticket {issue_key} not found")
            else:
                logger.error(f"JIRA API error: {e.message}, status: {e.status_code}")
                raise HTTPException(status_code=500, detail=f"Failed to get ticket: {e.message}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ticket info for {issue_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve ticket information")


@router.post("/process/{issue_key}")
async def process_ticket_manually(
    issue_key: str,
    force_reprocess: bool = Query(False, description="Force reprocessing even if already processed"),
    skip_quality_check: bool = Query(False, description="Skip quality assessment"),
    skip_ai_comment: bool = Query(False, description="Skip AI comment generation"),
    skip_transition: bool = Query(False, description="Skip status transition")
):
    """
    Manually trigger complete ticket processing.
    
    This endpoint allows manual triggering of the full ticket processing pipeline
    with options to skip certain steps.
    
    Args:
        issue_key: JIRA issue key to process
        force_reprocess: Force reprocessing even if already processed
        skip_quality_check: Skip quality assessment step
        skip_ai_comment: Skip AI comment generation step
        skip_transition: Skip status transition step
        
    Returns:
        Processing result with details of each step.
    """
    try:
        logger.info(f"Manual processing requested for {issue_key}")
        
        # Check if ticket exists
        jira_client = get_jira_client()
        try:
            ticket = jira_client.get_issue_sync(issue_key)
        except JiraAPIError as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Ticket {issue_key} not found")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to fetch ticket: {e.message}")
        
        # Check if ticket should be processed
        config_manager = get_config_manager()
        if not config_manager.should_process_issue_type(ticket.issue_type.value):
            raise HTTPException(
                status_code=400,
                detail=f"Issue type {ticket.issue_type.value} not configured for processing"
            )
        
        # Queue the ticket for processing with custom options
        from app.core.queue import get_queue_manager

        queue_manager = get_queue_manager()

        # Prepare processing options
        processing_options = {
            "force_reprocess": force_reprocess,
            "skip_quality_check": skip_quality_check,
            "skip_ai_comment": skip_ai_comment,
            "skip_transition": skip_transition
        }

        # For manual processing, we'll use high priority
        task_id = queue_manager.queue_ticket_processing(
            issue_key,
            "manual_trigger",
            "high",
            processing_options
        )
        
        logger.info(f"Successfully queued {issue_key} for manual processing with task ID {task_id}")
        
        return JSONResponse(
            status_code=202,  # Accepted for processing
            content={
                "status": "accepted",
                "issue_key": issue_key,
                "task_id": task_id,
                "processing_options": {
                    "force_reprocess": force_reprocess,
                    "skip_quality_check": skip_quality_check,
                    "skip_ai_comment": skip_ai_comment,
                    "skip_transition": skip_transition
                },
                "ticket_info": {
                    "summary": ticket.summary,
                    "issue_type": ticket.issue_type.value,
                    "priority": ticket.priority.value,
                    "status": ticket.status.value
                },
                "message": f"Ticket {issue_key} queued for processing. Use task ID {task_id} to check status."
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual processing failed for {issue_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Manual processing failed")


@router.get("/test/connection")
async def test_jira_connection():
    """
    Test JIRA API connection and permissions.

    Returns:
        Connection test results with permission information.
    """
    import httpx
    from datetime import datetime

    try:
        logger.info("Testing JIRA connection")

        jira_client = get_jira_client()
        settings = get_settings()

        # Check if we're in development mode with example.atlassian.net
        dev_mode = "example.atlassian.net" in settings.jira.base_url and settings.app.environment == "development"

        if dev_mode:
            logger.info("Using mock connection in development mode")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "jira_url": settings.jira.base_url,
                    "username": settings.jira.username,
                    "test_results": {
                        "connection": True,
                        "authentication": True,
                        "permissions": {"browse_projects": True, "view_issues": True},
                        "server_info": {
                            "user": "Development User",
                            "account_id": "dev-account-123",
                            "email": "dev@example.com"
                        },
                        "errors": []
                    },
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        # Test basic connectivity by getting server info
        # This is a simple test that doesn't require specific permissions
        test_results = {
            "connection": False,
            "authentication": False,
            "permissions": {},
            "server_info": {},
            "errors": []
        }
        
        try:
            # Try to make a simple API call
            # We'll use the current user endpoint as a test
            url = f"{settings.jira.base_url}/rest/api/2/myself"
            auth = (settings.jira.username, settings.jira.api_token)

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, auth=auth)

                if response.status_code == 200:
                    test_results["connection"] = True
                    test_results["authentication"] = True

                    user_info = response.json()
                    test_results["server_info"] = {
                        "user": user_info.get("displayName"),
                        "account_id": user_info.get("accountId"),
                        "email": user_info.get("emailAddress")
                    }

                elif response.status_code == 401:
                    test_results["connection"] = True
                    test_results["authentication"] = False
                    test_results["errors"].append("Authentication failed - check username and API token")

                else:
                    test_results["connection"] = True
                    test_results["errors"].append(f"Unexpected response: {response.status_code}")

        except Exception as e:
            test_results["errors"].append(f"Connection failed: {str(e)}")
        
        # Determine overall status
        overall_status = "healthy" if (test_results["connection"] and test_results["authentication"]) else "unhealthy"
        status_code = 200 if overall_status == "healthy" else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": overall_status,
                "jira_url": settings.jira.base_url,
                "username": settings.jira.username,
                "test_results": test_results,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"JIRA connection test failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@router.get("/debug/config")
async def debug_config():
    """
    Debug endpoint to check current JIRA configuration.

    Returns:
        Current JIRA configuration and environment variables.
    """
    import os
    from datetime import datetime

    try:
        settings = get_settings()
        jira_client = get_jira_client()

        return JSONResponse(
            status_code=200,
            content={
                "environment_variables": {
                    "JIRA_BASE_URL": os.getenv("JIRA_BASE_URL"),
                    "JIRA_USERNAME": os.getenv("JIRA_USERNAME"),
                    "ENVIRONMENT": os.getenv("ENVIRONMENT"),
                    "JIRA_API_TOKEN": "***" if os.getenv("JIRA_API_TOKEN") else None
                },
                "settings_config": {
                    "jira_base_url": settings.jira.base_url,
                    "jira_username": settings.jira.username,
                    "app_environment": settings.app.environment
                },
                "jira_client_config": {
                    "base_url": jira_client.base_url,
                    "username": jira_client.username,
                    "dev_mode": jira_client.dev_mode
                },
                "timestamp": datetime.now().isoformat()
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )
