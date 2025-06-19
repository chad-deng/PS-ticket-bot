"""
Google Gemini API client for PS Ticket Process Bot.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
import httpx
import json
import time

from app.core.config import get_settings
from app.models.ticket import JiraTicket, QualityAssessment
from app.utils.config_manager import get_config_manager


logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    """Custom exception for Gemini API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class GeminiClient:
    """Google Gemini API client with async support."""
    
    def __init__(self):
        """Initialize the Gemini client."""
        import os
        from dotenv import load_dotenv
        load_dotenv()  # Ensure environment variables are loaded

        self.settings = get_settings()
        self.config_manager = get_config_manager()

        # Use environment variables directly if available, otherwise fall back to settings
        self.api_key = os.getenv("GEMINI_API_KEY") or self.settings.gemini.api_key
        self.model = os.getenv("GEMINI_MODEL") or self.settings.gemini.model
        self.base_url = "https://generativelanguage.googleapis.com/v1"
        
        # Generation parameters
        self.temperature = self.settings.gemini.temperature
        self.top_p = self.settings.gemini.top_p
        self.top_k = self.settings.gemini.top_k
        self.max_output_tokens = self.settings.gemini.max_output_tokens
        
        # HTTP client configuration
        self.timeout = self.settings.gemini.timeout
        self.max_retries = self.settings.gemini.max_retries
        self.retry_delay = self.settings.gemini.retry_delay
        
        logger.info(f"Initialized Gemini client with model: {self.model}")
    
    async def generate_comment(self, ticket: JiraTicket, quality_assessment: QualityAssessment) -> str:
        """
        Generate an AI comment for a JIRA ticket based on quality assessment.
        
        Args:
            ticket: JiraTicket to generate comment for
            quality_assessment: Quality assessment result
            
        Returns:
            str: Generated comment text
            
        Raises:
            GeminiAPIError: If API call fails
        """
        logger.info(f"Generating AI comment for ticket {ticket.key}")
        
        # Construct the prompt
        prompt = self._construct_prompt(ticket, quality_assessment)
        
        # Generate content using Gemini API
        try:
            response = await self._call_gemini_api(prompt)
            comment = self._extract_comment_from_response(response)
            
            logger.info(f"Successfully generated comment for ticket {ticket.key}")
            return comment
            
        except Exception as e:
            logger.error(f"Failed to generate comment for ticket {ticket.key}: {e}")
            raise GeminiAPIError(f"Comment generation failed: {e}")
    
    def _construct_prompt(self, ticket: JiraTicket, quality_assessment: QualityAssessment) -> str:
        """
        Construct the prompt for Gemini API based on ticket and quality assessment.
        
        Args:
            ticket: JiraTicket data
            quality_assessment: Quality assessment result
            
        Returns:
            str: Constructed prompt
        """
        # Get system prompt from configuration
        gemini_config = self.config_manager.settings.yaml_config.get("gemini", {})
        comment_config = gemini_config.get("comment_generation", {})
        prompts = comment_config.get("prompts", {})
        
        system_prompt = prompts.get("system_prompt", """
You are a helpful JIRA ticket assistant for a Product Support team. Your role is to:
1. Analyze ticket quality and completeness
2. Generate professional, helpful comments for JIRA tickets
3. Request missing information in a polite and clear manner
4. Provide guidance on next steps

Always maintain a professional, helpful, and constructive tone.
        """).strip()
        
        user_prompt_template = prompts.get("user_prompt_template", """
Please analyze this JIRA ticket and generate a helpful comment:

**Ticket Details:**
- Summary: {summary}
- Description: {description}
- Issue Type: {issue_type}
- Priority: {priority}
- Reporter: {reporter}
- Has Attachments: {has_attachments}
- Steps to Reproduce: {steps_to_reproduce}
- Affected Version: {affected_version}

**Quality Assessment:**
- Overall Quality: {overall_quality}
- Issues Found: {issues_found}

**Instructions:**
1. Start with a professional greeting
2. Acknowledge the ticket submission
3. If quality is high, provide encouragement and next steps
4. If quality is medium/low, politely request missing information
5. Be specific about what information is needed
6. End with a helpful closing

Generate a professional JIRA comment (max 500 words):
        """).strip()
        
        # Format the user prompt with ticket data
        user_prompt = user_prompt_template.format(
            summary=ticket.summary or "No summary provided",
            description=ticket.description or "No description provided",
            issue_type=ticket.issue_type.value,
            priority=ticket.priority.value,
            reporter=ticket.reporter.display_name,
            has_attachments="Yes" if ticket.has_attachments else "No",
            steps_to_reproduce=ticket.steps_to_reproduce or "Not provided",
            affected_version=ticket.affected_version or "Not specified",
            overall_quality=quality_assessment.overall_quality.value,
            issues_found=", ".join(quality_assessment.issues_found) if quality_assessment.issues_found else "None"
        )
        
        # Combine system and user prompts
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        logger.debug(f"Constructed prompt for ticket {ticket.key} (length: {len(full_prompt)} chars)")
        return full_prompt
    
    async def _call_gemini_api(self, prompt: str) -> Dict[str, Any]:
        """
        Make API call to Gemini.
        
        Args:
            prompt: Text prompt for generation
            
        Returns:
            Dict: API response
            
        Raises:
            GeminiAPIError: If API call fails
        """
        url = f"{self.base_url}/models/{self.model}:generateContent"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": self.temperature,
                "topK": self.top_k,
                "topP": self.top_p,
                "maxOutputTokens": self.max_output_tokens,
                "candidateCount": 1
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }
        
        # Add API key to URL parameters
        params = {"key": self.api_key}
        
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        params=params,
                        headers=headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 429:
                        # Rate limit exceeded
                        if attempt < self.max_retries:
                            wait_time = self.retry_delay * (2 ** attempt)
                            logger.warning(f"Rate limit exceeded, retrying in {wait_time} seconds...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise GeminiAPIError("Rate limit exceeded", 429)
                    elif response.status_code == 400:
                        error_data = response.json() if response.content else {}
                        raise GeminiAPIError(f"Bad request: {error_data}", 400, error_data)
                    else:
                        error_data = response.json() if response.content else {}
                        raise GeminiAPIError(
                            f"API call failed: {response.status_code}",
                            response.status_code,
                            error_data
                        )
                        
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Request error, retrying in {wait_time} seconds: {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise GeminiAPIError(f"Request failed: {e}")
        
        raise GeminiAPIError("Max retries exceeded")
    
    def _extract_comment_from_response(self, response: Dict[str, Any]) -> str:
        """
        Extract the generated comment from Gemini API response.
        
        Args:
            response: Gemini API response
            
        Returns:
            str: Generated comment text
            
        Raises:
            GeminiAPIError: If response format is invalid
        """
        try:
            candidates = response.get("candidates", [])
            if not candidates:
                raise GeminiAPIError("No candidates in response")
            
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                raise GeminiAPIError("No parts in response content")
            
            text = parts[0].get("text", "")
            if not text:
                raise GeminiAPIError("No text in response")
            
            # Clean up the response text
            comment = text.strip()
            
            # Remove any markdown formatting that might interfere with JIRA
            comment = comment.replace("**", "")  # Remove bold markdown
            comment = comment.replace("*", "")   # Remove italic markdown
            
            return comment
            
        except Exception as e:
            logger.error(f"Failed to extract comment from response: {e}")
            raise GeminiAPIError(f"Failed to parse response: {e}")
    
    def generate_fallback_comment(self, ticket: JiraTicket, quality_assessment: QualityAssessment) -> str:
        """
        Generate a fallback comment when AI generation fails.
        
        Args:
            ticket: JiraTicket data
            quality_assessment: Quality assessment result
            
        Returns:
            str: Fallback comment text
        """
        logger.info(f"Generating fallback comment for ticket {ticket.key}")
        
        # Get comment templates from configuration
        templates = self.settings.get_comment_templates()
        
        quality_level = quality_assessment.overall_quality.value
        issues_found = quality_assessment.issues_found
        
        if quality_level == "high":
            template = templates.get("high_quality", {})
            greeting = template.get("greeting", "Thank you for submitting this well-detailed ticket.")
            body = template.get("body", "Your ticket contains all the necessary information for our team to investigate. We'll begin working on this shortly.")
            closing = template.get("closing", "We'll keep you updated on our progress.")
            
            comment = f"{greeting} {body} {closing}"
            
        elif quality_level == "medium":
            template = templates.get("medium_quality", {})
            greeting = template.get("greeting", "Thank you for submitting this ticket.")
            body = template.get("body", "To help us investigate this issue more effectively, could you please provide the following additional information:")
            closing = template.get("closing", "Once we have this information, we'll be able to proceed with the investigation.")
            
            comment = f"{greeting} {body}\n\n"
            for issue in issues_found:
                comment += f"- {issue}\n"
            comment += f"\n{closing}"
            
        else:  # low quality
            template = templates.get("low_quality", {})
            greeting = template.get("greeting", "Thank you for submitting this ticket.")
            body = template.get("body", "To properly investigate this issue, we need some additional information. Please provide:")
            closing = template.get("closing", "Please update this ticket with the requested information so we can assist you effectively.")
            
            comment = f"{greeting} {body}\n\n"
            for issue in issues_found:
                comment += f"- {issue}\n"
            comment += f"\n{closing}"
        
        return comment
    
    async def test_api_connection(self) -> Dict[str, Any]:
        """
        Test the Gemini API connection.
        
        Returns:
            Dict: Test result
        """
        test_prompt = "Generate a brief, professional response to acknowledge a JIRA ticket submission."
        
        try:
            start_time = time.time()
            response = await self._call_gemini_api(test_prompt)
            end_time = time.time()
            
            comment = self._extract_comment_from_response(response)
            
            return {
                "success": True,
                "response_time": end_time - start_time,
                "generated_text": comment[:100] + "..." if len(comment) > 100 else comment,
                "model": self.model
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model": self.model
            }


# Global Gemini client instance
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get the global Gemini client instance."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


def clear_gemini_client_cache():
    """Clear the global Gemini client cache to force reload."""
    global _gemini_client
    _gemini_client = None
