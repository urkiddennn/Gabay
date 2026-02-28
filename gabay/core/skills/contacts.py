import logging
from gabay.core.connectors.google_api import search_contacts, get_contact_by_name

logger = logging.getLogger(__name__)

async def handle_contacts_skill(user_id: str, query: str) -> str:
    """Interface for searching contacts."""
    if not query:
        return "Please provide a name or email to search for."
        
    contacts = search_contacts(user_id, query)
    if not contacts:
        return f"No contacts found matching '{query}'."
        
    response = f"Found {len(contacts)} contacts matching '{query}':\n"
    for c in contacts:
        response += f"👤 {c['name']} - {c['email']}\n"
        
    return response

def resolve_email(user_id: str, name_or_email: str) -> str:
    """Helper to resolve a name to an email address."""
    if "@" in name_or_email:
        return name_or_email
        
    contact = get_contact_by_name(user_id, name_or_email)
    if contact:
        return contact['email']
    return None
