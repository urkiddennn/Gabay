import requests
import logging

logger = logging.getLogger(__name__)

def get_weather_data(location: str) -> str:
    """
    Fetches weather data from wttr.in (a terminal-friendly weather service).
    """
    try:
        # If no location, wttr.in guesses based on IP
        target = "" if location.lower() == "current" else location
        url = f"https://wttr.in/{target}?format=3"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        else:
            return "I couldn't reach the weather service right now. Please try again later."
            
    except Exception as e:
        logger.error(f"Error fetching weather: {e}")
        return "Sorry, I had trouble getting the weather report."
