import asyncio
from gabay.worker.celery_app import celery_app
from gabay.core.skills.brief import generate_brief
from gabay.core.skills.save import save_file_or_text
from gabay.core.skills.search import execute_search
from gabay.core.memory import append_message

# We need a synchronous wrapper for async functions since Celery tasks are typically synchronous
def run_async(coro):
    """
    Synchronous wrapper for async functions with better event loop management.
    """
    try:
        return asyncio.get_event_loop().run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

@celery_app.task(name="worker.tasks.process_brief")
def process_brief(user_id: int):
    # Generate the brief
    result = run_async(generate_brief(str(user_id)))
        
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
    result = run_async(execute_search(str(user_id), query))
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_email")
def process_email(user_id: int, email_data_str: str):
    from gabay.core.skills.email import send_email_skill, handle_triage_skill, handle_smart_draft_skill
    import json
    
    try:
        data = json.loads(email_data_str)
        action = data.get("action", "send")
        
        if action == "triage":
            result = run_async(handle_triage_skill(str(user_id)))
        elif action == "smart_draft":
            thread_id = data.get("thread_id")
            prompt = data.get("prompt")
            result = run_async(handle_smart_draft_skill(str(user_id), thread_id, prompt))
        else:
            result = send_email_skill(str(user_id), email_data_str)
    except Exception as e:
        result = f"I failed to process that email request: {e}"
        
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_read")
def process_read(user_id: int, source: str = "all"):
    from gabay.core.skills.read import handle_read_skill
    result = run_async(handle_read_skill(str(user_id), source))
        
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_calendar")
def process_calendar(user_id: int, command_args: str):
    from gabay.core.skills.calendar import handle_calendar_skill, handle_calendar_briefing
    import json
    try:
        data = json.loads(command_args)
        action = data.get("action")
        if action == "briefing":
            result = run_async(handle_calendar_briefing(user_id))
        else:
            result = handle_calendar_skill(user_id, command_args)
    except Exception:
        result = handle_calendar_skill(user_id, command_args)
        
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_share")
def process_share(user_id: int, command_args: str):
    from gabay.core.skills.share import handle_share_skill
    result = run_async(handle_share_skill(user_id, command_args))
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_file_qa")
def process_file_qa(user_id: int, command_args: str):
    from gabay.core.skills.document_qa import handle_document_qa_skill
    result = run_async(handle_document_qa_skill(user_id, command_args))
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_news")
def process_news(user_id: int, topic: str):
    from gabay.core.skills.news import handle_news_skill
    result = run_async(handle_news_skill(topic))
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_docs")
def process_docs(user_id: int, command_args: str):
    from gabay.core.skills.docs import handle_docs_skill
    result = run_async(handle_docs_skill(user_id, command_args))
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_slides")
def process_slides(user_id: int, command_args: str):
    from gabay.core.skills.slides import handle_slides_skill
    import json
    def run_skill(args_str):
        data = json.loads(args_str)
        topic = data.get("topic")
        title = data.get("title")
        email_to = data.get("email_to")
        invite_email = data.get("invite_email")
        share_mode = data.get("share_mode", "private")
        role = data.get("role", "writer")
        
        return run_async(handle_slides_skill(
            user_id, topic, title=title, 
            email_to=email_to, invite_email=invite_email, 
            share_mode=share_mode, role=role
        ))

    try:
        result = run_skill(command_args)
    except Exception as e:
        logger.error(f"Error processing slides task: {e}")
        result = f"I couldn't process the slides request content: {e}"
        
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.process_sheets")
def process_sheets(user_id: int, command_args: str):
    from gabay.core.skills.sheets import handle_sheets_skill, handle_data_extraction_skill, handle_auto_report_skill
    import json
    
    def run_skill(args_str):
        data = json.loads(args_str)
        action = data.get("action", "create")
        
        if action == "extract":
            gmail_query = data.get("gmail_query")
            sheet_title = data.get("title")
            return run_async(handle_data_extraction_skill(user_id, gmail_query, sheet_title))
        
        elif action == "report":
            spreadsheet_id = data.get("spreadsheet_id")
            report_topic = data.get("topic")
            return run_async(handle_auto_report_skill(user_id, spreadsheet_id, report_topic))
        
        # Default create logic
        topic = data.get("topic")
        title = data.get("title")
        email_to = data.get("email_to")
        invite_email = data.get("invite_email")
        share_mode = data.get("share_mode", "private")
        role = data.get("role", "writer")
        
        return run_async(handle_sheets_skill(
            user_id, topic, title=title, 
            email_to=email_to, invite_email=invite_email, 
            share_mode=share_mode, role=role
        ))

    try:
        result = run_skill(command_args)
    except Exception as e:
        logger.error(f"Error processing sheets task: {e}")
        result = f"I couldn't process the spreadsheet request content: {e}"
        
    append_message(user_id, "assistant", result)
    send_telegram_message(user_id, result)
    return result

