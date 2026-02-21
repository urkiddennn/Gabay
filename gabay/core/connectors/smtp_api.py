import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from gabay.core.config import settings

from gabay.core.connectors.token_manager import token_manager

logger = logging.getLogger(__name__)

def send_smtp_email(recipient: str, subject: str, body: str, user_id: str = "local") -> str:
    """
    Sends an email using standard SMTP.
    Prefers credentials from token_manager (for shared Docker persistence).
    """
    config = token_manager.get_token("smtp", user_id) or {}
    
    host = config.get("host") or settings.smtp_host
    port = config.get("port") or settings.smtp_port
    user = config.get("user") or settings.smtp_user
    password = config.get("password") or settings.smtp_password

    if not host or not user or not password:
        return "SMTP credentials are not configured. Please setup SMTP in the Admin Dashboard."

    try:
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connect to server and send
        with smtplib.SMTP(host, port) as server:
            server.starttls() # Secure the connection
            server.login(user, password)
            server.send_message(msg)
            
        logger.info(f"Email successfully sent to {recipient}")
        return f"Successfully sent email to {recipient}!"
        
    except Exception as e:
        logger.error(f"Failed to send email via SMTP: {e}")
        return f"Error sending email: {str(e)}"
