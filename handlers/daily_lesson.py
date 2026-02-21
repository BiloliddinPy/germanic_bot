import re
import random
from typing import Any, Awaitable, cast
from database.repositories.word_repository import get_words_by_ids, get_random_words
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.learning_service import LearningService
from services.user_service import UserService
from services.stats_service import StatsService
from services.grammar_service import GrammarService
from database.repositories.session_repository import get_daily_lesson_state, save_daily_lesson_state, delete_daily_lesson_state
from database.repositories.lesson_repository import save_daily_plan, mark_grammar_topic_seen
from utils.ui_utils import send_single_ui_message

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

    if not message.from_user:
        return
    user_id = message.from_user.id
    StatsService.log_navigation(user_id, "daily_lesson", entry_type="text")
    await _show_entry_screen(message, user_id)

@router.callback_query(F.data == "daily_begin")
async def daily_begin_handler(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    profile = UserService.get_profile(user_id) or {}
    session_plan = LearningService.create_daily_plan(user_id, profile)
    save_daily_plan(user_id, session_plan)
    topic_id = session_plan.get("grammar_topic_id")
    level = str(session_plan.get("level") or profile.get("current_level") or "A1")
    if topic_id:
        mark_grammar_topic_seen(user_id, str(topic_id), level)

    # Initialize session state
    state = {
        "status": STATUS_IN_PROGRESS,
        "step": 1,
        "plan": session_plan,
        "results": {"quiz_correct": 0, "quiz_total": 0}
    }
    save_daily_lesson_state(user_id, state)

    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    await _render_step(message, user_id, state)

@router.callback_query(F.data == "daily_resume")
async def daily_resume_handler(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    state = get_daily_lesson_state(user_id)
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    if not state or state.get("status") != STATUS_IN_PROGRESS:
        await call.answer("Faol sessiya topilmadi.")
        await _show_entry_screen(message, user_id)
        return

    await _render_step(message, user_id, state)

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
        
    await cast(
        Awaitable[Message],
        send_single_ui_message(message, text, reply_markup=markup, parse_mode="Markdown", user_id=user_id),
    )

async def _render_step(message: Message, user_id: int, state: dict):
    step = state.get("step", 1)
    plan = state.get("plan", {})
    
    step_name = STEPS.get(step, "lesson")
    header = f"🚀 **{step}/6 — {step_name.title()}**\n\n"
    
    if step == 1: # Warmup
        topic_id = plan.get("grammar_topic_id")
        topic, _ = GrammarService.get_topic_by_id(topic_id)
        topic_title = topic["title"] if topic else "Bugungi mavzu"
        text = f"{header}Bugungi fokus: **{topic_title}**\n\nTayyormisiz?"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Ha, tayyorman!", callback_data="daily_step_2")]
        ])
    elif step == 2: # Vocab
        words = get_words_by_ids(plan.get("vocab_ids", []))
        if words:
            word_list = "\n".join([f"🔹 **{w['de']}** — {w['uz']}" for w in words])
            text = f"{header}Yangi so'zlar:\n\n{word_list}"
        else:
            text = f"{header}Bugungi dars uchun yangi so'zlar topilmadi, keyingi bosqichga o'tamiz."
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Keyingi", callback_data="daily_step_3")]
        ])
    elif step == 3: # Grammar
        topic_id = plan.get("grammar_topic_id")
        topic, _ = GrammarService.get_topic_by_id(topic_id)
        
        content = topic.get('content', '') if topic else "Mavzu topilmadi."
        # Sanitize Markdown
        content = re.sub(r"^#{1,6}\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"^>\s*\[!\w+\]\s*", "💡 ", content, flags=re.MULTILINE)
        content = re.sub(r"^>\s*", "  ", content, flags=re.MULTILINE)
        content = re.sub(r"^\|.*\|\s*$", "", content, flags=re.MULTILINE)
        content = re.sub(r"`(.*?)`", r"\1", content)
        content = re.sub(r"\*\*(.*?)\*\*", r"*\1*", content)
        content = re.sub(r"\n{3,}", "\n\n", content).strip()
        
        preview = content[:800] + ("..." if len(content) > 800 else "")
        title = topic['title'] if topic else "Grammatika"
        
        text = f"{header}📐 *{title}*\n\n{preview}"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Tushunarli", callback_data="daily_step_4")]
        ])
    elif step == 4: # Quiz
        quiz_ids = plan.get("practice_quiz_ids", [])
        quiz_index = state.get("quiz_index", 0)
        
        if not quiz_ids or quiz_index >= len(quiz_ids):
            correct = state.get('results', {}).get('quiz_correct', 0)
            text = f"{header}🧠 **Test yakunlandi!**\n\nNatijangiz: {correct}/{len(quiz_ids)} ta to'g'ri."
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Keyingi", callback_data="daily_step_5")]
            ])
        else:
            current_id = quiz_ids[quiz_index]
            target_word = get_words_by_ids([current_id])
            target_word = target_word[0] if target_word else {"de": "Noma'lum", "uz": "Noma'lum"}
            
            others = get_random_words(plan.get("level", "A1"), limit=15)
            options = [{"text": target_word["uz"], "correct": 1}]
            for w in others:
                if w["id"] != current_id and len(options) < 4:
                    if not any(opt["text"] == w["uz"] for opt in options):
                        options.append({"text": w["uz"], "correct": 0})
                        
            random.shuffle(options)
            
            text = f"{header}❔ **Savol {quiz_index + 1}/{len(quiz_ids)}**\n\nQuyidagi so'zning tarjimasini toping:\n\n🇩🇪 **{target_word['de']}**"
            markup = InlineKeyboardMarkup(inline_keyboard=[])
            for opt in options:
                # Limit text length just in case
                opt_text = opt["text"][:30] + ("..." if len(opt["text"]) > 30 else "")
                markup.inline_keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=opt_text,
                            callback_data=f"dquiz_{quiz_index}_{opt['correct']}",
                        )
                    ]
                )

    elif step == 5: # Production
        topic_id = plan.get("grammar_topic_id")
        topic, _ = GrammarService.get_topic_by_id(topic_id)
        topic_name = topic['title'] if topic else "erkin mavzu"
            
        text = f"{header}🗣️ **Mustaqil Amaliyot**\n\nBugungi o'tilgan **{topic_name}** mavzusini xotirangizda mustahkamlash uchun ovoz chiqarib 3 ta gap tuzing va yangi so'zlarni takrorlang.\n\n_Bu mashq faqat o'zingiz uchn, botga hech narsa yuborishingiz shart emas._"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Bajarildi", callback_data="daily_step_6")]
        ])
        
    elif step == 6: # Summary
        text = f"{header}🏁 **Tabriklaymiz!**\n\nBugungi dars muvaffaqiyatli yakunlandi. XP va seriyangiz (streak) saqlandi! 🎉"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Darsni yakunlash", callback_data="daily_finish")]
        ])
    else:
        text = f"{header}Dars bosqichi topilmadi. Qaytadan boshlang."
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Qayta boshlash", callback_data="daily_begin")]
        ])
        
    await message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

