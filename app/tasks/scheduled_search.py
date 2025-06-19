"""
Scheduled JIRA search tasks for PS Ticket Process Bot.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.queue import celery_app
from app.services.jira_client import get_jira_client, JiraAPIError
from app.utils.config_manager import get_config_manager
from app.tasks.ticket_processor import process_ticket


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)  # 5 minute retry delay
def scheduled_ticket_search(self, search_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Scheduled task to search for JIRA tickets and queue them for processing.
    
    Args:
        search_config: Optional search configuration override
        
    Returns:
        Dict: Search and processing results
    """
    start_time = datetime.utcnow()
    logger.info("Starting scheduled JIRA ticket search")
    
    result = {
        "search_started_at": start_time.isoformat(),
        "tickets_found": 0,
        "tickets_queued": 0,
        "tickets_skipped": 0,
        "errors": [],
        "success": False
    }
    
    try:
        # Get search configuration
        config = search_config or _get_default_search_config()
        logger.info(f"Using search config: {config}")
        
        # Get JIRA client and config manager
        jira_client = get_jira_client()
        config_manager = get_config_manager()
        
        # Build JQL query
        jql_query = _build_jql_query(config)
        logger.info(f"Executing JQL query: {jql_query}")
        
        # Search for tickets with pagination
        start_at = 0
        max_results = config.get("batch_size", 50)
        total_processed = 0
        
        while True:
            try:
                # Execute search
                search_results = jira_client.search_issues_sync(
                    jql=jql_query,
                    start_at=start_at,
                    max_results=max_results,
                    expand=["attachment"]
                )
                
                issues = search_results.get("issues", [])
                total_found = search_results.get("total", 0)
                is_last = search_results.get("isLast", True)
                
                logger.info(f"Found {len(issues)} issues in batch (total: {total_found})")
                result["tickets_found"] = total_found
                
                if not issues:
                    break
                
                # Process each issue
                for issue_data in issues:
                    issue_key = issue_data.get("key")
                    
                    try:
                        # Parse issue to check if it should be processed
                        ticket = jira_client._parse_issue_data(issue_data)
                        
                        # Check if issue type should be processed
                        if not config_manager.should_process_issue_type(ticket.issue_type.value):
                            logger.debug(f"Skipping {issue_key} - issue type {ticket.issue_type.value} not configured")
                            result["tickets_skipped"] += 1
                            continue
                        
                        # Check if ticket was recently processed (avoid duplicates)
                        if _was_recently_processed(issue_key, ticket.updated):
                            logger.debug(f"Skipping {issue_key} - recently processed")
                            result["tickets_skipped"] += 1
                            continue
                        
                        # Queue ticket for processing
                        priority = _determine_priority(ticket)
                        task_result = process_ticket.apply_async(
                            args=[issue_key, "scheduled_search"],
                            priority=priority,
                            queue="ticket_processing"
                        )
                        
                        logger.info(f"Queued {issue_key} for processing with task ID {task_result.id}")
                        result["tickets_queued"] += 1
                        
                        # Record processing attempt
                        _record_processing_attempt(issue_key, ticket.updated)
                        
                    except Exception as e:
                        error_msg = f"Error processing issue {issue_key}: {str(e)}"
                        logger.error(error_msg)
                        result["errors"].append(error_msg)
                
                total_processed += len(issues)
                
                # Check if we've processed all results
                if is_last or total_processed >= total_found:
                    break
                
                # Move to next batch
                start_at += max_results
                
                # Safety check to prevent infinite loops
                if start_at > 1000:  # Limit to 1000 tickets per search
                    logger.warning("Reached maximum search limit of 1000 tickets")
                    break
                    
            except JiraAPIError as e:
                error_msg = f"JIRA API error during search: {e.message}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
                break
            except Exception as e:
                error_msg = f"Unexpected error during search: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
                break
        
        # Mark as successful if we processed without major errors
        result["success"] = len(result["errors"]) == 0
        
        end_time = datetime.utcnow()
        result["search_completed_at"] = end_time.isoformat()
        result["duration_seconds"] = (end_time - start_time).total_seconds()
        
        logger.info(f"Scheduled search completed: {result['tickets_queued']} queued, "
                   f"{result['tickets_skipped']} skipped, {len(result['errors'])} errors")
        
        return result
        
    except Exception as e:
        logger.error(f"Fatal error in scheduled search: {e}", exc_info=True)
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying scheduled search (attempt {self.request.retries + 1})")
            raise self.retry(countdown=300 * (2 ** self.request.retries))  # Exponential backoff
        
        result["errors"].append(f"Fatal error: {str(e)}")
        result["search_completed_at"] = datetime.utcnow().isoformat()
        return result


