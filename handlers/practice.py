import json
import os
import random
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_or_create_user_profile
from database.repositories.progress_repository import record_navigation_event, update_module_progress, log_event
from database.repositories.session_repository import save_user_submission, get_recent_submissions, mark_writing_task_completed
from database.repositories.word_repository import get_words_by_level
from utils.ui_utils import send_single_ui_message, MAIN_MENU_TEXT, _md_escape
from keyboards.builders import get_levels_keyboard, get_practice_categories_keyboard

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

def _pick_topic(level: str, category: str = "daily"):
    situations = {
        "A1": {
            "daily": ["Mening oilam", "Sevimli ovqatim", "Uy hayvonim"],
            "work": ["Kasbim", "Ish stolim", "Hamkasbim"],
            "travel": ["Sayohat xaltam", "Mehmonxona", "Poyezd bekati"],
            "edu": ["Kursim", "Nemis tili darsi", "Kitobim"],
            "leisure": ["Dam olish kuni", "Kino", "Parkda sayr"]
        },
        "B1": {
            "daily": ["Sog'lom turmush tarzi", "Ijarada yashash muammolari"],
            "work": ["Ish qidirish jarayoni", "Muzokaralar"],
            "travel": ["Eko-turizm", "Chet elda yashash qiyinchiliklari"],
            "edu": ["Chet tilini o'rganish usullari", "Onlayn ta'lim"],
            "leisure": ["Ijtimoiy tarmoqlar foydasi", "Hobbilarning ahamiyati"]
        }
    }
    level_data = situations.get(level, situations["A1"])
    topics = level_data.get(category, level_data["daily"])
    title = random.choice(topics)
    return {"id": f"{level}_{category}_{random.randint(100,999)}", "title": title}

class PracticeState(StatesGroup):
    waiting_for_submission = State() 

def _practice_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Yozish (Schreiben)", callback_data="practice_mode:writing")],
        [InlineKeyboardButton(text="🎤 Gapirish (Sprechen)", callback_data="practice_mode:speaking")],
        [InlineKeyboardButton(text="📜 Mening ishlarim", callback_data="practice_history")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])

@router.message(F.text.contains("Gapirish va yozish") | F.text.contains("Sprechen & Schreiben"))
async def speaking_writing_handler(message: Message, state: FSMContext):
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "practice_main", entry_type="text")
    text = (
        "🗣️ **Sprechen & Schreiben**\n\n"
        "Professional til o'rganish bo'limiga xush kelibsiz!\n"
        "Bu yerda siz o'z fikringizni yozma va og'zaki bayon qilishni mashq qilasiz.\n\n"
        "Qaysi yo'nalishni tanlaysiz?"
    )
    await send_single_ui_message(message, text, reply_markup=_practice_main_menu(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("practice_mode:"))
async def practice_mode_callback(call: CallbackQuery, state: FSMContext):
    mode = call.data.split(":")[1]
    await state.update_data(mode=mode)
    text = (
        f"📍 **Bosqich: Darajani tanlang**\n\n"
        f"{'✍️ Yozish' if mode == 'writing' else '🎤 Gapirish'} uchun mos darajani tanlang:"
    )
    await call.message.edit_text(text, reply_markup=get_levels_keyboard("practice_level"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("practice_level_"))
async def practice_level_callback(call: CallbackQuery, state: FSMContext):
    level = call.data.replace("practice_level_", "")
    await state.update_data(level=level)
    text = (
        f"🎯 **Bosqich: Mavzu yo'nalishi**\n\n"
        f"Qaysi yo'nalishda mashq qilishni xohlaysiz? ({level})"
    )
    await call.message.edit_text(text, reply_markup=get_practice_categories_keyboard("practice_cat"), parse_mode="Markdown")

@router.callback_query(F.data.startswith("practice_cat_"))
async def practice_category_callback(call: CallbackQuery, state: FSMContext):
    category = call.data.replace("practice_cat_", "")
    data = await state.get_data()
    mode = data.get("mode", "writing")
    level = data.get("level", "A1")
    topic = _pick_topic(level, category)
    await _show_task(call.message, state, mode, level, topic)

async def _show_task(message: Message, state: FSMContext, mode: str, level: str, topic: dict):
    topic_title = topic.get("title", "Umumiy mavzu")
    await state.update_data(level=level, topic_id=topic.get("id", "general"), mode=mode)
    if mode == "writing":
        icon, title = "✍️", "Yozish (Schreiben)"
        instr = "3-5 ta gapdan iborat matn yozib yuboring."
    else:
        icon, title = "🎤", "Gapirish (Sprechen)"
        instr = "60 soniya davomida voice (ovozli xabar) yuboring."

    text = (
        f"{icon} **{_md_escape(title)} - {level}**\n\n"
        f"Mavzu: **{_md_escape(topic_title)}**\n\n"
        f"📝 **Vazifa:** {_md_escape(instr)}\n\n"
        "✅ Xabar yuborishingiz bilan u saqlanadi."
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Boshqa mavzu", callback_data=f"practice_refresh:{mode}:{level}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="practice_back_main")]
    ])
    await message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await state.set_state(PracticeState.waiting_for_submission)

