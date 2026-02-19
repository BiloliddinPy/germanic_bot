import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import create_table, get_user_profile, update_user_profile, update_streak, log_mistake, add_user
import sqlite3
import datetime

def validate_edtech_setup():
    print("--- EdTech Evolution Validation ---")
    
    # 1. Database Verification
    print("Checking database tables...")
    create_table() # Ensure latest schema
    
    conn = sqlite3.connect("germanic.db")
    cursor = conn.cursor()
    
    tables = ['user_profile', 'user_progress', 'user_streak', 'user_mistakes']
    for table in tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if cursor.fetchone():
            print(f"✅ Table '{table}' exists.")
        else:
            print(f"❌ Table '{table}' MISSING.")
            return False

    # 2. Profile Helper Verification
    print("\nTesting profile helpers...")
    test_user_id = 999999
    add_user(test_user_id, "Test User")
    update_user_profile(test_user_id, goal='exam', daily_time_minutes=20)
    profile = get_user_profile(test_user_id)
    if profile and profile['goal'] == 'exam' and profile['daily_time_minutes'] == 20:
        print("✅ Profile creation/update working.")
    else:
        print(f"❌ Profile helper FAILED. Data: {profile}")
        return False

    # 3. Streak Helper Verification
    print("\nTesting streak helpers...")
    update_streak(test_user_id)
    cursor.execute("SELECT current_streak FROM user_streak WHERE user_id = ?", (test_user_id,))
    res = cursor.fetchone()
    if res and res[0] == 1:
        print("✅ Streak initialization working.")
    else:
        print(f"❌ Streak initialization FAILED. Result: {res}")
        return False

    # 4. Mistake Helper Verification
    print("\nTesting mistake logging...")
    log_mistake(test_user_id, "word_123", "dictionary", "A1", tags="noun")
    log_mistake(test_user_id, "word_123", "dictionary", "A1")
    cursor.execute("SELECT mistake_count FROM user_mistakes WHERE user_id = ? AND item_id = ?", (test_user_id, "word_123"))
    res = cursor.fetchone()
    if res and res[0] == 2:
        print("✅ Mistake logging (counting) working.")
    else:
        print(f"❌ Mistake logging FAILED. Result: {res}")
        return False

    # Cleanup
    cursor.execute("DELETE FROM user_profile WHERE user_id = ?", (test_user_id,))
    cursor.execute("DELETE FROM user_streak WHERE user_id = ?", (test_user_id,))
    cursor.execute("DELETE FROM user_mistakes WHERE user_id = ?", (test_user_id,))
    conn.commit()
    conn.close()
    
    print("\n🎉 All foundations verified!")
    return True

if __name__ == "__main__":
    if validate_edtech_setup():
        sys.exit(0)
    else:
        sys.exit(1)
