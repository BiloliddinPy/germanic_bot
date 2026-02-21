from database.connection import get_connection
from database.connection import is_postgres_backend
import datetime
import logging


def _normalize_date(value) -> datetime.date | None:
    if value is None:
        return None
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None


def add_user(user_id: int, full_name: str, username: str | None = None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO user_profile (user_id)
            VALUES (?)
            ON CONFLICT(user_id) DO NOTHING
        """, (user_id,))
        # Optional: update name if needed, but keeping it simple as per original logic
        conn.commit()
    except Exception as e:
        logging.error(f"Error adding user {user_id}: {e}")
    finally:
        conn.close()

def get_user_profile(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profile WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_or_create_user_profile(user_id: int):
    profile = get_user_profile(user_id)
    if profile:
        return profile
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO user_profile (user_id) VALUES (?) "
            "ON CONFLICT(user_id) DO NOTHING",
            (user_id,),
        )
        conn.commit()
    except Exception as e:
        logging.error(f"Error creating user profile: {e}")
    finally:
        conn.close()
    
    return get_user_profile(user_id)

def update_user_profile(user_id: int, **kwargs):
    if not kwargs:
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values())
    values.append(user_id)
    
    try:
        cursor.execute(f"UPDATE user_profile SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", values)
        conn.commit()
    except Exception as e:
        logging.error(f"Error updating user profile {user_id}: {e}")
    finally:
        conn.close()

def get_days_since_first_use(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT created_at FROM user_profile WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return 0
        
    try:
        from datetime import datetime, date

        raw = row[0]
        if isinstance(raw, datetime):
            created_at = raw
        elif isinstance(raw, date):
            created_at = datetime.combine(raw, datetime.min.time())
        else:
            text = str(raw).strip()
            created_at = datetime.fromisoformat(text.replace("Z", "+00:00"))

        delta = datetime.now(created_at.tzinfo) - created_at if created_at.tzinfo else datetime.now() - created_at
        return delta.days + 1
    except Exception:
        return 0

def get_subscribed_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user_profile")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_subscribed_users_for_time(time_str: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user_profile WHERE notification_time = ?", (time_str,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def update_streak(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        today_date = datetime.date.today()
        today = today_date.isoformat()
        cursor.execute("SELECT current_streak, last_activity FROM user_streak WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.execute("INSERT INTO user_streak (user_id, current_streak, last_activity, highest_streak) VALUES (?, 1, ?, 1)", (user_id, today))
        else:
            curr, last = row
            last_date = _normalize_date(last)
            if last_date == today_date:
                pass # Already updated
            elif last_date == (today_date - datetime.timedelta(days=1)):
                new_streak = curr + 1
                if is_postgres_backend():
                    cursor.execute(
                        "UPDATE user_streak SET current_streak = ?, last_activity = ?, "
                        "highest_streak = GREATEST(highest_streak, ?) WHERE user_id = ?",
                        (new_streak, today, new_streak, user_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE user_streak SET current_streak = ?, last_activity = ?, "
                        "highest_streak = MAX(highest_streak, ?) WHERE user_id = ?",
                        (new_streak, today, new_streak, user_id),
                    )
            else:
                cursor.execute("UPDATE user_streak SET current_streak = 1, last_activity = ? WHERE user_id = ?", (today, user_id))
        conn.commit()
    except Exception as e:
        logging.error(f"Error updating streak: {e}")
    finally:
        conn.close()

def update_xp(user_id: int, amount: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE user_profile SET xp = xp + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
    except Exception as e:
        logging.error(f"Error updating XP: {e}")
    finally:
        conn.close()
