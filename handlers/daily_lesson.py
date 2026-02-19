from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from database import (
    get_or_create_user_profile,
    get_user_profile,
    update_user_profile,
    get_random_words,
    log_mistake,
    DB_NAME,
    record_navigation_event,
    log_event,
    update_module_progress,
    mark_daily_lesson_started,
    mark_daily_lesson_completed,
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
    get_daily_lesson_state,
    save_daily_lesson_state,
    save_user_submission,
    get_due_reviews,
    update_mastery,
)
import sqlite3
import json
import random
import os
import datetime
import re
from handlers.common import send_single_ui_message
from utils.ops_logging import log_structured

router = Router()

STATUS_IDLE = "idle"
STATUS_IN_PROGRESS = "in_progress"
STATUS_FINISHED = "finished"

STEP_WARMUP = 1
STEP_VOCAB = 2
STEP_GRAMMAR = 3
STEP_QUIZ = 4
STEP_PRODUCTION = 5
STEP_SUMMARY = 6

STEP_LABELS = {
    STEP_WARMUP: "warmup",
    STEP_VOCAB: "vocabulary",
    STEP_GRAMMAR: "grammar",
    STEP_QUIZ: "quiz",
    STEP_PRODUCTION: "production",
    STEP_SUMMARY: "summary",
}

LEVEL_GRAMMAR_FALLBACKS = {
    "A1": ["A1"],
    "A2": ["A2", "A1"],
    "B1": ["B1", "A2", "A1"],
    "B2": ["B2", "B1", "A2", "A1"],
    "C1": ["C1", "B2", "B1", "A2", "A1"],
}

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
    if is_correct:
        session["quiz_correct"] = int(session.get("quiz_correct") or 0) + 1
    else:
        session["quiz_wrong"] = int(session.get("quiz_wrong") or 0) + 1
    return session


def parse_indexed_callback(data: str, prefix: str, expected_int_count: int):
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
    for candidate_level in LEVEL_GRAMMAR_FALLBACKS.get(level, [level]):
        topics = data.get(candidate_level, [])
        if topics:
            return topics
    return []


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


