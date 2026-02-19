from database.connection import get_connection
import json
import logging

def save_daily_lesson_state(user_id: int, state_data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        state_json = json.dumps(state_data)
        cursor.execute("""
            INSERT INTO daily_lesson_sessions (user_id, session_data)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                session_data = excluded.session_data,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, state_json))
        conn.commit()
    except Exception as e:
        logging.error(f"Error saving daily lesson state for {user_id}: {e}")
    finally:
        conn.close()

def get_daily_lesson_state(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT session_data FROM daily_lesson_sessions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def delete_daily_lesson_state(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM daily_lesson_sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def save_user_submission(user_id: int, module: str, content: str, level: str = None, metadata: dict = None):
    conn = get_connection()
    cursor = conn.cursor()
    meta_json = json.dumps(metadata) if metadata else None
    try:
        cursor.execute("""
            INSERT INTO user_submissions (user_id, module, content, level, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, module, content, level, meta_json))
        conn.commit()
    except Exception as e:
        logging.error(f"Error saving user submission: {e}")
    finally:
        conn.close()
