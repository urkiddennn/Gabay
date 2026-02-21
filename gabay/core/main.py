from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
from gabay.core.config import settings

# Setting up logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Gabay Core FastAPI server...")
    from gabay.core.telegram_bot import get_telegram_app, start_telegram_polling, stop_telegram_polling
    
    # Initialize the Telegram Bot application
    telegram_app = get_telegram_app()
    app.state.telegram_app = telegram_app
    
    if telegram_app:
        # Start the bot explicitly
        await start_telegram_polling(telegram_app)
        
    yield
    
    # Shutdown gracefully
    if telegram_app:
        await stop_telegram_polling(telegram_app)

app = FastAPI(title="Gabay Core API", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "Gabay Web Interface for OAuth is running."}

# Additional routers for OAuth local callbacks
from gabay.core.connectors.oauth import auth_router
from gabay.core.utils.setup_routes import router as setup_router
from gabay.core.utils.admin_routes import router as admin_router
app.include_router(auth_router, prefix="/auth")
app.include_router(setup_router)
app.include_router(admin_router)