def get_distractors(level, correct_uz, limit=3):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT uz FROM words WHERE level = ? AND uz != ? ORDER BY RANDOM() LIMIT ?",
        (level, correct_uz, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def build_quiz_question(word, level, phase, grammar_topic_id):
    correct = word["uz"]
    distractors = get_distractors(level, correct, 3)
    unique_options = []
    for opt in distractors + [correct]:
        if opt and opt not in unique_options:
            unique_options.append(opt)
    if len(unique_options) < 2:
        return None
    random.shuffle(unique_options)
    return {
        "id": f"{phase}_{word['id']}",
        "phase": phase,
        "topic_id": grammar_topic_id,
        "word_id": word["id"],
        "text": f"🇩🇪 **{word['de']}** — tarjimasi nima?",
        "options": unique_options,
        "correct": correct,
    }


def _safe_topic(topic):
    return topic or {"id": None, "title": "Grammatika", "content": "", "example": "-"}


_MD_ESC_RE = re.compile(r"([\\_*`\[\]()~>#+\-=|{}.!])")


def _md_escape(value):
    if value is None:
        return ""
    return _MD_ESC_RE.sub(r"\\\1", str(value))


def _normalize_profile(user_id):
    profile = get_or_create_user_profile(user_id) or {}
    updates = {}
    if not profile.get("goal"):
        updates["goal"] = "general"
    if not profile.get("current_level"):
        updates["current_level"] = "A1"
    if not (profile.get("daily_time_minutes") or profile.get("daily_target")):
        updates["daily_target"] = 10
    if not profile.get("onboarding_completed"):
        updates["onboarding_completed"] = 1
    if updates:
        update_user_profile(user_id, **updates)
        profile = get_or_create_user_profile(user_id) or {}
    return profile


def _level_production_mode(level, user_id):
    if level in ("A1", "A2"):
        return "writing"
    if level == "C1":
        return "speaking"
    day_parity = (datetime.date.today().toordinal() + int(user_id or 0)) % 2
    return "speaking" if day_parity else "writing"


def _quiz_sizes(profile):
    minutes = int(profile.get("daily_time_minutes") or profile.get("daily_target") or 10)
    if minutes <= 10:
        return 3, 4
    if minutes >= 20:
        return 5, 5
    return 4, 4


def choose_grammar_topic(level, mistake_word_ids, user_id, avoid_topic_id=None):
    topics = load_grammar_for_level(level)
    if not topics:
        return None, "fallback"

    weak_topics = get_recent_topic_mistake_scores(user_id, level, days=14, limit=2)
    if weak_topics:
        by_id = {t.get("id"): t for t in topics if t.get("id")}
        for topic_id, score in weak_topics:
            if score >= 1.0 and topic_id in by_id and topic_id != avoid_topic_id:
                return by_id[topic_id], "topic_weakness"

    coverage = get_grammar_coverage_map(user_id, level)
    least_seen = sorted(topics, key=lambda t: coverage.get(t.get("id"), 0))
    if avoid_topic_id:
        non_repeating = [t for t in least_seen if t.get("id") != avoid_topic_id]
        if non_repeating:
            return non_repeating[0], "least_covered"
    return least_seen[0], "least_covered"


def select_vocab_for_topic(level, grammar_topic, count):
    pool = get_random_words(level, limit=max(40, count * 12))
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


def _practice_ids(level, user_id, count, vocab_ids):
    mistake_ids = get_weighted_mistake_word_ids(user_id, level, limit=12) or []
    mastered_ids = set(get_mastered_mistake_word_ids(user_id, level, limit=200) or [])

    picked = []
    for wid in mistake_ids:
        if wid in mastered_ids or wid in vocab_ids:
            continue
        picked.append(wid)
        if len(picked) >= max(2, min(count, 3)):
            break

    needed = count - len(picked)
    if needed > 0:
        pool = get_random_words(level, limit=needed * 6)
        blocked = set(vocab_ids + picked).union(mastered_ids)
        for w in pool:
            if w["id"] in blocked:
                continue
            picked.append(w["id"])
            blocked.add(w["id"])
            if len(picked) >= count:
                break
    return picked[:count]


def build_daily_plan(user_id, profile):
    level = profile.get("current_level", "A1")
    vocab_n, quiz_n = _quiz_sizes(profile)

    last_plan_obj = get_last_daily_plan(user_id)
    avoid_topic_id = None
    if last_plan_obj and isinstance(last_plan_obj.get("plan"), dict):
        avoid_topic_id = last_plan_obj["plan"].get("grammar_topic_id")

    topic, reason_code = choose_grammar_topic(level, [], user_id, avoid_topic_id=avoid_topic_id)
    topic = _safe_topic(topic)

    vocab_words = select_vocab_for_topic(level, topic, vocab_n)
    vocab_ids = [w["id"] for w in vocab_words]
    practice_ids = _practice_ids(level, user_id, quiz_n, vocab_ids)
    production_mode = _level_production_mode(level, user_id)

    return {
        "level": level,
        "reason_code": reason_code,
        "grammar_topic_id": topic.get("id"),
        "material_id": MATERIAL_CATALOG.get(level, MATERIAL_CATALOG["A1"])["id"],
        "vocab_ids": vocab_ids,
        "practice_quiz_ids": practice_ids,
        "writing_task_type": "short_sentences" if production_mode == "writing" else "speaking_voice",
        "production_mode": production_mode,
    }


def is_core_daily_plan(plan):
    required = {"grammar_topic_id", "material_id", "vocab_ids", "practice_quiz_ids", "writing_task_type"}
    return isinstance(plan, dict) and required.issubset(set(plan.keys()))


def _find_topic(level, topic_id):
    topics = load_grammar_for_level(level)
    if not topics:
        return _safe_topic(None)
    for topic in topics:
        if topic.get("id") == topic_id:
            return topic
    return topics[0]


def _build_warmup_question(level, topic, vocab_words):
    if vocab_words:
        word = vocab_words[0]
        q = build_quiz_question(word, level, "warmup", topic.get("id"))
        if q:
            return {
                "text": f"🔥 **Warmup**\n\n{q['text']}",
                "options": q["options"],
                "correct": q["correct"],
                "word_id": q["word_id"],
            }
    return {
        "text": f"🔥 **Warmup**\n\nBugungi fokus: **{topic.get('title', 'Grammatika')}**. Tayyormisiz?",
        "options": ["Ha, tayyorman", "Yana tushuntirib bering"],
        "correct": "Ha, tayyorman",
        "word_id": None,
    }


def _build_daily_session(plan):
    level = plan.get("level", "A1")
    topic = _safe_topic(_find_topic(level, plan.get("grammar_topic_id")))
    vocab_words = get_words_by_ids(plan.get("vocab_ids", []))
    if len(vocab_words) < 3:
        refill = get_random_words(level, limit=8)
        existing = {w["id"] for w in vocab_words}
        for w in refill:
            if w["id"] in existing:
                continue
            vocab_words.append(w)
            existing.add(w["id"])
            if len(vocab_words) >= 3:
                break
    vocab_words = vocab_words[:5]

    quiz_words = get_words_by_ids(plan.get("practice_quiz_ids", []))
    if len(quiz_words) < 4:
        refill = get_random_words(level, limit=12)
        existing = {w["id"] for w in quiz_words}
        for w in refill:
            if w["id"] in existing:
                continue
            quiz_words.append(w)
            existing.add(w["id"])
            if len(quiz_words) >= 4:
                break
    quiz_words = quiz_words[:5]

    questions = []
    for w in quiz_words:
        q = build_quiz_question(w, level, "practice", topic.get("id"))
        if q:
            questions.append(q)
    questions = questions[:5]

    production_mode = plan.get("production_mode") or (
        "writing" if plan.get("writing_task_type") != "speaking_voice" else "speaking"
    )

    return {
        "level": level,
        "topic": topic,
        "warmup": _build_warmup_question(level, topic, vocab_words),
        "vocab_words": vocab_words,
        "quiz": {
            "questions": questions,
            "index": 0,
            "correct": 0,
            "wrong": 0,
        },
        "production": {
            "mode": production_mode,
            "voice_received": False,
            "writing_done": False,
        },
        "summary": {
            "committed": False,
            "xp_earned": 0,
            "completion": {},
        },
    }


def _build_planner_payload(profile, plan, source):
    return {
        "source": source,
        "level": plan.get("level"),
        "daily_time_minutes": profile.get("daily_time_minutes") or profile.get("daily_target") or 10,
        "plan": {
            "reason_code": plan.get("reason_code"),
            "grammar_topic_id": plan.get("grammar_topic_id"),
            "vocab_ids": plan.get("vocab_ids", []),
            "practice_quiz_ids": plan.get("practice_quiz_ids", []),
            "production_mode": plan.get("production_mode"),
        },
    }


def _ensure_today_plan(user_id, profile):
    plan = get_cached_daily_plan(user_id)
    source = "cache"
    if not plan or not is_core_daily_plan(plan):
        plan = build_daily_plan(user_id, profile)
        save_daily_plan(user_id, plan)
        source = "generated"
    payload = _build_planner_payload(profile, plan, source)
    log_daily_plan_audit(user_id, f"plan_{source}", metadata=payload)
    return plan


def _entry_idle_text(plan):
    topic = _safe_topic(_find_topic(plan.get("level", "A1"), plan.get("grammar_topic_id")))
    return (
        "📅 **Bugungi dars**\n"
        "⏳ **~10 daqiqa**\n"
        f"🎯 **Fokus:** {_md_escape(topic.get('title', 'Grammatika'))}"
    )


def _entry_progress_text():
    return "📅 **Bugungi dars davom etmoqda**"


def _entry_finished_text(state_obj):
    xp = int(state_obj.get("xp_earned") or 0)
    return (
        "✅ **Bugungi dars yakunlandi**\n"
        f"⭐ XP: **+{xp}**\n"
        "Ertangi dars uchun tayyorsiz."
    )


def _entry_markup(status):
    if status == STATUS_IDLE:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Boshlash", callback_data="daily_begin")],
            [InlineKeyboardButton(text="🔄 Takrorlash (SRS)", callback_data="daily_review_mastery")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
    if status == STATUS_IN_PROGRESS:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Davom ettirish", callback_data="daily_resume")],
                [InlineKeyboardButton(text="Bekor qilish", callback_data="daily_cancel")],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ertangi darsni kutish", callback_data="daily_wait")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])


def _safe_edit_or_send(message: Message, text: str, markup: InlineKeyboardMarkup):
    try:
        return message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower():
            return message.edit_text(text, reply_markup=markup)
        raise


async def _show_entry_screen(message: Message, user_id: int):
    profile = _normalize_profile(user_id)
    state_obj = get_daily_lesson_state(user_id)
    status = state_obj.get("daily_status") or STATUS_IDLE

    if status == STATUS_FINISHED:
        text = _entry_finished_text(state_obj)
    elif status == STATUS_IN_PROGRESS:
        text = _entry_progress_text()
    else:
        plan = _ensure_today_plan(user_id, profile)
        text = _entry_idle_text(plan)

    await send_single_ui_message(message, text, reply_markup=_entry_markup(status), parse_mode="Markdown", user_id=user_id)


def _stale_answer_text(expected_step):
    return f"Bu tugma eskirgan. Joriy bosqich: {STEP_LABELS.get(expected_step, 'dars')}"


def _load_active_session(user_id):
    state_obj = get_daily_lesson_state(user_id)
    if (state_obj.get("daily_status") != STATUS_IN_PROGRESS) or (not isinstance(state_obj.get("session"), dict)):
        return None, state_obj
    return state_obj.get("session"), state_obj


def _save_session_state(user_id, step, session, xp_earned=0):
    save_daily_lesson_state(
        user_id=user_id,
        daily_status=STATUS_IN_PROGRESS,
        daily_step=step,
        session=session,
        xp_earned=xp_earned,
        ensure_started=True,
        mark_completed=False,
    )


def _build_step_header(step):
    return f"**{step}/6 — {STEP_LABELS.get(step, 'step').title()}**"


async def _render_step(message: Message, user_id: int):
    session, state_obj = _load_active_session(user_id)
    if not session:
        await _show_entry_screen(message, user_id)
        return

    step = int(state_obj.get("daily_step") or STEP_WARMUP)
    level = session.get("level", "A1")

    if step == STEP_WARMUP:
        warmup = session.get("warmup") or {}
        text = f"{_build_step_header(STEP_WARMUP)}\n\n{_md_escape(warmup.get('text', '-'))}"
        rows = []
        for idx, opt in enumerate(warmup.get("options", [])):
            rows.append([InlineKeyboardButton(text=opt, callback_data=f"daily_warmup_{idx}")])
        await _safe_edit_or_send(message, text, InlineKeyboardMarkup(inline_keyboard=rows))
        return

    if step == STEP_VOCAB:
        words = session.get("vocab_words", [])[:5]
        lines = [
            f"{i}. **{_md_escape(w.get('de', '-'))}** — {_md_escape(w.get('uz', '-'))}"
            for i, w in enumerate(words, 1)
        ]
        text = (
            f"{_build_step_header(STEP_VOCAB)}\n\n"
            "📘 **Lug'at (3-5 so'z)**\n\n"
            + ("\n".join(lines) if lines else "So'z topilmadi")
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Davom", callback_data="daily_vocab_next")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        await _safe_edit_or_send(message, text, markup)
        return

    if step == STEP_GRAMMAR:
        topic = _safe_topic(session.get("topic"))
        content = (topic.get("content") or "").strip()
        content = content[:420] + ("..." if len(content) > 420 else "")
        text = (
            f"{_build_step_header(STEP_GRAMMAR)}\n\n"
            f"📐 **{_md_escape(topic.get('title', 'Grammatika'))}**\n\n"
            f"{_md_escape(content or '-')}\n\n"
            f"📝 Misol: {_md_escape(topic.get('example', '-'))}"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Davom", callback_data="daily_grammar_next")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        await _safe_edit_or_send(message, text, markup)
        return

    if step == STEP_QUIZ:
        quiz = session.get("quiz") or {}
        questions = quiz.get("questions", [])
        q_idx = int(quiz.get("index") or 0)
        if q_idx >= len(questions):
            _save_session_state(user_id, STEP_PRODUCTION, session)
            await _render_step(message, user_id)
            return
        q = questions[q_idx]
        text = (
            f"{_build_step_header(STEP_QUIZ)}\n\n"
            f"🧠 **Savol {q_idx + 1}/{len(questions)}**\n\n"
            f"{_md_escape(q.get('text', '-'))}"
        )
        rows = []
        for opt_idx, opt in enumerate(q.get("options", [])):
            rows.append([InlineKeyboardButton(text=opt, callback_data=f"daily_quiz_{q_idx}_{opt_idx}")])
        rows.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")])
        await _safe_edit_or_send(message, text, InlineKeyboardMarkup(inline_keyboard=rows))
        return

    if step == STEP_PRODUCTION:
        prod = session.get("production") or {}
        topic = _safe_topic(session.get("topic"))
        mode = prod.get("mode", "writing")
        if mode == "speaking":
            text = (
                f"{_build_step_header(STEP_PRODUCTION)}\n\n"
                "🎤 **Speaking**\n"
                f"Mavzu: **{_md_escape(topic.get('title', 'Umumiy mavzu'))}**\n\n"
                "45-60 soniyalik voice xabar yuboring."
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Tekshirish", callback_data="daily_production_check")],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
            ])
            await _safe_edit_or_send(message, text, markup)
            return

        sentence_target = "1-2"
        if level in ("B1", "B2"):
            sentence_target = "2-3"
        text = (
            f"{_build_step_header(STEP_PRODUCTION)}\n\n"
            "✍️ **Writing**\n"
            f"Mavzu: **{_md_escape(topic.get('title', 'Umumiy mavzu'))}**\n"
            f"{sentence_target} ta qisqa gap yozing, keyin tasdiqlang."
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Bajarildi", callback_data="daily_prod_done")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        await _safe_edit_or_send(message, text, markup)
        return

    if step == STEP_SUMMARY:
        summary = session.get("summary") or {}
        completion = summary.get("completion") or {}
        streak = completion.get("streak", {"current_streak": 0, "best_streak": 0})
        quiz = session.get("quiz") or {}
        text = (
            f"{_build_step_header(STEP_SUMMARY)}\n\n"
            "✅ **Dars yakuni**\n"
            f"🧠 Quiz: **{int(quiz.get('correct') or 0)}/{len(quiz.get('questions', []))}**\n"
            f"🔥 Streak: **{streak.get('current_streak', 0)}**\n"
            f"⭐ XP: **+{int(summary.get('xp_earned') or 0)}**"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Yakunlash", callback_data="daily_finish")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
        ])
        await _safe_edit_or_send(message, text, markup)
        return


def _calc_xp(session):
    quiz = session.get("quiz") or {}
    correct = int(quiz.get("correct") or 0)
    total = len(quiz.get("questions", []))
    base = 12
    quiz_bonus = min(correct, total) * 2
    prod_bonus = 6
    return base + quiz_bonus + prod_bonus


def _commit_summary_if_needed(user_id, session):
    summary = session.get("summary") or {}
    if summary.get("committed"):
        return session

    level = session.get("level", "A1")
    completion = mark_daily_lesson_completed(user_id)
    xp_earned = 0

    if completion.get("completed_now"):
        xp_earned = _calc_xp(session)
        profile = get_or_create_user_profile(user_id) or {}
        current_xp = int(profile.get("xp") or 0)
        update_user_profile(user_id, xp=current_xp + xp_earned)

        update_module_progress(user_id, "daily_lesson", level, completed=True)
        update_module_progress(user_id, "quiz_test", level, completed=True)
        update_module_progress(user_id, "practice", level, completed=True)

    summary["committed"] = True
    summary["xp_earned"] = int(xp_earned)
    summary["completion"] = completion
    session["summary"] = summary

    log_event(
        user_id,
        "daily_session_finish",
        section_name="daily_lesson",
        level=level,
        metadata={
            "quiz_correct": int((session.get("quiz") or {}).get("correct") or 0),
            "quiz_total": len((session.get("quiz") or {}).get("questions", [])),
            "xp_earned": int(xp_earned),
        },
    )
    log_structured(
        "daily_lesson_finish",
        user_id=user_id,
        level=level,
        xp_earned=int(xp_earned),
    )
    return session


def _guard_step(call: CallbackQuery, expected_step):
    session, state_obj = _load_active_session(call.from_user.id)
    if not session:
        return None, None, "Sessiya topilmadi."
    current_step = int(state_obj.get("daily_step") or 0)
    if current_step != expected_step:
        return None, None, _stale_answer_text(current_step)
    return session, state_obj, None


@router.message(F.text == "🚀 Kunlik dars")
@router.message(F.text == "🚀 Tägliche Lektion")
@router.message(F.text == "🚀 Daily Lesson")
async def daily_lesson_start(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "daily_lesson", entry_type="text")
    await _show_entry_screen(message, message.from_user.id)


@router.callback_query(F.data == "daily_begin")
@router.callback_query(F.data == "daily_start")
async def daily_begin_callback(call: CallbackQuery):
    profile = _normalize_profile(call.from_user.id)
    state_obj = get_daily_lesson_state(call.from_user.id)
    status = state_obj.get("daily_status")
    if status == STATUS_FINISHED:
        await call.answer("Bugungi dars allaqachon yakunlangan.", show_alert=True)
        await _show_entry_screen(call.message, call.from_user.id)
        return
    if status == STATUS_IN_PROGRESS and state_obj.get("session"):
        await call.answer("Dars allaqachon boshlangan.", show_alert=False)
        await _render_step(call.message, call.from_user.id)
        return

    plan = _ensure_today_plan(call.from_user.id, profile)
    session = _build_daily_session(plan)

    mark_daily_lesson_started(call.from_user.id)
    update_module_progress(call.from_user.id, "daily_lesson", session.get("level", "A1"), completed=False)
    save_daily_lesson_state(
        user_id=call.from_user.id,
        daily_status=STATUS_IN_PROGRESS,
        daily_step=STEP_WARMUP,
        session=session,
        xp_earned=0,
        ensure_started=True,
        mark_completed=False,
    )

    log_event(call.from_user.id, "daily_session_start", section_name="daily_lesson", level=session.get("level"))
    log_structured("daily_lesson_start", user_id=call.from_user.id, level=session.get("level"))
    await _render_step(call.message, call.from_user.id)


@router.callback_query(F.data == "daily_resume")
async def daily_resume_callback(call: CallbackQuery):
    state_obj = get_daily_lesson_state(call.from_user.id)
    status = state_obj.get("daily_status")
    if status == STATUS_FINISHED:
        await call.answer("Bugungi dars yakunlangan.", show_alert=True)
        await _show_entry_screen(call.message, call.from_user.id)
        return
    if status != STATUS_IN_PROGRESS:
        await call.answer("Avval darsni boshlang.", show_alert=True)
        await _show_entry_screen(call.message, call.from_user.id)
        return
    await _render_step(call.message, call.from_user.id)


@router.callback_query(F.data == "daily_cancel")
async def daily_cancel_callback(call: CallbackQuery):
    state_obj = get_daily_lesson_state(call.from_user.id)
    if state_obj.get("daily_status") != STATUS_IN_PROGRESS:
        await call.answer("Faol dars topilmadi.", show_alert=True)
        return
    save_daily_lesson_state(
        user_id=call.from_user.id,
        daily_status=STATUS_IDLE,
        daily_step=0,
        session=None,
        xp_earned=0,
        ensure_started=False,
        mark_completed=False,
    )
    await call.answer("Bugungi sessiya bekor qilindi.", show_alert=False)
    await _show_entry_screen(call.message, call.from_user.id)


@router.callback_query(F.data == "daily_wait")
async def daily_wait_callback(call: CallbackQuery):
    await call.answer("Ertangi darsni kutamiz.", show_alert=False)
    # Redirect to home
    from handlers.common import _send_fresh_main_menu, MAIN_MENU_TEXT
    await _send_fresh_main_menu(call.message, MAIN_MENU_TEXT, user_id=call.from_user.id)


@router.callback_query(F.data.startswith("daily_warmup_"))
async def daily_warmup_callback(call: CallbackQuery):
    session, _, err = _guard_step(call, STEP_WARMUP)
    if err:
        await call.answer(err, show_alert=True)
        return

    try:
        opt_idx = int(call.data.replace("daily_warmup_", "", 1))
    except ValueError:
        await call.answer("Noto'g'ri tanlov.", show_alert=True)
        return

    warmup = session.get("warmup") or {}
    options = warmup.get("options", [])
    if opt_idx < 0 or opt_idx >= len(options):
        await call.answer("Noto'g'ri tanlov.", show_alert=True)
        return

    selected = options[opt_idx]
    correct = selected == warmup.get("correct")
    if correct:
        await call.answer("To'g'ri ✅", show_alert=False)
    else:
        await call.answer("Qabul qilindi, davom etamiz.", show_alert=False)
        if warmup.get("word_id"):
            tags = json.dumps({"topic_id": (session.get("topic") or {}).get("id"), "phase": "warmup"})
            log_mistake(call.from_user.id, warmup.get("word_id"), "daily_warmup", session.get("level", "A1"), tags=tags)

    _save_session_state(call.from_user.id, STEP_VOCAB, session)
    await _render_step(call.message, call.from_user.id)


@router.callback_query(F.data == "daily_vocab_next")
async def daily_vocab_next_callback(call: CallbackQuery):
    session, _, err = _guard_step(call, STEP_VOCAB)
    if err:
        await call.answer(err, show_alert=True)
        return

    update_module_progress(call.from_user.id, "dictionary", session.get("level", "A1"), completed=False)
    _save_session_state(call.from_user.id, STEP_GRAMMAR, session)
    await _render_step(call.message, call.from_user.id)


@router.callback_query(F.data == "daily_grammar_next")
async def daily_grammar_next_callback(call: CallbackQuery):
    session, _, err = _guard_step(call, STEP_GRAMMAR)
    if err:
        await call.answer(err, show_alert=True)
        return

    level = session.get("level", "A1")
    topic_id = (session.get("topic") or {}).get("id")
    update_module_progress(call.from_user.id, "grammar", level, completed=False)
    if topic_id:
        mark_grammar_topic_seen(call.from_user.id, topic_id, level)

    _save_session_state(call.from_user.id, STEP_QUIZ, session)
    await _render_step(call.message, call.from_user.id)


@router.callback_query(F.data.startswith("daily_quiz_"))
async def daily_quiz_callback(call: CallbackQuery):
    session, _, err = _guard_step(call, STEP_QUIZ)
    if err:
        await call.answer(err, show_alert=True)
        return

    parsed = parse_indexed_callback(call.data, "daily_quiz_", 2)
    if not parsed:
        await call.answer("Savol formati xato.", show_alert=True)
        return
    q_idx, opt_idx = parsed

    quiz = session.get("quiz") or {}
    questions = quiz.get("questions", [])
    current_idx = int(quiz.get("index") or 0)

    if q_idx != current_idx or q_idx >= len(questions):
        await call.answer("Bu eski savol.", show_alert=True)
        return

    q = questions[q_idx]
    options = q.get("options", [])
    if opt_idx < 0 or opt_idx >= len(options):
        await call.answer("Noto'g'ri tanlov.", show_alert=True)
        return

    selected = options[opt_idx]
    is_correct = selected == q.get("correct")
    if is_correct:
        quiz["correct"] = int(quiz.get("correct") or 0) + 1
        await call.answer("To'g'ri ✅", show_alert=False)
    else:
        quiz["wrong"] = int(quiz.get("wrong") or 0) + 1
        await call.answer(f"Noto'g'ri ❌\nTo'g'ri javob: {q.get('correct')}", show_alert=True)
        mistake_tags = json.dumps({"topic_id": q.get("topic_id"), "phase": "quiz"})
        log_mistake(call.from_user.id, q.get("word_id"), "daily_quiz", session.get("level", "A1"), tags=mistake_tags)

    quiz["index"] = current_idx + 1
    session["quiz"] = quiz

    if int(quiz.get("index") or 0) >= len(questions):
        _save_session_state(call.from_user.id, STEP_PRODUCTION, session)
    else:
        _save_session_state(call.from_user.id, STEP_QUIZ, session)
    await _render_step(call.message, call.from_user.id)


@router.callback_query(F.data == "daily_prod_done")
async def daily_production_done_callback(call: CallbackQuery):
    session, _, err = _guard_step(call, STEP_PRODUCTION)
    if err:
        await call.answer(err, show_alert=True)
        return

    production = session.get("production") or {}
    if production.get("mode") != "writing":
        await call.answer("Bu bosqichda voice yuboring.", show_alert=True)
        return

    production["writing_done"] = True
    session["production"] = production

    topic_id = (session.get("topic") or {}).get("id")
    level = session.get("level", "A1")
    
    # Save submission (New Phase 2 logic)
    # Since we don't have the message text here directly (it was likely handled by a different flow or implied), 
    # we might need to check how writing_done is triggered.
    # In daily_lesson, writing is handled by the user typing then clicking 'Bajarildi'.
    # We should add a message handler for writing in daily_lesson too.
    
    mark_writing_task_completed(call.from_user.id, level, topic_id, "daily_writing")
    
    # Check if we have recent text from user to save as submission
    # This is a bit tricky as we don't 'own' the text yet as a separate state.
    # For now, we rely on the user sending text then clicking the button.

    session = _commit_summary_if_needed(call.from_user.id, session)
    _save_session_state(call.from_user.id, STEP_SUMMARY, session, xp_earned=(session.get("summary") or {}).get("xp_earned", 0))
    await _render_step(call.message, call.from_user.id)


@router.callback_query(F.data == "daily_production_check")
async def daily_production_check_callback(call: CallbackQuery):
    session, _, err = _guard_step(call, STEP_PRODUCTION)
    if err:
        await call.answer(err, show_alert=True)
        return

    production = session.get("production") or {}
    if production.get("mode") != "speaking":
        await call.answer("Bu writing bosqichi.", show_alert=True)
        return

    if not production.get("voice_received"):
        await call.answer("Avval voice xabar yuboring.", show_alert=True)
        return

    session = _commit_summary_if_needed(call.from_user.id, session)
    _save_session_state(call.from_user.id, STEP_SUMMARY, session, xp_earned=(session.get("summary") or {}).get("xp_earned", 0))
    await _render_step(call.message, call.from_user.id)


@router.message(F.voice)
async def daily_voice_message_handler(message: Message):
    session, state_obj = _load_active_session(message.from_user.id)
    if not session:
        return
    if int(state_obj.get("daily_step") or 0) != STEP_PRODUCTION:
        return

    production = session.get("production") or {}
    if production.get("mode") != "speaking":
        return

    production["voice_received"] = True
    session["production"] = production

    level = session.get("level", "A1")
    topic_id = (session.get("topic") or {}).get("id")
    
    # Save submission (New Phase 2 logic)
    save_user_submission(message.from_user.id, "speaking", level, topic_id, message.voice.file_id)
    
    mark_writing_task_completed(message.from_user.id, level, topic_id, "speaking_voice")

    log_event(
        message.from_user.id,
        "daily_speaking_voice_received",
        section_name="daily_lesson",
        level=level,
        metadata={"topic_id": topic_id, "file_id": message.voice.file_id if message.voice else None},
    )
    _save_session_state(message.from_user.id, STEP_PRODUCTION, session)
    await message.answer("Voice qabul qilindi ✅\nDavom etish uchun dars oynasidagi 'Tekshirish' tugmasini bosing.")

@router.message(F.text)
async def daily_text_message_handler(message: Message):
    if message.text.startswith("/") or message.text in ["🚀 Kunlik dars", "📘 Lug‘at (A1–C1)", "📐 Grammatika"]:
        return
        
    session, state_obj = _load_active_session(message.from_user.id)
    if not session or int(state_obj.get("daily_step") or 0) != STEP_PRODUCTION:
        return

    production = session.get("production") or {}
    if production.get("mode") != "writing":
        return

    # Store text for later save_user_submission when 'Bajarildi' is clicked
    # OR save it immediately as a draft
    level = session.get("level", "A1")
    topic_id = (session.get("topic") or {}).get("id")
    save_user_submission(message.from_user.id, "writing", level, topic_id, message.text)
    
    await message.answer("Matn qabul qilindi ✅\nDavom etish uchun dars oynasidagi 'Bajarildi' tugmasini bosing.")


@router.callback_query(F.data == "daily_finish")
async def daily_finish_callback(call: CallbackQuery):
    session, _, err = _guard_step(call, STEP_SUMMARY)
    if err:
        await call.answer(err, show_alert=True)
        return

    summary = session.get("summary") or {}
    xp_earned = int(summary.get("xp_earned") or 0)
    save_daily_lesson_state(
        user_id=call.from_user.id,
        daily_status=STATUS_FINISHED,
        daily_step=STEP_SUMMARY,
        session=session,
        xp_earned=xp_earned,
        ensure_started=True,
        mark_completed=True,
    )

@router.callback_query(F.data == "daily_review_mastery")
async def daily_review_mastery_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    due_items = get_due_reviews(user_id, limit=10)
    
    if not due_items:
        # Fallback: check mistakes
        from database import get_user_mistakes_overview
        mistakes = get_user_mistakes_overview(user_id)
        if not mistakes:
            await call.answer("Hozircha takrorlash uchun so'zlar yo'q. ✅", show_alert=True)
            return
        
        # If mistakes exist but not in mastery yet, we can't 'review' by mastery rules easily
        # but we can just say "Good job" for now or start a mistake review.
        await call.answer("Barcha so'zlarni o'zlashtirgansiz! Yangi so'zlar o'rganishda davom eting.", show_alert=True)
        return

    # Start Mastery Review Session
    # We'll use a simplified version of the quiz logic
    # We need to fetch the actual words for these item_ids
    item_ids = [int(item['item_id']) for item in due_items if item['module'] == 'dictionary'] # Assuming mostly words for now
    words = get_words_by_ids(item_ids)
    
    if not words:
        await call.answer("Xatolik: so'zlar topilmadi.", show_alert=True)
        return

    questions = []
    for word in words:
        # Find which mastery record corresponds to this word
        q = build_quiz_question(word, word['level'], "srs_review", "srs")
        if q:
            questions.append(q)

    if not questions:
        await call.answer("Savollar tayyorlanmadi.", show_alert=True)
        return

    await state.update_data(
        srs_questions=questions,
        current_idx=0,
        correct_count=0,
        session_type="srs_review"
    )
    
    await _render_srs_step(call.message, questions[0], 0, len(questions))

async def _render_srs_step(message: Message, question: dict, index: int, total: int):
    builder = InlineKeyboardBuilder()
    for idx, opt in enumerate(question['options']):
        builder.button(text=opt, callback_data=f"srs_ans_{index}_{idx}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home"))
    
    text = (
        f"🔄 **SRS Takrorlash ({index+1}/{total})**\n\n"
        f"{question['text']}"
    )
    await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("srs_ans_"))
async def srs_answer_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("session_type") != "srs_review":
        return

    questions = data.get("srs_questions", [])
    current_idx = data.get("current_idx", 0)
    correct_count = data.get("correct_count", 0)
    
    parsed = parse_indexed_callback(call.data, "srs_ans_", 2)
    if not parsed or parsed[0] != current_idx:
        await call.answer("Eski savol!", show_alert=True)
        return
    
    _, opt_idx = parsed
    question = questions[current_idx]
    selected = question['options'][opt_idx]
    is_correct = selected == question['correct']
    
    # Update SRS Mastery in DB!
    update_mastery(call.from_user.id, question['word_id'], "dictionary", is_correct)
    
    if is_correct:
        correct_count += 1
        await call.answer("To'g'ri! ✅", show_alert=False)
    else:
        await call.answer(f"Noto'g'ri! ❌ To'g'ri javob: {question['correct']}", show_alert=True)

    next_idx = current_idx + 1
    if next_idx < len(questions):
        await state.update_data(current_idx=next_idx, correct_count=correct_count)
        await _render_srs_step(call.message, questions[next_idx], next_idx, len(questions))
    else:
        # Finish Review
        text = (
            "🏁 **Takrorlash yakunlandi!**\n\n"
            f"📊 Natija: {correct_count}/{len(questions)}\n"
            "So'zlar o'zlashtirish darajasiga qarab keyingi safar yana chiqadi."
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]])
        await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
        await state.clear()
