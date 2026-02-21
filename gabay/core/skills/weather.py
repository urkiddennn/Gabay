import logging
from gabay.core.connectors.weather_api import get_weather_data

logger = logging.getLogger(__name__)

def handle_weather_skill(location: str) -> str:
    """
    Orchestrates the weather fetching process.
    """
    if not location or location.lower() == "current":
        # We'll let wttr.in guess by IP or we could add a default city in .env
        logger.info("Fetching weather for current location (IP-based).")
    
    result = get_weather_data(location)
    
    if "Unknown location" in result:
        return f"I couldn't find the weather for '{location}'. Is that a city?"
        
    return f"🌦️ Current Weather: {result}"
