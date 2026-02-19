from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
from database import (
    get_user_progress_summary,
    get_daily_lesson_completion_rate,
    record_navigation_event,
    get_latest_daily_plan_audit,
    get_recent_topic_mistake_scores,
    get_user_profile,
    get_mastery_stats,
    get_submission_stats,
    get_due_review_count
)
from handlers.common import send_single_ui_message

router = Router()

def _load_grammar_topic_title(level, topic_id):
    if not level or not topic_id:
        return None
    file_path = "data/grammar.json"
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for topic in data.get(level, []):
            if topic.get("id") == topic_id:
                return topic.get("title")
    except Exception:
        return None
    return None

def _calc_module_line(module_stats, aliases):
    attempts = 0
    completions = 0
    for row in module_stats:
        if row.get("module") in aliases:
            attempts += row.get("attempts") or 0
            completions += row.get("completions") or 0
    rate = int((completions / attempts) * 100) if attempts > 0 else 0
    return attempts, completions, rate

@router.message(F.text == "📊 Progress & Stats")
@router.message(F.text == "📊 Progress")
@router.message(F.text == "📊 Natijalar")
@router.message(F.text == "📊 Fortschritt")
async def stats_handler(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    record_navigation_event(message.from_user.id, "progress", entry_type="text")
    progress = get_user_progress_summary(message.from_user.id)
    streak = progress.get("streak", {"current_streak": 0, "best_streak": 0})
    modules = progress.get("modules", [])
    completion_rate_7d = get_daily_lesson_completion_rate(message.from_user.id, days=7)
    latest_plan = get_latest_daily_plan_audit(message.from_user.id, days=7) or {}
    plan_meta = latest_plan.get("metadata") or {}
    plan_source = plan_meta.get("source")
    plan_level = plan_meta.get("level")
    plan_topic_id = ((plan_meta.get("plan") or {}).get("grammar_topic_id"))
    plan_topic_title = _load_grammar_topic_title(plan_level, plan_topic_id)
    reason_code = ((plan_meta.get("plan") or {}).get("reason_code")) or plan_meta.get("reason_code")
    profile = get_user_profile(message.from_user.id) or {}
    weak_level = plan_level or profile.get("current_level") or "A1"
    weak_topics = get_recent_topic_mistake_scores(message.from_user.id, weak_level, days=14, limit=3)

    # Phase 2: SRS & Submission Stats
    mastery = get_mastery_stats(message.from_user.id)
    submissions = get_submission_stats(message.from_user.id)
    due_count = get_due_review_count(message.from_user.id)
    
    total_mastered = sum(count for box, count in mastery.items() if box >= 4)
    total_learning = sum(count for box, count in mastery.items() if box < 4)

    if plan_source == "generated":
        source_text = "yangidan tuzilgan"
    elif plan_source == "cache":
        source_text = "keshdan olingan"
    else:
        source_text = "mavjud emas"

    if reason_code == "mistake_related":
        reason_text = "xatolarga moslashtirilgan"
    elif reason_code == "topic_weakness":
        reason_text = "zaif mavzuni mustahkamlash uchun"
    elif reason_code == "least_covered":
        reason_text = "kam mashq qilingan mavzudan"
    elif reason_code == "grammar_gap":
        reason_text = "grammatika natijasini mustahkamlash uchun"
    elif reason_code == "materials_gap":
        reason_text = "materiallar bilan ishlashni kuchaytirish uchun"
    else:
        reason_text = "balans asosida"

    plan_topic_text = plan_topic_title or "—"
    if weak_topics:
        weak_lines = []
        for topic_id, score in weak_topics:
            title = _load_grammar_topic_title(weak_level, topic_id) or topic_id
            weak_lines.append(f"▫️ {title} ({int(round(score))})")
        weak_topics_text = "\n".join(weak_lines)
    else:
        weak_topics_text = "▫️ Zaif mavzular hali aniqlanmadi"

    dict_attempts, dict_comp, dict_rate = _calc_module_line(modules, {"dictionary"})
    quiz_attempts, quiz_comp, quiz_rate = _calc_module_line(modules, {"quiz_test", "quiz"})
    grammar_attempts, grammar_comp, grammar_rate = _calc_module_line(modules, {"grammar"})
    materials_attempts, materials_comp, materials_rate = _calc_module_line(modules, {"materials", "video_materials"})

    if streak.get("current_streak", 0) >= 7:
        motivation = "🚀 Zo'r ketayapsiz! Ritmni saqlab qoling."
    elif streak.get("current_streak", 0) >= 3:
        motivation = "👏 Yaxshi progress! Har kuni oz-ozdan davom eting."
    else:
        motivation = "🌱 Kichik qadamlar katta natija beradi. Bugun ham davom etamiz."

    text = (
        "📊 **Natijalar**\n\n"
        f"🔥 **Joriy streak:** {streak.get('current_streak', 0)} kun\n"
        f"🏆 **Eng yaxshi streak:** {streak.get('best_streak', 0)} kun\n"
        f"✅ **Kunlik dars (7 kun):** {completion_rate_7d}%\n\n"
        "🧠 **O'zlashtirish (SRS)**\n"
        f"▫️ O'rganilmoqda: {total_learning} ta so'z\n"
        f"▫️ Mukammal bilasiz: {total_mastered} ta so'z\n"
        f"🔄 **Takrorlash kerak:** {due_count} ta so'z\n\n"
        "✍️ **Sprechen & Schreiben**\n"
        f"▫️ Yozma matnlar: {submissions.get('writing', 0)} ta\n"
        f"▫️ Gapirish mashqlari: {submissions.get('speaking', 0)} ta\n\n"
        "🧭 **Oxirgi dars rejasi**\n"
        f"▫️ Mavzu: {plan_topic_text}\n"
        f"▫️ Sabab: {reason_text}\n\n"
        f"🧩 **Zaif mavzular ({weak_level})**\n"
        f"{weak_topics_text}\n\n"
        "📚 **Modullar bo'yicha**\n"
        f"▫️ Lug'at: {dict_comp}/{dict_attempts} ({dict_rate}%)\n"
        f"▫️ Quiz: {quiz_comp}/{quiz_attempts} ({quiz_rate}%)\n"
        f"▫️ Grammatika: {grammar_comp}/{grammar_attempts} ({grammar_rate}%)\n\n"
        f"{motivation}"
    )
    
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])
    
    await send_single_ui_message(message, text, reply_markup=builder, parse_mode="Markdown")
