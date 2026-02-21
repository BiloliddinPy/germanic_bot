import logging
import os
import json
from typing import Any
from core.config import settings

# Public API for the database package
from database.repositories.user_repository import (
    add_user as add_user,
    get_or_create_user_profile as get_or_create_user_profile,
    get_user_profile as get_user_profile,
    update_streak as update_streak,
    update_user_profile as update_user_profile,
    update_xp as update_xp,
)
from database.repositories.word_repository import (
    add_word as add_word,
    get_random_words as get_random_words,
    get_total_words_count as get_total_words_count,
    get_words_by_level as get_words_by_level,
)
from database.repositories.progress_repository import (
    log_event as log_event,
    log_mistake as log_mistake,
    record_navigation_event as record_navigation_event,
    update_module_progress as update_module_progress,
)
from database.repositories.session_repository import (
    get_recent_submissions as get_recent_submissions,
    save_user_submission as save_user_submission,
)

__all__ = [
    "DB_NAME",
    "get_connection",
    "create_table",
    "bootstrap_words_if_empty",
    "log_ops_error",
    "add_user",
    "get_or_create_user_profile",
    "get_user_profile",
    "update_streak",
    "update_user_profile",
    "update_xp",
    "add_word",
    "get_random_words",
    "get_total_words_count",
    "get_words_by_level",
    "log_event",
    "log_mistake",
    "record_navigation_event",
    "update_module_progress",
    "get_recent_submissions",
    "save_user_submission",
]

# For backward compatibility
DB_NAME = settings.db_path

def log_ops_error(
    severity: str,
    where_ctx: str,
    error_type: str,
    message_short: str,
    user_id: int | None = None,
    update_id: int | None = None,
):
    """Compatibility wrapper for error logging."""
    metadata: dict[str, Any] = {
        "severity": severity,
        "where": where_ctx,
        "error_type": error_type,
        "message": message_short,
    }
    if update_id:
        metadata["update_id"] = update_id
    log_event(user_id=user_id or 0, event_type="error", metadata=metadata)

def get_connection():
    """Legacy wrapper for backward compatibility."""
    from database.connection import get_connection as core_conn
    return core_conn()

def create_table():
    """Initializes the database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # user_profile
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id INTEGER PRIMARY KEY,
            current_level TEXT DEFAULT 'A1',
            goal TEXT DEFAULT 'general',
            daily_time_minutes INTEGER DEFAULT 15,
            notification_time TEXT DEFAULT '09:00',
            onboarding_completed INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Safely push the notification_time to existing databases
    try:
        cursor.execute("ALTER TABLE user_profile ADD COLUMN notification_time TEXT DEFAULT '09:00'")
    except Exception:
        pass # Column already exists

    
    # words (Dictionary)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            de TEXT,
            uz TEXT,
            level TEXT,
            pos TEXT,
            example_de TEXT,
            example_uz TEXT,
            category TEXT,
            plural TEXT
        )
    """)
    
    # user_streak
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_streak (
            user_id INTEGER PRIMARY KEY,
            current_streak INTEGER DEFAULT 0,
            last_activity DATE,
            highest_streak INTEGER DEFAULT 0
        )
    """)
    
    # user_mastery (SRS)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_mastery (
            user_id INTEGER,
            item_id INTEGER,
            box INTEGER DEFAULT 0,
            next_review TIMESTAMP,
            last_reviewed TIMESTAMP,
            PRIMARY KEY (user_id, item_id)
        )
    """)
    
    # daily_plans
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_data TEXT,
            created_at DATE DEFAULT CURRENT_DATE
        )
    """)
    
    # daily_lesson_sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_lesson_sessions (
            user_id INTEGER PRIMARY KEY,
            session_data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ui_state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ui_state (
            user_id INTEGER,
            key TEXT,
            val TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, key)
        )
    """)
    
    # navigation_logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS navigation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            section_name TEXT,
            level TEXT,
            entry_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # user_progress
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER,
            module_name TEXT,
            level TEXT,
            completion_status INTEGER DEFAULT 0,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, module_name, level)
        )
    """)

    # user_mistakes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_mistakes (
            user_id INTEGER,
            item_id TEXT,
            module TEXT,
            mistake_type TEXT,
            mistake_count INTEGER DEFAULT 0,
            last_mistake_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mastered INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, item_id, module)
        )
    """)

    # quiz_results
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            level TEXT,
            score INTEGER,
            total INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # grammar_progress
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grammar_progress (
            user_id INTEGER,
            topic_id TEXT,
            level TEXT,
            seen_count INTEGER DEFAULT 0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, topic_id)
        )
    """)

    # event_logs (for grammar, daily, etc tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT,
            section_name TEXT,
            level TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def bootstrap_words_if_empty():
    """Loads initial data if the words table is empty."""
    
    # Check if we already have data
    if get_total_words_count("A1") > 0:
        return 0
    
    seed_path = os.path.join("data", "dictionary_seed.json")
    if not os.path.exists(seed_path):
        logging.error(f"Seed file not found: {seed_path}")
        return 0
        
    logging.info("Seeding dictionary data...")
    try:
        with open(seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        conn = get_connection()
        cursor = conn.cursor()
        
        # Batch insert for performance
        batch_size = 500
        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            cursor.executemany("""
                INSERT INTO words (level, de, uz, pos, plural, example_de, example_uz, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    item.get("level"),
                    item.get("de"),
                    item.get("uz"),
                    item.get("pos"),
                    item.get("plural"),
                    item.get("example_de"),
                    item.get("example_uz"),
                    item.get("category")
                ) for item in batch
            ])
        
        conn.commit()
        conn.close()
        logging.info(f"Successfully seeded {len(data)} words.")
        return len(data)
    except Exception as e:
        logging.exception(f"Error seeding database: {e}")
        return 0
