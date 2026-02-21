import requests
import logging
from gabay.core.config import settings

logger = logging.getLogger(__name__)

import time

def send_telegram_message(chat_id: int, text: str) -> bool:
    """Utility to send a message back to telegram synchronously. Splits long messages."""
    token = settings.telegram_bot_token
    if not token or token in ("TBD", "your_telegram_bot_token_here"):
        logger.warning(f"No valid token. Would have sent to {chat_id}: {text}")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    max_len = 4000
    
    try:
        if len(text) <= max_len:
            response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram API Error ({response.status_code}): {response.text}")
                return False
                
        # Smart split message into chunks if it's too long (avoid breaking markdown if possible)
        chunks = []
        current_chunk = ""
        paragraphs = text.split('\n')
        
        for p in paragraphs:
            # If a single line is somehow longer than max_len, we have to hard split it
            if len(p) > max_len:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                for i in range(0, len(p), max_len):
                    chunks.append(p[i:i+max_len])
                continue
                
            if len(current_chunk) + len(p) + 1 > max_len:
                chunks.append(current_chunk)
                current_chunk = p
            else:
                if current_chunk:
                    current_chunk += '\n' + p
                else:
                    current_chunk = p
                    
        if current_chunk:
            chunks.append(current_chunk)
            
        overall_success = True
        
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            chunk_text = chunk if i == 0 else f"(cont.)\n{chunk}"
            response = requests.post(url, json={"chat_id": chat_id, "text": chunk_text}, timeout=10)
            if response.status_code != 200:
                logger.error(f"Telegram API Error chunk {i} ({response.status_code}): {response.text}")
                overall_success = False
            time.sleep(0.5) # Slight delay to avoid hitting rate limits
            
        return overall_success
    except Exception as e:
        logger.error(f"Failed to connect to Telegram API: {e}")
        return False
