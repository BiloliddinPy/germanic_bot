import sqlite3
import logging
import random
import datetime
import json

DB_NAME = "germanic.db"

def create_table():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            daily_sub BOOLEAN DEFAULT 1
        )
    """)
    
    # Dictionary Progress
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dictionary_progress (
            user_id INTEGER,
            level TEXT,
            offset INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, level)
        )
    """)
    
    # Quiz Stats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            level TEXT,
            score INTEGER,
            total INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Feedback/Contact Messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Words Table (The core dictionary)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL, 
            de TEXT NOT NULL,
            uz TEXT NOT NULL,
            pos TEXT,               
            plural TEXT,            
            example_de TEXT,        
            example_uz TEXT,        
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- EdTech Features ---
    
    # User Profile (Step 1)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id INTEGER PRIMARY KEY,
            goal TEXT DEFAULT 'general',
            daily_target INTEGER DEFAULT 15,
            timezone TEXT DEFAULT 'UTC',
            onboarding_completed BOOLEAN DEFAULT 0,
            current_level TEXT DEFAULT 'A1',
            target_level TEXT,
            learning_goal TEXT,
            daily_time_minutes INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration: Add missing columns to user_profile if they don't exist
    columns_to_add = [
        ("target_level", "TEXT"),
        ("learning_goal", "TEXT"),
        ("daily_time_minutes", "INTEGER"),
        ("timezone", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
        ("first_seen_at", "TEXT")
    ]
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE user_profile ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass # Column already exists

    try:
        cursor.execute("UPDATE user_profile SET first_seen_at = COALESCE(first_seen_at, created_at, CURRENT_TIMESTAMP)")
    except sqlite3.OperationalError:
        pass

    # User Progress (Step 1)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            module TEXT,
            level TEXT,
            completed_items INTEGER DEFAULT 0,
            total_items INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Backward-compatible migration for user_progress column names
    progress_columns_to_add = [
        ("attempted_count", "INTEGER DEFAULT 0"),
        ("completed_count", "INTEGER DEFAULT 0")
    ]
    for col_name, col_type in progress_columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE user_progress ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass
    try:
        cursor.execute("UPDATE user_progress SET attempted_count = COALESCE(attempted_count, total_items, 0)")
        cursor.execute("UPDATE user_progress SET completed_count = COALESCE(completed_count, completed_items, 0)")
    except sqlite3.OperationalError:
        pass

    # User Streak (Step 1)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_streak (
            user_id INTEGER PRIMARY KEY,
            last_active_date DATE,
            current_streak INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0
        )
    """)

    # User Mistakes (Step 1)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id TEXT,
            module TEXT,
            level TEXT,
            mistake_count INTEGER DEFAULT 1,
            success_count INTEGER DEFAULT 0,
            mastered BOOLEAN DEFAULT 0,
            last_mistake_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tags TEXT
        )
    """)
    # Backward-compatible migration for new mistake tracking fields
    mistake_columns_to_add = [
        ("success_count", "INTEGER DEFAULT 0"),
        ("mastered", "BOOLEAN DEFAULT 0")
    ]
    for col_name, col_type in mistake_columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE user_mistakes ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass

    # Navigation Event Logging (Foundation Day 1)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            event_name TEXT,
            section_name TEXT,
            level TEXT,
            metadata TEXT
        )
    """)

    # UI state cache (message de-duplication for menu/start screens)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_ui_state (
            user_id INTEGER,
            state_key TEXT,
            state_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, state_key)
        )
    """)

    # Daily Lesson per-day status (Day 5)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_lesson_log (
            user_id INTEGER,
            lesson_date DATE,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            PRIMARY KEY (user_id, lesson_date)
        )
    """)

    # Daily plan cache (Day 6)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_daily_plan (
            user_id INTEGER,
            plan_date DATE,
            plan_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, plan_date)
        )
    """)

    # Daily plan audit (Day 7/8 prep)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_plan_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_date DATE,
            event TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Grammar topic coverage (Day 6)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_grammar_coverage (
            user_id INTEGER,
            topic_id TEXT,
            level TEXT,
            seen_count INTEGER DEFAULT 0,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, topic_id)
        )
    """)

    # Writing task completion hook (Day 7)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS writing_task_log (
            user_id INTEGER,
            task_date DATE,
            level TEXT,
            topic_id TEXT,
            task_type TEXT,
            status TEXT DEFAULT 'completed_self',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, task_date)
        )
    """)
    
    # Indexes for speed
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_level ON words(level)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_de ON words(de)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_lesson_user_date ON daily_lesson_log(user_id, lesson_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_plan_user_date ON user_daily_plan(user_id, plan_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_plan_audit_user_date ON daily_plan_audit(user_id, plan_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_grammar_coverage_user_level ON user_grammar_coverage(user_id, level)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_writing_task_user_date ON writing_task_log(user_id, task_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ui_state_user_key ON user_ui_state(user_id, state_key)")

    conn.commit()
    conn.close()
    logging.info("Germanic DB tables created/verified.")

# --- Content Management ---

def add_word(level, de, uz, pos=None, plural=None, example_de=None, example_uz=None, category=None):
    """Adds a word to the dictionary. Updates if exists (based on German word)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check if exists to avoid duplicates (simple check)
    cursor.execute("SELECT id FROM words WHERE de = ? AND level = ?", (de, level))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("""
            UPDATE words SET uz=?, pos=?, plural=?, example_de=?, example_uz=?, category=?
            WHERE id=?
        """, (uz, pos, plural, example_de, example_uz, category, existing[0]))
    else:
        cursor.execute("""
            INSERT INTO words (level, de, uz, pos, plural, example_de, example_uz, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (level, de, uz, pos, plural, example_de, example_uz, category))
        
    conn.commit()
    conn.close()

def get_words_by_level(level, limit=20, offset=0):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Access by column name
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM words 
        WHERE level = ? 
        ORDER BY de COLLATE NOCASE
        LIMIT ? OFFSET ?
    """, (level, limit, offset))
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows] # Convert to dict list

def get_words_by_level_and_letter(level, letter, limit=20, offset=0):
    """Get words filtered by level and starting letter."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Filter by first character of 'de' field (case-insensitive)
    cursor.execute("""
        SELECT * FROM words 
        WHERE level = ? AND LOWER(SUBSTR(de, 1, 1)) = LOWER(?)
        LIMIT ? OFFSET ?
    """, (level, letter, limit, offset))
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

def get_total_words_count(level):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM words WHERE level = ?", (level,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_words_count_by_letter(level, letter):
    """Get count of words filtered by level and starting letter."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM words 
        WHERE level = ? AND LOWER(SUBSTR(de, 1, 1)) = LOWER(?)
    """, (level, letter))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def search_words(level, query, limit=20):
    """Search words in both German (de) and Uzbek (uz) fields."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM words 
        WHERE level = ? AND (de LIKE ? OR uz LIKE ?)
        ORDER BY de COLLATE NOCASE
        LIMIT ?
    """, (level, f"%{query}%", f"%{query}%", limit))
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

def get_random_words(level, limit=4):
    """Fetches random words for Quiz"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM words WHERE level = ? ORDER BY RANDOM() LIMIT ?", (level, limit))
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

# --- User Management ---

def add_user(user_id, full_name, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name, username) VALUES (?, ?, ?)", 
                   (user_id, full_name, username))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def get_subscribed_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE daily_sub = 1")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def update_dictionary_progress(user_id, level, offset):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dictionary_progress (user_id, level, offset) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, level) DO UPDATE SET offset=?
    """, (user_id, level, offset, offset))
    conn.commit()
    conn.close()

def get_dictionary_progress(user_id, level):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT offset FROM dictionary_progress WHERE user_id=? AND level=?", (user_id, level))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_quiz_result(user_id, level, score, total):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO quiz_stats (user_id, level, score, total) VALUES (?, ?, ?, ?)",
                   (user_id, level, score, total))
    conn.commit()
    conn.close()

