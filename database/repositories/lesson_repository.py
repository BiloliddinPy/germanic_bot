from database.connection import get_connection
import json
import logging

def get_last_daily_plan(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT plan_data FROM daily_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def save_daily_plan(user_id: int, plan_data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        plan_json = json.dumps(plan_data)
        cursor.execute("INSERT INTO daily_plans (user_id, plan_data) VALUES (?, ?)", (user_id, plan_json))
        conn.commit()
    except Exception as e:
        logging.error(f"Error saving daily plan for {user_id}: {e}")
    finally:
        conn.close()

def get_grammar_coverage_map(user_id: int, level: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT topic_id, seen_count FROM grammar_progress WHERE user_id = ? AND level = ?", (user_id, level))
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def mark_grammar_topic_seen(user_id: int, topic_id: str, level: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO grammar_progress (user_id, topic_id, level, seen_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, topic_id, level) DO UPDATE SET
                seen_count = seen_count + 1,
                last_seen = CURRENT_TIMESTAMP
        """, (user_id, topic_id, level))
        conn.commit()
    except Exception as e:
        logging.error(f"Error marking grammar topic seen: {e}")
    finally:
        conn.close()
