from database.connection import get_connection
import logging
import datetime
from database.connection import is_postgres_backend

def get_admin_stats_snapshot():
    conn = get_connection()
    cursor = conn.cursor()
    stats = {}
    try:
        cursor.execute("SELECT COUNT(*) FROM user_profile")
        stats['total_users'] = cursor.fetchone()[0]
        if is_postgres_backend():
            cursor.execute(
                "SELECT COUNT(*) FROM user_profile WHERE DATE(created_at) = CURRENT_DATE"
            )
            stats['new_users_today'] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(DISTINCT user_id) FROM navigation_logs WHERE DATE(created_at) = CURRENT_DATE"
            )
            stats['active_users_today'] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM user_progress WHERE module_name = 'daily_lesson' "
                "AND completion_status = 1 AND DATE(last_active) = CURRENT_DATE"
            )
            stats['daily_completions_today'] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM user_progress WHERE module_name = 'daily_lesson' "
                "AND completion_status = 1 AND DATE(last_active) >= (CURRENT_DATE - INTERVAL '7 days')"
            )
            stats['daily_completions_last_7_days'] = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM user_profile WHERE date(created_at) = date('now', 'localtime')")
            stats['new_users_today'] = cursor.fetchone()[0]

            today = datetime.date.today().isoformat()
            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM navigation_logs WHERE date(created_at) = ?", (today,))
            stats['active_users_today'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM user_progress WHERE module_name = 'daily_lesson' AND completion_status = 1 AND date(last_active) = ?", (today,))
            stats['daily_completions_today'] = cursor.fetchone()[0]

            last_7_days = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
            cursor.execute("SELECT COUNT(*) FROM user_progress WHERE module_name = 'daily_lesson' AND completion_status = 1 AND date(last_active) >= ?", (last_7_days,))
            stats['daily_completions_last_7_days'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_mistakes")
        stats['total_mistakes_logged'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT item_id, SUM(mistake_count) as score 
            FROM user_mistakes 
            GROUP BY item_id 
            ORDER BY score DESC 
            LIMIT 5
        """)
        stats['top_weak_topics'] = [{"topic_id": row[0], "score": row[1]} for row in cursor.fetchall()]
        
    except Exception as e:
        logging.error(f"Error getting admin stats snapshot: {e}")
    finally:
        conn.close()
    return stats

def get_users_count() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM user_profile")
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    except Exception as e:
        logging.error(f"Error getting users count: {e}")
        return 0
    finally:
        conn.close()

def get_last_event_timestamp(user_id: int | None = None):
    conn = get_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT created_at FROM event_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
    else:
        cursor.execute("SELECT created_at FROM event_logs ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_recent_ops_errors(limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM event_logs WHERE LOWER(event_type) LIKE ? ORDER BY created_at DESC LIMIT ?",
            ("%error%", limit),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Error getting recent ops errors: {e}")
        return []
    finally:
        conn.close()
