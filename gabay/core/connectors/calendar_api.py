import logging
from datetime import datetime, timezone, timedelta
from gabay.core.connectors.google_api import get_google_service

logger = logging.getLogger(__name__)

def get_events(user_id: str, time_min: str = None, time_max: str = None) -> list[str]:
    """Retrieve events from the user's primary Google Calendar within a timeframe."""
    service = get_google_service(user_id, "calendar", "v3")
    if not service:
        return ["Google Calendar is not connected. Please authenticate in the Admin Dashboard."]

    try:
        now = datetime.now(timezone.utc)
        
        if not time_min:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_min = start.isoformat()
            
        if not time_max:
            end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            time_max = end.isoformat()

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=50,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return ["You have no events scheduled for this timeframe."]
            
        parsed_events = []
        for event in events:
            start_time = event['start'].get('dateTime', event['start'].get('date'))
            # Format time
            if 'T' in start_time:
                try:
                    dt = datetime.fromisoformat(start_time)
                    start_time = dt.strftime("%b %d, %I:%M %p")
                except:
                    pass
            summary = event.get('summary', 'Untitled Event')
            parsed_events.append(f"• {start_time}: {summary}")
            
        return parsed_events
    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}")
        return [f"Failed to fetch calendar events. Error: {str(e)}"]

def create_event(user_id: str, summary: str, start_time: str, end_time: str) -> str:
    """Create a new event on the user's primary calendar."""
    service = get_google_service(user_id, "calendar", "v3")
    if not service:
        return "Google Calendar is not connected."
        
    try:
        event = {
          'summary': summary,
          'start': {
            'dateTime': start_time,
            'timeZone': 'UTC',
          },
          'end': {
            'dateTime': end_time,
            'timeZone': 'UTC',
          }
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        return f"Event created: {event.get('htmlLink')}"
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return f"Failed to create event. Error: {str(e)}"