# --- EdTech Feature Helpers ---

def get_user_profile(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profile WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_user_profile(user_id, **kwargs):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Ensure profile exists
    cursor.execute("INSERT OR IGNORE INTO user_profile (user_id) VALUES (?)", (user_id,))
    cursor.execute("""
        UPDATE user_profile
        SET first_seen_at = COALESCE(first_seen_at, CURRENT_TIMESTAMP),
            created_at = COALESCE(created_at, CURRENT_TIMESTAMP)
        WHERE user_id = ?
    """, (user_id,))
    
    # Foundation Day 2 mapping: Ensure new names are synced with old ones for backward compatibility
    if 'learning_goal' in kwargs:
        kwargs['goal'] = kwargs['learning_goal']
    elif 'goal' in kwargs:
        kwargs['learning_goal'] = kwargs['goal']
        
    if 'daily_time_minutes' in kwargs:
        kwargs['daily_target'] = kwargs['daily_time_minutes']
    elif 'daily_target' in kwargs:
        kwargs['daily_time_minutes'] = kwargs['daily_target']

    kwargs['updated_at'] = datetime.datetime.now().isoformat()
    
    if kwargs:
        columns = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(user_id)
        cursor.execute(f"UPDATE user_profile SET {columns} WHERE user_id = ?", values)
        
    conn.commit()
    conn.close()

def get_or_create_user_profile(user_id):
    """Fetches user profile, creating it if it doesn't exist (Day 2)."""
    profile = get_user_profile(user_id)
    if not profile:
        update_user_profile(user_id)
        profile = get_user_profile(user_id)
    return profile

def update_streak(user_id):
    """Updates the user streak based on activity."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    cursor.execute("SELECT last_active_date, current_streak, best_streak FROM user_streak WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("INSERT INTO user_streak (user_id, last_active_date, current_streak, best_streak) VALUES (?, ?, 1, 1)",
                       (user_id, today))
    else:
        last_active, current, best = row
        last_active_date = datetime.datetime.strptime(last_active, '%Y-%m-%d').date() if isinstance(last_active, str) else last_active
        
        if last_active_date == today:
            pass # Already updated today
        elif last_active_date == yesterday:
            current += 1
            if current > best:
                best = current
            cursor.execute("UPDATE user_streak SET last_active_date = ?, current_streak = ?, best_streak = ? WHERE user_id = ?",
                           (today, current, best, user_id))
        else:
            # Streak broken
            cursor.execute("UPDATE user_streak SET last_active_date = ?, current_streak = 1 WHERE user_id = ?",
                           (today, user_id))
            
    conn.commit()
    conn.close()

def log_mistake(user_id, item_id, module, level, tags=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, mistake_count FROM user_mistakes 
        WHERE user_id = ? AND item_id = ? AND module = ? AND level = ?
    """, (user_id, str(item_id), module, level))
    row = cursor.fetchone()
    
    if row:
        cursor.execute("""
            UPDATE user_mistakes
            SET mistake_count = mistake_count + 1,
                mastered = 0,
                last_mistake_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (row[0],))
    else:
        cursor.execute("""
            INSERT INTO user_mistakes (user_id, item_id, module, level, tags) 
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, str(item_id), module, level, tags))
        
    conn.commit()
    conn.close()

