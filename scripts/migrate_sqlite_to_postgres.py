import argparse
import os
import sqlite3
import sys
from dataclasses import dataclass
from typing import Any, Iterable

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

psycopg: Any = None
sql: Any = None
try:  # pragma: no cover
    import psycopg as _psycopg
    from psycopg import sql as _sql

    psycopg = _psycopg
    sql = _sql
except Exception:
    pass


TABLES = [
    "user_profile",
    "words",
    "user_streak",
    "user_mastery",
    "daily_plans",
    "daily_lesson_sessions",
    "ui_state",
    "navigation_logs",
    "user_progress",
    "user_mistakes",
    "quiz_results",
    "grammar_progress",
    "event_logs",
    "user_submissions",
    "broadcast_jobs",
]

SEQUENCE_TABLES = [
    ("words", "id"),
    ("daily_plans", "id"),
    ("navigation_logs", "id"),
    ("quiz_results", "id"),
    ("event_logs", "id"),
    ("user_submissions", "id"),
    ("broadcast_jobs", "id"),
]


@dataclass
class MigrationStats:
    table: str
    sqlite_rows: int
    inserted_rows: int
    postgres_rows: int


def _sqlite_connect(path: str):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _sqlite_columns(conn, table: str) -> list[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [r["name"] for r in cur.fetchall()]


def _sqlite_table_exists(conn, table: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    )
    return cur.fetchone() is not None


def _sqlite_count(conn, table: str) -> int:
    if not _sqlite_table_exists(conn, table):
        return 0
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def _sqlite_fetch_batches(conn, table: str, cols: list[str], batch_size: int) -> Iterable[list[tuple]]:
    if not _sqlite_table_exists(conn, table):
        return
    col_sql = ", ".join(cols)
    cur = conn.cursor()
    cur.execute(f"SELECT {col_sql} FROM {table}")
    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        yield [tuple(row[col] for col in cols) for row in rows]


def _pg_table_exists(conn, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            (table,),
        )
        row = cur.fetchone()
        return bool(row and row[0])


def _pg_count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0


def _pg_truncate_all(conn, tables: list[str]):
    with conn.cursor() as cur:
        identifiers = [sql.Identifier(t) for t in tables]
        cur.execute(
            sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                sql.SQL(", ").join(identifiers)
            )
        )


def _pg_insert_batch(conn, table: str, cols: list[str], rows: list[tuple]):
    if not rows:
        return
    with conn.cursor() as cur:
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(c) for c in cols),
            sql.SQL(", ").join(sql.Placeholder() for _ in cols),
        )
        cur.executemany(query, rows)


def _pg_fix_sequences(conn):
    with conn.cursor() as cur:
        for table, id_col in SEQUENCE_TABLES:
            cur.execute(
                sql.SQL(
                    """
                    SELECT setval(
                        pg_get_serial_sequence(%s, %s),
                        COALESCE((SELECT MAX({id_col}) FROM {table}), 1),
                        true
                    )
                    """
                ).format(id_col=sql.Identifier(id_col), table=sql.Identifier(table)),
                (table, id_col),
            )


def migrate(sqlite_path: str, pg_url: str, batch_size: int, truncate: bool, dry_run: bool):
    if not os.path.exists(sqlite_path):
        raise RuntimeError(f"SQLite DB not found: {sqlite_path}")

    sqlite_conn = _sqlite_connect(sqlite_path)
    stats: list[MigrationStats] = []

    try:
        for table in TABLES:
            sqlite_rows = _sqlite_count(sqlite_conn, table)
            stats.append(
                MigrationStats(
                    table=table,
                    sqlite_rows=sqlite_rows,
                    inserted_rows=0,
                    postgres_rows=0,
                )
            )

        if dry_run:
            return stats

        if psycopg is None or sql is None:
            raise RuntimeError(
                "psycopg is required for non-dry-run migration. Install with: pip install -r requirements.txt"
            )
        if not pg_url:
            raise RuntimeError("DATABASE_URL is required when dry-run is disabled.")

        with psycopg.connect(pg_url) as pg_conn:
            for table in TABLES:
                if not _pg_table_exists(pg_conn, table):
                    raise RuntimeError(
                        f"Postgres table missing: {table}. Run bot once with DB_BACKEND=postgres first."
                    )

            if truncate:
                _pg_truncate_all(pg_conn, TABLES)

            for item in stats:
                if not _sqlite_table_exists(sqlite_conn, item.table):
                    continue
                cols = _sqlite_columns(sqlite_conn, item.table)
                inserted = 0
                for batch in _sqlite_fetch_batches(sqlite_conn, item.table, cols, batch_size):
                    _pg_insert_batch(pg_conn, item.table, cols, batch)
                    inserted += len(batch)
                item.inserted_rows = inserted

            _pg_fix_sequences(pg_conn)
            pg_conn.commit()

            for item in stats:
                item.postgres_rows = _pg_count(pg_conn, item.table)

        return stats
    finally:
        sqlite_conn.close()


def _print_report(stats: list[MigrationStats], dry_run: bool):
    print("SQLite -> Postgres Migration Report")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print("")
    ok = True
    for s in stats:
        if dry_run:
            print(f"- {s.table}: sqlite={s.sqlite_rows}")
            continue
        table_ok = s.sqlite_rows == s.inserted_rows == s.postgres_rows
        ok = ok and table_ok
        marker = "OK" if table_ok else "MISMATCH"
        print(
            f"- {s.table}: sqlite={s.sqlite_rows}, inserted={s.inserted_rows}, "
            f"postgres={s.postgres_rows} [{marker}]"
        )
    if not dry_run:
        print("")
        print("Result:", "SUCCESS" if ok else "FAILED")
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Migrate data from SQLite to Postgres with row-count verification."
    )
    parser.add_argument("--sqlite-path", default="germanic.db", help="Path to sqlite DB file")
    parser.add_argument("--pg-url", default=os.getenv("DATABASE_URL", ""), help="Postgres URL")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows per insert batch")
    parser.add_argument("--truncate", action="store_true", help="Truncate Postgres tables before migration")
    parser.add_argument("--dry-run", action="store_true", help="Show counts only, do not write to Postgres")
    args = parser.parse_args()

    stats = migrate(
        sqlite_path=args.sqlite_path,
        pg_url=args.pg_url,
        batch_size=max(100, args.batch_size),
        truncate=args.truncate,
        dry_run=args.dry_run,
    )
    ok = _print_report(stats, dry_run=args.dry_run)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
