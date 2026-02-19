import datetime

_START_TIME_UTC = datetime.datetime.utcnow()
_LAST_UPDATE_HANDLED_UTC = None


def mark_started():
    global _START_TIME_UTC
    _START_TIME_UTC = datetime.datetime.utcnow()


def mark_update_handled():
    global _LAST_UPDATE_HANDLED_UTC
    _LAST_UPDATE_HANDLED_UTC = datetime.datetime.utcnow()


def get_uptime_seconds() -> int:
    return max(int((datetime.datetime.utcnow() - _START_TIME_UTC).total_seconds()), 0)


def get_last_update_handled_iso() -> str | None:
    if not _LAST_UPDATE_HANDLED_UTC:
        return None
    return _LAST_UPDATE_HANDLED_UTC.isoformat(timespec="seconds") + "Z"