def resolve_mistake(user_id, item_id, module):
    """Reduces mistake weight and tracks mastery without deleting rows."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, mistake_count, COALESCE(success_count, 0) FROM user_mistakes 
        WHERE user_id = ? AND item_id = ? AND module = ?
    """, (user_id, str(item_id), module))
    row = cursor.fetchone()
    
    if row:
        m_id, count, success_count = row
        new_count = max((count or 0) - 1, 0)
        new_success = (success_count or 0) + 1
        mastered = 1 if (new_success >= 2 and new_count == 0) else 0
        cursor.execute("""
            UPDATE user_mistakes
            SET mistake_count = ?,
                success_count = ?,
                mastered = ?,
                last_mistake_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_count, new_success, mastered, m_id))
            
    conn.commit()
    conn.close()

def update_module_progress(user_id, module, level, completed=False):
    """Tracks attempts and completions for specific modules (Day 3)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, attempted_count, completed_count FROM user_progress
            WHERE user_id = ? AND module = ? AND level = ?
        """, (user_id, module, level))
        row = cursor.fetchone()

        if not row:
            cursor.execute("""
                INSERT INTO user_progress (user_id, module, level, attempted_count, completed_count)
                VALUES (?, ?, ?, 1, ?)
            """, (user_id, module, level, 1 if completed else 0))
        else:
            p_id, att, comp = row
            new_att = (att or 0) + 1
            new_comp = (comp or 0) + (1 if completed else 0)
            cursor.execute("""
                UPDATE user_progress SET attempted_count = ?, completed_count = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_att, new_comp, p_id))
    except sqlite3.OperationalError:
        # Legacy schema fallback (completed_items / total_items)
        cursor.execute("""
            SELECT id, total_items, completed_items FROM user_progress
            WHERE user_id = ? AND module = ? AND level = ?
        """, (user_id, module, level))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO user_progress (user_id, module, level, total_items, completed_items)
                VALUES (?, ?, ?, 1, ?)
            """, (user_id, module, level, 1 if completed else 0))
        else:
            p_id, total_items, completed_items = row
            new_total = (total_items or 0) + 1
            new_completed = (completed_items or 0) + (1 if completed else 0)
            cursor.execute("""
                UPDATE user_progress SET total_items = ?, completed_items = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_total, new_completed, p_id))

    conn.commit()
    conn.close()

