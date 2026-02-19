from database.connection import get_connection
import logging
import json

def update_module_progress(user_id: int, module_name: str, level: str, completed: bool = False):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if completed:
            cursor.execute("""
                INSERT INTO user_progress (user_id, module_name, level, completion_status, last_active)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, module_name, level) DO UPDATE SET
                    completion_status = 1,
                    last_active = CURRENT_TIMESTAMP
            """, (user_id, module_name, level))
        else:
            cursor.execute("""
                INSERT INTO user_progress (user_id, module_name, level, last_active)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, module_name, level) DO UPDATE SET
                    last_active = CURRENT_TIMESTAMP
            """, (user_id, module_name, level))
        conn.commit()
    except Exception as e:
        logging.error(f"Error updating module progress: {e}")
    finally:
        conn.close()

def record_navigation_event(user_id: int, section_name: str, level: str = None, entry_type: str = "callback"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO navigation_logs (user_id, section_name, level, entry_type)
            VALUES (?, ?, ?, ?)
        """, (user_id, section_name, level, entry_type))
        conn.commit()
    except Exception as e:
        logging.error(f"Error logging navigation: {e}")
    finally:
        conn.close()

def log_mistake(user_id: int, item_id: int, module: str, mistake_type: str = "vocab"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO user_mistakes (user_id, item_id, module, mistake_type, mistake_count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(user_id, item_id, module) DO UPDATE SET
                mistake_count = mistake_count + 1,
                last_mistake_at = CURRENT_TIMESTAMP,
                mastered = 0
        """, (user_id, str(item_id), module, mistake_type))
        conn.commit()
    except Exception as e:
        logging.error(f"Error logging mistake: {e}")
    finally:
        conn.close()

def log_event(user_id: int, event_type: str, section_name: str = None, level: str = None, metadata: dict = None):
    conn = get_connection()
    cursor = conn.cursor()
    meta_json = json.dumps(metadata) if metadata else None
    try:
        cursor.execute("""
            INSERT INTO event_logs (user_id, event_type, section_name, level, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, event_type, section_name, level, meta_json))
        conn.commit()
    except Exception as e:
        logging.error(f"Error logging event: {e}")
    finally:
        conn.close()

def add_quiz_result(user_id: int, level: str, score: int, total: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO quiz_results (user_id, level, score, total)
            VALUES (?, ?, ?, ?)
        """, (user_id, level, score, total))
        conn.commit()
    except Exception as e:
        logging.error(f"Error adding quiz result: {e}")
    finally:
        conn.close()
