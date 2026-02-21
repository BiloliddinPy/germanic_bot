from database.connection import get_connection
import datetime
import logging


def _coerce_int_list(rows):
    ids = []
    for row in rows:
        try:
            ids.append(int(row[0]))
        except Exception:
            continue
    return ids


def get_due_reviews(user_id: int, level: str | None = None, limit: int = 20):
    conn = get_connection()
    cursor = conn.cursor()
    if level:
        cursor.execute("""
            SELECT m.item_id FROM user_mastery m
            JOIN words w ON CAST(w.id AS TEXT) = CAST(m.item_id AS TEXT)
            WHERE m.user_id = ? AND w.level = ? AND m.next_review <= CURRENT_TIMESTAMP
            ORDER BY m.next_review ASC
            LIMIT ?
        """, (user_id, level, limit))
    else:
        cursor.execute("""
            SELECT item_id FROM user_mastery 
            WHERE user_id = ? AND next_review <= CURRENT_TIMESTAMP
            ORDER BY next_review ASC
            LIMIT ?
        """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def update_mastery(user_id: int, item_id: int, is_correct: bool):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Simple SRS: 1, 3, 7, 14, 30 days
    intervals = [0, 1, 3, 7, 14, 30, 90]
    
    cursor.execute("SELECT box FROM user_mastery WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    row = cursor.fetchone()
    
    current_box = row[0] if row else 0
    if is_correct:
        new_box = min(current_box + 1, len(intervals) - 1)
    else:
        new_box = max(current_box - 1, 0)
        
    days = intervals[new_box]
    next_review = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        cursor.execute("""
            INSERT INTO user_mastery (user_id, item_id, box, next_review)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, item_id) DO UPDATE SET
                box = excluded.box,
                next_review = excluded.next_review,
                last_reviewed = CURRENT_TIMESTAMP
        """, (user_id, item_id, new_box, next_review))
        conn.commit()
    except Exception as e:
        logging.error(f"Error updating mastery for {user_id}/{item_id}: {e}")
    finally:
        conn.close()

def get_level_progress_stats(user_id: int, level: str):
    """Calculates mastered words vs total words for a level."""
    from database.repositories.word_repository import get_total_words_count
    total = get_total_words_count(level)
    
    conn = get_connection()
    cursor = conn.cursor()
    # Mastery defined as box >= 4 (arbitrary senior standard)
    cursor.execute("""
        SELECT COUNT(*) FROM user_mastery m
        JOIN words w ON CAST(w.id AS TEXT) = CAST(m.item_id AS TEXT)
        WHERE m.user_id = ? AND w.level = ? AND m.box >= 4
    """, (user_id, level))
    mastered = cursor.fetchone()[0]
    conn.close()
    
    return mastered, total

def get_weighted_mistake_word_ids(user_id: int, level: str | None = None, limit: int = 20):
    conn = get_connection()
    cursor = conn.cursor()
    if level:
        cursor.execute("""
            SELECT m.item_id FROM user_mistakes m
            JOIN words w ON CAST(w.id AS TEXT) = m.item_id
            WHERE m.user_id = ? AND w.level = ? AND m.module = 'vocab' AND m.mastered = 0
            ORDER BY m.mistake_count DESC, m.last_mistake_at DESC
            LIMIT ?
        """, (user_id, level, limit))
    else:
        cursor.execute("""
            SELECT item_id FROM user_mistakes 
            WHERE user_id = ? AND module = 'vocab' AND mastered = 0
            ORDER BY mistake_count DESC, last_mistake_at DESC
            LIMIT ?
        """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return _coerce_int_list(rows)

def get_mastered_mistake_word_ids(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item_id FROM user_mistakes WHERE user_id = ? AND mastered = 1", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return _coerce_int_list(rows)
