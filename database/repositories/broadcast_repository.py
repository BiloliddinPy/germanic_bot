import datetime
import json
import logging
from typing import Any

from database.connection import get_connection, is_postgres_backend


def _utc_now_iso() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def enqueue_broadcast_jobs(
    user_ids: list[int],
    kind: str,
    payload: dict[str, Any],
    slot_key: str,
) -> int:
    if not user_ids:
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    payload_json = json.dumps(payload, ensure_ascii=False)
    inserted = 0
    try:
        for user_id in user_ids:
            dedupe_key = f"{kind}:{slot_key}:{user_id}"
            cursor.execute(
                """
                INSERT INTO broadcast_jobs (
                    user_id, kind, payload, status, attempts, available_at, dedupe_key
                )
                VALUES (?, ?, ?, 'pending', 0, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(dedupe_key) DO NOTHING
                """,
                (user_id, kind, payload_json, dedupe_key),
            )
            if int(getattr(cursor, "rowcount", 0) or 0) > 0:
                inserted += 1
        conn.commit()
    except Exception as exc:
        logging.error("enqueue_broadcast_jobs failed: %s", exc)
    finally:
        conn.close()
    return inserted


def claim_pending_jobs(limit: int = 1000) -> list[dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    claimed: list[dict[str, Any]] = []
    try:
        batch_limit = max(1, limit)
        if is_postgres_backend():
            cursor.execute(
                """
                WITH to_claim AS (
                    SELECT id
                    FROM broadcast_jobs
                    WHERE status = 'pending' AND available_at <= CURRENT_TIMESTAMP
                    ORDER BY id ASC
                    LIMIT ?
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE broadcast_jobs bj
                SET status = 'processing', locked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                FROM to_claim tc
                WHERE bj.id = tc.id
                RETURNING bj.id, bj.user_id, bj.kind, bj.payload, bj.attempts
                """,
                (batch_limit,),
            )
            for row in cursor.fetchall():
                claimed.append(
                    {
                        "id": int(row["id"]),
                        "user_id": int(row["user_id"]),
                        "kind": str(row["kind"]),
                        "payload": str(row["payload"]),
                        "attempts": int(row["attempts"] or 0),
                    }
                )
        else:
            cursor.execute(
                """
                SELECT id, user_id, kind, payload, attempts
                FROM broadcast_jobs
                WHERE status = 'pending' AND available_at <= CURRENT_TIMESTAMP
                ORDER BY id ASC
                LIMIT ?
                """,
                (batch_limit,),
            )
            rows = cursor.fetchall()
            for row in rows:
                job_id = int(row["id"])
                cursor.execute(
                    """
                    UPDATE broadcast_jobs
                    SET status = 'processing', locked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'pending'
                    """,
                    (job_id,),
                )
                if int(getattr(cursor, "rowcount", 0) or 0) > 0:
                    claimed.append(
                        {
                            "id": job_id,
                            "user_id": int(row["user_id"]),
                            "kind": str(row["kind"]),
                            "payload": str(row["payload"]),
                            "attempts": int(row["attempts"] or 0),
                        }
                    )
        conn.commit()
    except Exception as exc:
        logging.error("claim_pending_jobs failed: %s", exc)
    finally:
        conn.close()
    return claimed


def recover_stale_processing_jobs(stale_seconds: int = 900) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    recovered = 0
    safe_stale_seconds = max(30, stale_seconds)
    try:
        if is_postgres_backend():
            cursor.execute(
                """
                UPDATE broadcast_jobs
                SET status = 'pending',
                    locked_at = NULL,
                    available_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'processing'
                  AND locked_at IS NOT NULL
                  AND locked_at < (CURRENT_TIMESTAMP - (? * INTERVAL '1 second'))
                """,
                (safe_stale_seconds,),
            )
        else:
            cursor.execute(
                """
                UPDATE broadcast_jobs
                SET status = 'pending',
                    locked_at = NULL,
                    available_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'processing'
                  AND locked_at IS NOT NULL
                  AND locked_at < datetime('now', ?)
                """,
                (f"-{safe_stale_seconds} seconds",),
            )
        recovered = int(getattr(cursor, "rowcount", 0) or 0)
        conn.commit()
    except Exception as exc:
        logging.error("recover_stale_processing_jobs failed: %s", exc)
    finally:
        conn.close()
    return recovered


def mark_job_sent(job_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE broadcast_jobs
            SET status = 'sent', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (job_id,),
        )
        conn.commit()
    except Exception as exc:
        logging.error("mark_job_sent failed: %s", exc)
    finally:
        conn.close()


def reschedule_job(job_id: int, attempts_done: int, error_msg: str, delay_seconds: int, max_attempts: int):
    next_dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=max(1, delay_seconds))
    next_at = next_dt.strftime("%Y-%m-%d %H:%M:%S")
    next_attempts = attempts_done + 1
    status = "failed" if next_attempts >= max_attempts else "pending"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE broadcast_jobs
            SET status = ?, attempts = ?, last_error = ?, last_error_at = CURRENT_TIMESTAMP,
                available_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, next_attempts, error_msg[:500], next_at, job_id),
        )
        conn.commit()
    except Exception as exc:
        logging.error("reschedule_job failed: %s", exc)
    finally:
        conn.close()


def get_broadcast_queue_counts() -> dict[str, int]:
    conn = get_connection()
    cursor = conn.cursor()
    result = {"pending": 0, "processing": 0, "sent": 0, "failed": 0}
    try:
        cursor.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM broadcast_jobs
            GROUP BY status
            """
        )
        for row in cursor.fetchall():
            result[str(row["status"])] = int(row["cnt"])
    except Exception:
        pass
    finally:
        conn.close()
    return result
