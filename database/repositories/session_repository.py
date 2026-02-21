from database.connection import get_connection
from database.connection import is_postgres_backend
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
        logging.error(f"Error saving daily lesson state: {e}")
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

def save_user_submission(
    user_id: int,
    module: str,
    content: str,
    level: str | None = None,
    metadata: dict | None = None,
):
    conn = get_connection()
    cursor = conn.cursor()
    meta_json = json.dumps(metadata) if metadata else None
    try:
        # Check if table exists, if not create it (safe fallback for legacy schema)
        if is_postgres_backend():
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS user_submissions ("
                "id BIGSERIAL PRIMARY KEY, "
                "user_id BIGINT, module TEXT, content TEXT, level TEXT, "
                "metadata TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
        else:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS user_submissions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id INTEGER, module TEXT, content TEXT, level TEXT, "
                "metadata TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
        cursor.execute("""
            INSERT INTO user_submissions (user_id, module, content, level, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, module, content, level, meta_json))
        conn.commit()
    except Exception as e:
        logging.error(f"Error saving user submission: {e}")
    finally:
        conn.close()

def get_recent_submissions(user_id: int, limit: int = 5):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM user_submissions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()

def mark_writing_task_completed(user_id: int, level: str, topic_id: str, task_type: str):
    from database.repositories.progress_repository import log_event
    log_event(user_id, f"writing_task_completed_{task_type}", level=level, metadata={"topic_id": topic_id})
