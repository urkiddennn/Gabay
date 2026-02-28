import logging
import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from gabay.core.config import settings
from gabay.core.connectors.token_manager import token_manager
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

# Setup templates
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    # Check Telegram Status
    # Session file path in data directory
    session_path = Path(settings.data_dir) / "gabay_userbot.session"
    telegram_connected = session_path.exists()
    
    # Check Google Status (Gmail and Drive both use the same token for now)
    user_id = request.query_params.get("user_id", "local")
    google_token = token_manager.get_token("google", str(user_id))
    google_connected = google_token is not None
    
    # Check Notion Status (from Token Manager)
    notion_config = token_manager.get_token("notion", user_id) or {}
    notion_key = notion_config.get("api_key") or os.getenv("NOTION_API_KEY")
    notion_db = notion_config.get("database_id") or os.getenv("NOTION_DATABASE_ID")
    notion_connected = bool(notion_key and notion_db)

    # Check SMTP Status (from Token Manager)
    smtp_config = token_manager.get_token("smtp", user_id) or {}
    smtp_connected = bool(smtp_config.get("host") or (settings.smtp_host and settings.smtp_user and settings.smtp_password))

    # Check LLM Status
    groq_connected = bool(settings.groq_api_key or os.getenv("GROQ_API_KEY"))
    gemini_connected = bool(settings.gemini_api_key or os.getenv("GEMINI_API_KEY"))
    llm_provider = settings.llm_provider

    # Check Google OAuth App Status
    oauth_config_connected = bool(settings.google_client_id and settings.google_client_secret)

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "telegram_connected": telegram_connected,
        "gmail_connected": google_connected,
        "drive_connected": google_connected,
        "notion_connected": notion_connected,
        "smtp_connected": smtp_connected,
        "groq_connected": groq_connected,
        "gemini_connected": gemini_connected,
        "llm_provider": llm_provider,
        "oauth_config_connected": oauth_config_connected,
        "user_id": user_id
    })
