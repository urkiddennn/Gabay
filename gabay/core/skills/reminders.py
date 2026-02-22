import logging
import json
import os
import uuid
from datetime import datetime, timedelta
from dateutil import parser
from gabay.core.config import settings

logger = logging.getLogger(__name__)

from gabay.core.database import db

def parse_relative_time(time_str):
    """
    Super simple relative time parser. 
    In a real app, we'd use 'dateparser' or similar.
    """
    from datetime import timezone
    now = datetime.now(timezone.utc)
    
    try:
        # Try absolute parsing. 
        # If the LLM returned a UTC string, this will be aware.
        dt = parser.parse(time_str, fuzzy=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except:
        # Fallback for simple "in X hours" etc.
        if "hour" in time_str:
            num = int(''.join(filter(str.isdigit, time_str)))
            return now + timedelta(hours=num)
        if "minute" in time_str:
            num = int(''.join(filter(str.isdigit, time_str)))
            return now + timedelta(minutes=num)
        return now + timedelta(days=1)

def handle_reminder_skill(user_id: str, command_args_str: str) -> str:
    """
    Handles creating, listing, and deleting reminders.
    """
    try:
        data = json.loads(command_args_str)
        action = data.get("action", "create")
        
        if action == "create":
            message = data.get("message")
            trigger_str = data.get("trigger_time")
            frequency = data.get("frequency", "once")
            recipient = data.get("recipient")
            
            if not message or not trigger_str:
                return "I need a message and a time to set a reminder."
                
            trigger_dt = parse_relative_time(trigger_str)
            
            new_reminder = {
                "id": str(uuid.uuid4()),
                "user_id": int(user_id),
                "message": message,
                "trigger_time": trigger_dt.isoformat(),
                "original_trigger": trigger_str,
                "frequency": frequency,
                "recipient": recipient,
                "created_at": datetime.now().isoformat(),
                "status": "pending",
                # Optional recurring fields
                "interval_seconds": data.get("interval_seconds"),
                "remaining_count": data.get("remaining_count"),
                "action": data.get("action"),
                "payload": data.get("payload")
            }
            
            db.create_reminder(new_reminder)
            
            target_user = f"to {recipient}" if recipient else "for you"
            
            # Convert trigger_dt to local time for display
            # Since trigger_dt is UTC-aware, .astimezone() with no args converts to system local
            local_trigger = trigger_dt.astimezone()
            time_display = local_trigger.strftime('%I:%M %p').lower().lstrip('0')
            date_display = local_trigger.strftime('%b %d')
            
            freq_suffix = ""
            if frequency == "daily":
                freq_suffix = ", repeating daily"
            elif frequency == "weekly":
                freq_suffix = ", repeating weekly"

            return (
                f"✅ **Got it!** I've set a reminder {target_user}:\n\n"
                f"📝 \"{message}\"\n"
                f"⏰ {date_display} at {time_display}{freq_suffix}."
            )

        elif action == "list":
            user_reminders = db.get_reminders(user_id=int(user_id), status="pending")
            if not user_reminders:
                return "You have no active reminders."
            
            resp = "🔔 **Your Scheduled Reminders:**\n"
            for r in user_reminders:
                target = f"→ {r['recipient']}" if r.get('recipient') else "Self"
                resp += f"- [{target}] {r['message']} ({r['original_trigger']})\n"
            return resp

        elif action == "delete":
            msg_to_delete = data.get("message", "").lower()
            if not msg_to_delete:
                return "Please specify which reminder to delete."
            db.delete_reminder(user_id=int(user_id), message_key=msg_to_delete)
            return f"Requested deletion of reminders matching: '{msg_to_delete}'"

        return "Unknown reminder action."
        
    except Exception as e:
        logger.error(f"Error in reminder skill: {e}")
        return f"Error setting reminder: {e}"
