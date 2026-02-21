import random
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.repositories.word_repository import get_random_words
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
    if not message.from_user:
        return
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
