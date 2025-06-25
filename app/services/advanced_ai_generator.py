"""
Advanced AI Comment Generator for PS Ticket Process Bot.
Provides sophisticated, context-aware AI comment generation with dynamic templates.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from app.models.ticket import JiraTicket, QualityAssessment, IssueType
from app.services.gemini_client import GeminiClient, GeminiAPIError
from app.core.config import get_settings
from app.utils.config_manager import get_config_manager


logger = logging.getLogger(__name__)


class CommentType(Enum):
    """Types of AI comments that can be generated."""
    UNREPRODUCIBLE_BUG = "unreproducible_bug"
    HIGH_QUALITY_STANDARD = "high_quality_standard"
    MEDIUM_QUALITY_STANDARD = "medium_quality_standard"
    LOW_QUALITY_STANDARD = "low_quality_standard"
    DUPLICATE_FOUND = "duplicate_found"
    ESCALATION_REQUIRED = "escalation_required"


@dataclass
class CommentContext:
    """Context information for AI comment generation."""
    ticket: JiraTicket
    quality_assessment: QualityAssessment
    duplicate_tickets: List[Dict[str, Any]]
    suggested_status: str
    missing_fields: List[str]
    business_context: Dict[str, Any]
    user_history: Optional[Dict[str, Any]] = None


@dataclass
class AICommentResult:
    """Result of AI comment generation."""
    success: bool
    comment: str
    comment_type: CommentType
    confidence_score: float
    fallback_used: bool
    generation_time: float
    error_message: Optional[str] = None


class AdvancedAICommentGenerator:
    """Advanced AI comment generator with sophisticated context awareness."""
    
    def __init__(self):
        """Initialize the advanced AI comment generator."""
        self.settings = get_settings()
        self.config_manager = get_config_manager()
        self.gemini_client = GeminiClient()
        
        # Load advanced configuration
        self.ai_config = self._load_ai_configuration()
        
        logger.info("Initialized Advanced AI Comment Generator")
    
    def _load_ai_configuration(self) -> Dict[str, Any]:
        """Load advanced AI configuration from settings."""
        return {
            "max_comment_length": 800,
            "min_comment_length": 100,
            "confidence_threshold": 0.7,
            "context_window_size": 5,
            "enable_user_history": True,
            "enable_business_context": True,
            "prompt_templates": self._load_prompt_templates()
        }
    
    def _load_prompt_templates(self) -> Dict[str, str]:
        """Load sophisticated prompt templates for different scenarios."""
        return {
            "system_prompt": """You are an expert JIRA ticket assistant for a Product Support team with deep understanding of:
- Software development lifecycle and bug triage
- Customer support best practices
- Technical communication standards
- Business impact assessment

Your role is to generate professional, contextually appropriate comments that:
1. Demonstrate understanding of the technical issue
2. Provide clear, actionable guidance
3. Maintain appropriate tone based on issue severity
4. Consider business impact and customer experience
5. Follow established support workflows
6. Keep comments concise and focused
7. Avoid verbose explanations about processes or commitments

IMPORTANT RESTRICTIONS:
- Do NOT include greeting or closing sections (these are added automatically)
- Do NOT include process flow steps or workflow information
- Do NOT include status transition information
- Do NOT include duplicate ticket information
- Do NOT include commitment timelines or detailed process explanations
- Focus ONLY on the core content requested

Always be professional, empathetic, solution-oriented, and concise.""",
            
            "unreproducible_bug": """Analyze this unreproducible bug ticket and generate a specialized comment:

**Ticket Context:**
{ticket_context}

**Quality Assessment:**
{quality_context}

**Instructions:**
1. Acknowledge the complexity of unreproducible issues
2. Explain the need for developer investigation
3. Mention log analysis and system monitoring
4. Set appropriate expectations for resolution timeline
5. Provide reassurance about thorough investigation
6. Do not include process flow steps or status transition information
7. Do not include duplicate ticket information
8. Do not include greeting or closing - these will be added automatically
9. Focus only on the core content about the investigation approach

