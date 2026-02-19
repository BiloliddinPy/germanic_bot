import sqlite3
import logging
import os
from core.config import settings

def get_connection():
    """Legacy wrapper for backward compatibility during transition."""
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
            category TEXT
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
