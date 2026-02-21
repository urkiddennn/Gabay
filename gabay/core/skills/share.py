import logging
import json
from gabay.core.connectors.google_api import search_drive, share_file
from gabay.core.memory import get_contacts
from gabay.core.utils.userbot import send_userbot_message

logger = logging.getLogger(__name__)

async def handle_share_skill(user_id: int, command_args_str: str) -> str:
    """
    Handles sharing a file from Google Drive to a contact.
    Expects command_args_str to be a JSON string with 'file_query' and optionally 'contact_name'.
    """
    try:
        # We might receive just a string if LLM failed to format perfectly, so fallback
        try:
            data = json.loads(command_args_str)
            file_query = data.get("file_query", "")
            contact_name = data.get("contact_name", "").lower()
        except:
            file_query = command_args_str
            contact_name = ""
            
        if not file_query:
            return "What file would you like me to share?"
            
        # Search for the file
        results = search_drive(str(user_id), file_query)
        if not results:
            return f"I couldn't find any file matching '{file_query}' in your Google Drive."
            
        # Get the first result
        file_id = results[0].get("id")
        if not file_id:
            return "File found, but I couldn't retrieve its ID for sharing."
            
        share_result = share_file(str(user_id), file_id)
        if "error" in share_result:
            return share_result["error"]
            
        link = share_result["link"]
        name = share_result["name"]
        
        message = f"Here is the link to '{name}':\n{link}"
        
        if contact_name:
            contacts = get_contacts(user_id)
            recipient = contacts.get(contact_name) or contact_name
            success = await send_userbot_message(recipient, message)
            if success:
                return f"Successfully shared '{name}' with {contact_name.capitalize()}!"
            else:
                return f"I got the link for '{name}':\n{link}\n\nBut I failed to send it to '{contact_name}'. Please ensure my Userbot is logged in."
        else:
            return message
            
    except Exception as e:
        logger.error(f"Error in share skill: {e}")
        return f"I encountered an error while trying to share: {e}"
