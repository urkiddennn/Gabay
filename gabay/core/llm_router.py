import logging
from gabay.core.config import settings
from groq import AsyncGroq
import google.generativeai as genai
from pydantic import BaseModel
import json

logger = logging.getLogger(__name__)

# Fallback if GROQ_API_KEY is missing
class IntentResult(BaseModel):
    intent: str
    command_args: str = ""

async def classify_intent(message: str, chat_history: list = None, current_utc: str = None, user_local_time: str = None) -> IntentResult:
    """
    Classify user message intent: 'brief', 'save', 'search', or 'chat'.
    Uses local lightweight matching if no LLM is configured, or an LLM for complex queries.
    """
    # Basic regex matching for local testing
    msg_lower = message.lower().strip()
    
    if msg_lower.startswith("/brief") or "summarize my emails" in msg_lower:
        return IntentResult(intent="brief", command_args="")

    if msg_lower.startswith("/read") or "read my" in msg_lower:
        source = "all"
        if "email" in msg_lower or "gmail" in msg_lower:
            source = "gmail"
        elif "notion" in msg_lower:
            source = "notion"
        return IntentResult(intent="read", command_args=source)
    
    if msg_lower.startswith("/search "):
        keyword = message[8:].strip()
        return IntentResult(intent="search", command_args=keyword)
        
    if msg_lower.startswith("/save"):
        return IntentResult(intent="save", command_args="")
    
    if not settings.groq_api_key or settings.groq_api_key == "your_groq_api_key_here":
        print("\n" + "="*50)
        print("🧠 Groq API Key is missing!")
        print("Gabay uses Groq (Llama 3) for its smart intent routing.")
        
        import sys
        if sys.stdin.isatty():
            print("Get a free API key at: https://console.groq.com/keys")
            token_input = input("Enter your Groq API Key here (or press enter to skip and use basic regex matching): ").strip()
            
            if token_input:
                from gabay.core.config import save_to_env
                save_to_env("GROQ_API_KEY", token_input)
                settings.groq_api_key = token_input
                print("Groq API Key saved!\n")
            else:
                return IntentResult(intent="chat", command_args=message)
        else:
            logger.warning("Running in non-interactive mode. Please set GROQ_API_KEY in your .env file.")
            return IntentResult(intent="chat", command_args=message)
    try:
        time_context = ""
        if current_utc and user_local_time:
            time_context = f"\n[TIME CONTEXT] Current UTC time: {current_utc}. User's local time: {user_local_time}.\n"
        
        history_context = ""
        if chat_history:
            history_context = "\n[CONVERSATION HISTORY]\n"
            for h in chat_history:
                role = h.get("role", "user")
                content = h.get("content", "")
                history_context += f"{role.upper()}: {content}\n"
            
        system_prompt = (
            "You are an intent classifier for Gabay, a productivity assistant. "
            f"{time_context}"
            f"{history_context}"
            "Determine the intent of the user's message based on the message and the conversation history. "
            "Allowed intents: 'brief' (daily briefing of emails/notifications), "
            "'read' (reading content from a specific source like 'gmail' or 'notion'), "
            "'save' (saving a file to notions/drive), "
            "'search' (semantic search with keyword expansion), "
            "'email' (sending, triaging, or smart-drafting replies), "
            "'weather' (checking current weather or forecast), "
            "'message' (sending a Telegram message to a contact), "
            "'calendar' (managing, checking schedule, or meeting briefings), "
            "'share' (sharing a Google Drive file via link or with a contact), "
            "'file_qa' (answering questions about or summarizing a specific document/file), "
            "'news' (getting top news headlines, stories, or stock market updates), "
            "'reminder' (setting a one-time reminder or a recurring scheduled message), "
            "'docs' (creating, editing, researching, or templating documents), "
            "'slides' (creating professional presentations), "
            "'sheets' (creating, extracting from Gmail, automated reporting, or visualizing charts), "
            "'pdf' (merging multiple PDFs, digitally signing/stamping a document, or OCR on images/PDFs), "
            "'contacts' (searching for people, finding email addresses, or syncing contact info) "
            "or 'chat' (general conversation). "
            "Return ONLY a JSON formatted object with keys 'intent' and 'command_args'. "
            "If the intent is 'search', command_args should be the search keyword. "
            "If the intent is 'pdf', command_args MUST be a JSON object containing "
            "'action' ('merge', 'sign', or 'ocr'). "
            "For 'merge', include 'file_queries' (list of names) and optionally 'output_name'. "
            "For 'sign', include 'file_query' and 'signature_text'. "
            "For 'ocr', include 'file_query'. "
            "If the intent is 'contacts', command_args should be the name or search query. "
            "If the intent is 'email', command_args MUST be another JSON object containing "
            "'action' ('send', 'triage', or 'smart_draft'). "
            "For 'send', include 'recipient' and 'content', plus optionally 'file_query' or 'notion_query'. "
            "For 'triage', no extra args. For 'smart_draft', include 'thread_id' and 'prompt' (instructions). "
            "If the intent is 'weather', command_args should be the location name (city/country) or 'current' if not specified. "
            "If the intent is 'message', command_args MUST be another JSON object containing "
            "'contact_name' (the name of the person) and 'message_text' (the message to send). "
            "If the intent is 'read', command_args should be the source name: 'gmail', 'notion', or 'all'. "
            "If the intent is 'share', command_args MUST be a JSON object containing "
            "'file_query' (name or keyword of file) and optionally 'contact_name' (who to share with). "
            "If the intent is 'calendar', command_args MUST be a JSON object containing "
            "'action' ('read', 'create', or 'briefing'). "
            "For 'read' action, optionally include 'time_min' and 'time_max'. "
            "For 'create' action, include 'summary', 'start_time' and 'end_time', and optionally 'attendees'. "
            "If the intent is 'docs', command_args MUST be a JSON object containing "
            "'action' ('create', 'edit', 'research', or 'template'). "
            "For 'create', include 'title' and 'content'. "
            "For 'edit', include 'file_query' and 'content'. "
            "For 'research', include 'topic' and 'title'. "
            "For 'template', include 'template_type' (e.g. 'Meeting Minutes', 'Project Proposal') and 'content' (the notes to organize). "
            "Any 'docs' action can include 'share_mode', 'invite_email', and 'role'. "
            "If the intent is 'file_qa', command_args MUST be a JSON object containing "
            "'file_query' and 'question'. "
            "If the intent is 'news', command_args should be a STRING representing the topic or region. "
            "If the intent is 'reminder', command_args MUST be a JSON object containing "
            "'action' ('create', 'list', or 'delete'), 'message', 'trigger_time', 'frequency', and optional parameters. "
            "If the intent is 'slides', command_args MUST be a JSON object containing 'topic' and other optional attributes. "
            "If the intent is 'sheets', command_args MUST be a JSON object containing "
            "'action' ('create', 'extract', or 'report'). "
            "For 'extract', include 'gmail_query' (e.g., 'from:Stripe invoices') and 'title' (for the sheet). "
            "For 'report', include 'spreadsheet_id' and 'topic' (what to analyze). "
            "For all other intents, command_args can be a simple string."
        )

        if settings.llm_provider == "gemini":
            return await _classify_with_gemini(message, system_prompt)
        else:
            return await _classify_with_groq(message, system_prompt)
            
    except Exception as e:
        logger.error(f"Error calling LLM for classification: {e}")
        return IntentResult(intent="chat", command_args=message)

