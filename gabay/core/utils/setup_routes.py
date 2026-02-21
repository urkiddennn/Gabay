import logging
import os
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from gabay.core.config import settings, save_to_env
from gabay.core.utils.userbot import get_userbot_client
from gabay.core.connectors.token_manager import token_manager
from telethon import TelegramClient
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

# Setup templates
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Temporary storage for setup sessions (in-memory)
# In production, you might want to use Redis, but for local use this is fine.
setup_sessions = {}

@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, user_id: int = 0):
    return templates.TemplateResponse("setup.html", {"request": request, "user_id": user_id})

@router.get("/setup/config", response_class=HTMLResponse)
async def config_setup_page(request: Request, user_id: int = 0):
    return templates.TemplateResponse("config_setup.html", {
        "request": request, 
        "user_id": user_id,
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "groq_key": os.getenv("GROQ_API_KEY", ""),
        "google_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "google_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": os.getenv("SMTP_PORT", "587"),
        "smtp_user": os.getenv("SMTP_USER", ""),
        "tz": os.getenv("TZ", "Asia/Manila")
    })

@router.post("/setup/config")
async def handle_config_setup(
    request: Request,
    user_id: int = Form(0),
    bot_token: str = Form(None),
    groq_key: str = Form(None),
    google_id: str = Form(None),
    google_secret: str = Form(None),
    smtp_host: str = Form(None),
    smtp_port: str = Form(None),
    smtp_user: str = Form(None),
    smtp_pass: str = Form(None),
    tz: str = Form(None)
):
    if bot_token: save_to_env("TELEGRAM_BOT_TOKEN", bot_token)
    if groq_key: save_to_env("GROQ_API_KEY", groq_key)
    if google_id: save_to_env("GOOGLE_CLIENT_ID", google_id)
    if google_secret: save_to_env("GOOGLE_CLIENT_SECRET", google_secret)
    if smtp_host: save_to_env("SMTP_HOST", smtp_host)
    if smtp_port: save_to_env("SMTP_PORT", smtp_port)
    if smtp_user: save_to_env("SMTP_USER", smtp_user)
    if smtp_pass: save_to_env("SMTP_PASSWORD", smtp_pass)
    if tz: save_to_env("TZ", tz)
    
    return HTMLResponse(content=f"""
        <div style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: white; min-height: 100vh;">
            <h1 style="color: #4ade80;">✅ Configuration Saved!</h1>
            <p>Your settings have been updated. Please restart the backend services for changes to take effect.</p>
            <br>
            <a href="/admin?user_id={user_id}" style="color: #6366f1; text-decoration: none; font-weight: bold;">Go to Dashboard</a>
        </div>
    """)

@router.post("/setup/credentials")
async def handle_credentials(
    request: Request,
    user_id: int = Form(...),
    api_id: int = Form(...),
    api_hash: str = Form(...),
    phone: str = Form(...)
):
    # Save to .env and settings
    save_to_env("TELEGRAM_API_ID", str(api_id))
    save_to_env("TELEGRAM_API_HASH", api_hash)
    save_to_env("TELEGRAM_PHONE", phone)
    
    settings.telegram_api_id = api_id
    settings.telegram_api_hash = api_hash
    settings.telegram_phone = phone
    
    # Initialize client and request code
    client = await get_userbot_client()
    if not client:
        raise HTTPException(status_code=500, detail="Failed to initialize Telegram client")
    
    try:
        await client.connect()
        sent_code = await client.send_code_request(phone)
        
        # Store session data
        setup_sessions[user_id] = {
            "phone_code_hash": sent_code.phone_code_hash,
            "phone": phone
        }
        
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "user_id": user_id,
            "phone": phone
        })
    except Exception as e:
        logger.error(f"Error during credentials step: {e}")
        return HTMLResponse(content=f"Error: {e}. <a href='/setup?user_id={user_id}'>Try again</a>", status_code=400)
    finally:
        await client.disconnect()

@router.post("/setup/verify")
async def handle_verify(
    request: Request,
    user_id: int = Form(...),
    phone: str = Form(...),
    code: str = Form(...)
):
    session = setup_sessions.get(user_id)
    if not session:
        return RedirectResponse(url=f"/setup?user_id={user_id}")

    client = await get_userbot_client()
    try:
        await client.connect()
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=session.get("phone_code_hash")
        )
        
        # Cleanup
        del setup_sessions[user_id]
        
        return HTMLResponse(content="""
            <div style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: white; min-height: 100vh;">
                <h1 style="color: #4ade80;">✅ Setup Successful!</h1>
                <p>Gabay is now authorized. You can close this tab and go back to Telegram.</p>
            </div>
        """)
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        return HTMLResponse(content=f"Error: {e}. <a href='/setup?user_id={user_id}'>Try again</a>", status_code=400)
    finally:
        await client.disconnect()

@router.get("/setup/smtp", response_class=HTMLResponse)
async def smtp_setup_page(request: Request, user_id: str):
    return templates.TemplateResponse("smtp_setup.html", {
        "request": request,
        "user_id": user_id,
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_user": settings.smtp_user,
        "smtp_password": settings.smtp_password
    })

