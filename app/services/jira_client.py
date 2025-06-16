"""
JIRA API client for PS Ticket Process Bot.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import httpx
from requests.auth import HTTPBasicAuth
import requests

from app.core.config import get_settings
from app.models.ticket import JiraTicket, JiraUser, JiraAttachment, IssueType, Priority, TicketStatus
from app.utils.config_manager import get_config_manager


logger = logging.getLogger(__name__)


class JiraAPIError(Exception):
    """Custom exception for JIRA API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class JiraClient:
    """JIRA API client with async support."""
    
    def __init__(self):
        """Initialize the JIRA client."""
        self.settings = get_settings()
        self.config_manager = get_config_manager()
        
        self.base_url = self.settings.jira.base_url
        self.username = self.settings.jira.username
        self.api_token = self.settings.jira.api_token
        
        # Setup authentication
        self.auth = HTTPBasicAuth(self.username, self.api_token)
        
        # HTTP client configuration
        self.timeout = self.settings.jira.timeout
        self.max_retries = self.settings.jira.max_retries
        self.retry_delay = self.settings.jira.retry_delay
        
        # Field mappings
        self.field_mappings = self.config_manager.get_jira_field_mappings()
        
        logger.info(f"Initialized JIRA client for {self.base_url}")
    
    async def get_issue(self, issue_key: str) -> JiraTicket:
        """
        Fetch a JIRA issue by key and convert to JiraTicket model.
        
        Args:
            issue_key: JIRA issue key (e.g., SUPPORT-123)
            
        Returns:
            JiraTicket: Parsed ticket data
            
        Raises:
            JiraAPIError: If API call fails or issue not found
        """
        logger.info(f"Fetching JIRA issue: {issue_key}")
        
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        
        # Specify fields to expand
        params = {
            "expand": "attachment,changelog"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    auth=(self.username, self.api_token)
                )
                
                if response.status_code == 404:
                    raise JiraAPIError(f"Issue {issue_key} not found", 404)
                elif response.status_code != 200:
                    raise JiraAPIError(
                        f"Failed to fetch issue {issue_key}: {response.status_code}",
                        response.status_code,
                        response.json() if response.content else None
                    )
                
                issue_data = response.json()
                logger.info(f"Successfully fetched issue {issue_key}")
                
                return self._parse_issue_data(issue_data)
                
        except httpx.RequestError as e:
            logger.error(f"Request error fetching issue {issue_key}: {e}")
            raise JiraAPIError(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching issue {issue_key}: {e}")
            raise JiraAPIError(f"Unexpected error: {e}")
    
    def get_issue_sync(self, issue_key: str) -> JiraTicket:
        """
        Synchronous version of get_issue for compatibility.
        
        Args:
            issue_key: JIRA issue key
            
        Returns:
            JiraTicket: Parsed ticket data
        """
        logger.info(f"Fetching JIRA issue (sync): {issue_key}")
        
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {"expand": "attachment,changelog"}
        
        try:
            response = requests.get(
                url,
                params=params,
                auth=self.auth,
                timeout=self.timeout
            )
            
            if response.status_code == 404:
                raise JiraAPIError(f"Issue {issue_key} not found", 404)
            elif response.status_code != 200:
                raise JiraAPIError(
                    f"Failed to fetch issue {issue_key}: {response.status_code}",
                    response.status_code,
                    response.json() if response.content else None
                )
            
            issue_data = response.json()
            logger.info(f"Successfully fetched issue {issue_key}")
            
            return self._parse_issue_data(issue_data)
            
        except requests.RequestException as e:
            logger.error(f"Request error fetching issue {issue_key}: {e}")
            raise JiraAPIError(f"Request failed: {e}")
    
    def _parse_issue_data(self, issue_data: Dict[str, Any]) -> JiraTicket:
        """
        Parse JIRA API response into JiraTicket model.
        
        Args:
            issue_data: Raw JIRA API response
            
        Returns:
            JiraTicket: Parsed ticket data
        """
        fields = issue_data.get("fields", {})
        
        # Parse basic fields
        key = issue_data.get("key")
        issue_id = issue_data.get("id")
        summary = fields.get("summary", "")
        description = fields.get("description", "")
        
        # Parse issue type
        issue_type_data = fields.get("issuetype", {})
        issue_type_name = issue_type_data.get("name", "")
        try:
            issue_type = IssueType(issue_type_name)
        except ValueError:
            logger.warning(f"Unknown issue type: {issue_type_name}, defaulting to Bug")
            issue_type = IssueType.BUG
        
        # Parse priority
        priority_data = fields.get("priority", {})
        priority_name = priority_data.get("name", "Medium")
        try:
            priority = Priority(priority_name)
        except ValueError:
            logger.warning(f"Unknown priority: {priority_name}, defaulting to Medium")
            priority = Priority.MEDIUM
        
        # Parse status
        status_data = fields.get("status", {})
        status_name = status_data.get("name", "Open")
        try:
            status = TicketStatus(status_name)
        except ValueError:
            logger.warning(f"Unknown status: {status_name}, defaulting to Open")
            status = TicketStatus.OPEN
        
        # Parse reporter
        reporter_data = fields.get("reporter", {})
        reporter = JiraUser(
            account_id=reporter_data.get("accountId", ""),
            display_name=reporter_data.get("displayName", "Unknown"),
            email_address=reporter_data.get("emailAddress"),
            active=reporter_data.get("active", True)
        )
        
        # Parse assignee (optional)
        assignee = None
        assignee_data = fields.get("assignee")
        if assignee_data:
            assignee = JiraUser(
                account_id=assignee_data.get("accountId", ""),
                display_name=assignee_data.get("displayName", "Unknown"),
                email_address=assignee_data.get("emailAddress"),
                active=assignee_data.get("active", True)
            )
        
        # Parse timestamps
        created = datetime.fromisoformat(fields.get("created", "").replace("Z", "+00:00"))
        updated = datetime.fromisoformat(fields.get("updated", "").replace("Z", "+00:00"))
        
        # Parse custom fields using field mappings
        steps_to_reproduce = None
        affected_version = None
        customer_impact = None
        
        if "steps_to_reproduce" in self.field_mappings:
            steps_field = self.field_mappings["steps_to_reproduce"]
            steps_to_reproduce = fields.get(steps_field)
        
        if "affected_version" in self.field_mappings:
            version_field = self.field_mappings["affected_version"]
            affected_version = fields.get(version_field)
        
        if "customer_impact" in self.field_mappings:
            impact_field = self.field_mappings["customer_impact"]
            customer_impact = fields.get(impact_field)
        
        # Parse attachments
        attachments = []
        attachment_data = fields.get("attachment", [])
        for att in attachment_data:
            attachment = JiraAttachment(
                id=att.get("id", ""),
                filename=att.get("filename", ""),
                size=att.get("size", 0),
                mime_type=att.get("mimeType", ""),
                created=datetime.fromisoformat(att.get("created", "").replace("Z", "+00:00")),
                author=JiraUser(
                    account_id=att.get("author", {}).get("accountId", ""),
                    display_name=att.get("author", {}).get("displayName", "Unknown"),
                    email_address=att.get("author", {}).get("emailAddress"),
                    active=att.get("author", {}).get("active", True)
                )
            )
            attachments.append(attachment)
        
        # Parse project information
        project_data = fields.get("project", {})
        project_key = project_data.get("key", "")
        project_name = project_data.get("name", "")
        
        # Create JiraTicket instance
        ticket = JiraTicket(
            key=key,
            id=issue_id,
            summary=summary,
            description=description,
            issue_type=issue_type,
            priority=priority,
            status=status,
            reporter=reporter,
            assignee=assignee,
            created=created,
            updated=updated,
            steps_to_reproduce=steps_to_reproduce,
            affected_version=affected_version,
            customer_impact=customer_impact,
            attachments=attachments,
            project_key=project_key,
            project_name=project_name,
            raw_data=issue_data
        )
        
        logger.debug(f"Parsed ticket {key}: {issue_type.value} - {priority.value}")
        return ticket
    
    async def add_comment(self, issue_key: str, comment_body: str) -> Dict[str, Any]:
        """
        Add a comment to a JIRA issue.
        
        Args:
            issue_key: JIRA issue key
            comment_body: Comment text
            
        Returns:
            Dict: Comment creation response
            
        Raises:
            JiraAPIError: If comment creation fails
        """
        logger.info(f"Adding comment to issue {issue_key}")
        
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/comment"
        
        payload = {
            "body": comment_body
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    auth=(self.username, self.api_token)
                )
                
                if response.status_code != 201:
                    raise JiraAPIError(
                        f"Failed to add comment to {issue_key}: {response.status_code}",
                        response.status_code,
                        response.json() if response.content else None
                    )
                
                result = response.json()
                logger.info(f"Successfully added comment to {issue_key}")
                return result
                
        except httpx.RequestError as e:
            logger.error(f"Request error adding comment to {issue_key}: {e}")
            raise JiraAPIError(f"Request failed: {e}")
    
    async def transition_issue(self, issue_key: str, transition_id: str) -> Dict[str, Any]:
        """
        Transition a JIRA issue to a new status.
        
        Args:
            issue_key: JIRA issue key
            transition_id: ID of the transition to execute
            
        Returns:
            Dict: Transition response
            
        Raises:
            JiraAPIError: If transition fails
        """
        logger.info(f"Transitioning issue {issue_key} with transition {transition_id}")
        
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/transitions"
        
        payload = {
            "transition": {
                "id": transition_id
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    auth=(self.username, self.api_token)
                )
                
                if response.status_code != 204:
                    raise JiraAPIError(
                        f"Failed to transition {issue_key}: {response.status_code}",
                        response.status_code,
                        response.json() if response.content else None
                    )
                
                logger.info(f"Successfully transitioned {issue_key}")
                return {"success": True}
                
        except httpx.RequestError as e:
            logger.error(f"Request error transitioning {issue_key}: {e}")
            raise JiraAPIError(f"Request failed: {e}")
    
    async def get_available_transitions(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        Get available transitions for an issue.
        
        Args:
            issue_key: JIRA issue key
            
        Returns:
            List[Dict]: Available transitions
        """
        logger.debug(f"Getting available transitions for {issue_key}")
        
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/transitions"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    auth=(self.username, self.api_token)
                )
                
                if response.status_code != 200:
                    raise JiraAPIError(
                        f"Failed to get transitions for {issue_key}: {response.status_code}",
                        response.status_code
                    )
                
                result = response.json()
                transitions = result.get("transitions", [])
                
                logger.debug(f"Found {len(transitions)} transitions for {issue_key}")
                return transitions
                
        except httpx.RequestError as e:
            logger.error(f"Request error getting transitions for {issue_key}: {e}")
            raise JiraAPIError(f"Request failed: {e}")


# Global JIRA client instance
_jira_client: Optional[JiraClient] = None


def get_jira_client() -> JiraClient:
    """Get the global JIRA client instance."""
    global _jira_client
    if _jira_client is None:
        _jira_client = JiraClient()
    return _jira_client
