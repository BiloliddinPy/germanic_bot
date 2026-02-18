import os
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
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
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = [row[1] for row in cursor.fetchall()]
    return column_name in cols


def main():
    all_ok = True

    all_ok &= check(bool(config.BOT_TOKEN), "BOT_TOKEN mavjud", "BOT_TOKEN topilmadi (.env ni tekshiring)")

    database.create_table()
    all_ok &= check(os.path.exists(database.DB_NAME), f"{database.DB_NAME} mavjud", "DB fayl topilmadi")

    conn = sqlite3.connect(database.DB_NAME)
    cur = conn.cursor()

    required_tables = [
        "users",
        "words",
        "user_profile",
        "user_progress",
        "user_streak",
        "user_mistakes",
        "daily_lesson_log",
        "user_daily_plan",
        "daily_plan_audit",
        "user_ui_state",
        "user_grammar_coverage",
        "writing_task_log",
    ]
    for t in required_tables:
        all_ok &= check(table_exists(cur, t), f"{t} jadvali mavjud", f"{t} jadvali topilmadi")

    all_ok &= check(
        column_exists(cur, "user_mistakes", "success_count"),
        "user_mistakes.success_count mavjud",
        "user_mistakes.success_count topilmadi"
    )
    all_ok &= check(
        column_exists(cur, "user_mistakes", "mastered"),
        "user_mistakes.mastered mavjud",
        "user_mistakes.mastered topilmadi"
    )

    cur.execute("SELECT COUNT(*) FROM words")
    word_count = cur.fetchone()[0]
    all_ok &= check(word_count > 0, f"words jadvalida {word_count} ta yozuv bor", "words jadvali bo'sh")

    conn.close()

    if all_ok:
        print("OK: health_check muvaffaqiyatli tugadi.")
        return 0
    print("FAIL: health_check xatoliklar bilan tugadi.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
