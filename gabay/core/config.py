from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import pathlib

class Settings(BaseSettings):
    telegram_bot_token: str = "TBD"
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_phone: str = ""
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"
    data_dir: str = "/app/data" # in docker
    
    # LLM config
    groq_api_key: str = ""
    
    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    
    # Notion API
    notion_api_key: str = ""
    
    # OAuth Web UI config
    base_url: str = "http://localhost:8000"
    
    # SMTP Email config
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    
    # Notion config
    notion_database_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", arbitrary_types_allowed=True)

# For local development without Docker, use local data folder
if not os.path.exists("/app/data"):
    # Running locally
    import pathlib
    base_dir = pathlib.Path(__file__).parent.parent
    local_data_dir = base_dir / "data"
    local_data_dir.mkdir(exist_ok=True)
    os.environ["DATA_DIR"] = str(local_data_dir)

settings = Settings()

def save_to_env(key: str, value: str):
    """Utility to interactively save a new key to the .env file."""
    env_path = pathlib.Path(".env")
    if not env_path.exists():
        env_path.touch()
        
    # Read existing lines to avoid duplicates
    with open(env_path, "r") as f:
        lines = f.readlines()
        
    with open(env_path, "w") as f:
        key_found = False
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                key_found = True
            else:
                f.write(line)
        if not key_found:
            f.write(f"{key}={value}\n")
            
    # Update current runtime settings implicitly (or caller updates it)
    os.environ[key] = value