def get_user_progress_summary(user_id):
    """Returns a dictionary of user progress across all modules (Day 3)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Per-module stats
    try:
        cursor.execute("""
            SELECT module, SUM(attempted_count) as attempts, SUM(completed_count) as completions
            FROM user_progress WHERE user_id = ? GROUP BY module
        """, (user_id,))
        module_stats = [dict(r) for r in cursor.fetchall()]
    except sqlite3.OperationalError:
        cursor.execute("""
            SELECT module, SUM(total_items) as attempts, SUM(completed_items) as completions
            FROM user_progress WHERE user_id = ? GROUP BY module
        """, (user_id,))
        module_stats = [dict(r) for r in cursor.fetchall()]
    
    # Streak
    cursor.execute("SELECT current_streak, best_streak FROM user_streak WHERE user_id = ?", (user_id,))
    streak_row = cursor.fetchone()
    streak = dict(streak_row) if streak_row else {"current_streak": 0, "best_streak": 0}
    
    conn.close()
    return {
        "modules": module_stats,
        "streak": streak
    }

def get_user_mistakes_overview(user_id):
    """Returns top mistakes and total count (Day 3)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM user_mistakes
        WHERE user_id = ?
          AND COALESCE(mistake_count, 0) > 0
          AND COALESCE(mastered, 0) = 0
    """, (user_id,))
    total = cursor.fetchone()['total']
    
    cursor.execute("""
        SELECT * FROM user_mistakes 
        WHERE user_id = ?
          AND COALESCE(mistake_count, 0) > 0
          AND COALESCE(mastered, 0) = 0
        ORDER BY mistake_count DESC, last_mistake_at DESC 
        LIMIT 10
    """, (user_id,))
    top_mistakes = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return {
        "total_mistakes": total,
        "top_mistakes": top_mistakes
    }

def log_event(user_id, event_name, section_name=None, level=None, metadata=None):
    """Safely logs navigation and interaction events (Foundation Day 1)."""
    try:
        import json
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events (user_id, event_name, section_name, level, metadata) 
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, event_name, section_name, level, json.dumps(metadata) if metadata else None))
        conn.commit()
        conn.close()
    except Exception as e:
        import logging
        logging.error(f"Failed to log event: {e}")

def record_navigation_event(user_id, section_name, level=None, entry_type="menu"):
    """Specific wrapper for navigation tracking (Day 2)."""
    log_event(user_id, "navigation_entry", section_name=section_name, level=level, metadata={"entry_type": entry_type})

def get_ui_state(user_id, state_key):
    """Returns stored UI state value for user/key."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT state_value
            FROM user_ui_state
            WHERE user_id = ? AND state_key = ?
        """, (user_id, state_key))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logging.error(f"Failed to read ui state: {e}")
        return None

def set_ui_state(user_id, state_key, state_value):
    """Upserts UI state value for user/key."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_ui_state (user_id, state_key, state_value)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, state_key) DO UPDATE SET
                state_value = excluded.state_value,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, state_key, str(state_value)))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Failed to write ui state: {e}")

