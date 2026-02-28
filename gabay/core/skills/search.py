import logging
from gabay.core.connectors.google_api import search_drive
from gabay.core.connectors.notion_api import search_notion
from gabay.core.config import settings
from gabay.core.utils.llm import get_llm_response

logger = logging.getLogger(__name__)

async def execute_search(user_id: str, query: str) -> str:
    """
    LLM-enhanced search that expands the query into multiple variations for better recall.
    """
    if not query:
        return "Please provide a keyword to search."
        
    try:
        # 1. Query Expansion via LLM
        expansion_prompt = (
            f"The user is searching for: '{query}'. "
            "Suggest 3 better, specific search queries for finding relevant documents in Google Drive or Notion. "
            "Output only the 3 queries separated by commas. No extra text."
        )
        
        try:
            content = await get_llm_response(
                prompt=expansion_prompt,
                model="llama-3.1-8b-instant"
            )
            if content:
                expanded_queries = [q.strip() for q in content.split(",")]
            else:
                expanded_queries = []
            expanded_queries.append(query)
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            expanded_queries = [query]

        # 2. Consolidated Search
        drive_results = []
        notion_results = []
        seen_drive_ids = set()
        seen_notion_ids = set()
        
        for q in set(expanded_queries):
            d_res = search_drive(user_id, q)
            for r in d_res:
                if r['id'] not in seen_drive_ids:
                    drive_results.append(r)
                    seen_drive_ids.add(r['id'])
                    
            n_res = search_notion(user_id, q)
            for r in n_res:
                if r['id'] not in seen_notion_ids:
                    notion_results.append(r)
                    seen_notion_ids.add(r['id'])
        
        if not drive_results and not notion_results:
            admin_link = f"{settings.base_url}/admin?user_id={user_id}"
            return (
                f"No results found across Drive or Notion for **'{query}'**.\n\n"
                "💡 **Tip:** Try broadening your keywords or check your connections in the "
                f"[Admin Dashboard]({admin_link})."
            )
            
        response_lines = [f"Semantic search results for **'{query}'**:\n"]
        
        if drive_results:
            response_lines.append("📂 **Google Drive:**")
            for r in drive_results[:5]: # Top 5
                response_lines.append(f"- [{r['title']}]({r['link']})")
                
        if notion_results:
            if drive_results:
                response_lines.append("")
            response_lines.append("📝 **Notion:**")
            for r in notion_results[:5]:
                response_lines.append(f"- [{r['title']}]({r['link']})")
                
        return "\n".join(response_lines)
        
    except Exception as e:
        logger.error(f"Error executing search: {e}")
        return f"Search encountered an issue: {str(e)}"
