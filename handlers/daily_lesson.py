from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    get_user_profile,
    update_user_profile,
    get_random_words,
    log_mistake,
    DB_NAME,
    record_navigation_event,
    log_event,
    get_user_mistakes_overview,
    resolve_mistake,
    update_module_progress,
    mark_daily_lesson_started,
    mark_daily_lesson_completed,
    get_daily_lesson_nudges,
    get_cached_daily_plan,
    get_last_daily_plan,
    save_daily_plan,
    log_daily_plan_audit,
    get_grammar_coverage_map,
    mark_grammar_topic_seen,
    mark_writing_task_completed,
    get_weighted_mistake_word_ids,
    get_mastered_mistake_word_ids,
    get_recent_topic_mistake_scores,
    get_user_progress_summary,
    get_days_since_first_use
)
import sqlite3
from config import DAILY_LESSON_ENABLED, DAILY_MISTAKE_BLEND, DAILY_AVOID_SAME_WRITING
import json
import random
import os
from handlers.common import send_single_ui_message

router = Router()

class DailyLessonStates(StatesGroup):
    choosing_goal = State()
    choosing_time = State()
    choosing_level = State()

@router.message(F.text == "🚀 Kunlik dars")
@router.message(F.text == "🚀 Tägliche Lektion")
@router.message(F.text == "🚀 Daily Lesson")
async def daily_lesson_start(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "daily_lesson", entry_type="text")
    if not DAILY_LESSON_ENABLED:
        await send_single_ui_message(message, "Kunlik dars bo'limi hozircha faollashtirilmagan.")
        return

    profile = get_user_profile(message.from_user.id)
    
    if not profile or not profile.get('onboarding_completed'):
        await start_onboarding(message)
    else:
        # Check for mistakes to show Review button (Day 3)
        mistakes = get_user_mistakes_overview(message.from_user.id)
        nudges = get_daily_lesson_nudges(message.from_user.id)
        nudge_lines = ""
        if nudges.get("started_not_finished_today"):
            nudge_lines += "⏳ Bugun boshlangan darsingiz bor. Davom ettirib yakunlab qo'ying.\n"
        elif nudges.get("skipped_day"):
            nudge_lines += "🤝 Kecha tanaffus bo'ldi. Bugun kichik qadam bilan davom etamiz!\n"

        text = (
            "🚀 **Kunlik dars**\n\n"
            "Bugungi darsingiz tayyor! Shuningdek, xatolaringizni takrorlab olishingiz ham mumkin.\n\n"
            f"{nudge_lines}"
            f"📌 Sizda **{mistakes['total_mistakes']}** ta xato bor."
        )
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏁 Bugungi darsni boshlash", callback_data="daily_start")],
        ])
        if mistakes['total_mistakes'] > 0:
            builder.inline_keyboard.append([InlineKeyboardButton(text="🔁 Xatolarni takrorlash", callback_data="review_mistakes")])
        builder.inline_keyboard.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
        
        await send_single_ui_message(message, text, reply_markup=builder, parse_mode="Markdown")

