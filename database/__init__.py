import sqlite3
import logging
import os
from core.config import settings

# For backward compatibility
DB_NAME = settings.db_path

def log_ops_error(severity: str, where_ctx: str, error_type: str, message_short: str, user_id: int = None, update_id: int = None):
    """Compatibility wrapper for error logging."""
    from database.repositories.progress_repository import log_event
    metadata = {"severity": severity, "where": where_ctx, "error_type": error_type, "message": message_short}
    if update_id:
        metadata["update_id"] = update_id
    log_event(user_id=user_id or 0, event_type="error", metadata=metadata)

# Public API for the database package
from database.repositories.user_repository import add_user, get_user_profile, get_or_create_user_profile, update_user_profile, update_streak, update_xp
from database.repositories.word_repository import get_words_by_level, get_total_words_count, get_random_words, add_word
from database.repositories.progress_repository import record_navigation_event, log_mistake, log_event, update_module_progress
from database.repositories.session_repository import save_user_submission, get_recent_submissions

# For backward compatibility
DB_NAME = settings.db_path

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
            onboarding_completed INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
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
    
    conn.commit()
    conn.close()

def bootstrap_words_if_empty():
    """Loads initial data if the words table is empty."""
    from database.repositories.word_repository import get_total_words_count
    if get_total_words_count("A1") > 0:
        return 0
    
    logging.warning("Words table is empty and needs data import.")
    return 0
