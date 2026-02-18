import json
import os
import random
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import (
    get_or_create_user_profile,
    record_navigation_event,
    update_module_progress,
    mark_writing_task_completed,
    log_event
)
from handlers.common import send_single_ui_message

router = Router()
GRAMMAR_PATH = "data/grammar.json"


def _load_topics(level: str):
    if not os.path.exists(GRAMMAR_PATH):
        return []
    try:
        with open(GRAMMAR_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(level, [])
    except Exception:
        return []


def _pick_topic(level: str):
    topics = _load_topics(level)
    if not topics:
        return {"id": "general", "title": "Umumiy mavzu"}
    return random.choice(topics)


def _build_practice_text(level: str, topic: dict):
    topic_title = topic.get("title", "Umumiy mavzu")
    writing_prompt = (
        f"✍️ **Yozma topshiriq ({level})**\n"
        f"3-5 ta gap yozing: **{topic_title}** mavzusida."
    )
    speaking_prompt = (
        f"🎤 **Gapirish topshirig'i ({level})**\n"
        f"60 soniya davomida gapiring: **{topic_title}** mavzusida."
    )
    text = (
        "🗣️ **Sprechen & Schreiben**\n\n"
        f"{writing_prompt}\n\n"
        f"{speaking_prompt}\n\n"
        "Topshiriqni bajargach, mos tugmani bosing."
    )
    return text, writing_prompt, speaking_prompt


def _practice_menu(level: str, topic_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yozma bajarildi", callback_data=f"practice_done_writing:{level}:{topic_id}")],
        [InlineKeyboardButton(text="✅ Gapirish bajarildi", callback_data=f"practice_done_speaking:{level}:{topic_id}")],
        [InlineKeyboardButton(text="🔁 Yangi topshiriq", callback_data="practice_refresh")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])

@router.message(F.text == "🗣️ Gapirish va yozish")
@router.message(F.text == "🗣️ Sprechen & Schreiben")
async def speaking_writing_handler(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "practice", entry_type="text")
    profile = get_or_create_user_profile(message.from_user.id) or {}
    level = profile.get("current_level") or "A1"
    topic = _pick_topic(level)
    text, _, _ = _build_practice_text(level, topic)
    update_module_progress(message.from_user.id, "practice", level)
    await send_single_ui_message(
        message,
        text,
        reply_markup=_practice_menu(level, topic.get("id", "general")),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "practice_refresh")
async def practice_refresh(call: CallbackQuery):
    profile = get_or_create_user_profile(call.from_user.id) or {}
    level = profile.get("current_level") or "A1"
    topic = _pick_topic(level)
    text, _, _ = _build_practice_text(level, topic)
    await call.message.edit_text(
        text,
        reply_markup=_practice_menu(level, topic.get("id", "general")),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("practice_done_writing:"))
async def practice_done_writing(call: CallbackQuery):
    _, level, topic_id = call.data.split(":", 2)
    mark_writing_task_completed(call.from_user.id, level, topic_id, "short_paragraph")
    update_module_progress(call.from_user.id, "practice", level, completed=True)
    log_event(call.from_user.id, "practice_writing_done", section_name="practice", level=level, metadata={"topic_id": topic_id})
    await call.answer("Yozma topshiriq progressga yozildi ✅", show_alert=False)


@router.callback_query(F.data.startswith("practice_done_speaking:"))
async def practice_done_speaking(call: CallbackQuery):
    _, level, topic_id = call.data.split(":", 2)
    update_module_progress(call.from_user.id, "practice", level, completed=True)
    log_event(call.from_user.id, "practice_speaking_done", section_name="practice", level=level, metadata={"topic_id": topic_id})
    await call.answer("Gapirish topshirig'i progressga yozildi ✅", show_alert=False)
