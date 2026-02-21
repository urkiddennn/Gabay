import logging
from gabay.core.connectors.google_api import search_drive
from gabay.core.connectors.notion_api import search_notion
from gabay.core.config import settings

logger = logging.getLogger(__name__)

def execute_search(user_id: str, query: str) -> str:
    """
    Parallel or sequential search of Google Drive and Notion APIs.
    Returns a markdown formatted string of clickable links.
    """
    if not query:
        return "Please provide a keyword to search."
        
    try:
        drive_results = search_drive(user_id, query)
        notion_results = search_notion(user_id, query)
        
        if not drive_results and not notion_results:
            admin_link = f"{settings.base_url}/admin?user_id={user_id}"
            return (
                f"No results found for **'{query}'**.\n\n"
                "💡 **Tip:** Make sure your accounts are connected in the "
                f"[Admin Dashboard]({admin_link})."
            )
            
        response_lines = [f"Search results for **'{query}'**:\n"]
        
        if drive_results:
            response_lines.append("📂 **Google Drive:**")
            for r in drive_results:
                response_lines.append(f"- [{r['title']}]({r['link']})")
                
        if notion_results:
            if drive_results:
                response_lines.append("")
            response_lines.append("📝 **Notion:**")
            for r in notion_results:
                response_lines.append(f"- [{r['title']}]({r['link']})")
                
        return "\n".join(response_lines)
        
    except Exception as e:
        logger.error(f"Error executing search: {e}")
        return f"Search failed: {str(e)}"
