from database.connection import get_connection
import logging
import datetime

def get_admin_stats_snapshot():
    conn = get_connection()
    cursor = conn.cursor()
    stats = {}
    try:
        cursor.execute("SELECT COUNT(*) FROM user_profile")
        stats['total_users'] = cursor.fetchone()[0]
        
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
    cursor.execute("SELECT * FROM event_logs WHERE event_type LIKE '%error%' ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
