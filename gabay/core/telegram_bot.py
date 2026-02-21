import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from gabay.core.config import settings
from gabay.core.memory import append_message, get_recent_history, get_user_state
from gabay.core.llm_router import classify_intent
from gabay.core.skills.reminders import handle_reminder_skill
from gabay.core.utils.voice import transcribe_audio
from gabay.worker.tasks import process_brief, process_save, process_search, process_read, process_calendar, process_share, process_file_qa, process_news

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_link = f"{settings.base_url}/admin?user_id={user_id}"
    await update.message.reply_text(
        "👋 **Hello! I am Gabay**, your productivity assistant.\n\n"
        f"🛠 **[Open Admin Dashboard]({admin_link})**\n"
        "Use the link above to connect Telegram, Gmail, and Notion in one place!"
    )

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This will return the local Web UI link for OAuth
    if not update.effective_message:
        return
    pairing_link = f"{settings.base_url}/auth/login?user_id={update.effective_user.id}"
    await update.effective_message.reply_text(f"Please pair your accounts by visiting: {pairing_link}")

async def save_contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message:
        return
    user_id = update.effective_user.id
    if not context.args or len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /savecontact [name] [chat_id]")
        return
    name = context.args[0]
    try:
        contact_id = int(context.args[1])
        from gabay.core.memory import save_contact
        save_contact(user_id, name, contact_id)
        await update.effective_message.reply_text(f"Saved contact '{name}' with ID {contact_id}!")
    except ValueError:
        await update.effective_message.reply_text("The chat_id must be a number.")

async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the interactive MTProto setup."""
    if not update.effective_message:
        return
    user_id = update.effective_user.id
    response = await handle_interactive_setup(user_id, "/setup")
    await update.effective_message.reply_text(response)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, overridden_text: str = None):
    text = overridden_text or (update.effective_message.text if update.effective_message else None)
    if not text:
        return
    user_id = update.effective_user.id
    logger.info(f"Received message: {text} from {user_id}")
    
    # 1. Save chat history
    append_message(user_id, "user", text)
    
    # 2. Intent classification routing with time context
    from datetime import datetime, timezone
    current_utc = datetime.now(timezone.utc).isoformat()
    # For local dev, system local time is user local time. 
    # In Docker, it might be UTC unless TZ is set.
    user_local_time = datetime.now().isoformat() 
    
    classification = await classify_intent(text, current_utc=current_utc, user_local_time=user_local_time)
    intent = classification.intent
    args = classification.command_args
    
    # 3. Handle routing / offload to worker
    if intent == "brief":
        response_text = "Fetching your daily briefing from Gmail and Meta..."
        process_brief.delay(user_id)
    elif intent == "search":
        response_text = f"Searching your Google Drive and Notion for '{args}'..."
        process_search.delay(user_id, args)
    elif intent == "read":
        source = args or "all"
        response_text = f"Reading from {source}..."
        process_read.delay(user_id, source=source)
    elif intent == "email":
        import json
        try:
            email_data = json.loads(args)
            recipient = email_data.get("recipient", "Unknown")
            response_text = f"Drafting an email to {recipient}..."
            from gabay.worker.tasks import process_email
            process_email.delay(user_id, args)
        except Exception:
            response_text = "I couldn't quite catch the recipient or message. Could you rephrase?"
    elif intent == "save":
        response_text = "Please reply directly to a file/document with the /save command to save it."
        # If they actually provided text right after save
        if args:
            process_save.delay(user_id, text_content=args)
    elif intent == "weather":
        from gabay.core.skills.weather import handle_weather_skill
        response_text = handle_weather_skill(args)
    elif intent == "message":
        from gabay.core.skills.message import handle_message_skill
        response_text = await handle_message_skill(user_id, args)
    elif intent == "calendar":
        response_text = "Checking your calendar..."
        process_calendar.delay(user_id, args)
    elif intent == "share":
        response_text = "Processing your share request..."
        process_share.delay(user_id, args)
    elif intent == "file_qa":
        import json
        try:
            qa_data = json.loads(args)
            file_name = qa_data.get("file_query", "the document")
        except:
            file_name = "the document"
        response_text = f"Reading '{file_name}' to answer your question..."
        process_file_qa.delay(user_id, args)
    elif intent == "news":
        topic = args if args else "world"
        response_text = f"Fetching latest news on {topic}..."
        process_news.delay(user_id, topic)
    elif intent == "reminder":
        response_text = handle_reminder_skill(str(user_id), args)
    else:
        from gabay.core.skills.chat import handle_chat_skill
        response_text = await handle_chat_skill(user_id, text)
    
    append_message(user_id, "assistant", response_text)
    await update.effective_message.reply_text(response_text)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming voice messages, transcribes them, and routes to handle_message."""
    if not update.effective_message or not update.effective_message.voice:
        return
        
    user_id = update.effective_user.id
    voice = update.effective_message.voice
    
    # 1. Notify user
    status_msg = await update.effective_message.reply_text("🎤 **Listening...** (Transcribing voice note)")
    
    try:
        # 2. Download voice message
        voice_file = await voice.get_file()
        voice_path = f"data/voice_{user_id}_{voice_file.file_id}.ogg"
        os.makedirs("data", exist_ok=True)
        await voice_file.download_to_drive(voice_path)
        
        # 3. Transcribe
        transcribed_text = transcribe_audio(voice_path)
        
        # Cleanup
        if os.path.exists(voice_path):
            os.remove(voice_path)
            
        if not transcribed_text:
            await status_msg.edit_text("❌ Sorry, I couldn't transcribe that voice note.")
            return

        # 4. Process as normal message
        await status_msg.edit_text(f"📝 **Transcribed:** \"{transcribed_text}\"")
        await handle_message(update, context, overridden_text=transcribed_text)
        
    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await status_msg.edit_text(f"❌ Error processing voice command: {e}")

def get_telegram_app():
    if not settings.telegram_bot_token or settings.telegram_bot_token in ("TBD", "your_telegram_bot_token_here"):
        print("\n" + "="*50)
        print("🤖 Telegram Bot Token is missing!")
        
        import sys
        if sys.stdin.isatty():
            print("Please grab one from @BotFather on Telegram.")
            token_input = input("Enter your Bot Token here: ").strip()
            
            if token_input:
                from gabay.core.config import save_to_env
                save_to_env("TELEGRAM_BOT_TOKEN", token_input)
                settings.telegram_bot_token = token_input
                print("Token saved to .env!")
            else:
                logger.warning("No token provided. Telegram Polling won't start.")
                return None
        else:
            logger.warning("Running in non-interactive mode. Please set TELEGRAM_BOT_TOKEN in your .env file.")
            return None

    application = ApplicationBuilder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("auth", auth_command))
    application.add_handler(CommandHandler("setup", setup_command))
    application.add_handler(CommandHandler("savecontact", save_contact_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    return application

async def start_telegram_polling(application):
    if not application:
        return
    try:
        logger.info("Starting Telegram Bot via start_polling()...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Telegram Bot is successfully polling for updates!")
    except Exception as e:
        logger.error(f"❌ Failed to start Telegram Bot: {e}")
        logger.warning("The Chat API is still running. You can fix your token at http://localhost:8000/setup/config")

async def stop_telegram_polling(application):
    if not application:
        return
    logger.info("Stopping Telegram Bot...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