Generate only the core content about the unreproducible bug investigation without greeting, closing, or process details.""",
            
            "high_quality_comprehensive": """Analyze this high-quality ticket and generate an encouraging, professional comment:

**Ticket Context:**
{ticket_context}

**Quality Assessment:**
{quality_context}

**Business Context:**
{business_context}

**Instructions:**
1. Acknowledge the excellent ticket quality
2. Highlight specific strengths in the submission
3. Provide clear next steps and timeline expectations
4. Demonstrate understanding of business impact
5. Set professional tone that builds confidence
6. Do not include process flow steps or status transition information
7. Do not include duplicate ticket information
8. Do not include greeting or closing - these will be added automatically
9. Focus only on the core content about next steps and appreciation

Generate only the core content about ticket quality and next steps without greeting, closing, or process details.""",
            
            "improvement_guidance": """Analyze this ticket that needs improvement and generate helpful guidance:

**Ticket Context:**
{ticket_context}

**Quality Assessment:**
{quality_context}

**Missing Information:**
{missing_fields_context}

**Instructions:**
1. Provide specific, actionable requests for missing information
2. Keep explanations concise and focused
3. Maintain encouraging tone while being clear about requirements
4. Avoid verbose explanations about why information is needed
5. Do not include commitment timelines or detailed process explanations
6. Do not include process flow steps or status transition information
7. Do not include duplicate ticket information
8. Do not include greeting or closing - these will be added automatically
9. Focus only on the core content about what information is needed

Generate only the core content about missing information requirements without greeting, closing, or process details."""
        }
    
    async def generate_advanced_comment(self, context: CommentContext) -> AICommentResult:
        """
        Generate an advanced AI comment with full context awareness.
        
        Args:
            context: Complete context for comment generation
            
        Returns:
            AICommentResult: Generated comment with metadata
        """
        start_time = datetime.now()
        
        try:
            # Determine comment type based on context
            comment_type = self._determine_comment_type(context)
            
            # Build sophisticated prompt
            prompt = self._build_advanced_prompt(context, comment_type)
            
            # Generate comment using AI
            ai_comment = await self._generate_with_ai(prompt, context)
            
            # Validate and enhance the generated comment
            enhanced_comment = self._enhance_comment(ai_comment, context)
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(enhanced_comment, context)
            
            generation_time = (datetime.now() - start_time).total_seconds()
            
            return AICommentResult(
                success=True,
                comment=enhanced_comment,
                comment_type=comment_type,
                confidence_score=confidence,
                fallback_used=False,
                generation_time=generation_time
            )
            
        except Exception as e:
            logger.error(f"Advanced AI comment generation failed: {e}")
            
            # Generate fallback comment
            fallback_comment = self._generate_intelligent_fallback(context)
            generation_time = (datetime.now() - start_time).total_seconds()
            
            return AICommentResult(
                success=True,
                comment=fallback_comment,
                comment_type=self._determine_comment_type(context),
                confidence_score=0.5,
                fallback_used=True,
                generation_time=generation_time,
                error_message=str(e)
            )
    
    def _determine_comment_type(self, context: CommentContext) -> CommentType:
        """Determine the appropriate comment type based on context."""
        ticket = context.ticket
        quality = context.quality_assessment
        
        # Check for unreproducible bug
        if ticket.issue_type.value == "Unreproducible Bug":
            return CommentType.UNREPRODUCIBLE_BUG
        
        # Check for duplicates
        if context.duplicate_tickets:
            return CommentType.DUPLICATE_FOUND
        
        # Check quality level
        if quality.overall_quality.value == "high":
            return CommentType.HIGH_QUALITY_STANDARD
        elif quality.overall_quality.value == "medium":
            return CommentType.MEDIUM_QUALITY_STANDARD
        else:
            return CommentType.LOW_QUALITY_STANDARD
    
    def _build_advanced_prompt(self, context: CommentContext, comment_type: CommentType) -> str:
        """Build sophisticated prompt with full context."""
        templates = self.ai_config["prompt_templates"]
        
        # Build context sections
        ticket_context = self._build_ticket_context(context.ticket)
        quality_context = self._build_quality_context(context.quality_assessment)
        duplicate_context = self._build_duplicate_context(context.duplicate_tickets)
        business_context = self._build_business_context(context.business_context)
        missing_fields_context = self._build_missing_fields_context(context.missing_fields)
        
        # Select appropriate template
        if comment_type == CommentType.UNREPRODUCIBLE_BUG:
            template = templates["unreproducible_bug"]
            user_prompt = template.format(
                ticket_context=ticket_context,
                quality_context=quality_context
            )
        elif comment_type == CommentType.HIGH_QUALITY_STANDARD:
            template = templates["high_quality_comprehensive"]
            user_prompt = template.format(
                ticket_context=ticket_context,
                quality_context=quality_context,
                duplicate_context=duplicate_context,
                business_context=business_context
            )
        else:
            template = templates["improvement_guidance"]
            user_prompt = template.format(
                ticket_context=ticket_context,
                quality_context=quality_context,
                missing_fields_context=missing_fields_context
            )
        
        # Combine system and user prompts
        system_prompt = templates["system_prompt"]
        return f"{system_prompt}\n\n{user_prompt}"
    
    def _build_ticket_context(self, ticket: JiraTicket) -> str:
        """Build comprehensive ticket context string."""
        description = ticket.description or "No description provided"
        return f"""
