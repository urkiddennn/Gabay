from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from gabay.core.connectors.token_manager import token_manager
from gabay.core.config import settings
from google_auth_oauthlib.flow import Flow
import json
import base64

auth_router = APIRouter()
import logging
logger = logging.getLogger(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gabay | Account Pairing</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #3b82f6;
            --bg: #111115;
            --surface: #1A1A24;
            --border: rgba(255, 255, 255, 0.1);
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --google: #4285F4;
            --meta: #1877F2;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        body { background-color: var(--bg); color: var(--text-main); display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 40px; width: 100%; max-width: 450px; text-align: center; animation: fadeIn 0.4s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; text-transform: uppercase; letter-spacing: -0.025em; }
        p { color: var(--text-muted); font-size: 14px; margin-bottom: 32px; font-weight: 500; }
        .btn { display: inline-block; width: 100%; padding: 14px; margin: 10px 0; border-radius: 8px; text-decoration: none; color: white; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.025em; transition: opacity 0.2s ease; }
        .btn:hover { opacity: 0.9; }
        .btn-google { background: var(--google); }
        .btn-meta { background: var(--meta); }
    </style>
</head>
<body>
    <div class="card">
        <h1>Connect Your Accounts</h1>
        <p>Pair your accounts with Gabay to enable autonomous workflows.</p>
        <a href="/auth/google/login?user_id={user_id}" class="btn btn-google">Connect Google (Drive/Gmail)</a>
        <a href="/auth/meta/login?user_id={user_id}" class="btn btn-meta">Connect Meta (FB/IG)</a>
    </div>
</body>
</html>
"""

@auth_router.get("/login", response_class=HTMLResponse)
def login_view(user_id: str):
    """Temporary local Web UI for account pairing."""
    return HTML_TEMPLATE.replace("{user_id}", user_id)

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/spreadsheets"
]

@auth_router.get("/google/login")
def google_login(user_id: str, request: Request):
    if not settings.google_client_id or not settings.google_client_secret:
        return HTMLResponse("<html><body><h2>Error: Google Client ID or Secret not configured.</h2></body></html>")

    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [f"{settings.base_url}/auth/google/callback"]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=f"{settings.base_url}/auth/google/callback"
    )
    
    auth_url, _ = flow.authorization_url(
        prompt='consent', 
        access_type='offline', 
        include_granted_scopes='true'
    )
    
    # Stateless PKCE: Encode user_id and code_verifier into the state parameter
    state_data = {
        "user_id": user_id,
        "code_verifier": flow.code_verifier
    }
    state_b64 = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode().rstrip("=")
    
    # Re-inject state into the authorization URL
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    u = urlparse(auth_url)
    query = parse_qs(u.query)
    query['state'] = [state_b64]
    auth_url = urlunparse(u._replace(query=urlencode(query, doseq=True)))
    
    return RedirectResponse(auth_url)

@auth_router.get("/google/callback")
def google_callback(request: Request):
    code = request.query_params.get("code")
    # Stateless PKCE: Decode user_id and code_verifier from state
    state = request.query_params.get("state")
    user_id = request.query_params.get("user_id") or "local"
    code_verifier = None
    if state:
        try:
            # Add padding back if needed
            padding = 4 - (len(state) % 4)
            if padding < 4:
                state += "=" * padding
            state_data = json.loads(base64.urlsafe_b64decode(state).decode())
            user_id = state_data.get("user_id", user_id)
            code_verifier = state_data.get("code_verifier")
            logger.info(f"Decoded state for user_id: {user_id}")
        except Exception as e:
            logger.error(f"Failed to decode state: {e}")

    logger.info(f"Processing Google callback for user_id: {user_id}")
    
    if not code:
        return HTMLResponse("<html><body><h2>Error: Missing code in callback.</h2></body></html>")
        
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=f"{settings.base_url}/auth/google/callback"
    )
    
    # Set the code_verifier from state to satisfy PKCE
    if code_verifier:
        flow.code_verifier = code_verifier
    
    flow.fetch_token(code=code)
    creds = flow.credentials
    
    if not creds.refresh_token:
        logger.warning(f"No refresh token received for user {user_id}. Ensure you approved the offline access prompt.")
    else:
        logger.info(f"Successfully received refresh token for user {user_id}.")
        
    # creds.to_json() returns a string, we need a dict for token_manager
    token_data = json.loads(creds.to_json())
    token_manager.save_token("google", user_id, token_data)
    
    return HTMLResponse("<html><body><h2>Google Account Linked Successfully! You can close this window.</h2></body></html>")

@auth_router.get("/meta/login")
def meta_login(user_id: str):
    # Setup Meta OAuth Flow
    return RedirectResponse(f"/auth/meta/callback?user_id={user_id}&code=DUMMY_CODE_FOR_NOW")

@auth_router.get("/meta/callback")
def meta_callback(user_id: str, code: str):
    # Exchange code for token
    token_manager.save_token("meta", user_id, {"access_token": "mock_meta_access"})
    return HTMLResponse("<html><body><h2>Meta Account Linked Successfully! You can close this window.</h2></body></html>")
