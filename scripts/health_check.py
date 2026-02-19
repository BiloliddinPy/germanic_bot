import os
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
import database

def check(condition, ok_msg, fail_msg):
    if condition:
        print(f"OK: {ok_msg}")
        return True
    print(f"FAIL: {fail_msg}")
    return False

def table_exists(cursor, table_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def column_exists(cursor, table_name, column_name):
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        cols = [row[1] for row in cursor.fetchall()]
        return column_name in cols
    except Exception:
        return False

def main():
    all_ok = True

    all_ok &= check(bool(settings.bot_token), "BOT_TOKEN mavjud", "BOT_TOKEN topilmadi (.env ni tekshiring)")

    database.create_table()
    db_path = settings.db_path
    all_ok &= check(os.path.exists(db_path), f"{db_path} mavjud", "DB fayl topilmadi")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    required_tables = [
        "user_profile",
        "words",
        "user_mastery",
        "daily_plans",
        "daily_lesson_sessions",
        "ui_state",
        "navigation_logs",
        "user_progress",
        "user_mistakes",
        "quiz_results"
    ]
    for t in required_tables:
        all_ok &= check(table_exists(cur, t), f"{t} jadvali mavjud", f"{t} jadvali topilmadi")

    all_ok &= check(
        column_exists(cur, "user_mistakes", "mistake_count"),
        "user_mistakes.mistake_count mavjud",
        "user_mistakes.mistake_count topilmadi"
    )

    cur.execute("SELECT COUNT(*) FROM words")
    word_count = cur.fetchone()[0]
    all_ok &= check(word_count >= 0, f"words jadvalida {word_count} ta yozuv bor", "words jadvaliga kirish xatosi")

    conn.close()

    if all_ok:
        print("OK: health_check muvaffaqiyatli tugadi.")
        return 0
    print("FAIL: health_check xatoliklar bilan tugadi.")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
