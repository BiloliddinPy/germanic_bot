import re
import sqlite3
from pathlib import Path
from typing import Any

from core.config import settings

_POSTGRES_POOL: Any = None
_QMARK_RE = re.compile(r"\?")


def _to_postgres_placeholders(query: str) -> str:
    return _QMARK_RE.sub("%s", query)


class CompatRow:
    """
    SQLite-like row behavior for Postgres results.
    Supports:
    - row[0], row["column"]
    - unpacking: a, b = row
    - dict(row)
    """

    def __init__(self, columns: list[str], values: tuple[Any, ...]):
        self._columns = columns
        self._values = values
        self._idx = {name: i for i, name in enumerate(columns)}

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._idx[key]]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def keys(self):
        return self._columns


class CompatCursor:
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def execute(self, query: str, params: Any = None):
        sql = _to_postgres_placeholders(query)
        if params is None:
            self._cursor.execute(sql)
        else:
            self._cursor.execute(sql, params)
        return self

    def executemany(self, query: str, params_seq: Any):
        sql = _to_postgres_placeholders(query)
        self._cursor.executemany(sql, params_seq)
        return self

    def fetchone(self) -> Any:
        row = self._cursor.fetchone()
        if row is None:
            return None
        cols = [d.name for d in (self._cursor.description or [])]
        return CompatRow(cols, row)

    def fetchall(self) -> list[Any]:
        rows = self._cursor.fetchall()
        cols = [d.name for d in (self._cursor.description or [])]
        return [CompatRow(cols, r) for r in rows]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class CompatConnection:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self) -> Any:
        return CompatCursor(self._conn.cursor())

    def commit(self) -> Any:
        return self._conn.commit()

    def close(self) -> Any:
        return self._conn.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def _get_or_create_postgres_pool():
    global _POSTGRES_POOL
    if _POSTGRES_POOL is not None:
        return _POSTGRES_POOL

    if not settings.database_url:
        raise RuntimeError("DB_BACKEND=postgres but DATABASE_URL is empty.")
    try:
        from psycopg_pool import ConnectionPool  # type: ignore[reportMissingImports]
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Postgres backend requested but psycopg_pool is not installed."
        ) from exc

    _POSTGRES_POOL = ConnectionPool(
        conninfo=settings.database_url,
        min_size=max(1, settings.db_pool_min_size),
        max_size=max(max(1, settings.db_pool_min_size), settings.db_pool_max_size),
        open=True,
    )
    return _POSTGRES_POOL


def close_postgres_pool():
    global _POSTGRES_POOL
    if _POSTGRES_POOL is not None:
        _POSTGRES_POOL.close()
        _POSTGRES_POOL = None


def _get_sqlite_connection() -> Any:
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_postgres_connection() -> Any:
    pool = _get_or_create_postgres_pool()
    return CompatConnection(pool.connection())


def get_connection() -> Any:
    """
    Returns a DB connection based on selected backend.
    Default backend is sqlite for safe rollout.
    """
    if settings.db_backend == "postgres":
        return _get_postgres_connection()
    return _get_sqlite_connection()
