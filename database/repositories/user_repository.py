from database.connection import get_connection
import logging

def add_user(user_id: int, full_name: str, username: str = None):
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
        cursor.execute("INSERT OR IGNORE INTO user_profile (user_id) VALUES (?)", (user_id,))
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
        from datetime import datetime
        created_at = datetime.strptime(row[0].split(".")[0], "%Y-%m-%d %H:%M:%S")
        delta = datetime.now() - created_at
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
