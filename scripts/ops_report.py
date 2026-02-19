import argparse
import datetime
import os
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


def _connect_read_only(db_path: str):
    # Force read-only DB access for safe production reporting.
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _one(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return 0
    return row[0]


def _print_header(title: str):
    print(f"\n=== {title} ===")


def _daily_rows(cur, sql, params=()):
    cur.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _safe_pct(num: int, den: int) -> int:
    if den <= 0:
        return 0
    return int(round((num / den) * 100))


def _report_users(cur, since_date: str):
    _print_header("Users")
    total_users = _one(cur, "SELECT COUNT(*) FROM users")
    new_users = _one(cur, "SELECT COUNT(*) FROM users WHERE DATE(joined_at) >= ?", (since_date,))

    print(f"Total users: {total_users}")
    print(f"New users ({since_date}..today): {new_users}")

    rows = _daily_rows(
        cur,
        """
        SELECT DATE(joined_at) AS day, COUNT(*) AS cnt
        FROM users
        WHERE DATE(joined_at) >= ?
        GROUP BY DATE(joined_at)
        ORDER BY day ASC
        """,
        (since_date,),
    )

    if not rows:
        print("Daily signups: no data")
        return

    print("Daily signups:")
    for row in rows:
        print(f"  {row['day']}: {row['cnt']}")


def _report_activity(cur, since_date: str):
    _print_header("Activity")

    dau_rows = _daily_rows(
        cur,
        """
        SELECT DATE(timestamp) AS day, COUNT(DISTINCT user_id) AS dau
        FROM events
        WHERE DATE(timestamp) >= ?
        GROUP BY DATE(timestamp)
        ORDER BY day ASC
        """,
        (since_date,),
    )

    if dau_rows:
        print("DAU (events-based):")
        for row in dau_rows:
            print(f"  {row['day']}: {row['dau']}")
    else:
        print("DAU (events-based): no data")

    top_sections = _daily_rows(
        cur,
        """
        SELECT COALESCE(section_name, 'unknown') AS section_name, COUNT(*) AS cnt
        FROM events
        WHERE DATE(timestamp) >= ?
        GROUP BY COALESCE(section_name, 'unknown')
        ORDER BY cnt DESC
        LIMIT 10
        """,
        (since_date,),
    )

    if top_sections:
        print("Top sections (last period):")
        for row in top_sections:
            print(f"  {row['section_name']}: {row['cnt']}")


def _report_daily_lesson(cur, since_date: str):
    _print_header("Daily Lesson")

    started = _one(
        cur,
        "SELECT COUNT(*) FROM daily_lesson_log WHERE lesson_date >= ? AND started_at IS NOT NULL",
        (since_date,),
    )
    completed = _one(
        cur,
        "SELECT COUNT(*) FROM daily_lesson_log WHERE lesson_date >= ? AND completed_at IS NOT NULL",
        (since_date,),
    )
    print(f"Started sessions ({since_date}..today): {started}")
    print(f"Completed sessions ({since_date}..today): {completed}")
    print(f"Completion rate: {_safe_pct(completed, started)}%")

    by_day = _daily_rows(
        cur,
        """
        SELECT
            lesson_date AS day,
            SUM(CASE WHEN started_at IS NOT NULL THEN 1 ELSE 0 END) AS started,
            SUM(CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END) AS completed
        FROM daily_lesson_log
        WHERE lesson_date >= ?
        GROUP BY lesson_date
        ORDER BY day ASC
        """,
        (since_date,),
    )

    if by_day:
        print("By day:")
        for row in by_day:
            started_day = int(row.get("started") or 0)
            completed_day = int(row.get("completed") or 0)
            print(f"  {row['day']}: {completed_day}/{started_day} ({_safe_pct(completed_day, started_day)}%)")


def _report_mistakes(cur, top_n: int):
    _print_header("Mistakes")

    total_active = _one(
        cur,
        "SELECT COUNT(*) FROM user_mistakes WHERE COALESCE(mistake_count, 0) > 0 AND COALESCE(mastered, 0) = 0",
    )
    mastered = _one(
        cur,
        "SELECT COUNT(*) FROM user_mistakes WHERE COALESCE(mastered, 0) = 1",
    )

    print(f"Active mistake rows: {total_active}")
    print(f"Mastered rows: {mastered}")

    top_items = _daily_rows(
        cur,
        """
        SELECT item_id, level, SUM(COALESCE(mistake_count, 0)) AS total
        FROM user_mistakes
        WHERE COALESCE(mistake_count, 0) > 0 AND COALESCE(mastered, 0) = 0
        GROUP BY item_id, level
        ORDER BY total DESC
        LIMIT ?
        """,
        (top_n,),
    )

    if top_items:
        print(f"Top {top_n} weak items:")
        for row in top_items:
            print(f"  item_id={row['item_id']} level={row['level']} mistakes={row['total']}")
    else:
        print("Top weak items: no active mistakes")


def _report_errors_from_log(log_file: str):
    _print_header("Runtime Errors (bot.log)")
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return

    error_count = 0
    traceback_count = 0
    conflict_count = 0

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "ERROR" in line:
                error_count += 1
            if "Traceback" in line:
                traceback_count += 1
            if "TelegramConflictError" in line:
                conflict_count += 1

    print(f"ERROR lines: {error_count}")
    print(f"Traceback lines: {traceback_count}")
    print(f"TelegramConflictError lines: {conflict_count}")


def main():
    parser = argparse.ArgumentParser(description="Read-only operations report for Germanic bot")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument("--top", type=int, default=10, help="Top N weak items (default: 10)")
    parser.add_argument("--db", default=database.DB_NAME, help="Path to sqlite DB (default: germanic.db)")
    parser.add_argument("--log", default="bot.log", help="Path to bot log (default: bot.log)")
    args = parser.parse_args()

    days = max(args.days, 1)
    since_date = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()

    print("Germanic Bot Ops Report (read-only)")
    print(f"Date window: {since_date}..{datetime.date.today().isoformat()} ({days} days)")
    print(f"DB path: {args.db}")

    if not os.path.exists(args.db):
        print(f"DB not found: {args.db}")
        return 1

    try:
        conn = _connect_read_only(args.db)
    except sqlite3.OperationalError as exc:
        print(f"Unable to open DB in read-only mode: {exc}")
        return 1

    cur = conn.cursor()

    try:
        _report_users(cur, since_date)
        _report_activity(cur, since_date)
        _report_daily_lesson(cur, since_date)
        _report_mistakes(cur, max(args.top, 1))
        _report_errors_from_log(args.log)
    finally:
        conn.close()

    print("\nOK: ops report completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