@router.callback_query(F.data.startswith("daily_step_"))
async def daily_step_callback(call: CallbackQuery):
    data = call.data or ""
    try:
        next_step = int(data.split("_")[2])
    except (ValueError, IndexError):
        await call.answer("Noto'g'ri bosqich so'rovi.", show_alert=True)
        return
    user_id = call.from_user.id
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    state = get_daily_lesson_state(user_id)
    if state:
        state["step"] = next_step
        save_daily_lesson_state(user_id, state)
        await _render_step(message, user_id, state)
    else:
        await call.answer("Dars sessiyasi topilmadi.")
        await _show_entry_screen(message, user_id)

@router.callback_query(F.data.startswith("dquiz_"))
async def daily_quiz_answer(call: CallbackQuery):
    data = call.data or ""
    try:
        _, raw_index, raw_correct = data.split("_", 2)
        answer_quiz_index = int(raw_index)
        is_correct = int(raw_correct)
    except (ValueError, IndexError):
        await call.answer("Noto'g'ri javob formati.", show_alert=True)
        return
    user_id = call.from_user.id
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    state = get_daily_lesson_state(user_id)
    if not state:
        await call.answer("Sessiya topilmadi.", show_alert=True)
        return
    if int(state.get("step", 0)) != 4:
        await call.answer("Savol muddati tugagan.", show_alert=True)
        return

    current_quiz_index = int(state.get("quiz_index", 0))
    if answer_quiz_index != current_quiz_index:
        await call.answer("Bu savol allaqachon yakunlangan.")
        return
    if int(state.get("last_answered_quiz_index", -1)) == current_quiz_index:
        await call.answer("Javob qabul qilingan.")
        return

    # Write idempotency marker before awaits to avoid double-click races.
    state["last_answered_quiz_index"] = current_quiz_index
    save_daily_lesson_state(user_id, state)
        
    if is_correct:
        if "results" not in state:
            state["results"] = {}
        state["results"]["quiz_correct"] = state["results"].get("quiz_correct", 0) + 1
        await call.answer("✅ To'g'ri!")
        # Record positive SRS if needed using learning_service
        # LearningService.process_review_result(user_id, current_id, True)
    else:
        await call.answer("❌ Noto'g'ri!")
        
    state["quiz_index"] = state.get("quiz_index", 0) + 1
    
    quiz_ids = state.get("plan", {}).get("practice_quiz_ids", [])
    if state["quiz_index"] >= len(quiz_ids):
        state["step"] = 5
        
    save_daily_lesson_state(user_id, state)
    await _render_step(message, user_id, state)

@router.callback_query(F.data == "daily_finish")
async def daily_finish_callback(call: CallbackQuery):
    await call.answer("Dars yakunlandi! 🏆", show_alert=True)
    user_id = call.from_user.id
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    state = get_daily_lesson_state(user_id)
    if state:
        state["status"] = STATUS_FINISHED
        save_daily_lesson_state(user_id, state)
        # Log completion
        profile: dict[str, Any] = UserService.get_profile(user_id) or {}
        level = str(profile.get("current_level") or "A1")
        from database.repositories.progress_repository import log_event
        log_event(user_id, "daily_lesson_completed", level=level)
        StatsService.log_navigation(user_id, "daily_lesson_finish", entry_type="callback")
    
    from utils.ui_utils import _send_fresh_main_menu
    try:
        await message.delete()
    except Exception:
        pass
    await _send_fresh_main_menu(
        message,
        "🏆 **Ajoyib! Bugungi dars yakunlandi.**\n\n"
        "Natijangiz saqlandi. Xohlasangiz menyudan keyingi mashg'ulotni tanlang.",
        user_id=user_id,
    )

@router.callback_query(F.data == "daily_cancel")
async def daily_cancel_handler(call: CallbackQuery):
    user_id = call.from_user.id
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    delete_daily_lesson_state(user_id)
    await call.answer("Dars bekor qilindi.")
    await _show_entry_screen(message, user_id)
