import logging
import json
from gabay.core.connectors.google_api import create_google_sheet, update_sheet_values, share_file, search_gmail_full, get_sheet_values, add_chart_to_sheet
# ... existing imports ...

async def handle_visualize_skill(user_id: int, spreadsheet_id: str, title: str = "Data Visualization") -> str:
    """Adds a chart to an existing Google Sheet."""
    try:
        # We assume the data is in the first sheet (index 0)
        success = add_chart_to_sheet(str(user_id), spreadsheet_id, 0, title, "Sheet1!A1:B10")
        if success:
            return f"✅ **Chart Generated!** I've added a professional visualization to your spreadsheet: [Open Sheet](https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit)"
        else:
            return "Failed to generate chart. Please make sure the spreadsheet contains at least two columns of data."
    except Exception as e:
        logger.error(f"Error in visualize skill: {e}")
        return f"Error visualizing data: {e}"

from gabay.core.config import settings
from gabay.core.utils.llm import get_llm_response
from gabay.core.utils.telegram import send_telegram_message

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
        # 1. Phase 1: Planning & Design
        send_telegram_message(user_id, f"📊 **Designing Spreadsheet:** I'm planning the layout for your data on '{topic}'...")

        system_prompt = (
            "You are a professional data analyst. Your goal is to structure a clean, useful dataset on the given topic in a 2D table format. "
            "First, return a JSON object with a key 'schema' which is a list of the column headers. "
            "Then, include a key 'rows', which is a list of lists. The first list must be the headers (column names). "
            "Generate at least 15-20 rows of realistic, high-quality data."
        )
        
        user_prompt = f"Topic: {topic}\n\nPlease design and generate a professional dataset for a spreadsheet."
        
        sheet_data = await get_llm_response(
            system_prompt=system_prompt,
            prompt=user_prompt,
            response_format={ "type": "json_object" }
        )
        
        if not sheet_data:
            return "The AI assistant returned an empty response. Please try again."

        schema = sheet_data.get("schema", [])
        if schema:
            schema_str = ", ".join(schema)
            send_telegram_message(user_id, f"📐 **Spreadsheet Design:**\n\n**Columns:** {schema_str}\n\n*Populating data now...*")

        rows = sheet_data.get("rows", [])

        if not rows:
            return "I couldn't generate any data for this topic. Please try again."

        # 2. Create the Sheet
        send_telegram_message(user_id, "🔧 Creating Google Spreadsheet file...")
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

async def handle_data_extraction_skill(user_id: int, gmail_query: str, sheet_title: str) -> str:
    """
    Searches Gmail for a query, extracts structured data from matching emails, and saves it to a Google Sheet.
    """
    try:
        # 1. Fetch Emails
        send_telegram_message(user_id, f"🔍 **Searching Gmail:** I'm looking for emails matching '{gmail_query}'...")
        emails = search_gmail_full(str(user_id), query=gmail_query, max_results=10)
        if not emails:
            return f"No emails found matching your query: '{gmail_query}'"
            
        emails_text = ""
        for i, e in enumerate(emails):
            emails_text += f"[{i}] From: {e['sender']}\nSubject: {e['subject']}\nSnippet: {e['snippet']}\n\n"
            
        # 2. Extract Data via LLM
        send_telegram_message(user_id, f"🧠 **Extracting Data:** I found {len(emails)} emails. Extracting structured data now...")
        system_prompt = (
            "You are a data extraction specialist. Extract structured data from the provided emails. "
            "Identify recurring patterns (like dates, companies, amounts, or project names). "
            "Return a JSON object with a key 'rows', which is a list of lists. The first list must be headers. "
            "Each subsequent list should represent one email entry. "
            "Be precise and consistent with data types."
        )
        
        extraction_result = await get_llm_response(
            system_prompt=system_prompt,
            prompt=f"Extract data from these emails:\n\n{emails_text}",
            response_format={ "type": "json_object" }
        )
        
        if not extraction_result:
            return "The AI assistant returned an empty response during extraction. Please try again."

        rows = extraction_result.get("rows", [])
        
        if not rows or len(rows) < 2:
            return f"I found {len(emails)} emails, but couldn't extract enough structured data to build a spreadsheet."
            
        # 3. Create Sheet
        send_telegram_message(user_id, "🔧 Creating extraction spreadsheet...")
        final_title = sheet_title or f"Extracted Data: {gmail_query}"
        sheet_result = create_google_sheet(str(user_id), final_title)
        if "error" in sheet_result:
            return f"Failed to create extraction spreadsheet: {sheet_result['error']}"
            
        spreadsheet_id = sheet_result["id"]
        spreadsheet_link = sheet_result["link"]
        
        # 4. Populate
        success = update_sheet_values(str(user_id), spreadsheet_id, rows)
        if not success:
            return f"Spreadsheet created but data population failed. Link: {spreadsheet_link}"
            
        return f"✅ **Data Extraction Successful!**\n\nI processed {len(emails)} emails and structured the data into a new spreadsheet.\n\n**Sheet:** {final_title}\n**Link:** {spreadsheet_link}"

    except Exception as e:
        logger.error(f"Error in data extraction skill: {e}")
        return f"Sorry, I encountered an error extracting data to your spreadsheet: {e}"

async def handle_auto_report_skill(user_id: int, spreadsheet_id: str, report_topic: str) -> str:
    """
    Analyzes data from a Google Sheet and generates a professional summary report.
    """
    try:
        # 1. Fetch data
        send_telegram_message(user_id, f"📊 **Generating Report:** I'm reading your spreadsheet for analysis on '{report_topic}'...")
        values = get_sheet_values(str(user_id), spreadsheet_id)
        if not values:
            return "I couldn't find any data in that spreadsheet to analyze."
            
        # 2. Prepare data for LLM
        # Limiting to 30 rows to fit context nicely while being useful
        data_text = ""
        for row in values[:30]:
            data_text += " | ".join([str(cell) for cell in row]) + "\n"
            
        # 3. LLM Analysis
        system_prompt = (
            f"You are a professional business analyst. Analyze the following spreadsheet data and provide a concise summary report on '{report_topic}'.\n"
            "Guidelines:\n"
            "- Highlight key trends, anomalies, or summaries.\n"
            "- Provide 3 clear, actionable points.\n"
            "- Use professional Markdown formatting (bolding, lists).\n"
            "Keep the report concise and high-impact."
        )
        
        report = await get_llm_response(
            system_prompt=system_prompt,
            prompt=f"Spreadsheet Data:\n{data_text}"
        )
        return f"📊 **Automated Report: {report_topic}**\n\n{report}\n\n*Generated by analyzing your Google Sheet data.*"

    except Exception as e:
        logger.error(f"Error in auto report skill: {e}")
        return f"Sorry, I couldn't generate the automated report: {e}"