def mark_daily_lesson_started(user_id):
    """Creates/updates today's daily lesson entry as started."""
    try:
        today = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_lesson_log (user_id, lesson_date, started_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, lesson_date) DO UPDATE SET
                started_at = COALESCE(daily_lesson_log.started_at, CURRENT_TIMESTAMP)
        """, (user_id, today))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Failed to mark daily lesson start: {e}")

def mark_daily_lesson_completed(user_id):
    """
    Marks completion once per day and updates streak.
    Returns: {completed_now, streak, streak_reset}
    """
    result = {
        "completed_now": False,
        "streak": {"current_streak": 0, "best_streak": 0},
        "streak_reset": False
    }
    try:
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        today_str = today.isoformat()

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO daily_lesson_log (user_id, lesson_date, started_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (user_id, today_str))
        cursor.execute("""
            SELECT completed_at FROM daily_lesson_log
            WHERE user_id = ? AND lesson_date = ?
        """, (user_id, today_str))
        row = cursor.fetchone()
        cursor.execute("SELECT last_active_date FROM user_streak WHERE user_id = ?", (user_id,))
        streak_before = cursor.fetchone()
        conn.commit()
        conn.close()

        if not row or not row[0]:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE daily_lesson_log
                SET completed_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND lesson_date = ? AND completed_at IS NULL
            """, (user_id, today_str))
            conn.commit()
            conn.close()
            result["completed_now"] = True
            update_streak(user_id)

        if streak_before and streak_before[0]:
            last_active = datetime.datetime.strptime(streak_before[0], '%Y-%m-%d').date() if isinstance(streak_before[0], str) else streak_before[0]
            if last_active < yesterday:
                result["streak_reset"] = True

        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT current_streak, best_streak FROM user_streak WHERE user_id = ?", (user_id,))
        streak_row = cursor.fetchone()
        conn.close()
        if streak_row:
            result["streak"] = dict(streak_row)
    except Exception as e:
        logging.error(f"Failed to mark daily lesson completion: {e}")
    return result

def get_daily_lesson_completion_rate(user_id, days=7):
    """Returns integer completion percent for last N days."""
    try:
        if days <= 0:
            return 0
        since = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM daily_lesson_log
            WHERE user_id = ? AND lesson_date >= ? AND completed_at IS NOT NULL
        """, (user_id, since))
        completed_days = cursor.fetchone()[0]
        conn.close()
        return int((completed_days / days) * 100)
    except Exception as e:
        logging.error(f"Failed to get completion rate: {e}")
        return 0

def get_daily_lesson_nudges(user_id):
    """Returns daily lesson nudge state for current user interaction."""
    result = {"started_not_finished_today": False, "skipped_day": False}
    try:
        today = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT started_at, completed_at FROM daily_lesson_log
            WHERE user_id = ? AND lesson_date = ?
        """, (user_id, today))
        today_row = cursor.fetchone()
        if today_row and today_row[0] and not today_row[1]:
            result["started_not_finished_today"] = True

        cursor.execute("""
            SELECT lesson_date FROM daily_lesson_log
            WHERE user_id = ? AND completed_at IS NOT NULL
            ORDER BY lesson_date DESC LIMIT 1
        """, (user_id,))
        last_completed = cursor.fetchone()
        conn.close()

        if last_completed and last_completed[0] not in (today, yesterday):
            result["skipped_day"] = True
    except Exception as e:
        logging.error(f"Failed to compute nudges: {e}")
    return result

def get_days_since_first_use(user_id):
    """Returns days since first_seen_at (min 0)."""
    try:
        profile = get_user_profile(user_id)
        if not profile:
            return 0
        first_seen = profile.get("first_seen_at") or profile.get("created_at")
        if not first_seen:
            return 0
        first_dt = datetime.datetime.fromisoformat(str(first_seen).replace("Z", "+00:00"))
        return max((datetime.datetime.now() - first_dt).days, 0)
    except Exception:
        return 0

