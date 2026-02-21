import logging
import os
from gabay.core.memory import set_user_state, get_user_state, set_temp_data, get_temp_data, clear_user_state
from gabay.core.config import save_to_env, settings
from gabay.core.utils.userbot import get_userbot_client
from telethon import TelegramClient

logger = logging.getLogger(__name__)

async def handle_interactive_setup(user_id: int, message_text: str = None) -> str:
    """
    Directs the user to the secure web interface to bypass chat filters.
    """
    setup_link = f"{settings.base_url}/setup?user_id={user_id}"
    
    return (
        "🛠 **Gabay Web Setup**\n\n"
        "Telegram often blocks login codes sent directly in chat to protect you. "
        "To bypass this, please use our secure, private web setup page:\n\n"
        f"🔗 **[Open Secure Setup Page]({setup_link})**\n\n"
        "1. Enter your API credentials and phone number.\n"
        "2. Enter the login code on the website.\n"
        "3. Once successful, Gabay will be ready to go!"
    )
