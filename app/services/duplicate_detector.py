"""
Duplicate ticket detection service for PS Ticket Process Bot.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.models.ticket import JiraTicket
from app.services.jira_client import get_jira_client
from app.core.config import get_settings


logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Service for detecting duplicate tickets in JIRA."""
    
    def __init__(self):
        """Initialize the duplicate detector."""
        self.settings = get_settings()
        self.jira_client = get_jira_client()
        
        logger.info("Initialized DuplicateDetector service")
    
    async def find_duplicates(self, ticket: JiraTicket) -> Dict[str, Any]:
        """
        Find potential duplicate tickets for the given ticket.
        
        Args:
            ticket: JiraTicket to search duplicates for
            
        Returns:
            Dict containing duplicate search results
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
                    "potential_duplicates": [],
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

            # Execute search using the JIRA client
            search_results = self.jira_client.search_issues_sync(
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
                    "created": issue.get("fields", {}).get("created", ""),
                    "similarity_score": self._calculate_similarity_score(
                        ticket.summary, 
                        issue.get("fields", {}).get("summary", "")
                    )
                })

            # Sort by similarity score (highest first)
            duplicates.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

            duplicates_found = len(duplicates)
            message = f"Found {duplicates_found} potential duplicates for {ticket.key}"

            if duplicates_found > 0:
                logger.warning(f"{message}: {[d['key'] for d in duplicates]}")
            else:
                logger.info(f"No duplicates found for {ticket.key}")

            return {
                "success": True,
                "duplicates_found": duplicates_found,
                "potential_duplicates": duplicates,
                "message": message,
                "search_query": jql_query
            }

        except Exception as e:
            logger.error(f"Duplicate search failed for {ticket.key}: {e}")
            return {
                "success": False,
                "duplicates_found": 0,
                "potential_duplicates": [],
                "error": str(e),
                "message": f"Duplicate search failed: {str(e)}"
            }
    
    def find_duplicates_sync(self, ticket: JiraTicket) -> Dict[str, Any]:
        """
        Synchronous version of find_duplicates for compatibility.
        
        Args:
            ticket: JiraTicket to search duplicates for
            
        Returns:
            Dict containing duplicate search results
        """
        logger.info(f"Searching for duplicate tickets (sync) for {ticket.key}")
        
        try:
            # Build search query for potential duplicates
            summary_words = ticket.summary.split()
            if len(summary_words) < 2:
                logger.info(f"Summary too short for duplicate search: {ticket.key}")
                return {
                    "success": True,
                    "duplicates_found": 0,
                    "potential_duplicates": [],
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
            search_results = self.jira_client.search_issues_sync(
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
                    "created": issue.get("fields", {}).get("created", ""),
                    "similarity_score": self._calculate_similarity_score(
                        ticket.summary, 
                        issue.get("fields", {}).get("summary", "")
                    )
                })

            # Sort by similarity score (highest first)
            duplicates.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

            duplicates_found = len(duplicates)
            message = f"Found {duplicates_found} potential duplicates for {ticket.key}"

            if duplicates_found > 0:
                logger.warning(f"{message}: {[d['key'] for d in duplicates]}")
            else:
                logger.info(f"No duplicates found for {ticket.key}")

            return {
                "success": True,
                "duplicates_found": duplicates_found,
                "potential_duplicates": duplicates,
                "message": message,
                "search_query": jql_query
            }

        except Exception as e:
            logger.error(f"Duplicate search failed for {ticket.key}: {e}")
            return {
                "success": False,
                "duplicates_found": 0,
                "potential_duplicates": [],
                "error": str(e),
                "message": f"Duplicate search failed: {str(e)}"
            }
    
    def _calculate_similarity_score(self, summary1: str, summary2: str) -> float:
        """
        Calculate a simple similarity score between two summaries.
        
        Args:
            summary1: First summary
            summary2: Second summary
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not summary1 or not summary2:
            return 0.0
        
        # Convert to lowercase and split into words
        words1 = set(summary1.lower().split())
        words2 = set(summary2.lower().split())
        
        # Calculate Jaccard similarity (intersection over union)
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0.0
        
        return intersection / union


# Global duplicate detector instance
_duplicate_detector: Optional[DuplicateDetector] = None


def get_duplicate_detector() -> DuplicateDetector:
    """Get the global duplicate detector instance."""
    global _duplicate_detector
    if _duplicate_detector is None:
        _duplicate_detector = DuplicateDetector()
    return _duplicate_detector