def get_cached_daily_plan(user_id, plan_date=None):
    """Returns cached daily plan object for given date."""
    try:
        if not plan_date:
            plan_date = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plan_json FROM user_daily_plan
            WHERE user_id = ? AND plan_date = ?
        """, (user_id, plan_date))
        row = cursor.fetchone()
        conn.close()
        if not row or not row[0]:
            return None
        return json.loads(row[0])
    except Exception as e:
        logging.error(f"Failed to get cached daily plan: {e}")
        return None

def get_last_daily_plan(user_id, before_date=None):
    """Returns last cached daily plan before given date (defaults to today)."""
    try:
        if not before_date:
            before_date = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plan_json, plan_date
            FROM user_daily_plan
            WHERE user_id = ? AND plan_date < ?
            ORDER BY plan_date DESC
            LIMIT 1
        """, (user_id, before_date))
        row = cursor.fetchone()
        conn.close()
        if not row or not row[0]:
            return None
        return {"plan": json.loads(row[0]), "plan_date": row[1]}
    except Exception as e:
        logging.error(f"Failed to get last daily plan: {e}")
        return None

def save_daily_plan(user_id, plan_obj, plan_date=None):
    """Upserts daily plan cache for user/date."""
    try:
        if not plan_date:
            plan_date = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_daily_plan (user_id, plan_date, plan_json)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, plan_date) DO UPDATE SET
                plan_json = excluded.plan_json
        """, (user_id, plan_date, json.dumps(plan_obj)))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Failed to save daily plan: {e}")

def log_daily_plan_audit(user_id, event, metadata=None, plan_date=None):
    """Audit trail for daily plan generation/reuse decisions."""
    try:
        if not plan_date:
            plan_date = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_plan_audit (user_id, plan_date, event, metadata)
            VALUES (?, ?, ?, ?)
        """, (user_id, plan_date, event, json.dumps(metadata) if metadata else None))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Failed to log daily plan audit: {e}")

def get_latest_daily_plan_audit(user_id, days=7):
    """Returns latest daily plan audit row for user as dict."""
    try:
        since = (datetime.date.today() - datetime.timedelta(days=max(days - 1, 0))).isoformat()
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plan_date, event, metadata, created_at
            FROM daily_plan_audit
            WHERE user_id = ? AND plan_date >= ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id, since))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        result = dict(row)
        try:
            result["metadata"] = json.loads(result.get("metadata")) if result.get("metadata") else {}
        except Exception:
            result["metadata"] = {}
        return result
    except Exception as e:
        logging.error(f"Failed to get latest daily plan audit: {e}")
        return None

def mark_grammar_topic_seen(user_id, topic_id, level):
    """Tracks grammar topic exposure for adaptive topic rotation."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_grammar_coverage (user_id, topic_id, level, seen_count, last_seen_at)
            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, topic_id) DO UPDATE SET
                seen_count = seen_count + 1,
                last_seen_at = CURRENT_TIMESTAMP
        """, (user_id, topic_id, level))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Failed to mark grammar topic seen: {e}")

def get_grammar_coverage_map(user_id, level):
    """Returns topic_id -> seen_count map for level."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT topic_id, seen_count
            FROM user_grammar_coverage
            WHERE user_id = ? AND level = ?
        """, (user_id, level))
        rows = cursor.fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception as e:
        logging.error(f"Failed to get grammar coverage: {e}")
        return {}

