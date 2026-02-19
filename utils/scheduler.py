from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
import logging

from core.config import settings
from utils.backup_manager import run_backup_async

SCHEDULER_JOB_ID_DAILY_WORD = "send_daily_word_to_all"
SCHEDULER_JOB_ID_DAILY_BACKUP = "daily_sqlite_backup"
_scheduler: AsyncIOScheduler | None = None


async def start_scheduler(bot: Bot):
    from handlers.daily import send_daily_word_to_all
    global _scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_word_to_all,
        "cron",
        hour=9,
        minute=0,
        timezone="Asia/Tashkent",
        args=[bot],
        id=SCHEDULER_JOB_ID_DAILY_WORD,
        replace_existing=True
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
        "Scheduler started. daily_word=09:00 Asia/Tashkent, daily_backup=%02d:%02d UTC",
        backup_hour,
        backup_minute
    )


def get_scheduler_health():
    """
    Returns best-effort scheduler status for ops checks.
    """
    info = {"started": False, "next_run_time": None, "backup_next_run_time": None}
    if _scheduler is None:
        return info
    info["started"] = bool(_scheduler.running)
    try:
        job = _scheduler.get_job(SCHEDULER_JOB_ID_DAILY_WORD)
        if job and job.next_run_time:
            info["next_run_time"] = job.next_run_time.isoformat()
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
