import json
import random
import os
import datetime
import asyncio
import logging
from zoneinfo import ZoneInfo
from typing import Awaitable, cast
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from core.config import settings
from database.repositories.broadcast_repository import (
    claim_pending_jobs,
    enqueue_broadcast_jobs,
    mark_job_sent,
    recover_stale_processing_jobs,
    reschedule_job,
)
from utils.ui_utils import send_single_ui_message

router = Router()
DATA_DIR = "data"
DAILY_TIMEZONE = "Asia/Tashkent"


def _now_in_daily_tz() -> datetime.datetime:
    return datetime.datetime.now(ZoneInfo(DAILY_TIMEZONE))


def _current_time_slot() -> str:
    return _now_in_daily_tz().strftime("%H:00")


def _daily_slot_key(now_tz: datetime.datetime | None = None) -> str:
    ts = now_tz or _now_in_daily_tz()
    return ts.strftime("%Y-%m-%d_%H:00")


def _retry_delay_seconds(attempts_done: int) -> int:
    # 15s, 30s, 60s, 120s... capped at 15 min.
    return min(900, max(15, 15 * (2 ** max(0, attempts_done))))

def load_daily_words():
    file_path = f"{DATA_DIR}/daily_words.json"
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_todays_word():
    words = load_daily_words()
    if not words:
        return None
    day_of_year = _now_in_daily_tz().timetuple().tm_yday
    word_index = day_of_year % len(words)
    return words[word_index]

@router.message(F.text == "🌟 Kun so‘zi")
async def daily_word_manual_handler(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    word = get_todays_word()
    
    if not word:
        await cast(
            Awaitable[Message],
            send_single_ui_message(message, "Bugungi kun so'zi hali belgilanmagan.")
        )
        return

    text = (
        f"🌟 **Kun so‘zi**\n\n"
        f"🇩🇪 **{word['de']}** ({word['pos']})\n"
        f"🇺🇿 {word['uz']}\n\n"
        f"📌 Misol:\n"
        f"🇩🇪 _{word['example_de']}_\n"
        f"🇺🇿 _{word['example_uz']}_"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Boshqa so'z", callback_data="daily_random")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await cast(
        Awaitable[Message],
        send_single_ui_message(message, text, reply_markup=builder, parse_mode="Markdown")
    )

@router.callback_query(F.data == "daily_random")
async def daily_random_handler(call: CallbackQuery):
    words = load_daily_words()
    if not words:
         await call.answer("So'zlar yo'q.", show_alert=True)
         return
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
         
    word = random.choice(words)
    
    text = (
        f"🌟 **Tasodifiy so‘z**\n\n"
        f"🇩🇪 **{word['de']}** ({word['pos']})\n"
        f"🇺🇿 {word['uz']}\n\n"
        f"📌 Misol:\n"
        f"🇩🇪 _{word['example_de']}_\n"
        f"🇺🇿 _{word['example_uz']}_"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Yana", callback_data="daily_random")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

async def send_daily_word_to_all(bot: Bot):
    try:
        from database.repositories.user_repository import get_subscribed_users_for_time
        from core.texts import DAILY_QUOTES
        
        # Keep scheduler and DB time matching in the same timezone.
        current_time_str = _current_time_slot()
        users = get_subscribed_users_for_time(current_time_str)
        word = get_todays_word()
        
        if not word or not users:
            return

        quote = random.choice(DAILY_QUOTES)
        payload = {
            "quote_de": quote.get("de", ""),
            "quote_author": quote.get("author", ""),
            "quote_uz": quote.get("uz", ""),
            "word_de": word.get("de", ""),
            "word_pos": word.get("pos", ""),
            "word_uz": word.get("uz", ""),
            "slot": current_time_str,
        }
        inserted = enqueue_broadcast_jobs(
            users,
            kind="daily_word",
            payload=payload,
            slot_key=_daily_slot_key(),
        )
        logging.info(
            "Daily broadcast jobs enqueued slot=%s users=%d inserted=%d",
            current_time_str,
            len(users),
            inserted,
        )
    except Exception as e:
        logging.error(f"Daily broadcast error: {e}")


def _render_daily_payload(payload: dict) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"📜 **Kunlik Hikmat**\n"
        f"_{payload.get('quote_de', '')}_\n"
        f"— *{payload.get('quote_author', '')}*\n\n"
        f"🇺🇿 *{payload.get('quote_uz', '')}*\n\n"
        f"📚 **Bugungi yangi so'z:**\n"
        f"🔹 **{payload.get('word_de', '')}** ({payload.get('word_pos', '')}) — {payload.get('word_uz', '')}\n\n"
        f"⏳ *Sizning shaxsiy darsingiz tayyor! Boshlaymizmi?*"
    )
    builder = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Darsni boshlash", callback_data="daily_begin")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyuga", callback_data="home")],
        ]
    )
    return text, builder


async def process_broadcast_queue(bot: Bot):
    recovered = recover_stale_processing_jobs(
        stale_seconds=settings.broadcast_processing_stale_seconds
    )
    if recovered > 0:
        logging.warning("Recovered stale broadcast jobs: %d", recovered)
    jobs = claim_pending_jobs(limit=settings.broadcast_claim_batch_size)
    if not jobs:
        return

    sem = asyncio.Semaphore(max(1, settings.broadcast_send_concurrency))

    async def _send_one(job: dict):
        async with sem:
            attempts_done = int(job.get("attempts", 0))
            try:
                payload = json.loads(job.get("payload") or "{}")
                text, builder = _render_daily_payload(payload)
                await bot.send_message(
                    int(job["user_id"]),
                    text,
                    reply_markup=builder,
                    parse_mode="Markdown",
                )
                mark_job_sent(int(job["id"]))
            except Exception as exc:
                reschedule_job(
                    job_id=int(job["id"]),
                    attempts_done=attempts_done,
                    error_msg=str(exc),
                    delay_seconds=_retry_delay_seconds(attempts_done),
                    max_attempts=max(1, settings.broadcast_max_attempts),
                )

    await asyncio.gather(*[_send_one(j) for j in jobs], return_exceptions=True)
