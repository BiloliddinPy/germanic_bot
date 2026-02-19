from aiogram import BaseMiddleware
import logging
import datetime

from database import log_ops_error
from utils.error_notifier import schedule_ops_error_notification
from utils.runtime_state import mark_update_handled


class UpdateTrackingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        mark_update_handled()
        try:
            return await handler(event, data)
        except Exception as exc:
            user_id = _extract_user_id(event, data)
            update_id = _extract_update_id(data)
            where_ctx = type(event).__name__
            error_type = type(exc).__name__
            message_short = str(exc)
            log_ops_error(
                severity="ERROR",
                where_ctx=where_ctx,
                user_id=user_id,
                update_id=update_id,
                error_type=error_type,
                message_short=message_short
            )
            bot = _extract_bot(event, data)
            schedule_ops_error_notification(bot, {
                "ts_utc": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "severity": "ERROR",
                "where_ctx": where_ctx,
                "user_id": user_id,
                "update_id": update_id,
                "error_type": error_type,
                "message_short": message_short
            })
            # Keep full traceback in Railway logs.
            logging.exception("Unhandled update exception", exc_info=exc)
            raise


def _extract_update_id(data):
    try:
        event_update = data.get("event_update")
        return int(getattr(event_update, "update_id", None) or 0) or None
    except Exception:
        return None


def _extract_user_id(event, data):
    try:
        event_from_user = getattr(event, "from_user", None)
        if event_from_user and getattr(event_from_user, "id", None):
            return int(event_from_user.id)
    except Exception:
        pass
    try:
        if hasattr(event, "message") and getattr(event.message, "from_user", None):
            return int(event.message.from_user.id)
    except Exception:
        pass
    try:
        event_update = data.get("event_update")
        if event_update and getattr(event_update, "message", None) and event_update.message.from_user:
            return int(event_update.message.from_user.id)
    except Exception:
        pass
    return None


def _extract_bot(event, data):
    try:
        if data.get("bot"):
            return data.get("bot")
    except Exception:
        pass
    try:
        if getattr(event, "bot", None):
            return event.bot
    except Exception:
        pass
    try:
        event_update = data.get("event_update")
        if event_update and getattr(event_update, "bot", None):
            return event_update.bot
    except Exception:
        pass
    return None
