import json
import logging
from gabay.core.connectors.smtp_api import send_smtp_email
from gabay.core.connectors.google_api import search_drive, share_file
from gabay.core.connectors.notion_api import search_notion

logger = logging.getLogger(__name__)

def send_email_skill(user_id: str, email_data_str: str) -> str:
    """
    Parses the JSON email data extracted by the LLM and orchestrates the sending process.
    """
    try:
        data = json.loads(email_data_str)
        recipient = data.get("recipient")
        content = data.get("content")
        
        if not recipient or not content:
            return "Missing recipient or content for the email. Could you be more specific?"
            
        # 1. Hybrid Context: Check for Google Drive files
        file_query = data.get("file_query")
        drive_link_text = ""
        if file_query:
            results = search_drive(user_id, file_query)
            if results:
                file_id = results[0]["id"]
                name = results[0]["title"]
                share_result = share_file(user_id, file_id)
                if "link" in share_result:
                    drive_link_text = f"\n📎 File from Google Drive: {name}\nLink: {share_result['link']}"

        # 2. Hybrid Context: Check for Notion pages
        notion_query = data.get("notion_query")
        notion_link_text = ""
        if notion_query:
            results = search_notion(user_id, notion_query)
            if results:
                name = results[0]["title"]
                link = results[0]["link"]
                notion_link_text = f"\n📝 Page from Notion: {name}\nLink: {link}"

        # Default simple formatting. 
        subject = "Message from Gabay Assistant"
        hybrid_context = f"{drive_link_text}{notion_link_text}"
        body = f"{content}\n{hybrid_context}\n\n--\nSent via Gabay."
        
        # Dispatch to the real SMTP connector
        return send_smtp_email(recipient, subject, body, user_id=user_id)
        
    except Exception as e:
        logger.error(f"Error in send_email_skill: {e}")
        return "Sorry, I encountered an internal error drafting that email."