def _get_default_search_config() -> Dict[str, Any]:
    """
    Get default search configuration.
    
    Returns:
        Dict: Default search configuration
    """
    return {
        "projects": ["PS"],  # Product Support project
        "issue_types": ["Problem", "Bug", "Support Request"],
        "statuses": ["Open", "In Progress", "Reopened"],
        "time_range_hours": 24,  # Look for tickets updated in last 24 hours
        "batch_size": 50,
        "exclude_processed_within_hours": 6  # Don't reprocess tickets processed within 6 hours
    }


def _build_jql_query(config: Dict[str, Any]) -> str:
    """
    Build JQL query from search configuration.
    
    Args:
        config: Search configuration
        
    Returns:
        str: JQL query string
    """
    jql_parts = []
    
    # Project filter
    projects = config.get("projects", ["PS"])
    if projects:
        project_filter = " OR ".join([f'project = "{p}"' for p in projects])
        jql_parts.append(f"({project_filter})")
    
    # Issue type filter
    issue_types = config.get("issue_types", ["Problem", "Bug"])
    if issue_types:
        type_filter = " OR ".join([f'issuetype = "{t}"' for t in issue_types])
        jql_parts.append(f"({type_filter})")
    
    # Status filter
    statuses = config.get("statuses", ["Open"])
    if statuses:
        status_filter = " OR ".join([f'status = "{s}"' for s in statuses])
        jql_parts.append(f"({status_filter})")
    
    # Time range filter
    time_range_hours = config.get("time_range_hours", 24)
    if time_range_hours:
        jql_parts.append(f"updated >= -{time_range_hours}h")
    
    # Combine all parts with AND
    jql_query = " AND ".join(jql_parts)
    
    # Add ordering
    jql_query += " ORDER BY updated DESC"
    
    return jql_query


def _determine_priority(ticket) -> int:
    """
    Determine Celery task priority based on ticket properties.
    
    Args:
        ticket: JiraTicket instance
        
    Returns:
        int: Celery priority (1-9, higher is more urgent)
    """
    # High priority for blocker/P1 tickets
    if ticket.is_high_priority:
        return 9
    
    # Medium priority for recently created tickets
    if (datetime.utcnow() - ticket.created.replace(tzinfo=None)).total_seconds() < 3600:  # 1 hour
        return 7
    
    # Normal priority for everything else
    return 5


def _was_recently_processed(issue_key: str, updated_time: datetime) -> bool:
    """
    Check if a ticket was recently processed to avoid duplicates.
    
    Args:
        issue_key: JIRA issue key
        updated_time: Ticket's last updated time
        
    Returns:
        bool: True if recently processed
    """
    # For now, implement a simple time-based check
    # In production, you might want to use Redis or database to track this
    
    # Get the exclude window from config
    config = _get_default_search_config()
    exclude_hours = config.get("exclude_processed_within_hours", 6)
    
    # If ticket was updated very recently (within exclude window), consider it processed
    time_since_update = datetime.utcnow() - updated_time.replace(tzinfo=None)
    
    # Skip if updated less than 30 minutes ago (likely still being worked on)
    if time_since_update.total_seconds() < 1800:  # 30 minutes
        return True
    
    return False


def _record_processing_attempt(issue_key: str, updated_time: datetime) -> None:
    """
    Record that we attempted to process this ticket.
    
    Args:
        issue_key: JIRA issue key
        updated_time: Ticket's last updated time
    """
    # For now, just log it
    # In production, you might want to store this in Redis or database
    logger.debug(f"Recording processing attempt for {issue_key} (updated: {updated_time})")
