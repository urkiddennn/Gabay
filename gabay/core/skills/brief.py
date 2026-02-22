import logging
from gabay.core.connectors.imap_api import get_unread_emails_imap
from gabay.core.connectors.google_api import get_unread_emails
from gabay.core.connectors.meta_api import get_unread_notifications
from gabay.core.config import settings
from groq import AsyncGroq

logger = logging.getLogger(__name__)

async def generate_brief(user_id: str) -> str:
    """
    Fetch unread emails via IMAP/Gmail API and Facebook notifications, 
    then use an LLM to summarize and prioritize them for the user.
    """
    # 1. Fetch from IMAP (legacy/manual password config)
    emails_imap = get_unread_emails_imap()
    
    # 2. Fetch from Gmail API (modern OAuth connection)
    emails_google = get_unread_emails(user_id)
    
    # Combine and remove potential duplicates
    all_emails = list(set(emails_imap + emails_google))
    
    notifications = get_unread_notifications(user_id)
    
    if not all_emails and not notifications:
        return "You have no new emails or notifications right now. Enjoy your day!"
        
    raw_content = f"Emails:\n{chr(10).join(all_emails)}\n\nNotifications:\n{chr(10).join(notifications)}"
    
    if not settings.groq_api_key:
        return f"Here is your raw briefing (LLM not configured):\n\n{raw_content}"
        
    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        system_prompt = (
            "You are Gabay, a helpful productivity assistant. "
            "Summarize the following emails and notifications into a concise, "
            "friendly 'Daily Briefing'. Highlight anything that looks urgent. "
            "IMPORTANT FORMATTING RULES: You are sending this message via SMS/Telegram as PLAINTEXT. "
            "DO NOT USE ANY MARKDOWN FORMATTING AT ALL. "
            "NO asterisks (*), NO bolding (**), NO hashes (#), and NO tables. Use plain text and standard indentation or dashes (-) only."
        )
        
        response = await client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_content}
            ]
        )
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error generating brief: {e}")
        return f"Error generating summary. Here is the raw data:\n\n{raw_content}"
