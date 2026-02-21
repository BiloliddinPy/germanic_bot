import asyncio
import json
from typing import Any, Mapping

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

from database.connection import get_connection


def _normalize_key(key: StorageKey) -> tuple[int, int, int, int, str, str]:
    return (
        int(key.bot_id),
        int(key.chat_id),
        int(key.user_id),
        int(key.thread_id or 0),
        str(key.business_connection_id or ""),
        str(key.destiny or "default"),
    )


def _coerce_state(state: StateType = None) -> str | None:
    if state is None:
        return None
    if isinstance(state, State):
        return state.state
    return str(state)


class DBFSMStorage(BaseStorage):
    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        await asyncio.to_thread(self._set_state_sync, key, _coerce_state(state))

    async def get_state(self, key: StorageKey) -> str | None:
        return await asyncio.to_thread(self._get_state_sync, key)

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await asyncio.to_thread(self._set_data_sync, key, dict(data))

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_data_sync, key)

    async def close(self) -> None:
        return

    def _set_state_sync(self, key: StorageKey, state: str | None) -> None:
        conn = get_connection()
        try:
            cur = conn.cursor()
            bot_id, chat_id, user_id, thread_id, business_connection_id, destiny = _normalize_key(key)
            cur.execute(
                """
                INSERT INTO fsm_state (
                    bot_id, chat_id, user_id, thread_id, business_connection_id, destiny, state, data, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, '{}', CURRENT_TIMESTAMP)
                ON CONFLICT(bot_id, chat_id, user_id, thread_id, business_connection_id, destiny)
                DO UPDATE SET state = EXCLUDED.state, updated_at = CURRENT_TIMESTAMP
                """,
                (bot_id, chat_id, user_id, thread_id, business_connection_id, destiny, state),
            )
            conn.commit()
        finally:
            conn.close()

    def _get_state_sync(self, key: StorageKey) -> str | None:
        conn = get_connection()
        try:
            cur = conn.cursor()
            bot_id, chat_id, user_id, thread_id, business_connection_id, destiny = _normalize_key(key)
            cur.execute(
                """
                SELECT state
                FROM fsm_state
                WHERE bot_id = ? AND chat_id = ? AND user_id = ? AND thread_id = ?
                  AND business_connection_id = ? AND destiny = ?
                """,
                (bot_id, chat_id, user_id, thread_id, business_connection_id, destiny),
            )
            row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return row[0]

    def _set_data_sync(self, key: StorageKey, data: dict[str, Any]) -> None:
        conn = get_connection()
        try:
            cur = conn.cursor()
            bot_id, chat_id, user_id, thread_id, business_connection_id, destiny = _normalize_key(key)
            payload = json.dumps(data, ensure_ascii=False)
            cur.execute(
                """
                INSERT INTO fsm_state (
                    bot_id, chat_id, user_id, thread_id, business_connection_id, destiny, state, data, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bot_id, chat_id, user_id, thread_id, business_connection_id, destiny)
                DO UPDATE SET data = EXCLUDED.data, updated_at = CURRENT_TIMESTAMP
                """,
                (bot_id, chat_id, user_id, thread_id, business_connection_id, destiny, payload),
            )
            conn.commit()
        finally:
            conn.close()

    def _get_data_sync(self, key: StorageKey) -> dict[str, Any]:
        conn = get_connection()
        try:
            cur = conn.cursor()
            bot_id, chat_id, user_id, thread_id, business_connection_id, destiny = _normalize_key(key)
            cur.execute(
                """
                SELECT data
                FROM fsm_state
                WHERE bot_id = ? AND chat_id = ? AND user_id = ? AND thread_id = ?
                  AND business_connection_id = ? AND destiny = ?
                """,
                (bot_id, chat_id, user_id, thread_id, business_connection_id, destiny),
            )
            row = cur.fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            return {}
        try:
            parsed = json.loads(row[0])
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
