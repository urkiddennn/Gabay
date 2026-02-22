import logging
import json
from gabay.core.connectors.calendar_api import get_events, create_event
from gabay.core.connectors.smtp_api import send_smtp_email

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
            
            # Hybrid Context: Send follow-up email if requested
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
