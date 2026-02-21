import datetime

from database.repositories.user_repository import _normalize_date
from utils import backup_manager


def test_normalize_date_handles_iso_string():
    assert _normalize_date("2026-02-21") == datetime.date(2026, 2, 21)


def test_normalize_date_handles_timestamp_string():
    assert _normalize_date("2026-02-21 14:32:00") == datetime.date(2026, 2, 21)


def test_normalize_date_handles_date_object():
    d = datetime.date(2026, 2, 21)
    assert _normalize_date(d) == d


def test_backup_postgres_requires_database_url(monkeypatch):
    monkeypatch.setattr(backup_manager, "is_postgres_backend", lambda: True)
    result = backup_manager.create_backup_sync("test")
    assert result.get("success") is False
    assert result.get("method") == "pg_dump"
    assert "DATABASE_URL is empty" in (result.get("error") or "")
