import logging
from gabay.core.connectors.rss_api import fetch_feed
from gabay.core.config import settings
from groq import AsyncGroq

logger = logging.getLogger(__name__)

async def handle_news_skill(topic: str) -> str:
    """
    Fetches latest RSS feeds on a topic, then asks the LLM to format/summarize them.
    """
    if not topic or str(topic).strip() == "":
        topic = "world" # Default topic
        
    rss_text = fetch_feed(topic, max_items=5)
    
    if "error" in rss_text.lower() or "couldn't find" in rss_text.lower():
        # Fallback if the feed failed
        return rss_text
        
    if not settings.groq_api_key:
        return f"Here is the raw news feed (LLM not configured):\n\n{rss_text}"
        
    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        system_prompt = (
            "You are Gabay, a helpful productivity assistant. "
            "You have been provided with the latest news headlines and summaries from an RSS feed. "
            "Your job is to read these headlines and summarize them nicely for the user in a friendly, conversational tone. "
            "IMPORTANT FORMATTING RULES: You are sending this message via SMS/Telegram as PLAINTEXT. "
            "DO NOT USE ANY MARKDOWN FORMATTING AT ALL. "
            "NO asterisks (*), NO bolding (**), NO hashes (#), and NO tables. Use plain text and standard indentation or dashes (-) only."
        )
        
        user_prompt = f"User asked for news about: {topic}\n\nHere are the raw RSS items:\n\n{rss_text}"
        
        response = await client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error in news QA skill: {e}")
        return f"I fetched some news, but had trouble summarizing it. Here is the raw data:\n\n{rss_text}"
