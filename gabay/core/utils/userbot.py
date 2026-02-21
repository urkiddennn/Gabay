from telethon import TelegramClient
import logging
import os
from gabay.core.config import settings, save_to_env

logger = logging.getLogger(__name__)

# Session file path in data directory
SESSION_PATH = os.path.join(settings.data_dir, "gabay_userbot.session")

async def get_userbot_client():
    """
    Initializes and returns the Telethon TelegramClient.
    """
    api_id = settings.telegram_api_id
    api_hash = settings.telegram_api_hash

    if not api_id or not api_hash:
        logger.warning("Userbot API keys are missing. Userbot features will be disabled.")
        return None

    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    return client

async def send_userbot_message(recipient_id: str, message_text: str) -> bool:
    """
    Sends a message using the Userbot (MTProto).
    recipient_id can be a phone number, username, or chat ID.
    """
    client = await get_userbot_client()
    if not client:
        return False

    try:
        async with client:
            if not await client.is_user_authorized():
                logger.error("Userbot is not authorized. Messaging disabled.")
                return False
            
            await client.send_message(recipient_id, message_text)
            return True
    except Exception as e:
        logger.error(f"Userbot failed to send message: {e}")
        return False

if __name__ == "__main__":
    import asyncio
    
    async def setup():
        print("\n" + "="*50)
        print("📲 Telegram Userbot (MTProto) Setup")
        print("Please visit https://my.telegram.org to get your API keys.")
        
        api_id = settings.telegram_api_id
        api_hash = settings.telegram_api_hash
        
        if not api_id:
            api_id = int(input("Enter your App api_id: ").strip())
            save_to_env("TELEGRAM_API_ID", str(api_id))
            settings.telegram_api_id = api_id
            
        if not api_hash:
            api_hash = input("Enter your App api_hash: ").strip()
            save_to_env("TELEGRAM_API_HASH", api_hash)
            settings.telegram_api_hash = api_hash

        client = TelegramClient(SESSION_PATH, api_id, api_hash)
            
        async with client:
            if not await client.is_user_authorized():
                phone = settings.telegram_phone
                if not phone:
                    phone = input("Enter your phone number (e.g., +639300266353): ").strip()
                    save_to_env("TELEGRAM_PHONE", phone)
                
                await client.send_code_request(phone)
                code = input("Enter the login code sent to your Telegram: ").strip()
                await client.sign_in(phone, code)
                print("✅ Successfully authorized!")
            else:
                me = await client.get_me()
                print(f"✅ Already authorized as {me.first_name}!")
    
    asyncio.run(setup())