async def _classify_with_groq(message: str, system_prompt: str) -> IntentResult:
    """Classification logic using Groq."""
    client = AsyncGroq(api_key=settings.groq_api_key)
    response = await client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        response_format={ "type": "json_object" }
    )
    
    result_str = response.choices[0].message.content
    return _parse_intent_json(result_str)

async def _classify_with_gemini(message: str, system_prompt: str) -> IntentResult:
    """Classification logic using Google Gemini."""
    if not settings.gemini_api_key:
        logger.warning("Gemini API Key is missing. Falling back to chat.")
        return IntentResult(intent="chat", command_args=message)
        
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name="gemini-3-flash-preview",
        generation_config={"response_mime_type": "application/json"}
    )
    
    # Gemini combine system prompt and user message or uses a separate system instruction
    # Using system_instruction parameter if available or just prepending
    model = genai.GenerativeModel(
        model_name="gemini-3-flash-preview",
        system_instruction=system_prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    # Gemini generativeai library is synchronous by default but has async methods
    response = await model.generate_content_async(message)
    
    result_str = response.text
    return _parse_intent_json(result_str)

def _parse_intent_json(result_str: str) -> IntentResult:
    """Utility to parse JSON response from LLM into IntentResult."""
    try:
        res_data = json.loads(result_str)
        
        # Serialize nested dicts for IntentResult compatibility
        args_val = res_data.get("command_args")
        if args_val is None:
            args_val = ""
        elif isinstance(args_val, dict):
            args_val = json.dumps(args_val)
            
        return IntentResult(
            intent=res_data.get("intent") or "chat", 
            command_args=str(args_val)
        )
    except Exception as e:
        logger.error(f"Failed to parse LLM JSON response: {e}. Raw: {result_str}")
        return IntentResult(intent="chat", command_args="")
