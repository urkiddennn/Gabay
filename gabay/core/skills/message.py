import logging
import json
from gabay.core.memory import get_contacts
from gabay.core.utils.userbot import send_userbot_message

logger = logging.getLogger(__name__)

async def handle_message_skill(user_id: int, command_args_str: str) -> str:
    """
    Handles sending a message to a Telegram contact using the Userbot (MTProto).
    """
    try:
        data = json.loads(command_args_str)
        contact_name = data.get("contact_name", "").lower()
        message_text = data.get("message_text", "")
        
        if not contact_name or not message_text:
            return "Who do you want to message, and what should I say?"
            
        contacts = get_contacts(user_id)
        # Try to get the chat_id from contacts, otherwise try to use the name directly
        recipient = contacts.get(contact_name) or contact_name
        
        # Send the message using Userbot
        success = await send_userbot_message(recipient, message_text)
        
        if success:
            return f"Successfully sent message to {contact_name.capitalize()} via Userbot!"
        else:
            return f"I couldn't send the message to '{contact_name}'. Please make sure my API keys are correct and I am logged in."
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in message skill: {error_msg}")
        
        if "Could not find the input entity" in error_msg or "PeerIdInvalidError" in error_msg:
            return f"I couldn't find '{contact_name}' on Telegram. Because you logged in as a Bot, they MUST click 'Start' on your bot first."
        elif "UserIsBlockedError" in error_msg:
            return f"It looks like {contact_name} has blocked the bot."
        
        return f"I encountered an error while trying to send that message: {error_msg}"
