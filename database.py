import sqlite3
import logging
import random
import datetime
import json
import os
import glob
from collections import Counter
from config import DB_PATH, DB_PATH_DEFAULT

LEGACY_DB_NAME = "germanic.db"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def _to_abs_db_path(db_path: str) -> str:
    raw = (db_path or "").strip()
    if not raw:
        return raw
    expanded = os.path.expanduser(raw)
    if os.path.isabs(expanded):
        return expanded
    return os.path.join(PROJECT_ROOT, expanded)


def _resolve_db_name():
    configured = _to_abs_db_path(DB_PATH)
    legacy_db = os.path.join(PROJECT_ROOT, LEGACY_DB_NAME)
    default_db = _to_abs_db_path(DB_PATH_DEFAULT)

    def _words_count(db_path: str):
        if not db_path or not os.path.exists(db_path):
            return -1
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM words")
            count = int(cur.fetchone()[0])
            conn.close()
            return count
        except Exception:
            return 0

    candidates = []
    for path in [configured, legacy_db, default_db]:
        if path and path not in candidates:
            candidates.append(path)

    # Prefer DB files that already contain dictionary data.
    best_with_words = None
    best_count = -1
    for path in candidates:
        count = _words_count(path)
        if count > best_count:
            best_count = count
            best_with_words = path

    if best_count > 0:
        if configured and configured != best_with_words:
            logging.warning(
                "Configured DB_PATH=%s has no words; auto-switching to %s (%s words).",
                configured,
                best_with_words,
                best_count,
            )
        return best_with_words

    # If no populated DB found, keep explicit DB_PATH if provided.
    if configured:
        return configured
    if os.path.exists(legacy_db):
        return legacy_db
    return default_db


def _ensure_db_parent_dir(db_path: str):
    try:
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
    except Exception:
        pass


DB_NAME = _resolve_db_name()
_ensure_db_parent_dir(DB_NAME)


def _safe_words_count(db_path: str) -> int:
    if not db_path or not os.path.exists(db_path):
        return -1
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM words")
        count = int(cur.fetchone()[0])
        conn.close()
        return count
    except Exception:
        return 0