@router.post("/setup/smtp")
async def handle_smtp_setup(
    request: Request,
    user_id: str = Form(...),
    smtp_host: str = Form(...),
    smtp_port: int = Form(...),
    smtp_user: str = Form(...),
    smtp_password: str = Form(...)
):
    try:
        # Save to token_manager for shared access across containers
        token_manager.save_token("smtp", str(user_id), {
            "host": smtp_host,
            "port": smtp_port,
            "user": smtp_user,
            "password": smtp_password
        })
        
        # Still save to .env for legacy/local backup (optional)
        save_to_env("SMTP_HOST", smtp_host)
        save_to_env("SMTP_PORT", str(smtp_port))
        save_to_env("SMTP_USER", smtp_user)
        save_to_env("SMTP_PASSWORD", smtp_password)
        
        settings.smtp_host = smtp_host
        settings.smtp_port = smtp_port
        settings.smtp_user = smtp_user
        settings.smtp_password = smtp_password
        
        return HTMLResponse(content=f"""
            <div style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: white; min-height: 100vh;">
                <h1 style="color: #4ade80;">✅ SMTP Saved!</h1>
                <p>Gmail SMTP is now configured. You can close this tab.</p>
                <br>
                <a href="/admin?user_id={user_id}" style="color: #6366f1; text-decoration: none;">Back to Dashboard</a>
            </div>
        """)
    except Exception as e:
        logger.error(f"SMTP save error: {e}")
        return HTMLResponse(content=f"Error saving SMTP: {e}. <a href='/setup/smtp?user_id={user_id}'>Try again</a>", status_code=400)

@router.get("/setup/notion", response_class=HTMLResponse)
async def notion_setup_page(request: Request, user_id: str):
    return templates.TemplateResponse("notion_setup.html", {
        "request": request,
        "user_id": user_id,
        "notion_api_key": os.getenv("NOTION_API_KEY"),
        "notion_database_id": os.getenv("NOTION_DATABASE_ID") or getattr(settings, "notion_database_id", None)
    })

@router.post("/setup/notion")
async def handle_notion_setup(
    request: Request,
    user_id: str = Form(...),
    notion_api_key: str = Form(...),
    notion_database_id: str = Form(...)
):
    try:
        # Save to token_manager for shared access across containers
        token_manager.save_token("notion", str(user_id), {
            "api_key": notion_api_key,
            "database_id": notion_database_id
        })
        
        # Still save to .env for local backup
        save_to_env("NOTION_API_KEY", notion_api_key)
        save_to_env("NOTION_DATABASE_ID", notion_database_id)
        
        settings.notion_database_id = notion_database_id
        
        return HTMLResponse(content=f"""
            <div style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: white; min-height: 100vh;">
                <h1 style="color: #4ade80;">✅ Notion Connected!</h1>
                <p>Gabay can now search and add tasks to your Notion workspace. Don't forget to Invite your integration to your database page!</p>
                <br>
                <a href="/admin?user_id={user_id}" style="color: #6366f1; text-decoration: none;">Back to Dashboard</a>
            </div>
        """)
    except Exception as e:
        logger.error(f"Notion save error: {e}")
        return HTMLResponse(content=f"Error saving Notion key: {e}. <a href='/setup/notion?user_id={user_id}'>Try again</a>", status_code=400)

@router.get("/setup/groq", response_class=HTMLResponse)
async def groq_setup_page(request: Request, user_id: str):
    return templates.TemplateResponse("groq_setup.html", {
        "request": request,
        "user_id": user_id,
        "groq_api_key": os.getenv("GROQ_API_KEY", "")
    })

@router.post("/setup/groq")
async def handle_groq_setup(
    request: Request,
    user_id: str = Form(...),
    groq_api_key: str = Form(...)
):
    save_to_env("GROQ_API_KEY", groq_api_key)
    settings.groq_api_key = groq_api_key
    return RedirectResponse(url=f"/admin?user_id={user_id}", status_code=303)

@router.get("/setup/google_oauth", response_class=HTMLResponse)
async def google_oauth_setup_page(request: Request, user_id: str):
    return templates.TemplateResponse("google_oauth_setup.html", {
        "request": request,
        "user_id": user_id,
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "google_client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "")
    })

@router.post("/setup/google_oauth")
async def handle_google_oauth_setup(
    request: Request,
    user_id: str = Form(...),
    google_client_id: str = Form(...),
    google_client_secret: str = Form(...)
):
    save_to_env("GOOGLE_CLIENT_ID", google_client_id)
    save_to_env("GOOGLE_CLIENT_SECRET", google_client_secret)
    settings.google_client_id = google_client_id
    settings.google_client_secret = google_client_secret
    return RedirectResponse(url=f"/admin?user_id={user_id}", status_code=303)

@router.get("/setup/timezone", response_class=HTMLResponse)
async def timezone_setup_page(request: Request, user_id: str):
    return templates.TemplateResponse("timezone_setup.html", {
        "request": request,
        "user_id": user_id,
        "tz": os.getenv("TZ", "Asia/Manila")
    })

@router.post("/setup/timezone")
async def handle_timezone_setup(
    request: Request,
    user_id: str = Form(...),
    tz: str = Form(...)
):
    save_to_env("TZ", tz)
    return RedirectResponse(url=f"/admin?user_id={user_id}", status_code=303)
