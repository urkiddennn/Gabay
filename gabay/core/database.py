import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from gabay.core.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            data_dir = Path(settings.data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "gabay.db")
        
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 2. Virtual Table for Full-Text Search (FTS5)
            # This allows high-performance keyword searching
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages_fts'")
            if not cursor.fetchone():
                cursor.execute('''
                    CREATE VIRTUAL TABLE messages_fts USING fts5(
                        content,
                        content='messages',
                        content_rowid='id'
                    )
                ''')
                
                # Triggers to keep FTS index in sync
                cursor.execute('''
                    CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                    END;
                ''')
                cursor.execute('''
                    CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
                    END;
                ''')
                cursor.execute('''
                    CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
                        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                    END;
                ''')

            # 3. Contacts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, name)
                )
            ''')

            # 4. State Management
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_states (
                    user_id INTEGER PRIMARY KEY,
                    state TEXT,
                    temp_data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 5. Reminders Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    trigger_time TEXT NOT NULL,
                    original_trigger TEXT,
                    frequency TEXT DEFAULT 'once',
                    recipient TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    interval_seconds INTEGER,
                    remaining_count INTEGER,
                    action TEXT,
                    payload TEXT
                )
            ''')
            
            # 6. Save Logs (Metadata for uploads)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS save_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    source_type TEXT NOT NULL, -- 'notion' or 'drive'
                    content_meta TEXT,         -- URL or filename
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
        
        # Run migrations for existing databases
        self._migrate_reminders_table()

    def _migrate_reminders_table(self):
        """Add new columns to reminders table if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(reminders)")
            columns = [info['name'] for info in cursor.fetchall()]
            
            new_cols = [
                ("interval_seconds", "INTEGER"),
                ("remaining_count", "INTEGER"),
                ("action", "TEXT"),
                ("payload", "TEXT")
            ]
            
            for col_name, col_type in new_cols:
                if col_name not in columns:
                    logger.info(f"Migrating: Adding {col_name} to reminders table")
                    try:
                        cursor.execute(f"ALTER TABLE reminders ADD COLUMN {col_name} {col_type}")
                    except Exception as e:
                        logger.error(f"Error adding {col_name} to reminders: {e}")
            
            conn.commit()

    # --- Message Operations ---

    def append_message(self, user_id: int, role: str, content: str):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content)
            )
            conn.commit()

    def get_recent_history(self, user_id: int, limit: int = 10):
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            )
            # Reverse so it's in chronological order
            history = [{"role": row["role"], "content": row["content"]} for row in rows]
            history.reverse()
            return history

    def search_messages(self, user_id: int, query: str, limit: int = 5):
        """Perform keyword search across user's history."""
        with self._get_connection() as conn:
            # Join with the main messages table to get metadata
            rows = conn.execute('''
                SELECT m.role, m.content, m.created_at
                FROM messages m
                JOIN messages_fts f ON m.id = f.rowid
                WHERE m.user_id = ? AND messages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            ''', (user_id, query, limit))
            
            return [dict(row) for row in rows]

    # --- Contact Operations ---

    def save_contact(self, user_id: int, name: str, chat_id: int):
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO contacts (user_id, name, chat_id)
                VALUES (?, ?, ?)
            ''', (user_id, name.lower(), chat_id))
            conn.commit()

    def get_contacts(self, user_id: int):
        with self._get_connection() as conn:
            rows = conn.execute("SELECT name, chat_id FROM contacts WHERE user_id = ?", (user_id,))
            return {row["name"]: row["chat_id"] for row in rows}

    # --- State Operations ---

    def set_user_state(self, user_id: int, state: str):
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO user_states (user_id, state, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at
            ''', (user_id, state))
            conn.commit()

    def get_user_state(self, user_id: int):
        with self._get_connection() as conn:
            row = conn.execute("SELECT state FROM user_states WHERE user_id = ?", (user_id,)).fetchone()
            return row["state"] if row else None

    def set_temp_data(self, user_id: int, key: str, value: any):
        with self._get_connection() as conn:
            row = conn.execute("SELECT temp_data FROM user_states WHERE user_id = ?", (user_id,)).fetchone()
            data = json.loads(row["temp_data"]) if row and row["temp_data"] else {}
            data[key] = value
            
            conn.execute('''
                INSERT INTO user_states (user_id, temp_data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET temp_data=excluded.temp_data, updated_at=excluded.updated_at
            ''', (user_id, json.dumps(data)))
            conn.commit()

    def get_temp_data(self, user_id: int):
        with self._get_connection() as conn:
            row = conn.execute("SELECT temp_data FROM user_states WHERE user_id = ?", (user_id,)).fetchone()
            return json.loads(row["temp_data"]) if row and row["temp_data"] else {}

    def clear_user_state(self, user_id: int):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
            conn.commit()

    # --- Reminder Operations ---

    def create_reminder(self, reminder_data: dict):
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO reminders (id, user_id, message, trigger_time, original_trigger, frequency, recipient, status, created_at, interval_seconds, remaining_count, action, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                reminder_data["id"],
                reminder_data["user_id"],
                reminder_data["message"],
                reminder_data["trigger_time"],
                reminder_data.get("original_trigger"),
                reminder_data.get("frequency", "once"),
                reminder_data.get("recipient"),
                reminder_data.get("status", "pending"),
                reminder_data.get("created_at", datetime.now().isoformat()),
                reminder_data.get("interval_seconds"),
                reminder_data.get("remaining_count"),
                reminder_data.get("action"),
                reminder_data.get("payload")
            ))
            conn.commit()

    def get_reminders(self, user_id: int = None, status: str = None):
        with self._get_connection() as conn:
            query = "SELECT * FROM reminders"
            params = []
            conditions = []
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def update_reminder(self, reminder_id: str, updates: dict):
        with self._get_connection() as conn:
            fields = []
            params = []
            for k, v in updates.items():
                fields.append(f"{k} = ?")
                params.append(v)
            params.append(reminder_id)
            conn.execute(f"UPDATE reminders SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()

    def delete_reminder(self, user_id: int, message_key: str):
        with self._get_connection() as conn:
            conn.execute('''
                DELETE FROM reminders 
                WHERE user_id = ? AND LOWER(message) LIKE ?
            ''', (user_id, f"%{message_key.lower()}%"))
            conn.commit()

    # --- Save Log Operations ---

    def log_save(self, user_id: int, source_type: str, content_meta: str):
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO save_logs (user_id, source_type, content_meta)
                VALUES (?, ?, ?)
            ''', (user_id, source_type, content_meta))
            conn.commit()

db = DatabaseManager()
