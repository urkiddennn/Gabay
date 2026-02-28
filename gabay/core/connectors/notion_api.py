import os
import logging
from notion_client import Client
from gabay.core.config import settings
from gabay.core.connectors.token_manager import token_manager

logger = logging.getLogger(__name__)

def get_notion_config(user_id: str = "local"):
    return token_manager.get_token("notion", user_id) or {}

def get_notion_client(user_id: str = "local"):
    config = get_notion_config(user_id)
    notion_key = config.get("api_key") or os.getenv("NOTION_API_KEY")
    if not notion_key:
        logger.warning("Notion API Key not found")
        return None
    return Client(auth=notion_key)

def append_to_database(user_id: str, content: str) -> str:
    # Use local config if no specific user ID
    
    config = get_notion_config(user_id) or get_notion_config("local")
    
    client = get_notion_client(user_id) or get_notion_client("local")
    db_id = config.get("database_id") or os.getenv("NOTION_DATABASE_ID")
    
    if not client:
        return "Notion API key not configured."
    if not db_id:
        return "Notion Database ID not configured. Please add NOTION_DATABASE_ID to your settings."
        
    # Sanitize Database ID (remove dashes)
    db_id = db_id.replace("-", "")
        
    try:
        # Locate title property
        db = client.databases.retrieve(database_id=db_id)
        title_prop = next((name for name, prop in db['properties'].items() if prop['type'] == 'title'), 'Name')
        
        new_page = client.pages.create(
            parent={"database_id": db_id},
            properties={
                title_prop: {
                    "title": [{"text": {"content": content}}]
                }
            }
        )
        return new_page.get("url", "https://notion.so")
    except Exception as e:
        logger.error(f"Notion append error: {e}")
        return f"Error appending to Notion: {str(e)}"

def search_notion(user_id: str, query: str) -> list[dict]:
    client = get_notion_client()
    if not client:
        return []
        
    try:
        results = client.search(query=query, filter={"property": "object", "value": "page"}).execute()
        pages = results.get("results", [])
        
        parsed_results = []
        for page in pages:
            # Extract title
            properties = page.get("properties", {})
            title = "Untitled"
            for prop in properties.values():
                if prop.get("type") == "title" and prop.get("title"):
                    title = prop["title"][0]["plain_text"]
                    break
            
            parsed_results.append({
                "title": title,
                "link": page.get("url")
            })
        return parsed_results
    except Exception as e:
        logger.error(f"Notion search error: {e}")
        return []
