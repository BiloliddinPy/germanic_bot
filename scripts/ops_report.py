import argparse
import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_connection


def _print_header(title: str):
    print(f"\n=== {title} ===")


def _one(cur, sql: str, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return 0
    return int(row[0] or 0)


def _rows(cur, sql: str, params=()):
    cur.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _safe_pct(num: int, den: int) -> int:
    if den <= 0:
        return 0
    return int(round((num / den) * 100))


def _report_users(cur, since_date: str):
    _print_header("Users")
    total = _one(cur, "SELECT COUNT(*) FROM user_profile")
    new_users = _one(
        cur,
        "SELECT COUNT(*) FROM user_profile WHERE DATE(created_at) >= ?",
        (since_date,),
    )
    print(f"Total users: {total}")
    print(f"New users ({since_date}..today): {new_users}")

    daily = _rows(
        cur,
        """
        SELECT DATE(created_at) AS day, COUNT(*) AS cnt
        FROM user_profile
        WHERE DATE(created_at) >= ?
        GROUP BY DATE(created_at)
        ORDER BY day ASC
        """,
        (since_date,),
    )
    if not daily:
        print("Daily signups: no data")
        return
    print("Daily signups:")
    for row in daily:
        print(f"  {row['day']}: {int(row['cnt'] or 0)}")


def _report_activity(cur, since_date: str):
    _print_header("Activity")
    dau_rows = _rows(
        cur,
        """
        SELECT DATE(created_at) AS day, COUNT(DISTINCT user_id) AS dau
        FROM event_logs
        WHERE DATE(created_at) >= ?
        GROUP BY DATE(created_at)
        ORDER BY day ASC
        """,
        (since_date,),
    )
    if dau_rows:
        print("DAU (event_logs-based):")
        for row in dau_rows:
            print(f"  {row['day']}: {int(row['dau'] or 0)}")
    else:
        print("DAU (event_logs-based): no data")

    top_sections = _rows(
        cur,
        """
        SELECT COALESCE(section_name, 'unknown') AS section_name, COUNT(*) AS cnt
        FROM event_logs
        WHERE DATE(created_at) >= ?
        GROUP BY COALESCE(section_name, 'unknown')
        ORDER BY cnt DESC
        LIMIT 10
        """,
        (since_date,),
    )
    if top_sections:
        print("Top sections:")
        for row in top_sections:
            print(f"  {row['section_name']}: {int(row['cnt'] or 0)}")


def _report_daily_progress(cur, since_date: str):
    _print_header("Daily Progress")
    started = _one(
        cur,
        """
        SELECT COUNT(*)
        FROM user_progress
        WHERE module_name = 'daily_lesson'
          AND DATE(last_active) >= ?
        """,
        (since_date,),
    )
    completed = _one(
        cur,
        """
        SELECT COUNT(*)
        FROM user_progress
        WHERE module_name = 'daily_lesson'
          AND completion_status = 1
          AND DATE(last_active) >= ?
        """,
        (since_date,),
    )
    print(f"Daily lesson rows ({since_date}..today): {started}")
    print(f"Completed rows ({since_date}..today): {completed}")
    print(f"Completion rate: {_safe_pct(completed, started)}%")


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

    top_items = _rows(
        cur,
        """
        SELECT item_id, module, SUM(COALESCE(mistake_count, 0)) AS total
        FROM user_mistakes
        WHERE COALESCE(mistake_count, 0) > 0 AND COALESCE(mastered, 0) = 0
        GROUP BY item_id, module
        ORDER BY total DESC
        LIMIT ?
        """,
        (max(1, top_n),),
    )
    if not top_items:
        print("Top weak items: no active mistakes")
        return
    print(f"Top {max(1, top_n)} weak items:")
    for row in top_items:
        print(f"  item_id={row['item_id']} module={row['module']} mistakes={int(row['total'] or 0)}")


def _report_errors_from_log(log_file: str):
    _print_header("Runtime Errors (bot.log)")
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return

    error_count = 0
    traceback_count = 0
    conflict_count = 0
    with open(log_file, "r", encoding="utf-8", errors="ignore") as file_obj:
        for line in file_obj:
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
    parser = argparse.ArgumentParser(description="Operations report for Germanic bot (sqlite/postgres)")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument("--top", type=int, default=10, help="Top N weak items (default: 10)")
    parser.add_argument("--log", default="bot.log", help="Path to bot log (default: bot.log)")
    args = parser.parse_args()

    days = max(1, args.days)
    since_date = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
    print("Germanic Bot Ops Report")
    print(f"Date window: {since_date}..{datetime.date.today().isoformat()} ({days} days)")

    conn = get_connection()
    cur = conn.cursor()
    try:
        _report_users(cur, since_date)
        _report_activity(cur, since_date)
        _report_daily_progress(cur, since_date)
        _report_mistakes(cur, args.top)
        _report_errors_from_log(args.log)
    finally:
        conn.close()

    print("\nOK: ops report completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
