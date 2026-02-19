import datetime
import json
import logging


def log_structured(event: str, **fields):
    payload = {
        "event": event,
        "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    }
    payload.update(fields)
    logging.info(json.dumps(payload, ensure_ascii=False, default=str))
