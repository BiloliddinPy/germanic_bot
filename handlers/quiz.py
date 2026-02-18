import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards.builders import get_levels_keyboard, get_quiz_length_keyboard
from database import (
    add_quiz_result, 
    get_random_words, 
    get_total_words_count, 
    record_navigation_event,
    log_mistake,
    update_module_progress
)
from handlers.common import send_single_ui_message

router = Router()

class QuizState(StatesGroup):
    waiting_for_level = State()
    waiting_for_length = State()
    in_progress = State()

@router.message(F.text == "🧠 Test va Quiz")
@router.message(F.text == "🧠 Quiz & Tests")
@router.message(F.text == "🧠 Quiz & Test")
async def quiz_start_handler(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "quiz_test", entry_type="text")
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
    record_navigation_event(call.from_user.id, "quiz_test", level=level, entry_type="callback")
    
    count = get_total_words_count(level)
    if count < 4:
        await call.answer("Bu daraja uchun savollar yetarli emas (kamida 4 ta).", show_alert=True)
        return

    await state.update_data(level=level)
    await call.message.edit_text(
        f"✅ Daraja: **{level}**\n\nQancha savol bo'lishini xohlaysiz?",
        reply_markup=get_quiz_length_keyboard(level)
    )
    await state.set_state(QuizState.waiting_for_length)

@router.callback_query(F.data == "quiz_back")
async def quiz_back_handler(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "📝 **Quiz (Testlar)**\n\nBilimingizni sinash uchun darajani tanlang:",
        reply_markup=get_levels_keyboard("quiz")
    )
    await state.set_state(QuizState.waiting_for_level)

@router.callback_query(F.data.startswith("quiz_start_"))
async def quiz_start_questions(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    level = parts[2]
    length = int(parts[3])
    
    # DB Optimization: Get logical amount of words. 
    # If we need 10 questions, we fetch 10 random words.
    # But for distractors, we might need more? 
    # Simple logic: Fetch 'length' words. 
    # For each question, we need 3 distractors. 
    # We can fetch 'length * 4' words to be safe or just fetch 'length' and then fetch distractors separately if needed?
    # Better: Fetch 'length' distinct random words as "Correct Answers".
    # Then for each, pick 3 distractors from the same pool or DB?
    # Let's fetch 4 * length words to have a big pool.
    
    pool_size = min(length * 5, 100) # Cap at 100 for perf
    word_pool = get_random_words(level, limit=pool_size)
    
    if len(word_pool) < 4:
         await call.answer("Savollar yetarli emas.", show_alert=True)
         return

    # Select target words from pool
    selected_targets = random.sample(word_pool, k=min(length, len(word_pool)))
    questions = []
    
    for word in selected_targets:
        direction = random.choice(["de_uz", "uz_de"])
        
        if direction == "de_uz":
            question_text = f"🇩🇪 Nemischa: **{word['de']}**\n🇺🇿 Tarjimasi qanday?"
            correct_answer = word['uz']
            # Find distractors from pool
            potential_distractors = [w['uz'] for w in word_pool if w['uz'] != correct_answer]
        else:
            question_text = f"🇺🇿 O'zbekcha: **{word['uz']}**\n🇩🇪 Nemischa tarjimasi qanday?"
            correct_answer = word['de']
            potential_distractors = [w['de'] for w in word_pool if w['de'] != correct_answer]
            
        if len(potential_distractors) < 3:
            continue # Skip if not enough distractors
            
        distractors = random.sample(potential_distractors, 3)
        options = distractors + [correct_answer]
        random.shuffle(options)
        
        questions.append({
            "text": question_text,
            "options": options,
            "correct": correct_answer,
            "word_full": word
        })

    if not questions:
         await call.answer("Xatolik: savollar generatsiya qilinmadi.", show_alert=True)
         return

    await state.update_data(
        questions=questions, 
        current_index=0, 
        score=0,
        wrong_answers=[]
    )
    await state.set_state(QuizState.in_progress)
    
    # Track attempt (Day 3)
    update_module_progress(call.from_user.id, "quiz_test", level)
    
    await send_question(call.message, questions[0], 0, len(questions))

async def send_question(message, question, index, total):
    builder = InlineKeyboardMarkup(inline_keyboard=[])
    rows = []
    
    for opt in question['options']:
        rows.append([InlineKeyboardButton(text=opt, callback_data=f"quiz_answer_{index}_{question['options'].index(opt)}")])
    
    builder.inline_keyboard = rows
    
    await message.edit_text(
        f"❓ **Savol {index + 1}/{total}**\n\n{question['text']}",
        reply_markup=builder,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("quiz_answer_"))
async def quiz_answer_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    questions = data.get("questions")
    current_index = data.get("current_index")
    score = data.get("score")
    wrong_answers = data.get("wrong_answers")
    
    parts = call.data.split("_")
    try:
        q_idx = int(parts[2])
        opt_idx = int(parts[3])
    except (IndexError, ValueError):
        await call.answer("Xatolik!", show_alert=True)
        return
    
    if q_idx != current_index:
        await call.answer("Eski savol!", show_alert=True)
        return

    question = questions[current_index]
    selected_option = question['options'][opt_idx]
    is_correct = selected_option == question['correct']
    
    if is_correct:
        score += 1
        await call.answer("✅ To'g'ri!", show_alert=False)
    else:
        await call.answer(f"❌ Noto'g'ri! To'g'ri javob: {question['correct']}", show_alert=True)
        # Log mistake (Day 3)
        log_mistake(call.from_user.id, question['word_full']['id'], "quiz_test", data.get("level"))
        wrong_answers.append({
            "question": question['word_full']['de'],
            "correct": question['word_full']['uz']
        })
    
    next_index = current_index + 1
    
    if next_index < len(questions):
        await state.update_data(score=score, current_index=next_index, wrong_answers=wrong_answers)
        await send_question(call.message, questions[next_index], next_index, len(questions))
    else:
        await finish_quiz(call.message, score, len(questions), wrong_answers, data.get("level"))
        await state.clear()

async def finish_quiz(message, score, total, wrong_answers, level):
    # Track completion (Day 3)
    update_module_progress(message.chat.id, "quiz_test", level, completed=True)
    add_quiz_result(message.chat.id, level, score, total)
    
    percentage = int((score / total) * 100)
    result_text = (
        f"🏁 **Quiz yakunlandi!**\n\n"
        f"📊 Natija: {score}/{total} ({percentage}%)\n"
        f"🏆 Daraja: {level}\n"
    )
    
    if wrong_answers:
        result_text += "\n❌ **Xatolar:**\n"
        for item in wrong_answers[:10]: 
            result_text += f"▫️ {item['question']} — {item['correct']}\n"
            
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Qayta ishlash", callback_data=f"quiz_{level}")], 
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await message.edit_text(result_text, reply_markup=builder, parse_mode="Markdown")