@router.callback_query(F.data.startswith("practice_refresh:"))
async def practice_refresh_callback(call: CallbackQuery, state: FSMContext):
    _, mode, level = call.data.split(":")
    topic = _pick_topic(level)
    await _show_task(call.message, state, mode, level, topic)

@router.callback_query(F.data == "practice_back_main")
async def practice_back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🗣️ **Sprechen & Schreiben**\n\nTanlang:", reply_markup=_practice_main_menu())

@router.callback_query(F.data == "practice_history")
async def practice_history_callback(call: CallbackQuery):
    subs = get_recent_submissions(call.from_user.id, limit=5)
    if not subs:
        await call.answer("Hali ishlar mavjud emas.", show_alert=True)
        return
    text = "📜 **Mening oxirgi ishlarim:**\n\n"
    for i, s in enumerate(subs, 1):
        m_type = "✍️ Yozma" if s['module'] == 'writing' else "🎤 Ovozli"
        content = s['content'] if s['module'] == 'writing' else "[Voice message]"
        date = s['created_at'].split()[0]
        text += f"{i}. {m_type} ({s['level']}) - {date}\n_{content[:40]}..._\n\n"
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="practice_back_main")]])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

@router.message(PracticeState.waiting_for_submission, F.voice)
async def handle_practice_voice(message: Message, state: FSMContext):
    data = await state.get_data()
    level = data.get("level", "A1")
    topic_id = data.get("topic_id", "general")
    save_user_submission(message.from_user.id, "speaking", message.voice.file_id, level, {"topic_id": topic_id})
    update_module_progress(message.from_user.id, "practice", level, completed=True)
    log_event(message.from_user.id, "practice_speaking_submitted", section_name="practice", level=level, metadata={"topic_id": topic_id})
    await message.answer("Sizning nutqingiz saqlandi! ✅\nAI tez orada uni tahlil qiladi (Phase 3).")
    await _send_fresh_main_menu(message, MAIN_MENU_TEXT, user_id=message.from_user.id)
    await state.clear()

@router.message(PracticeState.waiting_for_submission, F.text)
async def handle_practice_text(message: Message, state: FSMContext):
    if message.text.startswith("/") or message.text in ["🏠 Bosh menyu"]:
        await state.clear()
        return 
    data = await state.get_data()
    level = data.get("level", "A1")
    topic_id = data.get("topic_id", "general")
    save_user_submission(message.from_user.id, "writing", message.text, level, {"topic_id": topic_id})
    mark_writing_task_completed(message.from_user.id, level, topic_id, "short_paragraph")
    update_module_progress(message.from_user.id, "practice", level, completed=True)
    log_event(message.from_user.id, "practice_writing_submitted", section_name="practice", level=level, metadata={"topic_id": topic_id})
    await message.answer("Sizning matningiz saqlandi! ✅\nAI tez orada xatolaringizni tekshiradi (Phase 3).")
    await _send_fresh_main_menu(message, MAIN_MENU_TEXT, user_id=message.from_user.id)
    await state.clear()