def get_weighted_mistake_word_ids(user_id, level, limit=20):
    """
    Returns mistake word IDs ranked by weighted priority.
    Weight = mistake_count * recency_factor.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT item_id, mistake_count, last_mistake_at
            FROM user_mistakes
            WHERE user_id = ?
              AND level = ?
              AND item_id GLOB '[0-9]*'
              AND COALESCE(mistake_count, 0) > 0
              AND COALESCE(mastered, 0) = 0
              AND module IN ('quiz_test', 'daily_quiz', 'daily_warmup', 'review_session')
            ORDER BY last_mistake_at DESC
            LIMIT 200
        """, (user_id, level))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        now = datetime.datetime.now()
        scored = {}
        for r in rows:
            try:
                item_id = int(r["item_id"])
            except Exception:
                continue
            count = int(r.get("mistake_count") or 1)
            last_raw = r.get("last_mistake_at")
            recency_factor = 1.0
            if last_raw:
                try:
                    last_dt = datetime.datetime.fromisoformat(str(last_raw).replace("Z", "+00:00"))
                except Exception:
                    try:
                        last_dt = datetime.datetime.strptime(str(last_raw), "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        last_dt = now
                days = max((now - last_dt).days, 0)
                if days <= 2:
                    recency_factor = 1.5
                elif days <= 7:
                    recency_factor = 1.2
            score = count * recency_factor
            scored[item_id] = max(scored.get(item_id, 0), score)

        ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
        return [item_id for item_id, _ in ranked[:limit]]
    except Exception as e:
        logging.error(f"Failed to get weighted mistake IDs: {e}")
        return []

def get_mastered_mistake_word_ids(user_id, level, limit=200):
    """Returns mastered word IDs to de-prioritize in future plans."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT item_id
            FROM user_mistakes
            WHERE user_id = ?
              AND level = ?
              AND item_id GLOB '[0-9]*'
              AND COALESCE(mastered, 0) = 1
            ORDER BY last_mistake_at DESC
            LIMIT ?
        """, (user_id, level, limit))
        rows = cursor.fetchall()
        conn.close()
        return [int(r[0]) for r in rows]
    except Exception as e:
        logging.error(f"Failed to get mastered mistake IDs: {e}")
        return []

def get_recent_topic_mistake_scores(user_id, level, days=14, limit=3):
    """
    Returns top weak topic IDs from mistake tags.
    Expected tag format: JSON with {"topic_id": "..."}.
    """
    try:
        since = (datetime.datetime.now() - datetime.timedelta(days=max(days, 1))).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tags, mistake_count, last_mistake_at
            FROM user_mistakes
            WHERE user_id = ?
              AND level = ?
              AND COALESCE(mistake_count, 0) > 0
              AND COALESCE(mastered, 0) = 0
              AND tags IS NOT NULL
              AND last_mistake_at >= ?
            ORDER BY last_mistake_at DESC
            LIMIT 500
        """, (user_id, level, since))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        now = datetime.datetime.now()
        topic_scores = {}
        for r in rows:
            tags_raw = r.get("tags")
            if not tags_raw:
                continue
            topic_id = None
            try:
                tags_obj = json.loads(tags_raw)
                topic_id = tags_obj.get("topic_id")
            except Exception:
                continue
            if not topic_id:
                continue

            count = int(r.get("mistake_count") or 1)
            recency_factor = 1.0
            last_raw = r.get("last_mistake_at")
            if last_raw:
                try:
                    last_dt = datetime.datetime.fromisoformat(str(last_raw).replace("Z", "+00:00"))
                except Exception:
                    try:
                        last_dt = datetime.datetime.strptime(str(last_raw), "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        last_dt = now
                age_days = max((now - last_dt).days, 0)
                if age_days <= 2:
                    recency_factor = 1.5
                elif age_days <= 7:
                    recency_factor = 1.2
            topic_scores[topic_id] = topic_scores.get(topic_id, 0.0) + (count * recency_factor)

        ranked = sorted(topic_scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:limit]
    except Exception as e:
        logging.error(f"Failed to get topic mistake scores: {e}")
        return []

def mark_writing_task_completed(user_id, level, topic_id, task_type, task_date=None):
    """Stores writing task completion hook for future AI scoring."""
    try:
        if not task_date:
            task_date = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO writing_task_log (user_id, task_date, level, topic_id, task_type, status)
            VALUES (?, ?, ?, ?, ?, 'completed_self')
            ON CONFLICT(user_id, task_date) DO UPDATE SET
                level = excluded.level,
                topic_id = excluded.topic_id,
                task_type = excluded.task_type,
                status = excluded.status
        """, (user_id, task_date, level, topic_id, task_type))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Failed to mark writing task completed: {e}")
