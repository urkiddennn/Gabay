import click
import uvicorn
import asyncio
import os
import subprocess
import sys
from pathlib import Path

# Add the current directory to sys.path only if running from source
if (Path.cwd() / "gabay").exists() and (Path.cwd() / "gabay" / "__init__.py").exists():
    sys.path.insert(0, str(Path.cwd()))

@click.group()
def cli():
    """Gabay - Your self-hosted Telegram-first AI assistant."""
    pass

@cli.command()
@click.option('--port', default=8000, help='Port to run the API on.')
@click.option('--host', default='0.0.0.0', help='Host to bind the API to.')
def api(port, host):
    """Start the Gabay FastAPI Core Server (OAuth Web UI)."""
    click.echo(f"Starting Gabay API on {host}:{port}...")
    uvicorn.run("gabay.core.main:app", host=host, port=port, reload=False)

@cli.command()
def bot():
    """Start the Gabay Telegram Bot."""
    click.echo("Starting Gabay Telegram Bot...")
    from gabay.core.telegram_bot import get_telegram_app, start_telegram_polling
    app = get_telegram_app()
    if app:
        asyncio.run(start_telegram_polling(app))
        # start_telegram_polling runs the updater, which blocks until stopped
        # If it doesn't block (like Application.run_polling() does), we need to keep it alive
        # Actually in our code, we did updater.start_polling() which is async. We should probably use run_polling
        # Let's just call app.run_polling() directly
        app.run_polling()

@cli.command()
def worker():
    """Start the Gabay Celery Worker."""
    click.echo("Starting Gabay Celery Worker...")
    # Using subprocess to run celery
    subprocess.run(["celery", "-A", "gabay.worker.celery_app", "worker", "--loglevel=INFO", "-E"])

@cli.command()
def beat():
    """Start the Gabay Celery Beat Scheduler."""
    click.echo("Starting Gabay Celery Beat Scheduler...")
    subprocess.run(["celery", "-A", "gabay.worker.celery_app", "beat", "--loglevel=INFO"])

@cli.command()
def all():
    """Run API, Bot, and Worker concurrently."""
    click.echo("Starting all Gabay services...")
    
    # We use subprocess to launch the other commands
    processes = []
    
    # API
    processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "gabay.core.main:app", "--host", "0.0.0.0", "--port", "8000"]))
    
    # Worker
    processes.append(subprocess.Popen(["celery", "-A", "gabay.worker.celery_app", "worker", "--loglevel=INFO", "-E"]))
    
    # Beat
    processes.append(subprocess.Popen(["celery", "-A", "gabay.worker.celery_app", "beat", "--loglevel=INFO"]))
    
    # Bot
    # We can just run it in the main process, or as another subprocess
    processes.append(subprocess.Popen([sys.executable, "-c", "from gabay.core.telegram_bot import get_telegram_app; app=get_telegram_app(); app and app.run_polling()"]))
    
    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        click.echo("Stopping all services...")
        for p in processes:
            p.terminate()

def _check_token(token: str):
    """Verify Telegram Bot Token and return username."""
    import requests
    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("result", {}).get("username")
    except Exception:
        pass
    return None

@cli.command()
def config():
    """Setup Gabay via CLI or Web Wizard."""
    from gabay.core.config import save_to_env, settings
    import requests # Ensure it's available for _check_token
    
    click.clear()
    click.echo(click.style("╔══════════════════════════════════════════════╗", fg="cyan"))
    click.echo(click.style("║         Gabay Configuration Wizard           ║", fg="cyan", bold=True))
    click.echo(click.style("╚══════════════════════════════════════════════╝", fg="cyan"))
    
    # 1. Ensure Bot Token is set and valid
    bot_token = settings.telegram_bot_token
    if not bot_token or bot_token in ("TBD", "your_bot_token_here"):
        click.echo("\n🤖 Let's start with your Telegram Bot Token.")
        click.echo("Get this from @BotFather on Telegram.")
        bot_token = click.prompt("Enter Bot Token", hide_input=True)
    
    click.echo("🔍 Verifying token...")
    username = _check_token(bot_token)
    
    if username:
        click.echo(click.style(f"✅ Verified! Your bot is @{username}", fg="green"))
        save_to_env("TELEGRAM_BOT_TOKEN", bot_token)
    else:
        click.echo(click.style("❌ Invalid token. Please check your credentials.", fg="red"))
        if not click.confirm("Continue anyway?"):
            return

    # 2. Choose Mode
    click.echo("\nHow would you like to configure the rest of Gabay?")
    click.echo(click.style("1. Web UI (Recommended) ", fg="yellow") + "- Setup everything in a beautiful dashboard.")
    click.echo(click.style("2. CLI Terminal        ", fg="yellow") + "- Configure directly in this window.")
    
    mode_choice = click.prompt("Select option (1/2)", type=int, default=1)
    
    if mode_choice == 1:
        click.echo("\n🚀 Launching Setup Wizard at http://localhost:8000/setup/config")
        click.echo(click.style("Please keep this terminal open while you configure Gabay.", dim=True))
        
        # Auto-open browser
        import webbrowser
        webbrowser.open("http://localhost:8000/setup/config")
        
        import uvicorn
        uvicorn.run("gabay.core.main:app", host="0.0.0.0", port=8000, reload=False, log_level="error")
    else:
        click.echo("\n--- CLI Configuration Wizard ---")
        
        groq_api_key = click.prompt("Groq API Key", default=settings.groq_api_key, hide_input=True)
        if groq_api_key:
            save_to_env("GROQ_API_KEY", groq_api_key)
            
        google_client_id = click.prompt("Google OAuth Client ID", default=settings.google_client_id)
        if google_client_id:
            save_to_env("GOOGLE_CLIENT_ID", google_client_id)
            
        google_client_secret = click.prompt("Google OAuth Client Secret", default=settings.google_client_secret, hide_input=True)
        if google_client_secret:
            save_to_env("GOOGLE_CLIENT_SECRET", google_client_secret)
            
        click.echo("\n--- Mailbox Credentials (SMTP) ---")
        smtp_host = click.prompt("SMTP Host", default=settings.smtp_host or "smtp.gmail.com")
        save_to_env("SMTP_HOST", smtp_host)
        
        smtp_port = click.prompt("SMTP Port", default=settings.smtp_port, type=int)
        save_to_env("SMTP_PORT", str(smtp_port))
        
        smtp_user = click.prompt("SMTP User", default=settings.smtp_user)
        if smtp_user:
            save_to_env("SMTP_USER", smtp_user)
            
        smtp_pass = click.prompt("SMTP Password", default=settings.smtp_password, hide_input=True)
        if smtp_pass:
            save_to_env("SMTP_PASSWORD", smtp_pass)

        click.echo("\n--- Region ---")
        tz = click.prompt("Timezone", default=settings.tz)
        save_to_env("TZ", tz)
            
        click.echo(click.style("\n✅ Configuration complete! Run 'gabay all' to start your assistant.", fg="green"))

if __name__ == '__main__':
    cli()
