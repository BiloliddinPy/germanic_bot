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


def test_backup_postgres_skip_is_non_critical_failure(monkeypatch):
    monkeypatch.setattr(backup_manager, "is_postgres_backend", lambda: True)
    result = backup_manager.create_backup_sync("test")
    assert result.get("success") is False
    assert result.get("non_critical") is True
    assert "postgres backup not implemented" in (result.get("error") or "")
