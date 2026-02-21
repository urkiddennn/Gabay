import os
import json
from pathlib import Path
from gabay.core.config import settings

def get_history_file(user_id: int) -> Path:
    history_dir = Path(settings.data_dir) / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir / f"chat_{user_id}.jsonl"

def append_message(user_id: int, role: str, content: str):
    """
    Append a single message to the user's chat history JSONL file.
    role: 'user', 'assistant', or 'system'
    """
    file_path = get_history_file(user_id)
    with open(file_path, "a", encoding="utf-8") as f:
        msg = {"role": role, "content": content}
        f.write(json.dumps(msg) + "\n")

def get_recent_history(user_id: int, limit: int = 10) -> list:
    """
    Read the last `limit` messages from the user's history file.
    """
    file_path = get_history_file(user_id)
    if not file_path.exists():
        return []
        
    messages = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                messages.append(json.loads(line))
    return messages[-limit:]

def save_contact(user_id: int, name: str, chat_id: int):
    """
    Save a mapping of name -> chat_id for a user.
    Stored in data/memory/contacts_{user_id}.json
    """
    contacts_dir = Path(settings.data_dir) / "memory"
    contacts_dir.mkdir(parents=True, exist_ok=True)
    file_path = contacts_dir / f"contacts_{user_id}.json"
    
    contacts = {}
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            contacts = json.load(f)
            
    contacts[name.lower()] = chat_id
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=4)

def get_contacts(user_id: int) -> dict:
    """
    Retrieve all contacts for a user.
    """
    file_path = Path(settings.data_dir) / "memory" / f"contacts_{user_id}.json"
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def set_user_state(user_id: int, state: str):
    """Sets a temporary state for the user (e.g. for multi-step setup)."""
    state_dir = Path(settings.data_dir) / "memory" / "states"
    state_dir.mkdir(parents=True, exist_ok=True)
    file_path = state_dir / f"state_{user_id}.json"
    
    data = {"state": state}
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def get_user_state(user_id: int) -> str:
    """Gets the current temporary state of the user."""
    file_path = Path(settings.data_dir) / "memory" / "states" / f"state_{user_id}.json"
    if not file_path.exists():
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("state")

def set_temp_data(user_id: int, key: str, value: any):
    """Saves temporary data needed during a stateful flow."""
    data_dir = Path(settings.data_dir) / "memory" / "temp"
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / f"temp_{user_id}.json"
    
    current_data = {}
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            current_data = json.load(f)
            
    current_data[key] = value
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(current_data, f)

def get_temp_data(user_id: int) -> dict:
    """Retrieves all temporary data for the user."""
    file_path = Path(settings.data_dir) / "memory" / "temp" / f"temp_{user_id}.json"
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def clear_user_state(user_id: int):
    """Wipes the state and temp data once a flow is finished."""
    state_file = Path(settings.data_dir) / "memory" / "states" / f"state_{user_id}.json"
    temp_file = Path(settings.data_dir) / "memory" / "temp" / f"temp_{user_id}.json"
    if state_file.exists():
        state_file.unlink()
    if temp_file.exists():
        temp_file.unlink()