async def start_onboarding(message: Message):
    text = (
        "🚀 **Kunlik darsga xush kelibsiz!**\n\n"
        "Boshlashdan oldin, maqsadlaringizni belgilab olaylik. Bu sizga moslashtirilgan dars rejasini tuzishga yordam beradi.\n\n"
        "Maqsadingiz nima?"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Imtihonga tayyorlanish", callback_data="daily_goal_exam")],
        [InlineKeyboardButton(text="🗣 Suhbat darajasini oshirish", callback_data="daily_goal_speaking")],
        [InlineKeyboardButton(text="🌍 Umumiy o'rganish", callback_data="daily_goal_general")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await send_single_ui_message(message, text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data.startswith("daily_goal_"))
async def onboarding_goal_callback(call: CallbackQuery, state: FSMContext):
    goal = call.data.replace("daily_goal_", "")
    update_user_profile(call.from_user.id, goal=goal)
    
    text = (
        "⏱ **Vaqtingizni belgilang**\n\n"
        "Har kuni nemis tiliga qancha vaqt ajrata olasiz?"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 10 daqiqa", callback_data="daily_time_10")],
        [InlineKeyboardButton(text="🕓 20 daqiqa", callback_data="daily_time_20")],
        [InlineKeyboardButton(text="🕔 30 daqiqa", callback_data="daily_time_30")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await call.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data.startswith("daily_time_"))
async def onboarding_time_callback(call: CallbackQuery, state: FSMContext):
    time = int(call.data.replace("daily_time_", ""))
    update_user_profile(call.from_user.id, daily_target=time)
    
    text = (
        "📊 **Hozirgi darajangiz**\n\n"
        "Nemis tili darajangizni tanlang:"
    )
    
    levels = ["A1", "A2", "B1", "B2", "C1"]
    builder = InlineKeyboardMarkup(inline_keyboard=[])
    for i in range(0, len(levels), 2):
        row = []
        row.append(InlineKeyboardButton(text=levels[i], callback_data=f"daily_level_{levels[i]}"))
        if i+1 < len(levels):
            row.append(InlineKeyboardButton(text=levels[i+1], callback_data=f"daily_level_{levels[i+1]}"))
        builder.inline_keyboard.append(row)
    builder.inline_keyboard.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
    
    await call.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data.startswith("daily_level_"))
async def onboarding_level_callback(call: CallbackQuery, state: FSMContext):
    level = call.data.replace("daily_level_", "")
    update_user_profile(call.from_user.id, current_level=level, onboarding_completed=1)
    
    profile = get_user_profile(call.from_user.id)
    
    text = (
        "🎉 **Onboarding yakunlandi!**\n\n"
        f"Maqsad: {profile['goal']}\n"
        f"Vaqt: {profile['daily_target']} daqiqa\n"
        f"Daraja: {profile['current_level']}\n\n"
        "Tayyor bo'lsangiz, birinchi darsni boshlaymiz!"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏁 Darsni boshlash", callback_data="daily_start")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await call.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data == "daily_start")
async def daily_start_callback(call: CallbackQuery, state: FSMContext):
    log_event(call.from_user.id, "daily_session_start", section_name="daily_lesson")
    mark_daily_lesson_started(call.from_user.id)
    profile = get_user_profile(call.from_user.id)
    plan = get_cached_daily_plan(call.from_user.id)
    plan_source = "cache"
    if not plan or not is_core_daily_plan(plan):
        plan = build_daily_plan(call.from_user.id, profile or {})
        save_daily_plan(call.from_user.id, plan)
        plan_source = "generated"

    payload = build_daily_planner_payload(call.from_user.id, profile or {}, plan, source=plan_source)
    log_daily_plan_audit(call.from_user.id, f"plan_{plan_source}", metadata=payload)
    log_event(
        call.from_user.id,
        "daily_plan_ready",
        section_name="daily_lesson",
        level=plan.get("level"),
        metadata={
            "source": plan_source,
            "grammar_topic_id": plan.get("grammar_topic_id"),
            "material_id": plan.get("material_id"),
            "vocab_n": len(plan.get("vocab_ids", [])),
            "quiz_n": len(plan.get("practice_quiz_ids", []))
        }
    )
    await show_daily_session(call.message, profile or {}, state, plan)

MATERIAL_CATALOG = {
    "A1": {"id": "mat_a1b1_docx", "title": "Grammatik Aktiv A1-B1", "path": "data/Grammatik Aktiv A1B1.docx"},
    "A2": {"id": "mat_a1b1_docx", "title": "Grammatik Aktiv A1-B1", "path": "data/Grammatik Aktiv A1B1.docx"},
    "B1": {"id": "mat_a1b1_docx", "title": "Grammatik Aktiv A1-B1", "path": "data/Grammatik Aktiv A1B1.docx"},
    "B2": {"id": "mat_b2c1_docx", "title": "Grammatik Aktiv B2-C1", "path": "data/Grammatik Aktiv B2-C1 .docx"},
    "C1": {"id": "mat_b2c1_docx", "title": "Grammatik Aktiv B2-C1", "path": "data/Grammatik Aktiv B2-C1 .docx"},
}


def get_material_by_id(material_id):
    for material in MATERIAL_CATALOG.values():
        if material.get("id") == material_id:
            return material
    return None


def apply_quiz_result_to_session(session: dict, is_correct: bool):
    """Mutates session quiz counters in a backward-compatible way."""
    if is_correct:
        session["quiz_correct"] = int(session.get("quiz_correct") or 0) + 1
    else:
        session["quiz_wrong"] = int(session.get("quiz_wrong") or 0) + 1
    return session


def parse_indexed_callback(data: str, prefix: str, expected_int_count: int):
    """
    Parses callback data with integer suffixes.
    Example: parse_indexed_callback("daily_quiz_5_2", "daily_quiz_", 2) -> (5, 2)
    Returns None for malformed input.
    """
    if not data.startswith(prefix):
        return None
    raw = data.replace(prefix, "", 1)
    parts = raw.split("_")
    if len(parts) != expected_int_count:
        return None
    values = []
    for part in parts:
        try:
            values.append(int(part))
        except ValueError:
            return None
    return tuple(values)

def load_grammar_for_level(level):
    file_path = "data/grammar.json"
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get(level, [])

def get_words_by_ids(word_ids):
    if not word_ids:
        return []
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(word_ids))
    cursor.execute(f"SELECT * FROM words WHERE id IN ({placeholders})", tuple(word_ids))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    by_id = {w["id"]: w for w in rows}
    return [by_id[w_id] for w_id in word_ids if w_id in by_id]

def get_user_recent_mistake_word_ids(user_id, level, limit=10):
    weighted = get_weighted_mistake_word_ids(user_id, level, limit=limit)
    if weighted:
        return weighted
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT item_id FROM user_mistakes
        WHERE user_id = ? AND level = ? AND item_id GLOB '[0-9]*'
        ORDER BY mistake_count DESC, last_mistake_at DESC
        LIMIT ?
    """, (user_id, level, limit))
    rows = cursor.fetchall()
    conn.close()
    return [int(r[0]) for r in rows]

def choose_grammar_topic(level, mistake_word_ids, user_id, avoid_topic_id=None, weak_topic_limit=3, weak_topic_min_score=1.0):
    topics = load_grammar_for_level(level)
    if not topics:
        return None, "fallback"

    weak_topics = get_recent_topic_mistake_scores(user_id, level, days=14, limit=weak_topic_limit)
    if weak_topics:
        by_id = {t.get("id"): t for t in topics if t.get("id")}
        for topic_id, score in weak_topics:
            if score >= weak_topic_min_score and topic_id in by_id and topic_id != avoid_topic_id:
                return by_id[topic_id], "topic_weakness"

    mistake_words = get_words_by_ids(mistake_word_ids[:5])
    tokens = []
    for w in mistake_words:
        tokens.extend([
            (w.get("de") or "").lower(),
            (w.get("uz") or "").lower(),
            (w.get("category") or "").lower()
        ])
    tokens = [t for t in tokens if t]

    if tokens:
        best_topic = None
        best_score = 0
        for topic in topics:
            blob = f"{topic.get('title','')} {topic.get('content','')} {topic.get('example','')}".lower()
            score = sum(1 for t in tokens if t in blob)
            if score > best_score:
                best_score = score
                best_topic = topic
        if best_topic and best_score > 0 and best_topic.get("id") != avoid_topic_id:
            return best_topic, "mistake_related"

    coverage = get_grammar_coverage_map(user_id, level)
    least_seen = sorted(topics, key=lambda t: coverage.get(t.get("id"), 0))
    if avoid_topic_id:
        non_repeating = [t for t in least_seen if t.get("id") != avoid_topic_id]
        if non_repeating:
            return non_repeating[0], "least_covered"
    return least_seen[0], "least_covered"

def _module_rate(progress_modules, aliases):
    attempts = 0
    completions = 0
    for row in progress_modules:
        if row.get("module") in aliases:
            attempts += int(row.get("attempts") or 0)
            completions += int(row.get("completions") or 0)
    rate = int((completions / attempts) * 100) if attempts > 0 else 0
    return attempts, completions, rate

def choose_writing_task_type(grammar_topic, previous_task_type=None):
    title = (grammar_topic.get("title", "") if grammar_topic else "").lower()
    candidates = []
    if "konjugation" in title or "verben" in title:
        candidates = ["sentence_conjugation", "sentence_order", "short_paragraph"]
    elif "präposition" in title:
        candidates = ["preposition_usage", "sentence_order", "short_paragraph"]
    elif "satz" in title or "syntax" in title:
        candidates = ["sentence_order", "sentence_conjugation", "short_paragraph"]
    else:
        candidates = ["short_paragraph", "sentence_order", "sentence_conjugation"]

    if DAILY_AVOID_SAME_WRITING and previous_task_type and previous_task_type in candidates and len(candidates) > 1:
        candidates = [c for c in candidates if c != previous_task_type] + [previous_task_type]
    return candidates[0]

def is_core_daily_plan(plan):
    required = {"grammar_topic_id", "material_id", "vocab_ids", "practice_quiz_ids", "writing_task_type"}
    return isinstance(plan, dict) and required.issubset(set(plan.keys()))

def select_vocab_for_topic(level, grammar_topic, count):
    """Selects 5-7 vocabulary items, preferring grammar-related ones."""
    pool = get_random_words(level, limit=max(80, count * 15))
    if not pool:
        return []

    topic_blob = f"{grammar_topic.get('title','')} {grammar_topic.get('content','')} {grammar_topic.get('example','')}".lower()
    scored = []
    for w in pool:
        score = 0
        for token in [(w.get("de") or "").lower(), (w.get("uz") or "").lower(), (w.get("category") or "").lower()]:
            if token and token in topic_blob:
                score += 1
        scored.append((score, w))
    scored.sort(key=lambda x: x[0], reverse=True)

    selected = []
    used = set()
    for score, w in scored:
        if w["id"] in used:
            continue
        if score > 0:
            selected.append(w)
            used.add(w["id"])
        if len(selected) >= count:
            break

    if len(selected) < count:
        for _, w in scored:
            if w["id"] not in used:
                selected.append(w)
                used.add(w["id"])
            if len(selected) >= count:
                break
    return selected[:count]

def build_quiz_question(word, level, phase, grammar_topic_id):
    correct = word["uz"]
    distractors = get_distractors(level, correct, 3)
    unique_options = []
    for opt in distractors + [correct]:
        if opt and opt not in unique_options:
            unique_options.append(opt)
    options = unique_options
    if len(options) < 2:
        return None
    random.shuffle(options)
    return {
        "id": f"{phase}_{word['id']}",
        "phase": phase,
        "topic_id": grammar_topic_id,
        "word_id": word["id"],
        "text": f"🇩🇪 **{word['de']}** — tarjimasi nima?",
        "options": options,
        "correct": correct
    }

def build_daily_plan(user_id, profile):
    level = profile.get("current_level", "A1")
    daily_minutes = profile.get("daily_time_minutes") or profile.get("daily_target") or 20

    if daily_minutes <= 10:
        vocab_n, practice_n = 5, 3
        weak_topic_limit = 1
        weak_topic_min_score = 3.0
        blend_adjust = -0.1
    elif daily_minutes >= 30:
        vocab_n, practice_n = 7, 5
        weak_topic_limit = 3
        weak_topic_min_score = 1.0
        blend_adjust = 0.2
    else:
        vocab_n, practice_n = 6, 4
        weak_topic_limit = 2
        weak_topic_min_score = 2.0
        blend_adjust = 0.0

    mistake_ids = get_user_recent_mistake_word_ids(user_id, level, limit=12)
    mastered_ids = set(get_mastered_mistake_word_ids(user_id, level, limit=300))
    last_plan_obj = get_last_daily_plan(user_id)
    avoid_topic_id = None
    previous_writing_type = None
    if last_plan_obj and isinstance(last_plan_obj.get("plan"), dict):
        avoid_topic_id = last_plan_obj["plan"].get("grammar_topic_id")
        previous_writing_type = last_plan_obj["plan"].get("writing_task_type")
    grammar_topic, reason_code = choose_grammar_topic(
        level,
        mistake_ids,
        user_id,
        avoid_topic_id=avoid_topic_id,
        weak_topic_limit=weak_topic_limit,
        weak_topic_min_score=weak_topic_min_score
    )
    progress = get_user_progress_summary(user_id)
    modules = progress.get("modules", [])
    grammar_attempts, _, grammar_rate = _module_rate(modules, {"grammar"})
    materials_attempts, _, materials_rate = _module_rate(modules, {"materials", "video_materials"})
    if reason_code == "least_covered":
        if grammar_attempts >= 3 and grammar_rate < 50:
            reason_code = "grammar_gap"
        elif materials_attempts >= 3 and materials_rate < 50:
            reason_code = "materials_gap"
    material = MATERIAL_CATALOG.get(level, MATERIAL_CATALOG["A1"])
    grammar_topic_id = grammar_topic.get("id") if grammar_topic else None

    vocab_words = select_vocab_for_topic(level, grammar_topic or {}, vocab_n)
    vocab_ids = [w["id"] for w in vocab_words]

    practice_ids = []
    if mistake_ids:
        blend = min(max(DAILY_MISTAKE_BLEND + blend_adjust, 0.0), 1.0)
        from_mistakes_n = max(1, int(round(practice_n * blend)))
        from_mistakes_n = min(from_mistakes_n, practice_n)
        if reason_code == "topic_weakness" and daily_minutes >= 30:
            from_mistakes_n = max(from_mistakes_n, practice_n - 1)
        for wid in mistake_ids:
            if wid in mastered_ids:
                continue
            practice_ids.append(wid)
            if len(practice_ids) >= from_mistakes_n:
                break

    needed = practice_n - len(practice_ids)
    if needed > 0:
        pool = get_random_words(level, limit=needed * 4)
        existing = set(vocab_ids + practice_ids)
        blocked = mastered_ids
        for w in pool:
            if w["id"] not in existing and w["id"] not in blocked:
                practice_ids.append(w["id"])
                existing.add(w["id"])
            if len(practice_ids) >= practice_n:
                break

    writing_task_type = choose_writing_task_type(grammar_topic or {}, previous_task_type=previous_writing_type)

    return {
        "level": level,
        "reason_code": reason_code,
        "grammar_topic_id": grammar_topic_id,
        "material_id": material["id"],
        "vocab_ids": vocab_ids,
        "practice_quiz_ids": practice_ids[:practice_n],
        "writing_task_type": writing_task_type
    }

def build_writing_prompt(task_type, grammar_topic):
    topic_title = grammar_topic.get("title", "Mavzu") if grammar_topic else "Mavzu"
    if task_type == "sentence_conjugation":
        return f"3 ta gap tuzing va fe'llarni to'g'ri tuslang: **{topic_title}**."
    if task_type == "preposition_usage":
        return f"4 ta gap yozing va to'g'ri predlog ishlating: **{topic_title}**."
    if task_type == "sentence_order":
        return f"3 ta murakkab gap yozing, so'z tartibiga e'tibor bering: **{topic_title}**."
    return f"5-6 jumladan iborat kichik matn yozing: **{topic_title}**."

def reason_text_from_code(reason_code):
    if reason_code == "topic_weakness":
        return "oxirgi xatolardagi zaif mavzuni mustahkamlash uchun"
    if reason_code == "mistake_related":
        return "kecha shu mavzuga yaqin xatolar bo'lgani uchun"
    if reason_code == "least_covered":
        return "bu mavzu sizda kam mashq qilingani uchun"
    if reason_code == "grammar_gap":
        return "grammatika blokida natijani mustahkamlash uchun"
    if reason_code == "materials_gap":
        return "materiallar bilan ishlash ko'rsatkichini oshirish uchun"
    return "mavzular balansi uchun tanlandi"

def build_daily_planner_payload(user_id, profile, plan, source):
    """AI-ready, rule-based payload without external AI calls."""
    progress = get_user_progress_summary(user_id)
    modules = progress.get("modules", [])
    module_attempts = {m.get("module"): int(m.get("attempts") or 0) for m in modules}
    return {
        "source": source,
        "level": plan.get("level") or profile.get("current_level", "A1"),
        "target_level": profile.get("target_level") or profile.get("current_level"),
        "daily_time_minutes": profile.get("daily_time_minutes") or profile.get("daily_target") or 20,
        "days_since_first_use": get_days_since_first_use(user_id),
        "streak": progress.get("streak", {}),
        "module_attempts": module_attempts,
        "plan": {
            "reason_code": plan.get("reason_code"),
            "grammar_topic_id": plan.get("grammar_topic_id"),
            "material_id": plan.get("material_id"),
            "vocab_ids": plan.get("vocab_ids", []),
            "practice_quiz_ids": plan.get("practice_quiz_ids", []),
            "writing_task_type": plan.get("writing_task_type")
        }
    }

async def show_daily_session(message: Message, profile: dict, state: FSMContext, plan: dict):
    level = plan.get("level") or profile.get("current_level", "A1")
    grammar_topic_id = plan.get("grammar_topic_id")
    grammar_topic = None
    for t in load_grammar_for_level(level):
        if t.get("id") == grammar_topic_id:
            grammar_topic = t
            break
    if not grammar_topic:
        topics = load_grammar_for_level(level)
        grammar_topic = topics[0] if topics else None
    topic_safe = grammar_topic or {"id": None, "title": "Grammatika", "content": "", "example": "-"}

    material = MATERIAL_CATALOG.get(level, MATERIAL_CATALOG["A1"])
    vocab_words = get_words_by_ids(plan.get("vocab_ids", []))
    practice_words = get_words_by_ids(plan.get("practice_quiz_ids", []))
    if len(vocab_words) < 5:
        existing = {w["id"] for w in vocab_words}
        refill = get_random_words(level, limit=30)
        for w in refill:
            if w["id"] not in existing:
                vocab_words.append(w)
                existing.add(w["id"])
            if len(vocab_words) >= 5:
                break
    if len(practice_words) < 3:
        existing = {w["id"] for w in practice_words}
        refill = get_random_words(level, limit=30)
        for w in refill:
            if w["id"] not in existing:
                practice_words.append(w)
                existing.add(w["id"])
            if len(practice_words) >= 3:
                break

    practice_questions = []
    for w in practice_words:
        q = build_quiz_question(w, level, "practice", topic_safe.get("id"))
        if q:
            practice_questions.append(q)

    context_text = (
        "🧭 **Bugungi dars rejasi**\n\n"
        f"📌 Bugungi dars mavzusi: **{topic_safe.get('title', 'Grammatika')}**\n"
        f"ℹ️ Sababi: {reason_text_from_code(plan.get('reason_code'))}"
    )

    writing_task_type = plan.get("writing_task_type", "short_paragraph")
    writing_prompt = build_writing_prompt(writing_task_type, topic_safe)

    steps = [{"type": "context", "text": context_text}]
    steps.append({"type": "vocab", "words": vocab_words, "topic": topic_safe})
    steps.append({"type": "grammar", "topic": topic_safe})
    steps.append({"type": "material", "material": material, "topic": topic_safe})
    for q in practice_questions:
        steps.append({"type": "quiz", "phase": "practice", "question": q})
    steps.append({"type": "writing", "task_type": writing_task_type, "prompt": writing_prompt, "topic": topic_safe})
    steps.append({"type": "finish"})

    session_data = {
        "level": level,
        "plan": plan,
        "steps": steps,
        "current_step": 0,
        "quiz_total": len(practice_questions),
        "quiz_correct": 0,
        "quiz_wrong": 0,
        "dictionary_progress_marked": False,
        "grammar_progress_marked": False,
        "materials_progress_marked": False,
        "quiz_progress_marked": False,
        "writing_progress_marked": False
    }
    await state.update_data(session=session_data)
    update_module_progress(message.chat.id, "daily_lesson", level)
    await render_session_step(message, state)

def get_distractors(level, correct_uz, limit=3):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT uz FROM words WHERE level = ? AND uz != ? ORDER BY RANDOM() LIMIT ?", (level, correct_uz, limit))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

async def render_session_step(message: Message, state: FSMContext):
    data = await state.get_data()
    session = data.get("session")
    if not session:
        await message.edit_text("Sessiya topilmadi. Iltimos, kunlik darsni qayta boshlang.")
        return

    steps = session.get("steps", [])
    idx = session.get("current_step", 0)
    if idx >= len(steps):
        idx = len(steps) - 1
    current = steps[idx]
    next_cb = f"daily_next_{idx}"

    if current["type"] == "context":
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Boshlash", callback_data=next_cb)],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        await message.edit_text(current["text"], reply_markup=builder, parse_mode="Markdown")

    elif current["type"] == "vocab":
        if not session.get("dictionary_progress_marked"):
            update_module_progress(message.chat.id, "dictionary", session["level"])
            session["dictionary_progress_marked"] = True
            await state.update_data(session=session)
        words = current.get("words", [])
        topic = current.get("topic", {})
        text = "📘 **Lug'at bloki (5-7 so'z)**\n\n"
        text += f"📌 Mavzu bilan bog'liq so'zlar: **{topic.get('title', 'Grammatika')}**\n\n"
        for i, w in enumerate(words, 1):
            text += f"{i}. **{w.get('de', '-') }** — {w.get('uz', '-')}\n"
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Grammatikaga o'tish", callback_data=next_cb)],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

    elif current["type"] == "quiz":
        if not session.get("quiz_progress_marked"):
            update_module_progress(message.chat.id, "quiz_test", session["level"])
            session["quiz_progress_marked"] = True
            await state.update_data(session=session)
        q = current["question"]
        label = "Asosiy mashq"
        quiz_no = 1 + len([s for s in steps[:idx + 1] if s.get("type") == "quiz"])
        total_quiz = len([s for s in steps if s.get("type") == "quiz"])
        text = f"🧠 **{label} ({quiz_no}/{total_quiz})**\n\n{q['text']}"
        builder = InlineKeyboardMarkup(inline_keyboard=[])
        for opt_idx, opt in enumerate(q["options"]):
            builder.inline_keyboard.append([InlineKeyboardButton(text=opt, callback_data=f"daily_quiz_{idx}_{opt_idx}")])
        builder.inline_keyboard.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
        await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

    elif current["type"] == "grammar":
        g = current.get("topic")
        if g:
            if not session.get("grammar_progress_marked"):
                update_module_progress(message.chat.id, "grammar", session["level"])
                mark_grammar_topic_seen(message.chat.id, g.get("id"), session["level"])
                session["grammar_progress_marked"] = True
                await state.update_data(session=session)
            text = (
                f"📐 **Grammatika fokus**\n\n"
                f"📌 **{g.get('title', 'Mavzu')}**\n\n"
                f"{(g.get('content') or '')[:350]}...\n\n"
                f"📝 **Misol:**\n{g.get('example', '-')}"
            )
        else:
            text = "📐 Grammatika mavzusi topilmadi. Keyingi bosqichga o'tamiz."
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Materialga o'tish", callback_data=next_cb)],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

    elif current["type"] == "material":
        mat = current.get("material", {})
        topic = current.get("topic", {})
        if not session.get("materials_progress_marked"):
            update_module_progress(message.chat.id, "materials", session["level"])
            session["materials_progress_marked"] = True
            await state.update_data(session=session)
        text = (
            f"📂 **Bog'liq material**\n\n"
            f"📌 Mavzu: **{topic.get('title', 'Grammatika')}**\n"
            f"📚 Material: **{mat.get('title', 'Material')}**\n"
            f"🗂 Fayl: `{mat.get('path', '-')}`\n\n"
            "Ushbu material orqali mavzuni chuqurroq ko'rib chiqing."
        )
        rows = []
        material_id = mat.get("id")
        if material_id:
            rows.append([InlineKeyboardButton(text="📎 Materialni yuborish", callback_data=f"daily_send_material_{material_id}")])
        rows.append([InlineKeyboardButton(text="➡️ Asosiy testga o'tish", callback_data=next_cb)])
        rows.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
        builder = InlineKeyboardMarkup(inline_keyboard=rows)
        await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

    elif current["type"] == "writing":
        topic = current.get("topic", {})
        if not session.get("writing_progress_marked"):
            update_module_progress(message.chat.id, "practice", session["level"])
            session["writing_progress_marked"] = True
            await state.update_data(session=session)
        text = (
            "✍️ **Yozma mashq**\n\n"
            f"📌 Mavzu: **{topic.get('title', 'Grammatika')}**\n"
            f"📝 Topshiriq: {current.get('prompt', '-')}\n\n"
            "Topshiriqni alohida yozib bajaring, keyin keyingi bosqichga o'ting."
        )
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Bajarildi, yakunlash", callback_data=next_cb)],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

    elif current["type"] == "finish":
        completion = mark_daily_lesson_completed(message.chat.id)
        if completion.get("completed_now"):
            # Track completion once per day
            update_module_progress(message.chat.id, "daily_lesson", session["level"], completed=True)
            if session.get("quiz_progress_marked"):
                update_module_progress(message.chat.id, "quiz_test", session["level"], completed=True)
        quiz_total = int(session.get("quiz_total") or 0)
        quiz_correct = int(session.get("quiz_correct") or 0)
        quiz_wrong = int(session.get("quiz_wrong") or 0)
        log_event(
            message.chat.id,
            "daily_session_finish",
            section_name="daily_lesson",
            metadata={"quiz_total": quiz_total, "quiz_correct": quiz_correct, "quiz_wrong": quiz_wrong}
        )
        streak = completion.get("streak", {"current_streak": 0, "best_streak": 0})
        if completion.get("completed_now"):
            status_line = f"✅ **Bugungi dars yakunlandi**\n🔥 **{streak.get('current_streak', 0)} kun ketma-ket**"
        else:
            status_line = f"✅ **Bugungi dars avvalroq yakunlangan**\n🔥 **{streak.get('current_streak', 0)} kun ketma-ket**"

        streak_note = ""
        if completion.get("streak_reset"):
            streak_note = "\n💡 Streak yangidan boshlandi. Hechqisi yo'q, bugundan qayta davom etamiz!"

        text = (
            "🎊 **Tabriklaymiz!**\n\n"
            f"{status_line}\n"
            f"🏆 Eng yaxshi streak: **{streak.get('best_streak', 0)} kun**\n"
            "🎯 Progress yangilandi."
            f"{streak_note}"
        )
        if quiz_total > 0:
            text += f"\n\n🧠 Quiz natijasi: **{quiz_correct}/{quiz_total}** (xato: {quiz_wrong})"
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data == "daily_next")
@router.callback_query(F.data.startswith("daily_next_"))
async def daily_next_callback(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    session = data.get("session")
    if not session:
        await call.answer("Sessiya topilmadi. Qayta boshlang.", show_alert=True)
        return

    expected_step = None
    if call.data.startswith("daily_next_"):
        try:
            expected_step = int(call.data.replace("daily_next_", "", 1))
        except ValueError:
            await call.answer("Noto'g'ri bosqich.", show_alert=True)
            return

    steps = session.get("steps", [])
    current_step = session.get("current_step", 0)
    if expected_step is not None and expected_step != current_step:
        await call.answer("Bu eski bosqich. Joriy ekrandan davom eting.", show_alert=True)
        return
    if current_step >= len(steps):
        await call.answer("Sessiya yakunlangan. Qayta boshlang.", show_alert=True)
        return

    if 0 <= current_step < len(steps):
        current = steps[current_step]
        if current.get("type") == "quiz":
            await call.answer("Avval savolga javob bering.", show_alert=True)
            return
        if current.get("type") == "writing":
            topic = current.get("topic", {})
            mark_writing_task_completed(
                user_id=call.from_user.id,
                level=session.get("level", "A1"),
                topic_id=topic.get("id"),
                task_type=current.get("task_type", "short_paragraph")
            )
    session["current_step"] = session.get("current_step", 0) + 1
    await state.update_data(session=session)
    await render_session_step(call.message, state)

@router.callback_query(F.data.startswith("daily_quiz_"))
async def daily_quiz_callback(call: CallbackQuery, state: FSMContext):
    parsed = parse_indexed_callback(call.data, "daily_quiz_", 2)
    if not parsed:
        await call.answer("Savol formati buzilgan.", show_alert=True)
        return
    step_idx, opt_idx = parsed
    
    data = await state.get_data()
    session = data.get("session")
    if not session:
        await call.answer("Sessiya topilmadi. Qayta boshlang.", show_alert=True)
        return
    steps = session.get("steps", [])
    current_step = session.get("current_step", 0)

    if step_idx != current_step or step_idx >= len(steps):
        await call.answer("Bu eski savol.", show_alert=True)
        return

    current = steps[step_idx]
    if current.get("type") != "quiz":
        await call.answer("Savol topilmadi.", show_alert=True)
        return

    q = current["question"]
    if opt_idx < 0 or opt_idx >= len(q["options"]):
        await call.answer("Noto'g'ri tanlov.", show_alert=True)
        return
    selected = q["options"][opt_idx]
    is_correct = selected == q["correct"]
    if is_correct:
        apply_quiz_result_to_session(session, True)
        await call.answer("✅ To'g'ri!", show_alert=False)
    else:
        apply_quiz_result_to_session(session, False)
        await call.answer(f"❌ Noto'g'ri! Javob: {q['correct']}", show_alert=True)
        mistake_tags = json.dumps({
            "topic_id": q.get("topic_id"),
            "phase": q.get("phase", "practice")
        })
        log_mistake(call.from_user.id, q["word_id"], "daily_quiz", session["level"], tags=mistake_tags)

    session["current_step"] = current_step + 1
    await state.update_data(session=session)
    await render_session_step(call.message, state)


@router.callback_query(F.data.startswith("daily_send_material_"))
async def daily_send_material(call: CallbackQuery, state: FSMContext):
    material_id = call.data.replace("daily_send_material_", "", 1)
    data = await state.get_data()
    session = data.get("session") or {}
    steps = session.get("steps", [])
    current_step = int(session.get("current_step") or 0)
    if current_step < 0 or current_step >= len(steps):
        await call.answer("Sessiya holati topilmadi.", show_alert=True)
        return
    current = steps[current_step]
    if current.get("type") != "material":
        await call.answer("Material bosqichidan yuboring.", show_alert=True)
        return
    current_material_id = ((current.get("material") or {}).get("id"))
    if current_material_id and material_id != current_material_id:
        await call.answer("Bu eskirgan material tugmasi.", show_alert=True)
        return
    material = get_material_by_id(material_id)
    if not material:
        await call.answer("Material topilmadi.", show_alert=True)
        return
    path = material.get("path")
    if not path or not os.path.exists(path):
        await call.answer("Material fayli topilmadi.", show_alert=True)
        return
    await call.answer("Material yuborilmoqda...")
    log_event(
        call.from_user.id,
        "daily_material_sent",
        section_name="daily_lesson",
        level=session.get("level"),
        metadata={"material_id": material_id}
    )
    await call.message.answer_document(
        FSInputFile(path),
        caption=f"📚 **{material.get('title', 'Material')}**",
        parse_mode="Markdown"
    )

# --- Review Mistakes Flow (Day 3) ---

@router.callback_query(F.data == "review_mistakes")
async def start_mistake_review(call: CallbackQuery, state: FSMContext):
    log_event(call.from_user.id, "review_mistakes_start", section_name="daily_lesson")
    mistakes_data = get_user_mistakes_overview(call.from_user.id)
    
    if not mistakes_data['top_mistakes']:
        await call.answer("Xatolar topilmadi!", show_alert=True)
        return
        
    # Fetch actual word data for these mistakes
    review_items = []
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    for m in mistakes_data['top_mistakes']:
        # Assuming item_id is word_id for now
        try:
            item_id = int(m['item_id'])
        except Exception:
            continue
        cursor.execute("SELECT * FROM words WHERE id = ?", (item_id,))
        word = cursor.fetchone()
        if word:
            review_items.append(dict(word))
    conn.close()
    
    if not review_items:
        await call.answer("Xatolar tafsilotlari topilmadi.", show_alert=True)
        return
        
    # Generate review quiz questions
    questions = []
    for word in review_items:
        distractors = get_distractors(word['level'], word['uz'], 3)
        options = distractors + [word['uz']]
        random.shuffle(options)
        questions.append({
            "text": f"🔄 **Takrorlash**: 🇩🇪 **{word['de']}** - tarjimasi nima?",
            "options": options,
            "correct": word['uz'],
            "word_id": word['id'],
            "level": word.get("level")
        })
        
    review_level = questions[0].get("level") if questions else "A1"
    session_data = {
        "is_review": True,
        "questions": questions,
        "current_index": 0,
        "score": 0,
        "level": review_level
    }
    
    await state.update_data(review_session=session_data)
    update_module_progress(call.from_user.id, "review_session", review_level)
    await render_review_step(call.message, state)

async def render_review_step(message: Message, state: FSMContext):
    data = await state.get_data()
    session = data.get("review_session")
    if not session:
        await message.edit_text("Review sessiyasi topilmadi. Qayta boshlang.")
        return
    idx = session['current_index']
    total = len(session['questions'])
    
    if idx < total:
        q = session['questions'][idx]
        text = f"🧠 **Xatolar ustida ishlash ({idx+1}/{total})**\n\n{q['text']}"
        builder = InlineKeyboardMarkup(inline_keyboard=[])
        for i, opt in enumerate(q['options']):
            builder.inline_keyboard.append([InlineKeyboardButton(text=opt, callback_data=f"review_ans_{idx}_{i}")])
        builder.inline_keyboard.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
        await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")
    else:
        log_event(message.chat.id, "review_mistakes_finish", section_name="daily_lesson")
        update_module_progress(message.chat.id, "review_session", session.get("level", "A1"), completed=True)
        text = "🏆 **Takrorlash yakunlandi!**\n\nXatolar ustida yaxshi ishladingiz. O'rganishda davom eting!"
        builder = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]])
        await message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data.startswith("review_ans_"))
async def review_answer_callback(call: CallbackQuery, state: FSMContext):
    parsed = parse_indexed_callback(call.data, "review_ans_", 2)
    if not parsed:
        await call.answer("Javob formati buzilgan.", show_alert=True)
        return
    idx, opt_idx = parsed
    
    data = await state.get_data()
    session = data.get("review_session")
    if not session:
        await call.answer("Sessiya tugagan. Qayta boshlang.", show_alert=True)
        return
    if idx != session.get("current_index"):
        await call.answer("Bu eski savol.", show_alert=True)
        return
    if idx < 0 or idx >= len(session.get("questions", [])):
        await call.answer("Savol topilmadi.", show_alert=True)
        return
    q = session['questions'][idx]
    if opt_idx < 0 or opt_idx >= len(q.get("options", [])):
        await call.answer("Noto'g'ri tanlov.", show_alert=True)
        return
    
    correct = q['options'][opt_idx] == q['correct']
    if correct:
        await call.answer("✅ To'g'ri! Xato og'irligi kamaytirildi.", show_alert=False)
        resolve_mistake(call.from_user.id, q['word_id'], "quiz_test")
        resolve_mistake(call.from_user.id, q['word_id'], "daily_quiz")
    else:
        await call.answer(f"❌ Noto'g'ri! To'g'ri javob: {q['correct']}", show_alert=True)
        log_mistake(call.from_user.id, q['word_id'], "review_session", q.get("level") or session.get("level") or "A1")
        
    session['current_index'] += 1
    await state.update_data(review_session=session)
    await render_review_step(call.message, state)