- Key: {ticket.key}
- Summary: {ticket.summary}
- Description: {description[:200]}{'...' if len(description) > 200 else ''}
- Issue Type: {ticket.issue_type.value}
- Priority: {ticket.priority.value}
- Reporter: {ticket.reporter.display_name}
- Created: {ticket.created_at}
- Has Attachments: {'Yes' if ticket.has_attachments else 'No'}
- Steps to Reproduce: {ticket.steps_to_reproduce or 'Not provided'}
- Affected Version: {ticket.affected_version or 'Not specified'}
        """.strip()
    
    def _build_quality_context(self, quality: QualityAssessment) -> str:
        """Build quality assessment context string."""
        return f"""
- Overall Quality: {quality.overall_quality.value.upper()}
- Quality Score: {quality.score}/100
- Issues Found: {len(quality.issues_found)}
- Specific Issues: {', '.join(quality.issues_found) if quality.issues_found else 'None'}
- Summary Valid: {'Yes' if quality.summary_valid else 'No'}
- Description Valid: {'Yes' if quality.description_valid else 'No'}
- Steps Valid: {'Yes' if quality.steps_valid else 'No'}
        """.strip()
    
    def _build_duplicate_context(self, duplicates: List[Dict[str, Any]]) -> str:
        """Build duplicate tickets context string."""
        if not duplicates:
            return "No duplicate tickets found."
        
        context = f"Found {len(duplicates)} potential duplicate(s):\n"
        for dup in duplicates[:3]:  # Limit to 3 duplicates
            context += f"- {dup.get('key', 'Unknown')}: {dup.get('summary', 'No summary')[:50]}... ({dup.get('status', 'Unknown')})\n"
        
        return context.strip()
    
    def _build_business_context(self, business_context: Dict[str, Any]) -> str:
        """Build business context string."""
        if not business_context:
            return "Standard business priority."
        
        context_parts = []
        if business_context.get("affects_top_merchants"):
            context_parts.append("- Affects top 450 merchants")
        if business_context.get("high_priority_customer"):
            context_parts.append("- High priority customer")
        if business_context.get("revenue_impact"):
            context_parts.append(f"- Revenue impact: {business_context['revenue_impact']}")
        
        return "\n".join(context_parts) if context_parts else "Standard business priority."
    
    def _build_missing_fields_context(self, missing_fields: List[str]) -> str:
        """Build missing fields context string."""
        if not missing_fields:
            return "All required fields are complete."
        
        return f"Missing {len(missing_fields)} required field(s):\n" + "\n".join(f"- {field}" for field in missing_fields)
    
    async def _generate_with_ai(self, prompt: str, context: CommentContext) -> str:
        """Generate comment using AI with the sophisticated prompt."""
        try:
            # Use the existing Gemini client but with our advanced prompt
            response = await self.gemini_client._call_gemini_api(prompt)
            comment = self.gemini_client._extract_comment_from_response(response)
            return comment
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            raise
    
    def _enhance_comment(self, comment: str, context: CommentContext) -> str:
        """Enhance the AI-generated comment with standardized greeting and closing."""
        # Ensure comment starts with the standard greeting
        greeting = f"Hello {context.ticket.reporter.display_name},\n\nThank you for bringing this issue to our attention. To ensure we can provide you with the most effective assistance, I'd like to guide you through providing some additional information that will significantly improve our ability to resolve this quickly."

        # Remove any existing greeting from AI-generated content
        lines = comment.split('\n')
        content_start = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.lower().startswith(('hello', 'hi', 'thank you')):
                content_start = i
                break

        # Extract the main content (skip AI-generated greeting)
        main_content = '\n'.join(lines[content_start:]).strip()

        # Build the enhanced comment with standard structure
        enhanced_comment = greeting

        if main_content:
            enhanced_comment += f"\n\n{main_content}"

        # Add standard closing
        closing = "\n\nI'm here to help if you need any clarification on what information would be most helpful!"
        enhanced_comment += closing

        # Add standardized signature
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        signature = f"\n\n—\nThis comment was generated using Advanced AI with concise formatting\nGenerated on: {timestamp}"
        enhanced_comment += signature

        return enhanced_comment
    
    def _calculate_confidence_score(self, comment: str, context: CommentContext) -> float:
        """Calculate confidence score for the generated comment."""
        score = 0.5  # Base score
        
        # Length check
        if self.ai_config["min_comment_length"] <= len(comment) <= self.ai_config["max_comment_length"]:
            score += 0.2
        
        # Content quality checks
        if "thank you" in comment.lower():
            score += 0.1
        if "next steps" in comment.lower():
            score += 0.1
        if context.ticket.reporter.display_name in comment:
            score += 0.1
        
        return min(1.0, score)
    
    def _generate_intelligent_fallback(self, context: CommentContext) -> str:
        """Generate an intelligent fallback comment with standardized greeting and closing."""
        ticket = context.ticket
        quality = context.quality_assessment

        # Standard greeting
        fallback = f"Hello {ticket.reporter.display_name},\n\n"
        fallback += "Thank you for bringing this issue to our attention. To ensure we can provide you with the most effective assistance, I'd like to guide you through providing some additional information that will significantly improve our ability to resolve this quickly.\n\n"

        # Main content based on quality assessment
        if quality.overall_quality.value == "high":
            fallback += "Your ticket contains good information. We'll investigate this issue and provide updates."
        else:
            fallback += "**Required Information for Optimal Resolution:**\n\n"

            # Add missing fields
            if context.missing_fields:
                for field in context.missing_fields[:5]:  # Limit to 5 fields
                    fallback += f"• {field}\n"

            fallback += "\nPlease update the ticket with this information so we can proceed with the investigation."

        # Standard closing
        fallback += "\n\nI'm here to help if you need any clarification on what information would be most helpful!"

        # Standard signature
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        fallback += f"\n\n—\nThis comment was generated using Advanced AI with concise formatting\nGenerated on: {timestamp}"

        return fallback


# Global instance
_advanced_generator: Optional[AdvancedAICommentGenerator] = None


def get_advanced_ai_generator() -> AdvancedAICommentGenerator:
    """Get the global advanced AI comment generator instance."""
    global _advanced_generator
    if _advanced_generator is None:
        _advanced_generator = AdvancedAICommentGenerator()
    return _advanced_generator


def clear_advanced_generator_cache():
    """Clear the global advanced generator cache."""
    global _advanced_generator
    _advanced_generator = None
