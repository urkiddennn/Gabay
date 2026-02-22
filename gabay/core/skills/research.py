import logging
import json
from gabay.core.config import settings
from groq import AsyncGroq

logger = logging.getLogger(__name__)

async def handle_research_skill(user_id: str, topic: str) -> str:
    """
    Performs deep research on a topic using the LLM and returns a formatted report.
    In the future, this will integrate with web search APIs.
    """
    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        
        system_prompt = (
            "You are Gabay Research AI. Your task is to provide a comprehensive, detailed, and cited research report on the user's topic. "
            "Structure your response with: "
            "1. Abstract/Summary\n"
            "2. Key Findings\n"
            "3. Detailed Analysis\n"
            "4. Citations (Internal knowledge and logical deductions)\n\n"
            "IMPORTANT: While you don't have live web access right now, use your extensive knowledge base to provide the most up-to-date and accurate information possible as of your last training data. "
            "If the user asks for citations, cite real-world sources you know exist."
        )
        
        user_prompt = f"Research Topic: {topic}\n\nPlease provide a full research paper on this."
        
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        report = response.choices[0].message.content
        return report
        
    except Exception as e:
        logger.error(f"Error in research skill: {e}")
        return f"I encountered an error during research: {e}"
