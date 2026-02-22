import json
import os
from pathlib import Path
from gabay.core.config import settings
from gabay.core.memory import db, append_message, save_contact

def migrate():
    data_dir = Path(settings.data_dir)
    history_dir = data_dir / "history"
    memory_dir = data_dir / "memory"
    
    print("🚀 Starting Gabay Data Migration...")

    # 1. Migrate Chat History
    if history_dir.exists():
        for file in history_dir.glob("chat_*.jsonl"):
            try:
                user_id = int(file.stem.split("_")[1])
                print(f"📄 Migrating history for user {user_id}...")
                count = 0
                with open(file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            msg = json.loads(line)
                            # Using the db manager directly to avoid file checks
                            db.append_message(user_id, msg["role"], msg["content"])
                            count += 1
                print(f"  ✅ Migrated {count} messages.")
            except Exception as e:
                print(f"  ❌ Error migrating {file.name}: {e}")

    # 2. Migrate Contacts
    if memory_dir.exists():
        for file in memory_dir.glob("contacts_*.json"):
            try:
                user_id = int(file.stem.split("_")[1])
                print(f"👤 Migrating contacts for user {user_id}...")
                with open(file, "r", encoding="utf-8") as f:
                    contacts = json.load(f)
                    for name, chat_id in contacts.items():
                        db.save_contact(user_id, name, chat_id)
                print(f"  ✅ Migrated {len(contacts)} contacts.")
            except Exception as e:
                print(f"  ❌ Error migrating {file.name}: {e}")

    # 3. Migrate States
    states_dir = memory_dir / "states"
    if states_dir.exists():
        for file in states_dir.glob("state_*.json"):
            try:
                user_id = int(file.stem.split("_")[1])
                print(f"⚙️ Migrating state for user {user_id}...")
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    db.set_user_state(user_id, data.get("state"))
                print(f"  ✅ Migrated state.")
            except Exception as e:
                print(f"  ❌ Error migrating {file.name}: {e}")

    print("\n🎉 Migration complete! Your data is now in SQLite.")
    print("Empty JSON files are still on disk as backup, but will no longer be used.")

if __name__ == "__main__":
    migrate()
