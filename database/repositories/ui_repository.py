from database.connection import get_connection
import logging

def get_ui_state(user_id: int, key: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT val FROM ui_state WHERE user_id = ? AND key = ?", (user_id, key))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_ui_state(user_id: int, key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ui_state (user_id, key, val)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET
                val = excluded.val,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, key, str(value)))
        conn.commit()
    except Exception as e:
        logging.error(f"Error setting UI state for {user_id}/{key}: {e}")
    finally:
        conn.close()
