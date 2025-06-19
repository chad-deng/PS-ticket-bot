"""
JIRA Status Transition Automation for PS Ticket Process Bot.
Provides automated status transitions with proper validation and error handling.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio

from app.services.jira_client import get_jira_client
from app.models.ticket import JiraTicket, QualityAssessment
from app.core.config import get_settings


logger = logging.getLogger(__name__)


class TransitionResult(Enum):
    """Results of status transition attempts."""
    SUCCESS = "success"
    FAILED = "failed"
    NOT_ALLOWED = "not_allowed"
    INVALID_TRANSITION = "invalid_transition"
    API_ERROR = "api_error"


@dataclass
class StatusTransition:
    """Represents a JIRA status transition."""
    from_status: str
    to_status: str
    transition_id: str
    transition_name: str
    required_fields: List[str]
    conditions: List[str]


@dataclass
class TransitionAttempt:
    """Result of a transition attempt."""
    success: bool
    result: TransitionResult
    from_status: str
    to_status: str
    transition_id: Optional[str]
    error_message: Optional[str] = None
    validation_errors: List[str] = None


class JiraStatusAutomation:
    """Automated JIRA status transition system."""
    
    def __init__(self):
        """Initialize the JIRA status automation system."""
        self.settings = get_settings()
        self.jira_client = get_jira_client()
        
        # Load transition mappings
        self.transition_mappings = self._load_transition_mappings()
        
        logger.info("Initialized JIRA Status Automation")
    
    def _load_transition_mappings(self) -> Dict[str, Dict[str, StatusTransition]]:
        """Load status transition mappings from configuration."""
        # Default transition mappings - these should be configurable
        return {
            "PS": {  # Project key
                "open_to_qa_investigating": StatusTransition(
                    from_status="Open",
                    to_status="QA investigating",
                    transition_id="11",  # This needs to be discovered from JIRA
                    transition_name="Start QA Investigation",
                    required_fields=[],
                    conditions=["ticket_has_required_info"]
                ),
                "open_to_pending_csc": StatusTransition(
                    from_status="Open",
                    to_status="Pending_CSC",
                    transition_id="21",  # This needs to be discovered from JIRA
                    transition_name="Request More Information",
                    required_fields=[],
                    conditions=["ticket_missing_info"]
                ),
                "open_to_dev_investigating": StatusTransition(
                    from_status="Open",
                    to_status="Dev investigating",
                    transition_id="31",  # This needs to be discovered from JIRA
                    transition_name="Send to Development",
                    required_fields=[],
                    conditions=["unreproducible_bug"]
                ),
                "cancelled_to_qa_investigating": StatusTransition(
                    from_status="Cancelled",
                    to_status="QA investigating",
                    transition_id="41",  # This needs to be discovered from JIRA
                    transition_name="Reopen and Start QA Investigation",
                    required_fields=[],
                    conditions=["ticket_has_required_info"]
                ),
                "cancelled_to_pending_csc": StatusTransition(
                    from_status="Cancelled",
                    to_status="Pending_CSC",
                    transition_id="51",  # This needs to be discovered from JIRA
                    transition_name="Reopen and Request Information",
                    required_fields=[],
                    conditions=["ticket_missing_info"]
                ),
                "cancelled_to_dev_investigating": StatusTransition(
                    from_status="Cancelled",
                    to_status="Dev investigating",
                    transition_id="61",  # This needs to be discovered from JIRA
                    transition_name="Reopen and Send to Development",
                    required_fields=[],
                    conditions=["unreproducible_bug"]
                )
            }
        }
    
    async def get_available_transitions(self, ticket_key: str) -> List[Dict[str, Any]]:
        """
        Get available transitions for a ticket from JIRA.
        
        Args:
            ticket_key: JIRA ticket key
            
        Returns:
            List of available transitions
        """
        try:
            jira = self.jira_client.get_client()
            
            # Get transitions using JIRA REST API
            url = f"{self.jira_client.base_url}/rest/api/2/issue/{ticket_key}/transitions"
            
            response = await self._make_jira_request("GET", url)
            
            if response.get("transitions"):
                transitions = []
                for transition in response["transitions"]:
                    transitions.append({
                        "id": transition["id"],
                        "name": transition["name"],
                        "to_status": transition["to"]["name"],
                        "to_status_id": transition["to"]["id"]
                    })
                return transitions
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get transitions for {ticket_key}: {e}")
            return []
    
    async def discover_transition_ids(self, ticket_key: str) -> Dict[str, str]:
        """
        Discover actual transition IDs from JIRA for a ticket.
        
        Args:
            ticket_key: JIRA ticket key
            
        Returns:
            Dict mapping transition names to IDs
        """
        transitions = await self.get_available_transitions(ticket_key)
        
        transition_map = {}
        for transition in transitions:
            # Create a normalized key for the transition
            to_status = transition["to_status"].lower().replace(" ", "_")
            transition_map[to_status] = transition["id"]
        
        logger.info(f"Discovered transitions for {ticket_key}: {transition_map}")
        return transition_map
    
    async def execute_status_transition(
        self, 
        ticket: JiraTicket, 
        target_status: str,
        comment: Optional[str] = None
    ) -> TransitionAttempt:
        """
        Execute a status transition for a ticket.
        
        Args:
            ticket: JiraTicket to transition
            target_status: Target status name
            comment: Optional comment to add during transition
            
        Returns:
            TransitionAttempt result
        """
        logger.info(f"Attempting to transition {ticket.key} to {target_status}")
        
        try:
            # Get current status
            current_status = ticket.status.value
            
            # Discover available transitions
            available_transitions = await self.get_available_transitions(ticket.key)
            
            # Find the appropriate transition
            transition_id = None
            for transition in available_transitions:
                if transition["to_status"].lower() == target_status.lower():
                    transition_id = transition["id"]
                    break
            
            if not transition_id:
                return TransitionAttempt(
                    success=False,
                    result=TransitionResult.INVALID_TRANSITION,
                    from_status=current_status,
                    to_status=target_status,
                    transition_id=None,
                    error_message=f"No valid transition found from {current_status} to {target_status}"
                )
            
            # Execute the transition
            success = await self._perform_transition(ticket.key, transition_id, comment)
            
            if success:
                logger.info(f"Successfully transitioned {ticket.key} from {current_status} to {target_status}")
                return TransitionAttempt(
                    success=True,
                    result=TransitionResult.SUCCESS,
                    from_status=current_status,
                    to_status=target_status,
                    transition_id=transition_id
                )
            else:
                return TransitionAttempt(
                    success=False,
                    result=TransitionResult.FAILED,
                    from_status=current_status,
                    to_status=target_status,
                    transition_id=transition_id,
                    error_message="Transition execution failed"
                )
                
        except Exception as e:
            logger.error(f"Status transition failed for {ticket.key}: {e}")
            return TransitionAttempt(
                success=False,
                result=TransitionResult.API_ERROR,
                from_status=ticket.status.value,
                to_status=target_status,
                transition_id=None,
                error_message=str(e)
            )
    
    async def _perform_transition(
        self, 
        ticket_key: str, 
        transition_id: str, 
        comment: Optional[str] = None
    ) -> bool:
        """
        Perform the actual JIRA transition.
        
        Args:
            ticket_key: JIRA ticket key
            transition_id: Transition ID to execute
            comment: Optional comment to add
            
        Returns:
            bool: Success status
        """
        try:
            url = f"{self.jira_client.base_url}/rest/api/2/issue/{ticket_key}/transitions"
            
            payload = {
                "transition": {
                    "id": transition_id
                }
            }
            
            # Add comment if provided
            if comment:
                payload["update"] = {
                    "comment": [{
                        "add": {
                            "body": comment
                        }
                    }]
                }
            
            response = await self._make_jira_request("POST", url, payload)
            
            # JIRA transitions return 204 No Content on success
            return True
            
        except Exception as e:
            logger.error(f"Failed to perform transition {transition_id} on {ticket_key}: {e}")
            return False
    
    async def _make_jira_request(
        self, 
        method: str, 
        url: str, 
        payload: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to JIRA API.
        
        Args:
            method: HTTP method
            url: Request URL
            payload: Optional request payload
            
        Returns:
            Response data
        """
        import httpx
        
        auth = (self.jira_client.username, self.jira_client.api_token)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, auth=auth, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, auth=auth, headers=headers, json=payload)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            # Handle empty responses (like 204 No Content)
            if response.status_code == 204:
                return {}
            
            return response.json()
    
    def determine_target_status(
        self, 
        ticket: JiraTicket, 
        quality_assessment: QualityAssessment
    ) -> str:
        """
        Determine the target status based on business rules.
        
        Args:
            ticket: JiraTicket to analyze
            quality_assessment: Quality assessment result
            
        Returns:
            Target status name
        """
        # Apply the business rules from Phase 1
        if ticket.issue_type.value == "Unreproducible Bug":
            # Check if description and customer login details are present
            description_ok = len(ticket.description or "") >= 10
            
            # Check for login details in description or summary
            text_to_check = f"{ticket.summary or ''} {ticket.description or ''}".lower()
            login_keywords = ["login", "username", "email", "account", "user id", "customer id", "credential"]
            login_ok = any(keyword in text_to_check for keyword in login_keywords)
            
            if description_ok and login_ok:
                return "Dev investigating"
            else:
                return "Pending_CSC"
        else:
            # For other issue types, check overall quality
            score = quality_assessment.score
            issues_count = len(quality_assessment.issues_found)
            
            if score >= 50 or issues_count <= 4:
                return "QA investigating"
            else:
                return "Pending_CSC"
    
    async def automate_ticket_transition(
        self, 
        ticket: JiraTicket, 
        quality_assessment: QualityAssessment,
        comment: Optional[str] = None
    ) -> TransitionAttempt:
        """
        Fully automate ticket transition based on business rules.
        
        Args:
            ticket: JiraTicket to process
            quality_assessment: Quality assessment result
            comment: Optional comment to add
            
        Returns:
            TransitionAttempt result
        """
        # Determine target status
        target_status = self.determine_target_status(ticket, quality_assessment)
        
        logger.info(f"Automating transition for {ticket.key}: {ticket.status.value} → {target_status}")
        
        # Execute the transition
        result = await self.execute_status_transition(ticket, target_status, comment)
        
        return result


# Global instance
_status_automation: Optional[JiraStatusAutomation] = None


def get_jira_status_automation() -> JiraStatusAutomation:
    """Get the global JIRA status automation instance."""
    global _status_automation
    if _status_automation is None:
        _status_automation = JiraStatusAutomation()
    return _status_automation
