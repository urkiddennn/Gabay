import feedparser
import logging

logger = logging.getLogger(__name__)

# Predefined common feeds
FEEDS = {
    "world": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    "philippines": "https://news.google.com/rss?hl=en-PH&gl=PH&ceid=PH:en",
    "tech": "https://news.google.com/rss/search?q=technology&hl=en-US&gl=US&ceid=US:en",
    "stocks": "https://finance.yahoo.com/news/rssindex",
    "business": "https://news.google.com/rss/search?q=business&hl=en-US&gl=US&ceid=US:en"
}

def fetch_feed(topic: str, max_items: int = 5) -> str:
    """
    Fetches the top news or updates for a given topic via RSS.
    Returns a formatted string of the top headlines and their links/summaries.
    """
    topic = topic.lower().strip()
    
    # Try to map the requested topic to our curated list
    feed_url = None
    for key in FEEDS:
        if key in topic:
            feed_url = FEEDS[key]
            break
            
    # Default to a google news search if not found
    if not feed_url:
        feed_url = f"https://news.google.com/rss/search?q={topic}&hl=en-US&gl=US&ceid=US:en"
        
    try:
        logger.info(f"Fetching RSS feed: {feed_url}")
        feed = feedparser.parse(feed_url)
        
        if not feed.entries:
            return f"I couldn't find any recent news items for '{topic}'."
            
        entries = feed.entries[:max_items]
        
        result_lines = [f"Here are the latest updates for '{topic}':\n"]
        for i, entry in enumerate(entries):
            title = entry.get('title', 'No Title')
            # Fallback to description if summary is not present, or just leave it empty
            summary = entry.get('summary', entry.get('description', ''))
            
            # Clean up the summary (RSS summaries often have HTML tags)
            import re
            summary = re.sub('<[^<]+?>', '', summary).strip()
            if len(summary) > 200:
                summary = summary[:197] + "..."
                
            result_lines.append(f"{i+1}. {title}")
            if summary and summary != title:
                result_lines.append(f"   {summary}")
            result_lines.append("") # Empty line for spacing
            
        return "\n".join(result_lines)
    except Exception as e:
        logger.error(f"Error fetching feed '{topic}': {e}")
        return f"I encountered an error trying to fetch the news for '{topic}': {e}"
