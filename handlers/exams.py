import random
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.repositories.word_repository import get_total_words_count, get_random_words
from database.repositories.progress_repository import record_navigation_event, update_module_progress, add_quiz_result, log_mistake
from utils.ui_utils import send_single_ui_message

router = Router()

class ExamState(StatesGroup):
    in_progress = State()

def _exam_levels_keyboard():
    levels = ["A1", "A2", "B1", "B2", "C1"]
    rows = []
    for i in range(0, len(levels), 2):
        row = [InlineKeyboardButton(text=levels[i], callback_data=f"exam_level_{levels[i]}")]
        if i + 1 < len(levels):
            row.append(InlineKeyboardButton(text=levels[i + 1], callback_data=f"exam_level_{levels[i + 1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _build_exam_questions(level: str, total: int = 10):
    pool = get_random_words(level, limit=min(total * 6, 120))
    if len(pool) < 4:
        return []

    sample_size = min(total, len(pool))
    selected_targets = random.sample(pool, k=sample_size)
    questions = []
    for word in selected_targets:
        correct = word.get("uz")
        distractors_pool = [w.get("uz") for w in pool if w.get("uz") != correct and w.get("uz")]
        if len(distractors_pool) < 3:
            continue
        options = random.sample(distractors_pool, 3) + [correct]
        random.shuffle(options)
        questions.append({
            "text": f"🇩🇪 **{word.get('de', '-') }** — tarjimasi nima?",
            "options": options,
            "correct": correct,
            "word_id": word.get("id")
        })
    return questions

def _placement_message(score: int, total: int, level: str):
    pct = int((score / total) * 100) if total else 0
    if pct >= 85:
        recommendation = f"{level} ni yaxshi egallagansiz. Keyingi darajaga o'tishga tayyorsiz."
    elif pct >= 60:
        recommendation = f"{level} darajada barqarorlik bor. Amaliy mashqlar bilan kuchaytiring."
    else:
        recommendation = f"{level} bazasini mustahkamlash tavsiya etiladi."
    return pct, recommendation

@router.message(F.text == "🎓 Imtihon tayyorgarligi")
async def exams_handler(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass
    await state.clear()
    text = (
        "🎓 **Imtihon tayyorgarligi**\n\n"
        "🔧 Bu bo'lim hozirda ishlanmoqda...\n\n"
        "Tez orada siz uchun:\n"
        "• 🏆 **Goethe-Zertifikat** — A1-C1\n"
        "• 📋 **ÖSD** — Avstriya sertifikati\n"
        "• 📝 **TELC** — Evropa til sertifikati\n\n"
        "_Mock imtihonlar yaratilmoqda. Kuting!_ 🚀"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    await send_single_ui_message(message, text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("exam_level_"))
async def exam_level_selected(call: CallbackQuery, state: FSMContext):
    level = call.data.replace("exam_level_", "", 1)
    count = get_total_words_count(level)
    if count < 4:
        await call.answer("Bu daraja uchun savol yetarli emas.", show_alert=True)
        return

    questions = _build_exam_questions(level, total=10)
    if len(questions) < 4:
        await call.answer("Testni tuzib bo'lmadi, keyinroq urinib ko'ring.", show_alert=True)
        return

    record_navigation_event(call.from_user.id, "exam_prep", level=level, entry_type="callback")
    update_module_progress(call.from_user.id, "exam_prep", level)
    await state.set_state(ExamState.in_progress)
    await state.update_data(
        exam_level=level,
        exam_questions=questions,
        exam_index=0,
        exam_score=0
    )
    await _send_exam_question(call.message, questions[0], 0, len(questions))

async def _send_exam_question(message: Message, question: dict, index: int, total: int):
    rows = []
    for opt_idx, option in enumerate(question["options"]):
        rows.append([InlineKeyboardButton(text=option, callback_data=f"exam_answer_{index}_{opt_idx}")])
    await message.edit_text(
        f"🎓 **Placement Test** ({index + 1}/{total})\n\n{question['text']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("exam_answer_"))
async def exam_answer_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    questions = data.get("exam_questions") or []
    current_index = data.get("exam_index", 0)
    score = data.get("exam_score", 0)
    level = data.get("exam_level", "A1")

    parts = call.data.split("_")
    q_idx = int(parts[2])
    opt_idx = int(parts[3])

    if q_idx != current_index or current_index >= len(questions):
        await call.answer("Bu eski savol.", show_alert=True)
        return

    question = questions[current_index]
    selected = question["options"][opt_idx]
    if selected == question["correct"]:
        score += 1
        await call.answer("✅ To'g'ri!", show_alert=False)
    else:
        await call.answer(f"❌ Noto'g'ri. To'g'ri javob: {question['correct']}", show_alert=True)
        log_mistake(call.from_user.id, question.get("word_id"), "exam_quiz", level)

    next_index = current_index + 1
    if next_index < len(questions):
        await state.update_data(exam_index=next_index, exam_score=score)
        await _send_exam_question(call.message, questions[next_index], next_index, len(questions))
        return

    update_module_progress(call.from_user.id, "exam_prep", level, completed=True)
    add_quiz_result(call.from_user.id, level, score, len(questions))
    pct, recommendation = _placement_message(score, len(questions), level)
    text = (
        "🏁 **Placement test yakunlandi**\n\n"
        f"📊 Natija: **{score}/{len(questions)} ({pct}%)**\n"
        f"🎯 Tavsiya: {recommendation}"
    )
    await state.clear()
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Qayta topshirish", callback_data=f"exam_restart_{level}")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ]),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("exam_restart_"))
async def exam_restart_handler(call: CallbackQuery, state: FSMContext):
    level = call.data.replace("exam_restart_", "", 1)
    questions = _build_exam_questions(level, total=10)
    if len(questions) < 4:
        await call.answer("Testni qayta tuzib bo'lmadi.", show_alert=True)
        return
    await state.set_state(ExamState.in_progress)
    await state.update_data(
        exam_level=level,
        exam_questions=questions,
        exam_index=0,
        exam_score=0
    )
    update_module_progress(call.from_user.id, "exam_prep", level)
    await _send_exam_question(call.message, questions[0], 0, len(questions))
