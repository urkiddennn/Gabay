import logging
from gabay.core.connectors.imap_api import get_unread_emails_imap
from gabay.core.connectors.google_api import get_unread_emails_full
from gabay.core.connectors.meta_api import get_unread_notifications
from gabay.core.config import settings

logger = logging.getLogger(__name__)

async def generate_brief(user_id: str) -> str:
    """
    Fetch unread emails via IMAP/Gmail API and Facebook notifications, 
    then use an LLM to summarize and prioritize them for the user.
    """
    # Fetch from IMAP
    emails_imap = get_unread_emails_imap()
    
    # Fetch from Gmail API
    emails_google_raw = get_unread_emails_full(user_id)
    emails_google = [f"From: {e['sender']} - Subject: {e['subject']}" for e in emails_google_raw]
    
    # Remove duplicates
    all_emails = list(set(emails_imap + emails_google))
    
    notifications = get_unread_notifications(user_id)
    
    if not all_emails and not notifications:
        return "You have no new emails or notifications right now. Enjoy your day!"
        
    raw_content = f"Emails:\n{chr(10).join(all_emails)}\n\nNotifications:\n{chr(10).join(notifications)}"
    
    from gabay.core.utils.llm import get_llm_response
    
    system_prompt = (
        "You are Gabay, a helpful productivity assistant. "
        "Summarize the following emails and notifications into a concise, "
        "friendly 'Daily Briefing'. Highlight anything that looks urgent. "
        "IMPORTANT: You are sending this via Telegram as PLAINTEXT. "
        "DO NOT USE ANY MARKDOWN. No asterisks, bolding, hashes, or tables."
    )
    
    result = await get_llm_response(raw_content, system_prompt)
    if not result:
        return f"Error generating summary. Raw data:\n\n{raw_content}"
    
    return result
