import logging
from gabay.core.connectors.google_api import get_unread_emails_full
from gabay.core.connectors.notion_api import search_notion

logger = logging.getLogger(__name__)

async def handle_read_skill(user_id: str, source: str = "all") -> str:
    """
    Handles the 'read' intent by fetching content from the specified source.
    """
    results = []
    
    if source in ("gmail", "all"):
        try:
            emails = get_unread_emails_full(user_id)
            if emails:
                results.append("📬 **Recent Unread Emails (Gmail):**")
                results.extend([f"• From: {e['sender']} - {e['subject']}" for e in emails])
            else:
                if source == "gmail":
                    results.append("You have no unread emails in Gmail.")
        except Exception as e:
            logger.error(f"Error reading from Gmail: {e}")
            results.append("❌ Error reading from Gmail.")

    if source in ("notion", "all"):
        try:
            # For Notion, we'll try to find recent pages or items.
            # Using search_notion with an empty query might return recent items if the API supports it,
            # but notion-client's search usually requires something or returns everything.
            # Let's try searching for " " or "*" or just empty.
            notion_items = search_notion(user_id, "")
            if notion_items:
                results.append("\n📝 **Recent Notion Pages:**")
                results.extend([f"• [{item['title']}]({item['link']})" for item in notion_items])
            else:
                if source == "notion":
                    results.append("No recent items found in Notion.")
        except Exception as e:
            logger.error(f"Error reading from Notion: {e}")
            results.append("❌ Error reading from Notion.")

    if not results:
        return "I couldn't find anything new to read from your connected accounts."

    return "\n".join(results)