@celery_app.task(name="worker.tasks.check_reminders")
def check_reminders():
    from gabay.core.database import db
    from datetime import datetime, timedelta, timezone
    import logging
    
    logger = logging.getLogger("gabay.worker.tasks")
    reminders = db.get_reminders(status="pending")
    now = datetime.now(timezone.utc)
    
    for r in reminders:
        trigger_dt = datetime.fromisoformat(r["trigger_time"])
        # Ensure trigger_dt is aware (in case it was stored without TZ info)
        if trigger_dt.tzinfo is None:
            trigger_dt = trigger_dt.replace(tzinfo=timezone.utc)
            
        if now >= trigger_dt:
            logger.info(f"Triggering reminder: {r['id']} - {r['message']}")
            execute_reminder.delay(r["id"])
            
            # Update status immediately to prevent double firing
            updates = {}
            interval = r.get("interval_seconds")
            remaining = r.get("remaining_count")

            if interval and (remaining is None or remaining > 0):
                # Reschedule
                next_trigger = trigger_dt + timedelta(seconds=interval)
                updates["trigger_time"] = next_trigger.isoformat()
                if remaining is not None:
                    updates["remaining_count"] = remaining - 1
            elif r["frequency"] == "daily":
                updates["trigger_time"] = (trigger_dt + timedelta(days=1)).isoformat()
            elif r["frequency"] == "weekly":
                updates["trigger_time"] = (trigger_dt + timedelta(weeks=1)).isoformat()
            else:
                updates["status"] = "completed"
            
            db.update_reminder(r["id"], updates)

@celery_app.task(name="worker.tasks.execute_reminder")
def execute_reminder(reminder_id: str):
    from gabay.core.database import db
    from gabay.core.memory import get_contacts
    from gabay.core.utils.telegram import send_telegram_message
    
    # Query specific reminder by ID
    with db._get_connection() as conn:
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    
    reminder = dict(row) if row else None
    
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
    
    action = reminder.get("action")
    payload = reminder.get("payload")
    
    if action == "email" and payload:
        # Instead of just a text message, run the email task
        process_email.delay(user_id, payload)
    else:
        # Default: Send text message
        send_telegram_message(target_chat_id, f"{prefix}{message}")

@celery_app.task(name="worker.tasks.proactive_heartbeat")
def proactive_heartbeat():
    from gabay.core.connectors.token_manager import token_manager
    import logging
    logger = logging.getLogger("gabay.worker.tasks")
    
    user_ids = token_manager.get_all_users()
    logger.info(f"Running proactive heartbeat for users: {user_ids}")
    for uid_str in user_ids:
        try:
            user_id = int(uid_str)
            # 1. Triage Gmail
            triage_gmail_proactive.delay(user_id)
            # 2. Check Upcoming Meetings
            check_meeting_briefings.delay(user_id)
        except Exception as e:
            logger.error(f"Heartbeat failed for user {uid_str}: {e}")

@celery_app.task(name="worker.tasks.triage_gmail_proactive")
def triage_gmail_proactive(user_id: int):
    from gabay.core.skills.email import handle_triage_skill
    run_async(handle_triage_skill(str(user_id), proactive=True))

@celery_app.task(name="worker.tasks.check_meeting_briefings")
def check_meeting_briefings(user_id: int):
    from gabay.core.skills.calendar import handle_calendar_briefing
    run_async(handle_calendar_briefing(user_id))

from gabay.core.utils.telegram import send_telegram_message
