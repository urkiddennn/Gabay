import logging
import json
from datetime import datetime
from gabay.core.connectors.google_api import create_google_doc, append_to_google_doc, search_drive, share_file
from gabay.core.skills.research import handle_research_skill
from gabay.core.memory import get_contacts
from gabay.core.utils.userbot import send_userbot_message
from gabay.core.config import settings
from gabay.core.utils.llm import get_llm_response
from gabay.core.utils.telegram import send_telegram_message

logger = logging.getLogger(__name__)

async def handle_docs_skill(user_id: int, command_args_str: str) -> str:
    """
    Handles creating, editing, and researching for Google Docs.
    Expects JSON with 'action' (create, edit, research) and relevant parameters.
    """
    try:
        data = json.loads(command_args_str)
        action = data.get("action", "create")
        title = data.get("title", "Untitled Document")
        content = data.get("content", "")
        topic = data.get("topic", "")
        
        # Hybrid Orchestration: Email or Invite
        email_to = data.get("email_to")
        invite_email = data.get("invite_email")
        share_mode = data.get("share_mode", "private") # 'public' or 'private'
        role = data.get("role", "writer") # 'reader' or 'writer'
        
        if action == "research":
            if not topic:
                return "What topic would you like me to research for your document?"
            research_text = await handle_research_skill(str(user_id), topic)
            creation_result = create_google_doc(str(user_id), title, research_text)
            if "error" in creation_result:
                return f"I researched the topic but failed to create the document: {creation_result['error']}"
            
            doc_id = creation_result['id']
            result_msg = f"Done! I've researched '{topic}' and created a document titled '{title}'.\nLink: {creation_result['link']}"

            # Advanced Sharing
            target_invite = invite_email or email_to
            if target_invite:
                share_result = share_file(str(user_id), doc_id, email=target_invite, role=role)
                if "error" not in share_result:
                    result_msg += f"\nI've invited {target_invite} to edit the doc."
            elif share_mode == "public":
                share_file(str(user_id), doc_id) # Default is public reader
                result_msg += "\nI've made the document accessible to anyone with the link."
            
            # Handle follow-up actions
            if email_to:
                from gabay.core.skills.email import send_email_skill
                email_data = json.dumps({"recipient": email_to, "content": f"Here is the research paper I created for you on '{topic}':\n\n{creation_result['link']}"})
                send_email_skill(str(user_id), email_data)
                result_msg += f"\nI've also emailed the link to {email_to}."
                
            return result_msg

        elif action == "create":
            send_telegram_message(user_id, f"📝 **Creating Document:** I'm drafting your document titled '{title}'...")
            creation_result = create_google_doc(str(user_id), title, content)
            if "error" in creation_result:
                return f"Failed to create document: {creation_result['error']}"
            
            doc_id = creation_result['id']
            result_msg = f"Document '{title}' created successfully!\nLink: {creation_result['link']}"
            
            # Advanced Sharing for new docs
            target_invite = invite_email or email_to
            if target_invite:
                share_result = share_file(str(user_id), doc_id, email=target_invite, role=role)
                if "error" not in share_result:
                    result_msg += f"\nI've invited {target_invite} to edit the doc."
            elif share_mode == "public":
                share_file(str(user_id), doc_id)
                result_msg += "\nI've made the document accessible to anyone with the link."
                
            return result_msg

        elif action == "edit":
            file_query = data.get("file_query") or title
            results = search_drive(str(user_id), file_query)
            if not results:
                return f"I couldn't find a document matching '{file_query}' to edit."
            
            doc_id = results[0]["id"]
            success = append_to_google_doc(str(user_id), doc_id, content)
            if success:
                return f"Successfully updated '{results[0]['title']}'."
            else:
                return f"Failed to update the document."
        
        elif action == "template":
            template_type = data.get("template_type", "Meeting Minutes")
            raw_notes = data.get("content", "")
            if not raw_notes:
                return "Please provide the raw notes you want me to organize."
            return await handle_document_templating_skill(user_id, raw_notes, template_type)
        
        else:
            return "I don't know how to perform that action on documents yet."

    except Exception as e:
        logger.error(f"Error in docs skill: {e}")
        return f"I encountered an error managing your documents: {e}"

async def handle_document_templating_skill(user_id: int, raw_notes: str, template_type: str) -> str:
    """
    Organizes raw notes into professional templates (Proposal, Meeting Minutes, SOP).
    """
    try:
        send_telegram_message(user_id, f"🎨 **Organizing Notes:** Applying professional template '{template_type}' to your notes...")
        system_prompt = (
            f"You are a professional documentation expert. Convert the following raw notes into a beautifully structured '{template_type}'.\n"
            "Use clear headings (Markdown style), bullet points, and a professional tone.\n"
            "Templates styles:\n"
            "- Meeting Minutes: Include Attendees, Agenda, Key Decisions, Action Items.\n"
            "- Project Proposal: Include Executive Summary, Objectives, Scope, Timeline, Budget.\n"
            "- SOP: Include Purpose, Scope, Prerequisites, Step-by-Step Procedure.\n"
            "Return ONLY the organized document content."
        )
        
        templated_content = await get_llm_response(
            system_prompt=system_prompt,
            prompt=f"Raw Notes:\n{raw_notes}"
        )
        
        if not templated_content:
            return "The AI assistant returned empty templated content. Please try again."
        title = f"{template_type}: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        creation_result = create_google_doc(str(user_id), title, templated_content)
        if "error" in creation_result:
            return f"I organized your notes but failed to create the document: {creation_result['error']}"
            
        return f"📜 **{template_type} Created!**\n\nI've organized your notes into a professional document.\nLink: {creation_result['link']}"
        
    except Exception as e:
        logger.error(f"Error in document templating: {e}")
        return f"Failed to template document: {e}"
