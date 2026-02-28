import logging
import json
from gabay.core.connectors.smtp_api import send_smtp_email
from gabay.core.connectors.google_api import (
    search_drive, share_file, get_unread_emails_full, get_thread_messages
)
from gabay.core.connectors.notion_api import search_notion
from gabay.core.config import settings
from gabay.core.skills.search import execute_search

logger = logging.getLogger(__name__)

def send_email_skill(user_id: str, email_data_str: str) -> str:
    """
    Parses the JSON email data extracted by the LLM and orchestrates the sending process.
    """
    try:
        data = json.loads(email_data_str)
        recipient = data.get("recipient")
        content = data.get("content")
        
        if not recipient or not content:
            return "Missing recipient or content for the email. Could you be more specific?"
            
        # Check Google Drive
        file_query = data.get("file_query")
        drive_link_text = ""
        if file_query:
            results = search_drive(user_id, file_query)
            if results:
                file_id = results[0]["id"]
                name = results[0]["title"]
                share_result = share_file(user_id, file_id)
                if "link" in share_result:
                    drive_link_text = f"\n📎 File from Google Drive: {name}\nLink: {share_result['link']}"

        # Check Notion
        notion_query = data.get("notion_query")
        notion_link_text = ""
        if notion_query:
            results = search_notion(user_id, notion_query)
            if results:
                name = results[0]["title"]
                link = results[0]["link"]
                notion_link_text = f"\n📝 Page from Notion: {name}\nLink: {link}"

        subject = "Message from Gabay Assistant"
        hybrid_context = f"{drive_link_text}{notion_link_text}"
        body = f"{content}\n{hybrid_context}\n\n--\nSent via Gabay."
        
        return send_smtp_email(recipient, subject, body, user_id=user_id)
        
    except Exception as e:
        logger.error(f"Error in send_email_skill: {e}")
        return "Sorry, I encountered an internal error drafting that email."

async def handle_triage_skill(user_id: str, proactive: bool = False) -> str:
    """
    Categorizes unread emails based on user priorities and importance.
    """
    from gabay.core.database import db
    from gabay.core.utils.telegram import send_telegram_message
    
    try:
        # Fetch priorities
        priorities = db.get_user_priorities(int(user_id))
        priorities_context = f"User Priorities: {', '.join(priorities)}" if priorities else "No specific priorities set."

        # Fetch emails
        emails = get_unread_emails_full(user_id, max_results=10)
        if not emails:
            return "No unread emails to triage."

        # Categorize via LLM
        from gabay.core.utils.llm import get_llm_response
        
        emails_text = "\n".join([f"{i}: {e['sender']} - {e['subject']}" for i, e in enumerate(emails)])

        system_prompt = (
            "You are Gabay Triage AI. Categorize unread emails for the user.\n"
            f"{priorities_context}\n"
            "Categories: 'Urgent', 'Internal', 'Newsletter', 'Social'.\n"
            "Return JSON: {'triage': [{'index': int, 'category': str, 'reason': str}]}."
        )

        res_data = await get_llm_response(
            f"Triage these emails:\n\n{emails_text}", 
            system_prompt, 
            response_format={"type": "json_object"}
        )
        if not res_data:
            return "Failed to triage emails."
            
        triage_data = res_data.get("triage", [])
        
        report = "📬 **Email Triage Report**\n\n"
        urgent_count = 0
        for item in triage_data:
            idx = item.get('index')
            if idx is not None and idx < len(emails):
                category = item.get('category', 'Other')
                email = emails[idx]
                icon = "🚨" if category == "Urgent" else "📩"
                report += f"{icon} **{category}**: {email['subject']} (from {email['sender']})\n"
                if category == "Urgent":
                    urgent_count += 1

        if proactive and urgent_count == 0:
            return "No urgent emails found."

        if proactive:
            send_telegram_message(int(user_id), report)
            return report
        else:
            return report

    except Exception as e:
        logger.error(f"Triage error: {e}")
        return f"Failed to triage emails: {e}"

async def handle_smart_draft_skill(user_id: str, thread_id: str, prompt: str) -> str:
    """
    Drafts a context-aware email reply by looking at thread history and related documents.
    """
    try:
        # Fetch thread history
        messages = get_thread_messages(user_id, thread_id)
        if not messages:
            return "I couldn't find that email thread to draft a reply."
            
        context_text = "\n".join([f"{m['from']}: {m['snippet']}" for m in messages])
        
        # Search for related files/notes
        search_query = f"{prompt} {messages[-1]['snippet']}"
        search_results = await execute_search(user_id, search_query)
        
        # Generate draft
        from gabay.core.utils.llm import get_llm_response
        
        system_prompt = (
            "You are a professional email assistant. Draft a reply based on the thread context, "
            "related search info, and user's prompt.\n\n"
            f"Thread History:\n{context_text}\n\n"
            f"Relevant Files/Notes Found:\n{search_results}\n\n"
            "Return ONLY the drafted email body."
        )
        
        draft = await get_llm_response(f"User's request: {prompt}", system_prompt)
        if not draft:
            return "Failed to generate smart draft."

        return f"💡 **Smart Draft Generated:**\n\n{draft}\n\n*Context derived from history and knowledge base.*"
        
    except Exception as e:
        logger.error(f"Error in smart draft: {e}")
        return f"Sorry, I couldn't generate a smart draft: {e}"
