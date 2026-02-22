import os
import json
from pathlib import Path
from gabay.core.config import settings

def get_history_file(user_id: int) -> Path:
    history_dir = Path(settings.data_dir) / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir / f"chat_{user_id}.jsonl"

from gabay.core.database import db

def append_message(user_id: int, role: str, content: str):
    """
    Append a single message to the user's chat history in SQLite.
    role: 'user', 'assistant', or 'system'
    """
    db.append_message(user_id, role, content)

def get_recent_history(user_id: int, limit: int = 10) -> list:
    """
    Read the last `limit` messages from the user's history in SQLite.
    """
    return db.get_recent_history(user_id, limit)

def search_history(user_id: int, query: str, limit: int = 5) -> list:
    """
    Search the user's chat history using FTS5 keyword matching.
    """
    return db.search_messages(user_id, query, limit)

def save_contact(user_id: int, name: str, chat_id: int):
    """
    Save a mapping of name -> chat_id for a user in SQLite.
    """
    db.save_contact(user_id, name, chat_id)

def get_contacts(user_id: int) -> dict:
    """
    Retrieve all contacts for a user from SQLite.
    """
    return db.get_contacts(user_id)

def set_user_state(user_id: int, state: str):
    """Sets a temporary state for the user in SQLite."""
    db.set_user_state(user_id, state)

def get_user_state(user_id: int) -> str:
    """Gets the current temporary state of the user from SQLite."""
    return db.get_user_state(user_id)

def set_temp_data(user_id: int, key: str, value: any):
    """Saves temporary data needed during a stateful flow in SQLite."""
    db.set_temp_data(user_id, key, value)

def get_temp_data(user_id: int) -> dict:
    """Retrieves all temporary data for the user from SQLite."""
    return db.get_temp_data(user_id)

def clear_user_state(user_id: int):
    """Wipes the state and temp data for a user in SQLite."""
    db.clear_user_state(user_id)