def bootstrap_words_if_empty() -> int:
    """
    Self-heal: if current DB has no words, copy dictionary from best local source.
    Returns imported row count.
    """
    current_count = _safe_words_count(DB_NAME)
    if current_count > 0:
        return 0

    legacy_db = os.path.join(PROJECT_ROOT, LEGACY_DB_NAME)
    default_db = _to_abs_db_path(DB_PATH_DEFAULT)
    backups = sorted(glob.glob(os.path.join(PROJECT_ROOT, "backups", "*.sqlite")), reverse=True)

    source_candidates = []
    for path in [legacy_db, default_db] + backups:
        if path and path != DB_NAME and path not in source_candidates:
            source_candidates.append(path)

    best_source = None
    best_count = 0
    for path in source_candidates:
        cnt = _safe_words_count(path)
        if cnt > best_count:
            best_count = cnt
            best_source = path

    # Case A: Found a populated DB source
    if best_source and best_count > 0:
        src = sqlite3.connect(best_source)
        src.row_factory = sqlite3.Row
        src_cur = src.cursor()
        src_cur.execute(
            "SELECT level, de, uz, pos, plural, example_de, example_uz, category, created_at "
            "FROM words"
        )
        rows = [tuple(r) for r in src_cur.fetchall()]
        src.close()
    else:
        # Case B: No DB source, try JSON seed
        seed_path = os.path.join(PROJECT_ROOT, "data", "dictionary_seed.json")
        if os.path.exists(seed_path):
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    seed_data = json.load(f)
                rows = [
                    (
                        r["level"],
                        r["de"],
                        r["uz"],
                        r.get("pos"),
                        r.get("plural"),
                        r.get("example_de"),
                        r.get("example_uz"),
                        r.get("category"),
                        datetime.datetime.now().isoformat(),
                    )
                    for r in seed_data
                ]
                best_source = "JSON_SEED"
            except Exception as e:
                logging.error("Failed to load JSON seed: %s", e)
                return 0
        else:
            return 0
    if not rows:
        return 0

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO words (level, de, uz, pos, plural, example_de, example_uz, category, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()
    logging.warning(
        "Words table was empty in %s. Restored %s rows from %s.",
        DB_NAME,
        len(rows),
        best_source,
    )
    return len(rows)

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
        ("first_seen_at", "TEXT"),
        ("xp", "INTEGER DEFAULT 0")
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

    # User Mastery (Spaced Repetition System) - Phase 2
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_mastery (
            user_id INTEGER,
            item_id TEXT,
            module TEXT,
            box INTEGER DEFAULT 1,
            next_review DATE,
            last_reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_suspended BOOLEAN DEFAULT 0,
            PRIMARY KEY (user_id, item_id, module)
        )
    """)
    # Index for fast retrieval of due items
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mastery_due ON user_mastery(user_id, next_review)")

    # User Submissions (Speaking/Writing) - Phase 2
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            module TEXT, -- 'writing' or 'speaking'
            level TEXT,
            topic_id TEXT,
            content TEXT, -- Text for writing, file_id for speaking
            feedback_ai TEXT, -- Placeholder for Phase 3
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for checking recent submissions
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_user ON user_submissions(user_id, module)")

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
    daily_lesson_columns_to_add = [
        ("daily_status", "TEXT DEFAULT 'idle'"),
        ("daily_step", "INTEGER DEFAULT 0"),
        ("session_json", "TEXT"),
        ("xp_earned", "INTEGER DEFAULT 0"),
        ("updated_at", "TIMESTAMP")
    ]
    for col_name, col_type in daily_lesson_columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE daily_lesson_log ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass

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

    # Ops error log (Phase: Ops Hardening Foundation)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ops_error_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            severity TEXT,
            where_ctx TEXT,
            user_id INTEGER,
            update_id INTEGER,
            error_type TEXT,
            message_short TEXT
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ops_error_log_ts ON ops_error_log(ts_utc)")

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

def get_words_by_ids(word_ids):
    """Returns a list of word dictionaries for the given IDs."""
    if not word_ids:
        return []
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Use placeholders for the IN clause
    placeholders = ",".join(["?"] * len(word_ids))
    cursor.execute(f"SELECT * FROM words WHERE id IN ({placeholders})", word_ids)
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

def get_daily_lesson_state(user_id, lesson_date=None):
    """
    Returns today's daily lesson state.
    Shape:
    {
      lesson_date, started_at, completed_at,
      daily_status: idle|in_progress|finished,
      daily_step: int,
      session: dict,
      xp_earned: int
    }
    """
    try:
        if not lesson_date:
            lesson_date = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lesson_date, started_at, completed_at, daily_status, daily_step, session_json, xp_earned
            FROM daily_lesson_log
            WHERE user_id = ? AND lesson_date = ?
        """, (user_id, lesson_date))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {
                "lesson_date": lesson_date,
                "started_at": None,
                "completed_at": None,
                "daily_status": "idle",
                "daily_step": 0,
                "session": None,
                "xp_earned": 0
            }
        raw = dict(row)
        session = None
        session_raw = raw.get("session_json")
        if session_raw:
            try:
                session = json.loads(session_raw)
            except Exception:
                session = None
        status = raw.get("daily_status") or "idle"
        if raw.get("completed_at"):
            status = "finished"
        return {
            "lesson_date": raw.get("lesson_date") or lesson_date,
            "started_at": raw.get("started_at"),
            "completed_at": raw.get("completed_at"),
            "daily_status": status,
            "daily_step": int(raw.get("daily_step") or 0),
            "session": session,
            "xp_earned": int(raw.get("xp_earned") or 0)
        }
    except Exception as e:
        logging.error(f"Failed to get daily lesson state: {e}")
        return {
            "lesson_date": lesson_date or datetime.date.today().isoformat(),
            "started_at": None,
            "completed_at": None,
            "daily_status": "idle",
            "daily_step": 0,
            "session": None,
            "xp_earned": 0
        }

def save_daily_lesson_state(
    user_id,
    daily_status,
    daily_step,
    session=None,
    xp_earned=None,
    lesson_date=None,
    ensure_started=False,
    mark_completed=False
):
    """Upserts today's state row for deterministic daily lesson resume."""
    try:
        if not lesson_date:
            lesson_date = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_lesson_log (user_id, lesson_date, started_at, daily_status, daily_step, session_json, xp_earned, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, lesson_date) DO UPDATE SET
                daily_status = excluded.daily_status,
                daily_step = excluded.daily_step,
                session_json = excluded.session_json,
                xp_earned = COALESCE(excluded.xp_earned, daily_lesson_log.xp_earned, 0),
                started_at = CASE
                    WHEN ? = 1 THEN COALESCE(daily_lesson_log.started_at, CURRENT_TIMESTAMP)
                    ELSE daily_lesson_log.started_at
                END,
                completed_at = CASE
                    WHEN ? = 1 THEN COALESCE(daily_lesson_log.completed_at, CURRENT_TIMESTAMP)
                    ELSE daily_lesson_log.completed_at
                END,
                updated_at = CURRENT_TIMESTAMP
        """, (
            user_id,
            lesson_date,
            datetime.datetime.now().isoformat() if ensure_started else None,
            daily_status,
            int(daily_step or 0),
            json.dumps(session) if session is not None else None,
            int(xp_earned or 0) if xp_earned is not None else 0,
            1 if ensure_started else 0,
            1 if mark_completed else 0
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Failed to save daily lesson state: {e}")

def mark_daily_lesson_started(user_id):
    """Creates/updates today's daily lesson entry as started."""
    try:
        today = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_lesson_log (user_id, lesson_date, started_at, daily_status, daily_step, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP, 'in_progress', 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, lesson_date) DO UPDATE SET
                started_at = COALESCE(daily_lesson_log.started_at, CURRENT_TIMESTAMP),
                daily_status = CASE
                    WHEN daily_lesson_log.completed_at IS NOT NULL THEN 'finished'
                    ELSE 'in_progress'
                END,
                daily_step = CASE
                    WHEN daily_lesson_log.daily_step IS NULL OR daily_lesson_log.daily_step = 0 THEN 1
                    ELSE daily_lesson_log.daily_step
                END,
                updated_at = CURRENT_TIMESTAMP
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
                SET completed_at = CURRENT_TIMESTAMP,
                    daily_status = 'finished',
                    daily_step = 6,
                    updated_at = CURRENT_TIMESTAMP
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


