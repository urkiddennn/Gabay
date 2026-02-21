import asyncio
from gabay.worker.celery_app import celery_app
from gabay.core.skills.brief import generate_brief
from gabay.core.skills.save import save_file_or_text
from gabay.core.skills.search import execute_search
from gabay.core.memory import append_message

# We need a synchronous wrapper for async functions since Celery tasks are typically synchronous
def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@celery_app.task(name="worker.tasks.process_brief")
def process_brief(user_id: int):
    # Generate the brief
    try:
        result = run_async(generate_brief(str(user_id)))
    except RuntimeError:
        # In case the event loop is already running or missing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(generate_brief(str(user_id)))
        
    # We would ideally send this back to Telegram via the Bot API
    # For now, we save it to memory so the core can serve it or the bot can send it
    append_message(user_id, "assistant", result)
    
    # Send message to user
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_save")
def process_save(user_id: int, file_path: str = None, text_content: str = None):
    result = save_file_or_text(str(user_id), file_path, text_content)
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_search")
def process_search(user_id: int, query: str):
    result = execute_search(str(user_id), query)
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_email")
def process_email(user_id: int, email_data_str: str):
    from gabay.core.skills.email import send_email_skill
    result = send_email_skill(str(user_id), email_data_str)
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_read")
def process_read(user_id: int, source: str = "all"):
    from gabay.core.skills.read import handle_read_skill
    try:
        result = run_async(handle_read_skill(str(user_id), source))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(handle_read_skill(str(user_id), source))
        
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_calendar")
def process_calendar(user_id: int, command_args: str):
    from gabay.core.skills.calendar import handle_calendar_skill
    result = handle_calendar_skill(user_id, command_args)
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_share")
def process_share(user_id: int, command_args: str):
    from gabay.core.skills.share import handle_share_skill
    try:
        result = run_async(handle_share_skill(user_id, command_args))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(handle_share_skill(user_id, command_args))
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_file_qa")
def process_file_qa(user_id: int, command_args: str):
    from gabay.core.skills.document_qa import handle_document_qa_skill
    try:
        result = run_async(handle_document_qa_skill(user_id, command_args))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(handle_document_qa_skill(user_id, command_args))
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_news")
def process_news(user_id: int, topic: str):
    from gabay.core.skills.news import handle_news_skill
    try:
        result = run_async(handle_news_skill(topic))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(handle_news_skill(topic))
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.check_reminders")
def check_reminders():
    from gabay.core.skills.reminders import load_reminders, save_reminders
    from datetime import datetime, timedelta, timezone
    import logging
    
    logger = logging.getLogger("gabay.worker.tasks")
    reminders = load_reminders()
    now = datetime.now(timezone.utc)
    updated = False
    
    for r in reminders:
        if r["status"] == "pending":
            trigger_dt = datetime.fromisoformat(r["trigger_time"])
            # Ensure trigger_dt is aware (in case it was stored without TZ info)
            if trigger_dt.tzinfo is None:
                trigger_dt = trigger_dt.replace(tzinfo=timezone.utc)
                
            if now >= trigger_dt:
                logger.info(f"Triggering reminder: {r['id']} - {r['message']}")
                execute_reminder.delay(r["id"])
                
                # Update status immediately to prevent double firing
                if r["frequency"] == "daily":
                    r["trigger_time"] = (trigger_dt + timedelta(days=1)).isoformat()
                elif r["frequency"] == "weekly":
                    r["trigger_time"] = (trigger_dt + timedelta(weeks=1)).isoformat()
                else:
                    r["status"] = "completed"
                updated = True
                
    if updated:
        save_reminders(reminders)

@celery_app.task(name="worker.tasks.execute_reminder")
def execute_reminder(reminder_id: str):
    from gabay.core.skills.reminders import load_reminders
    from gabay.core.memory import get_contacts
    from gabay.core.utils.telegram import send_telegram_message
    
    reminders = load_reminders()
    reminder = next((r for r in reminders if r["id"] == reminder_id), None)
    
    if not reminder:
        return
        
    user_id = int(reminder["user_id"])
    message = reminder["message"]
    recipient_name = reminder.get("recipient")
    
    target_chat_id = user_id # Default to self
    
    if recipient_name:
        contacts = get_contacts(user_id)
        target_chat_id = contacts.get(recipient_name.lower(), user_id)
        
    prefix = "🔔 **Reminder:** " if target_chat_id == user_id else ""
    send_telegram_message(target_chat_id, f"{prefix}{message}")

from gabay.core.utils.telegram import send_telegram_message
