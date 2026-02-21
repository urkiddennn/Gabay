import imaplib
import email
from email.header import decode_header
import logging
from gabay.core.config import settings

logger = logging.getLogger(__name__)

def get_unread_emails_imap() -> list[str]:
    """
    Fetches unread email subjects using IMAP.
    Requires SMTP_USER (as IMAP user) and SMTP_PASSWORD in .env.
    Note: Most providers use 'imap.gmail.com' for IMAP host.
    """
    # We'll assume the user might want a separate IMAP_HOST but for simplicity 
    # we'll try to derive it or use a common default if not provided.
    imap_host = os.environ.get("IMAP_HOST", "imap.gmail.com") 
    
    if not settings.smtp_user or not settings.smtp_password:
        return []

    try:
        # Connect to the server
        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(settings.smtp_user, settings.smtp_password)
        mail.select("inbox")

        # Search for unread emails (UNSEEN)
        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK':
            return []

        email_list = []
        # Get the list of email IDs
        for num in messages[0].split()[:5]: # Get last 5 unread
            status, data = mail.fetch(num, '(RFC822)')
            if status != 'OK':
                continue
            
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    from_match = msg.get("From")
                    email_list.append(f"From: {from_match} - Subject: {subject}")

        mail.logout()
        return email_list
        
    except Exception as e:
        logger.error(f"Failed to fetch emails via IMAP: {e}")
        return []

import os # Needed for imap_host env fetch
