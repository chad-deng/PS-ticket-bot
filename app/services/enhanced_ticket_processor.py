"""
Enhanced Ticket Processor for PS Ticket Process Bot Phase 2.
Integrates advanced AI comment generation with automated status transitions.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from app.models.ticket import JiraTicket, QualityAssessment
from app.services.advanced_ai_generator import (
    get_advanced_ai_generator, 
    CommentContext, 
    AICommentResult
)
from app.services.jira_status_automation import (
    get_jira_status_automation,
    TransitionAttempt
)
from app.services.jira_client import get_jira_client
from app.core.quality_engine import QualityEngine
from app.services.duplicate_detector import DuplicateDetector


logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Complete result of enhanced ticket processing."""
    success: bool
    ticket_key: str
    quality_assessment: QualityAssessment
    ai_comment_result: AICommentResult
    status_transition: TransitionAttempt
    duplicate_tickets: List[Dict[str, Any]]
    processing_time: float
    error_message: Optional[str] = None


class EnhancedTicketProcessor:
    """Enhanced ticket processor with Phase 2 capabilities."""
    
    def __init__(self):
        """Initialize the enhanced ticket processor."""
        self.jira_client = get_jira_client()
        self.quality_engine = QualityEngine()
        self.duplicate_detector = DuplicateDetector()
        self.ai_generator = get_advanced_ai_generator()
        self.status_automation = get_jira_status_automation()
        
        logger.info("Initialized Enhanced Ticket Processor (Phase 2)")
    
    async def process_ticket_enhanced(self, ticket_key: str) -> ProcessingResult:
        """
        Process a ticket with enhanced Phase 2 capabilities.
        
        Args:
            ticket_key: JIRA ticket key to process
            
        Returns:
            ProcessingResult: Complete processing result
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting enhanced processing for ticket {ticket_key}")
            
            # Step 1: Fetch ticket from JIRA
            ticket = await self._fetch_ticket(ticket_key)
            if not ticket:
                return self._create_error_result(
                    ticket_key, 
                    "Failed to fetch ticket from JIRA",
                    start_time
                )
            
            # Step 2: Perform quality assessment
            quality_assessment = await self._assess_quality(ticket)
            
            # Step 3: Search for duplicates
            duplicate_tickets = await self._search_duplicates(ticket)
            
            # Step 4: Build context for AI generation
            context = await self._build_comment_context(
                ticket, 
                quality_assessment, 
                duplicate_tickets
            )
            
            # Step 5: Generate advanced AI comment
            ai_result = await self.ai_generator.generate_advanced_comment(context)
            
            # Step 6: Post comment to JIRA
            comment_posted = await self._post_comment_to_jira(ticket_key, ai_result.comment)
            
            # Step 7: Execute automated status transition
            status_transition = await self.status_automation.automate_ticket_transition(
                ticket, 
                quality_assessment,
                comment=None  # Comment already posted separately
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Enhanced processing completed for {ticket_key} in {processing_time:.2f}s")
            
            return ProcessingResult(
                success=True,
                ticket_key=ticket_key,
                quality_assessment=quality_assessment,
                ai_comment_result=ai_result,
                status_transition=status_transition,
                duplicate_tickets=duplicate_tickets,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Enhanced processing failed for {ticket_key}: {e}")
            return self._create_error_result(ticket_key, str(e), start_time)
    
    async def _fetch_ticket(self, ticket_key: str) -> Optional[JiraTicket]:
        """Fetch ticket from JIRA."""
        try:
            return await self.jira_client.get_ticket(ticket_key)
        except Exception as e:
            logger.error(f"Failed to fetch ticket {ticket_key}: {e}")
            return None
    
    async def _assess_quality(self, ticket: JiraTicket) -> QualityAssessment:
        """Perform quality assessment on the ticket."""
        try:
            return await self.quality_engine.assess_ticket_quality(ticket)
        except Exception as e:
            logger.error(f"Quality assessment failed for {ticket.key}: {e}")
            # Return a default assessment
            from app.models.ticket import QualityLevel
            return QualityAssessment(
                ticket_key=ticket.key,
                overall_quality=QualityLevel.LOW,
                issues_found=["Quality assessment failed"],
                score=0
            )
    
    async def _search_duplicates(self, ticket: JiraTicket) -> List[Dict[str, Any]]:
        """Search for duplicate tickets."""
        try:
            duplicates = await self.duplicate_detector.find_duplicates(ticket)
            return duplicates.get("potential_duplicates", [])
        except Exception as e:
            logger.error(f"Duplicate search failed for {ticket.key}: {e}")
            return []
    
    async def _build_comment_context(
        self, 
        ticket: JiraTicket, 
        quality_assessment: QualityAssessment,
        duplicate_tickets: List[Dict[str, Any]]
    ) -> CommentContext:
        """Build comprehensive context for AI comment generation."""
        
        # Determine suggested status
        suggested_status = self.status_automation.determine_target_status(
            ticket, 
            quality_assessment
        )
        
        # Extract missing fields from quality assessment
        missing_fields = quality_assessment.issues_found
        
        # Build business context
        business_context = await self._build_business_context(ticket)
        
        return CommentContext(
            ticket=ticket,
            quality_assessment=quality_assessment,
            duplicate_tickets=duplicate_tickets,
            suggested_status=suggested_status,
            missing_fields=missing_fields,
            business_context=business_context
        )
    
    async def _build_business_context(self, ticket: JiraTicket) -> Dict[str, Any]:
        """Build business context for the ticket."""
        context = {}
        
        # Check for high priority
        if ticket.priority.value in ["P1", "P2", "Critical", "High"]:
            context["high_priority"] = True
        
        # Check for top merchant impact (from description/summary)
        text_to_check = f"{ticket.summary or ''} {ticket.description or ''}".lower()
        if any(keyword in text_to_check for keyword in ["top 450", "top merchants", "merchant"]):
            context["affects_top_merchants"] = True
        
        # Check for revenue impact keywords
        revenue_keywords = ["revenue", "payment", "billing", "financial", "money"]
        if any(keyword in text_to_check for keyword in revenue_keywords):
            context["revenue_impact"] = "potential"
        
        return context
    
    async def _post_comment_to_jira(self, ticket_key: str, comment: str) -> bool:
        """Post the generated comment to JIRA."""
        try:
            success = await self.jira_client.add_comment(ticket_key, comment)
            if success:
                logger.info(f"Successfully posted AI comment to {ticket_key}")
            else:
                logger.error(f"Failed to post comment to {ticket_key}")
            return success
        except Exception as e:
            logger.error(f"Error posting comment to {ticket_key}: {e}")
            return False
    
    def _create_error_result(
        self, 
        ticket_key: str, 
        error_message: str, 
        start_time: datetime
    ) -> ProcessingResult:
        """Create an error result."""
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Create minimal objects for error case
        from app.models.ticket import QualityLevel, QualityAssessment
        from app.services.advanced_ai_generator import AICommentResult, CommentType
        from app.services.jira_status_automation import TransitionAttempt, TransitionResult
        
        return ProcessingResult(
            success=False,
            ticket_key=ticket_key,
            quality_assessment=QualityAssessment(
                ticket_key=ticket_key,
                overall_quality=QualityLevel.LOW,
                issues_found=[error_message],
                score=0
            ),
            ai_comment_result=AICommentResult(
                success=False,
                comment="",
                comment_type=CommentType.LOW_QUALITY_STANDARD,
                confidence_score=0.0,
                fallback_used=True,
                generation_time=0.0,
                error_message=error_message
            ),
            status_transition=TransitionAttempt(
                success=False,
                result=TransitionResult.API_ERROR,
                from_status="Unknown",
                to_status="Unknown",
                transition_id=None,
                error_message=error_message
            ),
            duplicate_tickets=[],
            processing_time=processing_time,
            error_message=error_message
        )
    
    async def process_multiple_tickets(self, ticket_keys: List[str]) -> List[ProcessingResult]:
        """
        Process multiple tickets concurrently.
        
        Args:
            ticket_keys: List of JIRA ticket keys
            
        Returns:
            List of ProcessingResults
        """
        logger.info(f"Processing {len(ticket_keys)} tickets concurrently")
        
        # Process tickets concurrently with a reasonable limit
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent processes
        
        async def process_with_semaphore(ticket_key: str) -> ProcessingResult:
            async with semaphore:
                return await self.process_ticket_enhanced(ticket_key)
        
        tasks = [process_with_semaphore(key) for key in ticket_keys]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process {ticket_keys[i]}: {result}")
                processed_results.append(
                    self._create_error_result(
                        ticket_keys[i], 
                        str(result), 
                        datetime.now()
                    )
                )
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_processing_summary(self, results: List[ProcessingResult]) -> Dict[str, Any]:
        """
        Generate a summary of processing results.
        
        Args:
            results: List of ProcessingResults
            
        Returns:
            Summary statistics
        """
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        
        # AI comment statistics
        ai_successful = sum(1 for r in results if r.ai_comment_result.success)
        fallback_used = sum(1 for r in results if r.ai_comment_result.fallback_used)
        
        # Status transition statistics
        transitions_successful = sum(1 for r in results if r.status_transition.success)
        
        # Average processing time
        avg_processing_time = sum(r.processing_time for r in results) / total if total > 0 else 0
        
        return {
            "total_tickets": total,
            "successful_processing": successful,
            "failed_processing": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "ai_comments": {
                "successful": ai_successful,
                "fallback_used": fallback_used,
                "success_rate": (ai_successful / total * 100) if total > 0 else 0
            },
            "status_transitions": {
                "successful": transitions_successful,
                "success_rate": (transitions_successful / total * 100) if total > 0 else 0
            },
            "average_processing_time": avg_processing_time
        }


# Global instance
_enhanced_processor: Optional[EnhancedTicketProcessor] = None


def get_enhanced_ticket_processor() -> EnhancedTicketProcessor:
    """Get the global enhanced ticket processor instance."""
    global _enhanced_processor
    if _enhanced_processor is None:
        _enhanced_processor = EnhancedTicketProcessor()
    return _enhanced_processor
