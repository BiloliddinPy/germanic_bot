import json
import os
import random
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    get_or_create_user_profile,
    record_navigation_event,
    update_module_progress,
    mark_writing_task_completed,
    log_event,
    save_user_submission
)
from handlers.common import send_single_ui_message
from utils.ops_logging import log_structured

router = Router()
GRAMMAR_PATH = "data/grammar.json"

class PracticeState(StatesGroup):
    waiting_for_submission = State() # General state for either voice or text

async def _show_practice_menu(message: Message, state: FSMContext, level: str, topic: dict):
    text, _, _ = _build_practice_text(level, topic)
    await state.update_data(level=level, topic_id=topic.get("id", "general"))
    await send_single_ui_message(
        message,
        text,
        reply_markup=_practice_menu(level, topic.get("id", "general")),
        parse_mode="Markdown"
    )
    await state.set_state(PracticeState.waiting_for_submission)
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
        f"3-5 ta gap yozing: **{topic_title}**"
    )
    speaking_prompt = (
        f"🎤 **Gapirish topshirig'i ({level})**\n"
        f"60 soniya gapiring: **{topic_title}**"
    )
    text = (
        "🗣️ **Sprechen & Schreiben**\n\n"
        f"{writing_prompt}\n"
        "*(Xabar ko'rinishida yozib yuboring)*\n\n"
        f"{speaking_prompt}\n"
        "*(Voice xabar yuboring)*\n\n"
        "✅ Topshiriqni yuborganingizdan so'ng, u avtomatik saqlanadi."
    )
    return text, writing_prompt, speaking_prompt


def _practice_menu(level: str, topic_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Yangi topshiriq", callback_data="practice_refresh")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])

@router.message(F.text == "🗣️ Gapirish va yozish")
@router.message(F.text == "🗣️ Sprechen & Schreiben")
async def speaking_writing_handler(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "practice", entry_type="text")
    profile = get_or_create_user_profile(message.from_user.id) or {}
    level = profile.get("current_level") or "A1"
    topic = _pick_topic(level)
    update_module_progress(message.from_user.id, "practice", level)
    await _show_practice_menu(message, state, level, topic)


@router.callback_query(F.data == "practice_refresh")
async def practice_refresh(call: CallbackQuery, state: FSMContext):
    profile = get_or_create_user_profile(call.from_user.id) or {}
    level = profile.get("current_level") or "A1"
    topic = _pick_topic(level)
    await _show_practice_menu(call.message, state, level, topic)


@router.message(PracticeState.waiting_for_submission, F.voice)
async def handle_practice_voice(message: Message, state: FSMContext):
    data = await state.get_data()
    level = data.get("level", "A1")
    topic_id = data.get("topic_id", "general")
    
    file_id = message.voice.file_id
    save_user_submission(message.from_user.id, "speaking", level, topic_id, file_id)
    update_module_progress(message.from_user.id, "practice", level, completed=True)
    log_event(message.from_user.id, "practice_speaking_submitted", section_name="practice", level=level, metadata={"topic_id": topic_id})
    
    await message.answer("Sizning nutqingiz saqlandi! ✅\nAI tez orada uni tahlil qiladi (Phase 3).")
    # Show main menu or return to practice
    from handlers.common import _send_fresh_main_menu, MAIN_MENU_TEXT
    await _send_fresh_main_menu(message, MAIN_MENU_TEXT, user_id=message.from_user.id)
    await state.clear()

@router.message(PracticeState.waiting_for_submission, F.text)
async def handle_practice_text(message: Message, state: FSMContext):
    if message.text.startswith("/") or message.text in ["🚀 Kunlik dars", "📘 Lug‘at (A1–C1)", "📐 Grammatika"]:
        return # Ignore commands/menu buttons
        
    data = await state.get_data()
    level = data.get("level", "A1")
    topic_id = data.get("topic_id", "general")
    
    save_user_submission(message.from_user.id, "writing", level, topic_id, message.text)
    mark_writing_task_completed(message.from_user.id, level, topic_id, "short_paragraph")
    update_module_progress(message.from_user.id, "practice", level, completed=True)
    log_event(message.from_user.id, "practice_writing_submitted", section_name="practice", level=level, metadata={"topic_id": topic_id})
    
    await message.answer("Sizning matningiz saqlandi! ✅\nAI tez orada xatolaringizni tekshiradi (Phase 3).")
    from handlers.common import _send_fresh_main_menu, MAIN_MENU_TEXT
    await _send_fresh_main_menu(message, MAIN_MENU_TEXT, user_id=message.from_user.id)
    await state.clear()


@router.callback_query(F.data.startswith("practice_done_"))
async def practice_done_legacy_handler(call: CallbackQuery):
    # This handled the old "Done" buttons that didn't save content.
    # We can keep it for users who just want to mark completion without typing, 
    # but we should encourage typing/speaking.
    await call.answer("Iltimos, matn yozing yoki voice yuboring!", show_alert=True)
