from database.connection import get_connection
import random
import sqlite3
import logging

def get_words_by_level(level: str, limit: int = 20, offset: int = 0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM words 
        WHERE level = ? 
        ORDER BY de COLLATE NOCASE
        LIMIT ? OFFSET ?
    """, (level, limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_words_by_level_and_letter(level: str, letter: str, limit: int = 20, offset: int = 0):
    conn = get_connection()
    cursor = conn.cursor()
    pattern = f"{letter.lower()}%"
    p_der = f"der {letter.lower()}%"
    p_die = f"die {letter.lower()}%"
    p_das = f"das {letter.lower()}%"
    cursor.execute("""
        SELECT * FROM words 
        WHERE level = ? AND (
            LOWER(de) LIKE ? OR 
            LOWER(de) LIKE ? OR 
            LOWER(de) LIKE ? OR 
            LOWER(de) LIKE ?
        )
        ORDER BY de COLLATE NOCASE
        LIMIT ? OFFSET ?
    """, (level, pattern, p_der, p_die, p_das, limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_total_words_count(level: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM words WHERE level = ?", (level,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_words_count_by_letter(level: str, letter: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    pattern = f"{letter.lower()}%"
    p_der = f"der {letter.lower()}%"
    p_die = f"die {letter.lower()}%"
    p_das = f"das {letter.lower()}%"
    cursor.execute("""
        SELECT COUNT(*) FROM words 
        WHERE level = ? AND (
            LOWER(de) LIKE ? OR 
            LOWER(de) LIKE ? OR 
            LOWER(de) LIKE ? OR 
            LOWER(de) LIKE ?
        )
    """, (level, pattern, p_der, p_die, p_das))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_random_words(level: str, limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM words WHERE level = ? ORDER BY RANDOM() LIMIT ?", (level, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_words_by_ids(word_ids: list):
    if not word_ids:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(word_ids))
    cursor.execute(f"SELECT * FROM words WHERE id IN ({placeholders})", word_ids)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_word(level, de, uz, pos, plural="", example_de="", example_uz="", category=""):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO words (level, de, uz, pos, plural, example_de, example_uz, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (level, de, uz, pos, plural, example_de, example_uz, category))
        conn.commit()
    except Exception as e:
        logging.error(f"Error adding word {de}: {e}")
    finally:
        conn.close()
