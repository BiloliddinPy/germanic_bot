import asyncio
import datetime
import logging
from collections import deque

from core.config import settings

_ENABLED = True
_LAST_ALERT_TS_UTC = None
_LAST_RATE_NOTICE_TS_UTC = None
_SENT_ALERT_TS = deque()
_RATE_DROPPED_TS = deque()
_DEDUP_DROPPED_TS = deque()
_DEDUP_LAST_SEEN = {}

_RATE_LIMIT_PER_MIN = 5
_RATE_WINDOW_SEC = 60
_DEDUP_WINDOW_SEC = 120


def _utc_now():
    return datetime.datetime.utcnow()


def _fmt_utc(dt):
    if not dt:
        return "-"
    return dt.isoformat(timespec="seconds") + "Z"


def _cleanup_old(now):
    threshold_rate = now - datetime.timedelta(seconds=_RATE_WINDOW_SEC)
    while _SENT_ALERT_TS and _SENT_ALERT_TS[0] < threshold_rate:
        _SENT_ALERT_TS.popleft()
    while _RATE_DROPPED_TS and _RATE_DROPPED_TS[0] < threshold_rate:
        _RATE_DROPPED_TS.popleft()
    while _DEDUP_DROPPED_TS and _DEDUP_DROPPED_TS[0] < threshold_rate:
        _DEDUP_DROPPED_TS.popleft()

    threshold_dedup = now - datetime.timedelta(seconds=_DEDUP_WINDOW_SEC)
    stale_keys = [k for k, ts in _DEDUP_LAST_SEEN.items() if ts < threshold_dedup]
    for key in stale_keys:
        _DEDUP_LAST_SEEN.pop(key, None)


def get_ops_alerts_status():
    now = _utc_now()
    _cleanup_old(now)
    return {
        "enabled": _ENABLED,
        "last_alert_ts_utc": _fmt_utc(_LAST_ALERT_TS_UTC),
        "last_rate_notice_ts_utc": _fmt_utc(_LAST_RATE_NOTICE_TS_UTC),
        "sent_last_minute": len(_SENT_ALERT_TS),
        "rate_limited_last_minute": len(_RATE_DROPPED_TS),
        "dedup_suppressed_last_minute": len(_DEDUP_DROPPED_TS)
    }


def set_ops_alerts_enabled(enabled: bool):
    global _ENABLED
    _ENABLED = bool(enabled)
    return _ENABLED


def toggle_ops_alerts_enabled():
    global _ENABLED
    _ENABLED = not _ENABLED
    return _ENABLED


def _normalize_message_short(value):
    if value is None:
        return "-"
    short = str(value).replace("\n", " ").replace("\r", " ").strip()
    return short[:200] if len(short) > 200 else short


async def _safe_send(bot, text):
    if not settings.admin_id or not bot:
        return False
    try:
        await bot.send_message(chat_id=int(settings.admin_id), text=text)
        return True
    except Exception as e:
        logging.warning(f"Failed to send ops alert to admin: {e}")
        return False


async def notify_ops_error(bot, payload: dict):
    """
    Sends compact Telegram error alert to ADMIN_ID with dedup + rate limits.
    Never raises.
    """
    global _LAST_ALERT_TS_UTC, _LAST_RATE_NOTICE_TS_UTC
    try:
        if not _ENABLED or not settings.admin_id:
            return
        now = _utc_now()
        _cleanup_old(now)

        severity = (payload.get("severity") or "ERROR").upper()
        where_ctx = payload.get("where_ctx") or "-"
        user_id = payload.get("user_id")
        error_type = payload.get("error_type") or "Exception"
        message_short = _normalize_message_short(payload.get("message_short"))
        ts_utc = payload.get("ts_utc") or _fmt_utc(now)

        dedup_key = (error_type, message_short, where_ctx)
        last_seen = _DEDUP_LAST_SEEN.get(dedup_key)
        if last_seen and (now - last_seen).total_seconds() < _DEDUP_WINDOW_SEC:
            _DEDUP_DROPPED_TS.append(now)
            return
        _DEDUP_LAST_SEEN[dedup_key] = now

        if len(_SENT_ALERT_TS) >= _RATE_LIMIT_PER_MIN:
            _RATE_DROPPED_TS.append(now)
            should_send_notice = (
                _LAST_RATE_NOTICE_TS_UTC is None
                or (now - _LAST_RATE_NOTICE_TS_UTC).total_seconds() >= _RATE_WINDOW_SEC
            )
            if should_send_notice:
                notice_text = (
                    "⚠️ Ops alerts rate-limited.\n"
                    "Too many errors in 1 minute; extra alerts are dropped.\n"
                    "Use /ops_last_errors for details."
                )
                if await _safe_send(bot, notice_text):
                    _LAST_RATE_NOTICE_TS_UTC = now
                    _LAST_ALERT_TS_UTC = now
            return

        text = (
            "🚨 Bot Error Alert\n"
            f"time_utc: {ts_utc}\n"
            f"severity: {severity}\n"
            f"where: {where_ctx}\n"
            f"user_id: {user_id if user_id is not None else '-'}\n"
            f"error_type: {error_type}\n"
            f"message: {message_short}\n\n"
            "Hint: Use /ops_last_errors for details."
        )
        if await _safe_send(bot, text):
            _SENT_ALERT_TS.append(now)
            _LAST_ALERT_TS_UTC = now
    except Exception as e:
        logging.warning(f"Ops notifier internal failure: {e}")
        return


def schedule_ops_error_notification(bot, payload: dict):
    """Fire-and-forget notifier call. Never raises."""
    try:
        asyncio.create_task(notify_ops_error(bot, payload))
    except Exception as e:
        logging.warning(f"Failed to schedule ops error notification: {e}")
