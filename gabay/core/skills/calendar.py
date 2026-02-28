from gabay.core.connectors.calendar_api import get_events, create_event, get_raw_events
from gabay.core.connectors.smtp_api import send_smtp_email
from gabay.core.skills.search import execute_search
import logging
import json
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

def handle_calendar_skill(user_id: int, command_args_str: str) -> str:
    """
    Handles interacting with Google Calendar.
    command_args_str can be JSON with 'action' (e.g., 'read', 'create') 
    or just a string. Currently supports reading today's events.
    """
    try:
        data = {}
        try:
            data = json.loads(command_args_str)
        except:
            pass
            
        action = data.get("action", "read")
        
        if action == "read":
            time_min = data.get("time_min")
            time_max = data.get("time_max")
            events = get_events(str(user_id), time_min, time_max)
            
            if not events:
                return "You have no events during that time."
            
            response = "📅 **Here is your Schedule:**\n" + "\n".join(events)
            return response
            
        elif action == "create":
            summary = data.get("summary", "New Event")
            start_time = data.get("start_time")
            end_time = data.get("end_time")
            attendees = data.get("attendees", [])
            email_confirmation_to = data.get("email_confirmation_to")
            
            if not start_time or not end_time:
                return "I need a start time and end time to create an event."
                
            result = create_event(str(user_id), summary, start_time, end_time, attendees=attendees)
            
            # Send follow-up email if requested
            if "Event created" in result and email_confirmation_to:
                try:
                    event_link = result.split(": ")[1] if ": " in result else ""
                    subject = f"Appointment: {summary}"
                    email_body = f"I've scheduled our appointment: {summary}\nTime: {start_time}\n\nLink: {event_link}\n\n--\nSent via Gabay."
                    send_smtp_email(email_confirmation_to, subject, email_body, user_id=str(user_id))
                    result += f" and confirmation email sent to {email_confirmation_to}."
                except Exception as e:
                    logger.error(f"Failed to send hybrid email for calendar: {e}")
                    result += " (Failed to send follow-up email)"
                    
            return result
            
        else:
            return "I don't know how to do that with your calendar yet."
            
    except Exception as e:
        logger.error(f"Error in calendar skill: {e}")
        return f"Error interacting with calendar: {e}"

async def handle_calendar_briefing(user_id: int):
    """
    Proactively checks for upcoming meetings and sends a briefing with related documents.
    """
    from gabay.core.utils.telegram import send_telegram_message
    
    try:
        # Check events in next 45 minutes
        now = datetime.now(timezone.utc)
        soon = now + timedelta(minutes=45)
        
        events = get_raw_events(str(user_id), time_min=now.isoformat(), time_max=soon.isoformat())
        if not events:
            return
            
        for event in events:
            summary = event.get('summary', 'Meeting')
            start_time_str = event['start'].get('dateTime', event['start'].get('date'))
            
            # 2. Extract context and search Docs
            search_query = f"{summary} meeting notes proposal"
            relevant_docs = await execute_search(str(user_id), search_query)
            
            briefing = f"📅 **Upcoming Meeting Briefing**\n\n"
            briefing += f"**Event:** {summary}\n"
            briefing += f"**Time:** {start_time_str}\n\n"
            
            if "I couldn't find" not in relevant_docs:
                briefing += f"🔍 **Related Context Found:**\n{relevant_docs}\n"
            else:
                briefing += "🔍 No specific related documents found for this meeting.\n"
                
            briefing += "\n*Sent 30 mins before your meeting starts.*"
            
            send_telegram_message(user_id, briefing)
            
    except Exception as e:
        logger.error(f"Error in meeting briefing: {e}")
