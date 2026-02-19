import random
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.assessment_service import AssessmentService
from services.stats_service import StatsService
from services.learning_service import LearningService
from keyboards.builders import get_levels_keyboard, get_quiz_length_keyboard
from utils.ui_utils import send_single_ui_message

router = Router()

class QuizState(StatesGroup):
    waiting_for_level = State()
    waiting_for_length = State()
    in_progress = State()

@router.message(F.text == "🧠 Test va Quiz")
async def quiz_start_handler(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass
    
    StatsService.log_navigation(message.from_user.id, "quiz_test", entry_type="text")
    
    await send_single_ui_message(
        message,
        "📝 **Quiz (Testlar)**\n\nBilimingizni sinash uchun darajani tanlang:",
        reply_markup=get_levels_keyboard("quiz"),
        parse_mode="Markdown"
    )
    await state.set_state(QuizState.waiting_for_level)

@router.callback_query(F.data.startswith("quiz_") & ~F.data.contains("start") & ~F.data.contains("answer") & ~F.data.contains("back"))
async def quiz_level_handler(call: CallbackQuery, state: FSMContext):
    level = call.data.split("_")[1]
    await state.update_data(level=level)
    
    await call.message.edit_text(
        f"✅ Daraja: **{level}**\n\nQancha savol bo'lishini xohlaysiz?",
        reply_markup=get_quiz_length_keyboard(level)
    )
    await state.set_state(QuizState.waiting_for_length)

@router.callback_query(F.data.startswith("quiz_start_"))
async def quiz_start_questions(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    level = parts[2]
    length = int(parts[3])
    
    questions = AssessmentService.generate_quiz(level, length)
    if not questions:
        await call.answer("Savollar toplishda xatolik (so'zlar kam).", show_alert=True)
        return

    await state.update_data(
        questions=questions,
        current_idx=0,
        score=0,
        level=level
    )
    
    await _send_next_question(call, questions[0], 0, length)
    await state.set_state(QuizState.in_progress)

@router.callback_query(QuizState.in_progress, F.data.startswith("quiz_answer_"))
async def quiz_answer_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("current_idx")
    questions = data.get("questions")
    score = data.get("score")
    
    if idx is None or not questions:
        await call.answer("Sessiya muddati tugagan. Iltimos, qaytadan boshlang.", show_alert=True)
        await quiz_start_handler(call.message, state)
        return
    
    selected_answer = call.data.replace("quiz_answer_", "")
    correct_answer = questions[idx]["correct_answer"]
    
    is_correct = AssessmentService.validate_answer(correct_answer, selected_answer)
    
    # Update Mastery if it's a word-based quiz
    LearningService.process_review_result(call.from_user.id, questions[idx]["word_id"], is_correct)
    
    if is_correct:
        score += 1
        await call.answer("To'g'ri! ✅")
    else:
        await call.answer(f"Noto'g'ri! ❌\nTo'g'ri: {correct_answer}", show_alert=True)

    idx += 1
    await state.update_data(current_idx=idx, score=score)

    if idx < len(questions):
        await _send_next_question(call, questions[idx], idx, len(questions))
    else:
        await _show_quiz_results(call, score, len(questions), data["level"])
        await state.clear()

async def _send_next_question(call, question, idx, total):
    text = (
        f"❓ **Savol {idx+1}/{total}**\n\n"
        f"So'z: **{question['de']}**\n"
        f"Tarjimasini tanlang:"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=opt, callback_data=f"quiz_answer_{opt}")] for opt in question["options"]
    ])
    
    await call.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

async def _show_quiz_results(call, score, total, level):
    percentage = round((score / total) * 100)
    text = (
        f"🏁 **Quiz yakunlandi!**\n\n"
        f"📊 Natija: **{score}/{total}** ({percentage}%)\n"
        f"Daraja: **{level}**\n\n"
    )
    
    if percentage >= 80:
        text += "Ajoyib natija! 🌟"
    elif percentage >= 50:
        text += "Yaxshi, davom eting! 👍"
    else:
        text += "Yana biroz mashq qilish kerak. 📚"
        
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Qayta urinish", callback_data=f"quiz_{level}")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    StatsService.mark_progress(call.from_user.id, "quiz", level, completed=(percentage >= 80))
    
    await call.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")
