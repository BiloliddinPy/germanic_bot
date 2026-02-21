from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
import logging

from core.config import settings
from database.connection import get_connection, is_postgres_backend
from utils.backup_manager import run_backup_async

SCHEDULER_JOB_ID_DAILY_WORD = "send_daily_word_to_all"
SCHEDULER_JOB_ID_BROADCAST_PROCESSOR = "process_broadcast_queue"
SCHEDULER_JOB_ID_DAILY_BACKUP = "daily_sqlite_backup"
_scheduler: AsyncIOScheduler | None = None
_scheduler_leader_conn = None
SCHEDULER_ADVISORY_LOCK_KEY = 99170031


def _acquire_scheduler_leader_lock() -> bool:
    global _scheduler_leader_conn
    if not is_postgres_backend():
        return True
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT pg_try_advisory_lock(?)", (SCHEDULER_ADVISORY_LOCK_KEY,))
        row = cur.fetchone()
        is_leader = bool(row and row[0])
        if is_leader:
            _scheduler_leader_conn = conn
            return True
        conn.close()
        return False
    except Exception as exc:
        logging.exception("Scheduler leader lock check failed: %s", exc)
        return False


def _release_scheduler_leader_lock():
    global _scheduler_leader_conn
    if _scheduler_leader_conn is None:
        return
    try:
        cur = _scheduler_leader_conn.cursor()
        cur.execute("SELECT pg_advisory_unlock(?)", (SCHEDULER_ADVISORY_LOCK_KEY,))
    except Exception:
        pass
    try:
        _scheduler_leader_conn.close()
    except Exception:
        pass
    _scheduler_leader_conn = None


async def start_scheduler(bot: Bot):
    from handlers.daily import send_daily_word_to_all, process_broadcast_queue, DAILY_TIMEZONE
    global _scheduler
    if not _acquire_scheduler_leader_lock():
        logging.warning("Scheduler not started on this replica (leader lock not acquired).")
        _scheduler = None
        return
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_word_to_all,
        "cron",
        hour="*",
        minute=0,
        timezone=DAILY_TIMEZONE,
        args=[bot],
        id=SCHEDULER_JOB_ID_DAILY_WORD,
        replace_existing=True
    )
    scheduler.add_job(
        process_broadcast_queue,
        "interval",
        minutes=1,
        args=[bot],
        id=SCHEDULER_JOB_ID_BROADCAST_PROCESSOR,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    backup_hour, backup_minute = _parse_backup_time_utc(settings.backup_time_utc)
    scheduler.add_job(
        run_backup_async,
        "cron",
        hour=backup_hour,
        minute=backup_minute,
        timezone="UTC",
        args=[bot, "scheduler"],
        id=SCHEDULER_JOB_ID_DAILY_BACKUP,
        replace_existing=True
    )
    scheduler.start()
    _scheduler = scheduler
    logging.info(
        "Scheduler started. enqueue=hourly@%s, queue_processor=1m, daily_backup=%02d:%02d UTC",
        DAILY_TIMEZONE,
        backup_hour,
        backup_minute
    )


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
    _release_scheduler_leader_lock()


def get_scheduler_health():
    """
    Returns best-effort scheduler status for ops checks.
    """
    info = {
        "started": False,
        "next_run_time": None,
        "processor_next_run_time": None,
        "backup_next_run_time": None,
        "leader": (not is_postgres_backend()) or (_scheduler_leader_conn is not None),
    }
    if _scheduler is None:
        return info
    info["started"] = bool(_scheduler.running)
    try:
        job = _scheduler.get_job(SCHEDULER_JOB_ID_DAILY_WORD)
        if job and job.next_run_time:
            info["next_run_time"] = job.next_run_time.isoformat()
        processor_job = _scheduler.get_job(SCHEDULER_JOB_ID_BROADCAST_PROCESSOR)
        if processor_job and processor_job.next_run_time:
            info["processor_next_run_time"] = processor_job.next_run_time.isoformat()
        backup_job = _scheduler.get_job(SCHEDULER_JOB_ID_DAILY_BACKUP)
        if backup_job and backup_job.next_run_time:
            info["backup_next_run_time"] = backup_job.next_run_time.isoformat()
    except Exception:
        pass
    return info


def _parse_backup_time_utc(raw: str):
    default = (3, 0)
    try:
        hour_str, minute_str = str(raw).strip().split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except Exception:
        pass
    return default
