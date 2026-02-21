import logging
from gabay.core.config import settings
from groq import AsyncGroq
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Fallback basic intent classification if OPENAI_API_KEY is not set yet
class IntentResult(BaseModel):
    intent: str
    command_args: str = ""

async def classify_intent(message: str, current_utc: str = None, user_local_time: str = None) -> IntentResult:
    """
    Classify user message intent: 'brief', 'save', 'search', or 'chat'.
    Uses local lightweight matching if no LLM is configured, or an LLM for complex queries.
    """
    # Simple hardcoded fallback matching (for local development/testing without API key)
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
        # LLM-based Intent Classification Strategy
        client = AsyncGroq(api_key=settings.groq_api_key)
        
        time_context = ""
        if current_utc and user_local_time:
            time_context = f"\n[TIME CONTEXT] Current UTC time: {current_utc}. User's local time: {user_local_time}.\n"
            
        system_prompt = (
            "You are an intent classifier for Gabay, a productivity assistant. "
            f"{time_context}"
            "Determine the intent of the user's message. "
            "Allowed intents: 'brief' (daily briefing of emails/notifications), "
            "'read' (reading content from a specific source like 'gmail' or 'notion'), "
            "'save' (saving a file to notions/drive), "
            "'search' (searching for a keyword), "
            "'email' (sending an email to someone), "
            "'weather' (checking current weather or forecast), "
            "'message' (sending a Telegram message to a contact), "
            "'calendar' (managing or checking schedule/events), "
            "'share' (sharing a Google Drive file via link or with a contact), "
            "'file_qa' (answering questions about or summarizing a specific document/file), "
            "'news' (getting top news headlines, stories, or stock market updates), "
            "'reminder' (setting a one-time reminder or a recurring scheduled message), "
            "or 'chat' (general conversation). "
            "Return ONLY a JSON formatted object with keys 'intent' and 'command_args'. "
            "If the intent is 'search', command_args should be the search keyword. "
            "If the intent is 'email', command_args MUST be another JSON object containing "
            "'recipient' (the email address or name) and 'content' (the message to send). "
            "If the intent is 'weather', command_args should be the location name (city/country) or 'current' if not specified. "
            "If the intent is 'message', command_args MUST be another JSON object containing "
            "'contact_name' (the name of the person) and 'message_text' (the message to send). "
            "If the intent is 'read', command_args should be the source name: 'gmail', 'notion', or 'all'. "
            "If the intent is 'share', command_args MUST be a JSON object containing "
            "'file_query' (name or keyword of file) and optionally 'contact_name' (who to share with). "
            "If the intent is 'calendar', command_args MUST be a JSON object containing "
            "'action' ('read' or 'create'). "
            "For 'read' action, optionally include 'time_min' and 'time_max' (in ISO 8601 format, e.g., 2026-02-01T00:00:00Z) to specify a date range. If the user asks for 'this month', calculate the start and end of the current month. "
            "For 'create' action, include 'summary', 'start_time' and 'end_time' (ISO format). "
            "If the intent is 'file_qa', command_args MUST be a JSON object containing "
            "'file_query' (name or keyword of the file) and 'question' (the specific question to answer or 'Please summarize this document.' if just asking for a summary). "
            "If the intent is 'news', command_args should be a simple STRING representing the topic or region (e.g., 'tech', 'philippines', 'stocks'). If not specified, default to 'world'. "
            "If the intent is 'reminder', command_args MUST be a JSON object containing "
            "'action' ('create', 'list', or 'delete'), 'message' (the text to remind or send. REPHRASE this from the user's perspective into the assistant's perspective - e.g., if the user says 'remind me that I have a meeting', the message should be 'You have a meeting'), "
            "'trigger_time' (A UTC ISO 8601 TIMESTAMP, e.g., '2026-02-21T09:00:00Z'. Use the [TIME CONTEXT] to calculate this relative to the user's intent), "
            "'frequency' ('once', 'daily', or 'weekly'), and optionally 'recipient' (contact name if sending to someone else). "
            "For all other intents, command_args can be a simple string."
        )
        
        response = await client.chat.completions.create(
            model="groq/compound-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            response_format={ "type": "json_object" }
        )
        
        result_str = response.choices[0].message.content
        import json
        res_data = json.loads(result_str)
        
        # `command_args` might be a nested dict for emails, or a string for other intents.
        # We'll pass it exactly as the model gave it or cast to string if needed by caller.
        args_val = res_data.get("command_args")
        if args_val is None:
            args_val = ""
        elif isinstance(args_val, dict):
            # Keep it as a json string so we don't break the IntentResult type signature yet
            args_val = json.dumps(args_val)
            
        return IntentResult(
            intent=res_data.get("intent") or "chat", 
            command_args=str(args_val)
        )
    except Exception as e:
        logger.error(f"Error calling LLM for classification: {e}")
        return IntentResult(intent="chat", command_args=message)
