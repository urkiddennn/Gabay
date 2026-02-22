from gabay.core.memory import append_message, get_recent_history, search_history, db
import time
import os

def test_sqlite_memory():
    user_id = 888  # Docker Test User
    
    print(f"🐳 Testing SQLite Memory System INSIDE Docker...")
    print(f"📂 Database Path: {db.db_path}")
    print(f"📂 Current Data Dir: {os.getenv('DATA_DIR', '/app/data')}")

    # 1. Test Appending
    print("\n📝 Step 1: Appending test messages...")
    append_message(user_id, "user", "Docker is running with SQLite now.")
    append_message(user_id, "assistant", "Confirmed. I am storing this in the SQLite database inside the container.")
    print("✅ Messages appended.")

    # 2. Test Recent History
    print("\n🕒 Step 2: Retrieving recent history...")
    history = get_recent_history(user_id, limit=2)
    for msg in history:
        print(f"  [{msg['role']}] {msg['content']}")
    
    if len(history) == 2:
        print("✅ History retrieval works.")
    else:
        print("❌ History retrieval failed.")

    # 3. Test SEARCH (FTS5)
    print("\n🔍 Step 3: Testing Full-Text Search...")
    time.sleep(0.1) 
    
    search_query = "SQLite"
    results = search_history(user_id, search_query)
    
    print(f"  Searching for: '{search_query}'")
    if results:
        for res in results:
            print(f"  ✅ Match found: \"{res['content']}\"")
    else:
        print("  ❌ No matches found for 'SQLite'.")

    # 4. Cleanup test data
    print("\n🧹 Cleaning up test data...")
    with db._get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        conn.commit()
    print("✅ Cleanup complete.")

if __name__ == "__main__":
    test_sqlite_memory()
