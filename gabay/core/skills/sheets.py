import logging
import json
from gabay.core.connectors.google_api import create_google_sheet, update_sheet_values, share_file
from gabay.core.config import settings
from groq import AsyncGroq

logger = logging.getLogger(__name__)

async def handle_sheets_skill(user_id: int, topic: str, title: str = None, email_to: str = None, invite_email: str = None, share_mode: str = 'private', role: str = 'writer') -> str:
    """
    Handles creating a professional Google Sheet.
    Uses LLM to structure data for the spreadsheet.
    """
    # Import inside to avoid circular deps if any
    from gabay.core.skills.email import send_smtp_email
    
    if not title:
        title = f"Data on {topic}"
        
    try:
        # 1. Generate Structured Data via LLM
        client = AsyncGroq(api_key=settings.groq_api_key)
        
        system_prompt = (
            "You are a professional data analyst. Your goal is to structure a clean, useful dataset on the given topic in a 2D table format. "
            "Return a JSON object with a key 'rows', which is a list of lists. The first list must be the headers (column names). "
            "Generate at least 15-20 rows of realistic, high-quality data. "
            "Return ONLY the JSON object."
        )
        
        user_prompt = f"Topic: {topic}\n\nPlease generate a professional dataset for a spreadsheet."
        
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={ "type": "json_object" }
        )
        
        content = response.choices[0].message.content
        if not content:
            return "The AI assistant returned an empty response. Please try again."

        try:
            sheet_data = json.loads(content)
            rows = sheet_data.get("rows", [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse sheets JSON: {e}. Content: {content}")
            return "I failed to parse the spreadsheet data structure. Please try again."

        if not rows:
            return "I couldn't generate any data for this topic. Please try again."

        # 2. Create the Sheet
        sheet_result = create_google_sheet(str(user_id), title)
        if "error" in sheet_result:
            return f"Failed to create spreadsheet: {sheet_result['error']}"
            
        spreadsheet_id = sheet_result["id"]
        spreadsheet_link = sheet_result["link"]

        # 3. Populate values
        success = update_sheet_values(str(user_id), spreadsheet_id, rows)
        if not success:
            return f"Spreadsheet '{title}' created, but failed to populate data. Link: {spreadsheet_link}"

        result_msg = f"Professional spreadsheet '{title}' created successfully!\nLink: {spreadsheet_link}"

        # 4. Hybrid Orchestration: Sharing & Invites
        target_invite = invite_email or email_to
        if target_invite:
            share_result = share_file(str(user_id), spreadsheet_id, email=target_invite, role=role)
            if "error" not in share_result:
                result_msg += f"\nI've invited {target_invite} to access the spreadsheet."
        elif share_mode == "public":
            share_file(str(user_id), spreadsheet_id)
            result_msg += "\nI've made the spreadsheet accessible to anyone with the link."

        # 5. Hybrid Orchestration: Email Follow-up
        if email_to:
            try:
                subject = f"Spreadsheet: {title}"
                email_body = f"I've created a professional spreadsheet on '{topic}' for you.\n\nLink: {spreadsheet_link}\n\n--\nSent via Gabay."
                send_smtp_email(email_to, subject, email_body, user_id=str(user_id))
                result_msg += f" and sent the link to {email_to}."
            except Exception as e:
                logger.error(f"Failed to send follow-up email for sheets: {e}")
                result_msg += " (Failed to send follow-up email)"

        return result_msg

    except Exception as e:
        logger.error(f"Error in sheets skill: {e}")
        return f"I encountered an error making your spreadsheet: {e}"
