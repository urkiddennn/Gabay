import json
import logging
from gabay.core.connectors.smtp_api import send_smtp_email

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
            
        # Default simple formatting. 
        subject = "Message from Gabay Assistant"
        body = f"{content}\n\n--\nSent via Gabay."
        
        # Dispatch to the real SMTP connector
        return send_smtp_email(recipient, subject, body)
        
    except Exception as e:
        logger.error(f"Error in send_email_skill: {e}")
        return "Sorry, I encountered an internal error drafting that email."
