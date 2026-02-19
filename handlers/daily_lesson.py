import logging
import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from services.learning_service import LearningService
from services.user_service import UserService
from services.stats_service import StatsService
from services.grammar_service import GrammarService
from database.repositories.session_repository import get_daily_lesson_state, save_daily_lesson_state, save_user_submission, delete_daily_lesson_state
from database.repositories.lesson_repository import save_daily_plan, get_last_daily_plan
from utils.ui_utils import send_single_ui_message, _md_escape
from core.config import settings

router = Router()

# Constants
STATUS_IDLE = "idle"
STATUS_IN_PROGRESS = "in_progress"
STATUS_FINISHED = "finished"

STEPS = {
    1: "warmup",
    2: "vocabulary",
    3: "grammar",
    4: "quiz",
    5: "production",
    6: "summary"
}

@router.message(F.text == "🚀 Kunlik dars")
async def daily_lesson_start(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    
    user_id = message.from_user.id
    StatsService.log_navigation(user_id, "daily_lesson", entry_type="text")
    await _show_entry_screen(message, user_id)

@router.callback_query(F.data == "daily_begin")
async def daily_begin_handler(call: CallbackQuery):
    user_id = call.from_user.id
    profile = UserService.get_profile(user_id)
    
    # Create or load plan
    plan = get_last_daily_plan(user_id)
    # Check if plan is from today
    # (Simplified for now: always create if not in progress)
    
    session_plan = LearningService.create_daily_plan(user_id, profile)
    save_daily_plan(user_id, session_plan)
    
    # Initialize session state
    state = {
        "status": STATUS_IN_PROGRESS,
        "step": 1,
        "plan": session_plan,
        "results": {"quiz_correct": 0, "quiz_total": 0}
    }
    save_daily_lesson_state(user_id, state)
    
    await _render_step(call.message, user_id, state)

@router.callback_query(F.data == "daily_resume")
async def daily_resume_handler(call: CallbackQuery):
    user_id = call.from_user.id
    state = get_daily_lesson_state(user_id)
    if not state or state.get("status") != STATUS_IN_PROGRESS:
        await call.answer("Faol sessiya topilmadi.")
        await _show_entry_screen(call.message, user_id)
        return
    
    await _render_step(call.message, user_id, state)

async def _show_entry_screen(message: Message, user_id: int):
    state = get_daily_lesson_state(user_id)
    status = state.get("status") if state else STATUS_IDLE
    
    if status == STATUS_FINISHED:
        text = "✅ **Bugungi dars yakunlandi!**\n\nErtaga yangi mavzular bilan uchrashamiz. ✨"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
    elif status == STATUS_IN_PROGRESS:
        text = "📅 **Bugungi dars davom etmoqda**\n\nQolgan joyidan davom ettiramizmi?"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Davom ettirish", callback_data="daily_resume")],
            [InlineKeyboardButton(text="Bekor qilish", callback_data="daily_cancel")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
    else:
        text = "🚀 **Kunlik yangi dars tayyor!**\n\nBugun siz bilan yangi so'zlar va grammatika ustida ishlaymiz."
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Boshlash", callback_data="daily_begin")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        
    await send_single_ui_message(message, text, reply_markup=markup, parse_mode="Markdown", user_id=user_id)

async def _render_step(message: Message, user_id: int, state: dict):
    step = state.get("step", 1)
    plan = state.get("plan", {})
    
    header = f"🚀 **{step}/6 — {STEPS[step].title()}**\n\n"
    
    if step == 1: # Warmup
        topic_id = plan.get("grammar_topic_id")
        topic, _ = GrammarService.get_topic_by_id(topic_id)
        text = f"{header}Bugungi fokus: **{topic['title']}**\n\nTayyormisiz?"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Ha, tayyorman!", callback_data="daily_step_2")]
        ])
    elif step == 2: # Vocab
        from database.repositories.word_repository import get_words_by_ids
        words = get_words_by_ids(plan.get("vocab_ids", []))
        word_list = "\n".join([f"🔹 **{w['de']}** — {w['uz']}" for w in words])
        text = f"{header}Yangi so'zlar:\n\n{word_list}"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Keyingi", callback_data="daily_step_3")]
        ])
    elif step == 3: # Grammar
        topic_id = plan.get("grammar_topic_id")
        topic, _ = GrammarService.get_topic_by_id(topic_id)
        text = f"{header}📐 **{topic['title']}**\n\n{topic['content'][:500]}..."
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Tushunarli", callback_data="daily_step_4")]
        ])
    elif step == 4: # Quiz
        # This would handle multiple questions, simplified for structure
        text = f"{header}🧠 Kichik test vaqti!"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Boshlash", callback_data="daily_step_5")]
        ])
    elif step == 5: # Production
        mode = plan.get("production_mode")
        text = f"{header}🗣️ **{mode.title()}** vaqti!\n\nBerilgan mavzuda fikringizni yozing yoki ovozli xabar yuboring."
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Bajarildi", callback_data="daily_step_6")]
        ])
    elif step == 6: # Summary
        text = f"{header}🏁 **Tabriklaymiz!**\n\nBugungi dars muvaffaqiyatli yakunlandi."
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Tugatish", callback_data="daily_finish")]
        ])
        
    await message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

@router.callback_query(F.data.startswith("daily_step_"))
async def daily_step_callback(call: CallbackQuery):
    next_step = int(call.data.split("_")[2])
    user_id = call.from_user.id
    state = get_daily_lesson_state(user_id)
    if state:
        state["step"] = next_step
        save_daily_lesson_state(user_id, state)
        await _render_step(call.message, user_id, state)
    else:
        await call.answer("Dars sessiyasi topilmadi.")
        await _show_entry_screen(call.message, user_id)

@router.callback_query(F.data == "daily_finish")
async def daily_finish_callback(call: CallbackQuery):
    user_id = call.from_user.id
    state = get_daily_lesson_state(user_id)
    if state:
        state["status"] = STATUS_FINISHED
        save_daily_lesson_state(user_id, state)
    
    await call.answer("Dars yakunlandi! 🏆")
    from utils.ui_utils import _send_fresh_main_menu
    await _send_fresh_main_menu(call.message, "Ajoyib! Bugungi dars yakunlandi. Nima bilan davom etamiz?", user_id=user_id)

@router.callback_query(F.data == "daily_cancel")
async def daily_cancel_handler(call: CallbackQuery):
    user_id = call.from_user.id
    delete_daily_lesson_state(user_id)
    await call.answer("Dars bekor qilindi.")
    await _show_entry_screen(call.message, user_id)
