import asyncio
import datetime
import gzip
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import threading
from pathlib import Path
from core.config import settings
from database import log_ops_error
from database.connection import is_postgres_backend
from utils.error_notifier import schedule_ops_error_notification

BACKUP_THRESHOLD_COMPRESS_BYTES = 5 * 1024 * 1024
BACKUP_SEND_MAX_BYTES = 45 * 1024 * 1024
BACKUP_RETENTION_DAYS = 14
BACKUP_FILE_RE = re.compile(r"^backup_(\d{4}-\d{2}-\d{2}_\d{4}_UTC)\.sqlite(?:\.gz|\.zip)?$")

_backup_lock = threading.Lock()


def _utc_now():
    return datetime.datetime.utcnow()


def _pick_backup_dir() -> Path:
    candidates = [Path("backups"), Path("/tmp/backups")]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue
    fallback = Path("/tmp")
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _backup_filename(now_utc: datetime.datetime) -> str:
    return f"backup_{now_utc.strftime('%Y-%m-%d_%H%M')}_UTC.sqlite"


def _backup_with_cli(src_db: str, dst_path: str):
    cli = shutil.which("sqlite3")
    if not cli:
        return False, "sqlite3 cli not available"
    try:
        proc = subprocess.run(
            [cli, src_db, f".backup {dst_path}"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "cli backup failed").strip()
            return False, msg[:280]
        if not os.path.exists(dst_path):
            return False, "cli backup produced no file"
        return True, None
    except Exception as e:
        return False, str(e)[:280]


def _backup_with_python_api(src_db: str, dst_path: str):
    src_conn = None
    dst_conn = None
    try:
        src_conn = sqlite3.connect(src_db, timeout=30)
        dst_conn = sqlite3.connect(dst_path, timeout=30)
        with dst_conn:
            src_conn.backup(dst_conn)
        return True, None
    except Exception as e:
        return False, str(e)[:280]
    finally:
        try:
            if dst_conn:
                dst_conn.close()
        except Exception:
            pass
        try:
            if src_conn:
                src_conn.close()
        except Exception:
            pass


def _maybe_compress(path: Path):
    try:
        size = path.stat().st_size
    except Exception:
        return None
    if size <= BACKUP_THRESHOLD_COMPRESS_BYTES:
        return None
    gz_path = Path(str(path) + ".gz")
    try:
        with open(path, "rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst)
        return gz_path
    except Exception:
        return None


def _list_backup_files(base_dir: Path):
    items = []
    if not base_dir.exists():
        return items
    for p in base_dir.iterdir():
        if not p.is_file():
            continue
        match = BACKUP_FILE_RE.match(p.name)
        if not match:
            continue
        try:
            stat = p.stat()
        except Exception:
            continue
        items.append({
            "path": str(p),
            "name": p.name,
            "group": match.group(1),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "mtime_iso": datetime.datetime.utcfromtimestamp(stat.st_mtime).isoformat(timespec="seconds") + "Z",
            "compressed": p.name.endswith(".gz") or p.name.endswith(".zip")
        })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def _apply_retention(base_dir: Path, keep_days: int = BACKUP_RETENTION_DAYS):
    files = _list_backup_files(base_dir)
    if not files:
        return []

    group_to_latest = {}
    for f in files:
        prev = group_to_latest.get(f["group"])
        if prev is None or f["mtime"] > prev:
            group_to_latest[f["group"]] = f["mtime"]

    keep_groups = [g for g, _ in sorted(group_to_latest.items(), key=lambda kv: kv[1], reverse=True)[:keep_days]]
    keep_set = set(keep_groups)

    removed = []
    for f in files:
        if f["group"] in keep_set:
            continue
        try:
            os.remove(f["path"])
            removed.append(f["path"])
        except Exception:
            continue
    return removed


def list_backups(limit: int = 10):
    base_dir = _pick_backup_dir()
    files = _list_backup_files(base_dir)
    grouped = {}
    for f in files:
        existing = grouped.get(f["group"])
        if not existing:
            grouped[f["group"]] = f
            continue
        # prefer compressed artifact for delivery/listing
        if f["compressed"] and not existing["compressed"]:
            grouped[f["group"]] = f
    chosen = sorted(grouped.values(), key=lambda x: x["mtime"], reverse=True)
    return chosen[: max(1, min(limit, 100))]


def get_latest_backup():
    items = list_backups(limit=1)
    return items[0] if items else None


def format_bytes(size: int | None):
    if size is None:
        return "n/a"
    units = ["B", "KB", "MB", "GB"]
    val = float(size)
    idx = 0
    while val >= 1024 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    return f"{val:.2f} {units[idx]}"


def create_backup_sync(trigger: str = "manual"):
    if not _backup_lock.acquire(blocking=False):
        return {
            "success": False,
            "error": "backup already in progress",
            "trigger": trigger,
            "backup_dir": str(_pick_backup_dir())
        }

    try:
        if is_postgres_backend():
            return {
                "success": True,
                "trigger": trigger,
                "method": "skipped_postgres_not_implemented",
                "backup_dir": str(_pick_backup_dir()),
                "note": "Postgres backup is not configured yet (pg_dump step pending).",
            }

        src_db = os.path.abspath(settings.db_path)
        if not os.path.exists(src_db):
            return {
                "success": False,
                "error": "source db file not found",
                "trigger": trigger,
                "backup_dir": str(_pick_backup_dir())
            }

        backup_dir = _pick_backup_dir()
        now = _utc_now()
        file_name = _backup_filename(now)
        sqlite_path = backup_dir / file_name

        ok, err = _backup_with_cli(src_db, str(sqlite_path))
        method = "sqlite3_cli"
        if not ok:
            ok, err = _backup_with_python_api(src_db, str(sqlite_path))
            method = "python_backup_api"

        if not ok:
            return {
                "success": False,
                "error": err or "unknown backup failure",
                "trigger": trigger,
                "backup_dir": str(backup_dir),
                "method": method
            }

        compressed_path = _maybe_compress(sqlite_path)
        primary_path = compressed_path or sqlite_path
        primary_size = primary_path.stat().st_size if primary_path.exists() else None
        removed = _apply_retention(backup_dir, BACKUP_RETENTION_DAYS)

        return {
            "success": True,
            "trigger": trigger,
            "method": method,
            "backup_dir": str(backup_dir),
            "sqlite_path": str(sqlite_path),
            "compressed_path": str(compressed_path) if compressed_path else None,
            "primary_path": str(primary_path),
            "primary_size": primary_size,
            "created_utc": now.isoformat(timespec="seconds") + "Z",
            "retention_removed": removed
        }
    finally:
        _backup_lock.release()


async def run_backup_async(bot=None, trigger: str = "manual"):
    result = await asyncio.to_thread(create_backup_sync, trigger)
    if result.get("success"):
        logging.info(
            "Backup completed trigger=%s method=%s path=%s size=%s",
            trigger,
            result.get("method"),
            result.get("primary_path"),
            result.get("primary_size")
        )
        return result

    err = result.get("error") or "backup failed"
    logging.warning("Backup failed trigger=%s err=%s", trigger, err)
    log_ops_error(
        severity="ERROR",
        where_ctx="backup_manager",
        user_id=None,
        update_id=None,
        error_type="BackupError",
        message_short=err
    )
    schedule_ops_error_notification(bot, {
        "severity": "ERROR",
        "where_ctx": "backup_manager",
        "user_id": None,
        "update_id": None,
        "error_type": "BackupError",
        "message_short": err
    })
    return result
