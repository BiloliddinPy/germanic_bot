import argparse
import datetime as dt
import os
import re
import sys


CONFLICT_TOKEN = "TelegramConflictError"
CONNECTED_TOKEN = "Connection established"


def parse_ts(line: str):
    # Expected format starts with ISO timestamp like:
    # 2026-02-18T22:07:08.273247094Z ...
    raw = line.split(" ", 1)[0].strip()
    if "T" not in raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    if "." in raw:
        head, tail = raw.split(".", 1)
        # Keep only first 6 digits for Python microseconds.
        frac = re.sub(r"[^0-9].*$", "", tail)
        suffix = tail[len(frac):]
        frac = (frac + "000000")[:6]
        raw = f"{head}.{frac}{suffix}"
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def load_lines(path: str):
    if path == "-":
        return sys.stdin.read().splitlines()
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().splitlines()


def main():
    parser = argparse.ArgumentParser(
        description="Check aiogram polling conflict severity from logs."
    )
    parser.add_argument("--file", default="bot.log", help="Log path or '-' for stdin")
    parser.add_argument("--minutes", type=int, default=10, help="Lookback window (minutes)")
    parser.add_argument("--warn", type=int, default=3, help="Warn threshold within window")
    parser.add_argument("--crit", type=int, default=10, help="Critical threshold within window")
    args = parser.parse_args()

    lines = load_lines(args.file)
    if not lines:
        print("OK: log is empty, no conflict detected.")
        return 0

    conflicts = []
    connected = []
    saw_timestamp = False
    for line in lines:
        ts = parse_ts(line)
        if ts is not None:
            saw_timestamp = True
        if CONFLICT_TOKEN in line:
            conflicts.append(ts)
        if CONNECTED_TOKEN in line:
            connected.append(ts)

    if not conflicts:
        print("OK: no TelegramConflictError found.")
        return 0

    if saw_timestamp:
        conflict_ts = [t for t in conflicts if t is not None]
        connected_ts = [t for t in connected if t is not None]
        last_ts = max(conflict_ts + connected_ts) if connected_ts else conflict_ts[-1]
        window_start = last_ts - dt.timedelta(minutes=max(args.minutes, 1))
        recent_conflicts = [t for t in conflict_ts if t >= window_start]
        recent_connected = [t for t in connected_ts if t >= window_start]

        after_last_connect = 0
        if connected_ts:
            last_connect = connected_ts[-1]
            after_last_connect = len([t for t in conflict_ts if t > last_connect])
    else:
        # Fallback for logs without timestamps (still actionable for conflict checks).
        recent_conflicts = conflicts
        recent_connected = connected
        after_last_connect = 0

    summary = (
        f"total_conflicts={len(conflicts)} "
        f"recent_conflicts={len(recent_conflicts)} "
        f"recent_connected={len(recent_connected)} "
        f"after_last_connect={after_last_connect} "
        f"time_window={'enabled' if saw_timestamp else 'disabled'}"
    )

    if len(recent_conflicts) >= max(args.crit, args.warn + 1):
        print(f"CRITICAL: polling conflict storm detected ({summary})")
        return 2
    if len(recent_conflicts) >= max(args.warn, 1):
        print(f"WARN: polling conflict observed ({summary})")
        return 1

    print(f"OK: low conflict level ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
