import logging
from gabay.core.config import settings
from gabay.core.memory import get_recent_history
from gabay.core.utils.llm import get_llm_response

logger = logging.getLogger(__name__)

async def handle_chat_skill(user_id: str, message: str) -> str:
    """
    Handles general conversation using the configured LLM (Groq or Gemini). 
    Includes recent chat history for context.
    """
    # Check if we have at least one valid key for the active provider
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            return "I'm currently in basic mode. Please configure my Gemini API key to enable full conversation!"
    else:
        if not settings.groq_api_key:
            return "I'm currently in basic mode. Please configure my Groq API key to enable full conversation!"

    try:
        history = get_recent_history(user_id, limit=20)
        
        messages = [
            {"role": "system", "content": "You are Gabay, a helpful and friendly productivity assistant. You can chat about anything! Be helpful, polite, and practical. If asked about real-time data like weather or traffic, provide the best information you can based on your knowledge, but mention you don't have a live internet sensor for that specific location right now. IMPORTANT FORMATTING RULES: You are sending this message via SMS/Telegram as PLAINTEXT. DO NOT USE ANY MARKDOWN FORMATTING AT ALL. NO asterisks (*), NO bolding (**), NO hashes (#), and NO tables. Use plain text only."}
        ]
        
        # Add history
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
            
        # Add current message
        messages.append({"role": "user", "content": message})
        
        response = await get_llm_response(messages=messages)
        
        if response:
            return response
        else:
            return "I'm having a bit of trouble thinking right now. Could you check my API configuration?"
        
    except Exception as e:
        logger.error(f"Error in chat skill: {e}")
        return "I'm having a bit of trouble thinking right now. Could you try again in a moment?"