def get_last_event_timestamp():
    """Returns latest events.timestamp value as text (or None)."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(timestamp) FROM events")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception:
        return None


def get_admin_stats_snapshot():
    """
    Admin analytics snapshot.
    Safe-by-default: returns best-effort values if some tables/columns are missing.
    """
    snapshot = {
        "total_users": 0,
        "active_users_today": 0,
        "daily_completions_today": 0,
        "daily_completions_last_7_days": 0,
        "total_mistakes_logged": 0,
        "top_weak_topics": []
    }
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) AS c FROM users")
            row = cursor.fetchone()
            snapshot["total_users"] = int(row["c"]) if row else 0
        except Exception:
            snapshot["total_users"] = 0

        active_today = 0
        try:
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) AS c
                FROM daily_lesson_log
                WHERE (
                    started_at IS NOT NULL AND DATE(started_at) = DATE('now')
                ) OR (
                    completed_at IS NOT NULL AND DATE(completed_at) = DATE('now')
                ) OR (
                    lesson_date = DATE('now')
                )
            """)
            row = cursor.fetchone()
            active_today = int(row["c"]) if row else 0
        except Exception:
            active_today = 0
        if active_today == 0:
            try:
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) AS c
                    FROM events
                    WHERE DATE(timestamp) = DATE('now')
                """)
                row = cursor.fetchone()
                active_today = int(row["c"]) if row else 0
            except Exception:
                active_today = 0
        snapshot["active_users_today"] = active_today

        try:
            cursor.execute("""
                SELECT COUNT(*) AS c
                FROM daily_lesson_log
                WHERE lesson_date = DATE('now')
                  AND completed_at IS NOT NULL
            """)
            row = cursor.fetchone()
            snapshot["daily_completions_today"] = int(row["c"]) if row else 0
        except Exception:
            snapshot["daily_completions_today"] = 0

        try:
            cursor.execute("""
                SELECT COUNT(*) AS c
                FROM daily_lesson_log
                WHERE lesson_date >= DATE('now', '-6 day')
                  AND completed_at IS NOT NULL
            """)
            row = cursor.fetchone()
            snapshot["daily_completions_last_7_days"] = int(row["c"]) if row else 0
        except Exception:
            snapshot["daily_completions_last_7_days"] = 0

        try:
            cursor.execute("SELECT COALESCE(SUM(mistake_count), 0) AS c FROM user_mistakes")
            row = cursor.fetchone()
            snapshot["total_mistakes_logged"] = int(row["c"]) if row else 0
        except Exception:
            snapshot["total_mistakes_logged"] = 0

        topic_scores = Counter()
        try:
            cursor.execute("""
                SELECT tags, COALESCE(mistake_count, 1) AS mistake_count
                FROM user_mistakes
                WHERE tags IS NOT NULL
                  AND COALESCE(mastered, 0) = 0
                LIMIT 5000
            """)
            for row in cursor.fetchall():
                raw_tags = row["tags"]
                if not raw_tags:
                    continue
                try:
                    tags_obj = json.loads(raw_tags)
                except Exception:
                    continue
                topic_id = tags_obj.get("topic_id")
                if not topic_id:
                    continue
                topic_scores[topic_id] += int(row["mistake_count"] or 1)
        except Exception:
            pass

        snapshot["top_weak_topics"] = [
            {"topic_id": topic_id, "score": score}
            for topic_id, score in topic_scores.most_common(5)
        ]

        conn.close()
    except Exception as e:
        logging.error(f"Failed to build admin stats snapshot: {e}")
    return snapshot


def log_ops_error(severity, where_ctx, user_id, update_id, error_type, message_short):
    """
    Writes compact ops error records. Must never raise.
    """
    try:
        conn = sqlite3.connect(DB_NAME, timeout=2)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ops_error_log (severity, where_ctx, user_id, update_id, error_type, message_short)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            severity,
            where_ctx,
            user_id,
            update_id,
            error_type,
            (str(message_short)[:280] if message_short is not None else None)
        ))
        conn.commit()
        conn.close()
    except Exception:
        # Never crash request flow due to ops logging failure.
        return


def get_recent_ops_errors(limit=10):
    """
    Returns latest compact ops error records.
    Safe on missing table/schema.
    """
    try:
        safe_limit = max(1, min(int(limit), 50))
    except Exception:
        safe_limit = 10
    try:
        conn = sqlite3.connect(DB_NAME, timeout=2)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ts_utc, severity, where_ctx, user_id, update_id, error_type, message_short
            FROM ops_error_log
            ORDER BY id DESC
            LIMIT ?
        """, (safe_limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []

# --- Spaced Repetition System (SRS) Helpers ---

def get_due_reviews(user_id, limit=20):
    """
    Fetches items due for review based on Spaced Repetition (Leitner).
    Items in box 1 are reviewed daily, box 2 every 3 days, etc.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    today = datetime.date.today().isoformat()
    
    # Priority:
    # 1. Overdue items (next_review <= today)
    # 2. Ordered by box (lowest box first - review "hard" items first)
    cursor.execute("""
        SELECT * FROM user_mastery
        WHERE user_id = ? 
          AND next_review <= ?
          AND is_suspended = 0
        ORDER BY box ASC, next_review ASC
        LIMIT ?
    """, (user_id, today, limit))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_mastery(user_id, item_id, module, is_correct):
    """
    Updates the Leitner box for an item.
    - Correct: Box + 1 (capped at 5), next_review pushed further.
    - Incorrect: Box = 1, next_review = tomorrow.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Intervals in days for boxes 1-5
    intervals = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
    
    # Check current box
    cursor.execute("""
        SELECT box FROM user_mastery 
        WHERE user_id = ? AND item_id = ? AND module = ?
    """, (user_id, str(item_id), module))
    row = cursor.fetchone()
    
    current_box = row[0] if row else 0 # 0 means new
    
    if is_correct:
        # If new (0), start at 1. If 1, go to 2, etc.
        new_box = min(current_box + 1, 5)
        if current_box == 0: new_box = 1
    else:
        new_box = 1 # Reset to start on mistake
        
    days_to_add = intervals.get(new_box, 1)
    next_review = datetime.date.today() + datetime.timedelta(days=days_to_add)
    
    cursor.execute("""
        INSERT INTO user_mastery (user_id, item_id, module, box, next_review, last_reviewed_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, item_id, module) DO UPDATE SET
            box = excluded.box,
            next_review = excluded.next_review,
            last_reviewed_at = CURRENT_TIMESTAMP
    """, (user_id, str(item_id), module, new_box, next_review.isoformat()))
    
    conn.commit()
    conn.close()


# --- Phase 2: User Submissions (Speaking/Writing) ---

def save_user_submission(user_id, module, level, topic_id, content):
    """Saves a user's writing or speaking submission (Phase 2)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_submissions (user_id, module, level, topic_id, content)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, module, level, str(topic_id), str(content)))
    conn.commit()
    conn.close()

def get_mastery_stats(user_id):
    """Returns count of items in each Leitner box."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT box, COUNT(*) FROM user_mastery 
        WHERE user_id = ? GROUP BY box
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return dict(rows)

def get_submission_stats(user_id):
    """Returns count of writing and speaking submissions."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT module, COUNT(*) FROM user_submissions 
        WHERE user_id = ? GROUP BY module
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return dict(rows)

def get_due_review_count(user_id):
    """Returns number of items currently due for SRS review."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today = datetime.date.today().isoformat()
    cursor.execute("""
        SELECT COUNT(*) FROM user_mastery 
        WHERE user_id = ? AND next_review <= ? AND is_suspended = 0
    """, (user_id, today))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_recent_submissions(user_id, limit=5):
    """Retrieves recent user submissions for review (Phase 2)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM user_submissions 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_level_progress_stats(user_id, level):
    """Returns (mastered_count, total_count) for a specific level."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Total words in level
    cursor.execute("SELECT COUNT(*) FROM words WHERE level = ?", (level,))
    res_total = cursor.fetchone()
    total = res_total[0] if res_total else 0
    
    # Mastered words in level (Box 4 or 5)
    cursor.execute("""
        SELECT COUNT(*) FROM user_mastery m
        JOIN words w ON m.item_id = w.id
        WHERE m.user_id = ? AND w.level = ? AND m.module = 'dictionary' AND m.box >= 4
    """, (user_id, level))
    res_mastered = cursor.fetchone()
    mastered = res_mastered[0] if res_mastered else 0
    
    conn.close()
    return mastered, total
