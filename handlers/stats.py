from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import datetime

from services.user_service import UserService
from services.learning_service import LearningService
from utils.ui_utils import _get_progress_bar
from utils.ui_utils import send_single_ui_message
from database.connection import get_connection

router = Router()


def _to_datetime(value) -> datetime.datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _fmt_datetime_short(value) -> str:
    dt = _to_datetime(value)
    if not dt:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M")


def _get_results_snapshot(user_id: int) -> dict:
    snapshot = {
        "daily_total_completed": 0,
        "daily_last_completed_at": None,
        "quiz_attempts": 0,
        "quiz_avg_pct": 0.0,
        "quiz_best_pct": 0.0,
        "quiz_latest_score": None,
        "quiz_latest_total": None,
        "quiz_latest_at": None,
        "writing_completed": 0,
        "writing_last_at": None,
        "speaking_completed": 0,
        "speaking_last_at": None,
    }
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*), MAX(created_at) FROM event_logs WHERE user_id = ? AND event_type = ?",
            (user_id, "daily_lesson_completed"),
        )
        row = cursor.fetchone()
        if row:
            snapshot["daily_total_completed"] = int(row[0] or 0)
            snapshot["daily_last_completed_at"] = row[1]

        cursor.execute(
            "SELECT score, total, created_at FROM quiz_results WHERE user_id = ?",
            (user_id,),
        )
        quiz_rows = cursor.fetchall() or []
        if quiz_rows:
            quiz_attempts = len(quiz_rows)
            snapshot["quiz_attempts"] = quiz_attempts
            pct_values = []
            for item in quiz_rows:
                score = int(item[0] or 0)
                total = int(item[1] or 0)
                if total > 0:
                    pct_values.append((score / total) * 100.0)
            if pct_values:
                snapshot["quiz_avg_pct"] = round(sum(pct_values) / len(pct_values), 1)
                snapshot["quiz_best_pct"] = round(max(pct_values), 1)
            latest = sorted(
                quiz_rows,
                key=lambda r: _to_datetime(r[2]) or datetime.datetime.min,
                reverse=True,
            )[0]
            snapshot["quiz_latest_score"] = int(latest[0] or 0)
            snapshot["quiz_latest_total"] = int(latest[1] or 0)
            snapshot["quiz_latest_at"] = latest[2]

        cursor.execute(
            "SELECT COUNT(*), MAX(created_at) FROM user_submissions "
            "WHERE user_id = ? AND LOWER(module) IN (?, ?)",
            (user_id, "writing", "schreiben"),
        )
        row = cursor.fetchone()
        writing_sub_count = int((row[0] if row else 0) or 0)
        writing_sub_last = row[1] if row else None

        cursor.execute(
            "SELECT COUNT(*), MAX(created_at) FROM event_logs "
            "WHERE user_id = ? AND LOWER(event_type) LIKE ?",
            (user_id, "writing_task_completed_%"),
        )
        row = cursor.fetchone()
        writing_evt_count = int((row[0] if row else 0) or 0)
        writing_evt_last = row[1] if row else None

        snapshot["writing_completed"] = writing_sub_count if writing_sub_count > 0 else writing_evt_count
        snapshot["writing_last_at"] = writing_sub_last or writing_evt_last

        cursor.execute(
            "SELECT COUNT(*), MAX(created_at) FROM user_submissions "
            "WHERE user_id = ? AND LOWER(module) IN (?, ?)",
            (user_id, "speaking", "sprechen"),
        )
        row = cursor.fetchone()
        speaking_sub_count = int((row[0] if row else 0) or 0)
        speaking_sub_last = row[1] if row else None

        cursor.execute(
            "SELECT COUNT(*), MAX(created_at) FROM event_logs "
            "WHERE user_id = ? AND LOWER(event_type) LIKE ?",
            (user_id, "speaking_task_completed_%"),
        )
        row = cursor.fetchone()
        speaking_evt_count = int((row[0] if row else 0) or 0)
        speaking_evt_last = row[1] if row else None

        snapshot["speaking_completed"] = speaking_sub_count if speaking_sub_count > 0 else speaking_evt_count
        snapshot["speaking_last_at"] = speaking_sub_last or speaking_evt_last
    except Exception:
        return snapshot
    finally:
        conn.close()
    return snapshot


@router.message(F.text == "📊 Natijalar")
async def show_stats_dashboard(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    if not message.from_user:
        return
    user_id = message.from_user.id
    profile = UserService.get_profile(user_id) or {}
    level = str(profile.get("current_level") or "A1")
    mastery = LearningService.get_mastery_level(user_id, level)
    progress_bar = _get_progress_bar(mastery["percentage"])
    snapshot = _get_results_snapshot(user_id)

    status_emoji = "🟢" if mastery["percentage"] >= 60 else "🟡" if mastery["percentage"] >= 30 else "🔴"
    quiz_latest_line = "-"
    if snapshot["quiz_latest_total"]:
        quiz_latest_line = (
            f"{snapshot['quiz_latest_score']}/{snapshot['quiz_latest_total']} "
            f"({_fmt_datetime_short(snapshot['quiz_latest_at'])})"
        )

    text = (
        "📊 *Natijalar*\n\n"
        "🎓 *Daraja Progressi*\n"
        f"📚 Joriy daraja: *{level}*\n"
        f"{status_emoji} *Level Progress ({level}):*\n"
        f"{progress_bar} *{mastery['percentage']}%*\n"
        f"_{mastery['mastered']} / {mastery['total']} so'z o'zlashtirilgan_\n\n"
        "🚀 *Kunlik Dars*\n"
        f"• Yakunlangan darslar: *{snapshot['daily_total_completed']}*\n"
        f"• Oxirgi yakun: *{_fmt_datetime_short(snapshot['daily_last_completed_at'])}*\n\n"
        "🧠 *Quiz*\n"
        f"• Urinishlar soni: *{snapshot['quiz_attempts']}*\n"
        f"• O'rtacha natija: *{snapshot['quiz_avg_pct']}%*\n"
        f"• Eng yaxshi natija: *{snapshot['quiz_best_pct']}%*\n"
        f"• Oxirgi urinish: *{quiz_latest_line}*\n\n"
        "✍️ *Schreiben* va 🗣️ *Sprechen*\n"
        f"• Schreiben yakunlari: *{snapshot['writing_completed']}* (oxirgi: {_fmt_datetime_short(snapshot['writing_last_at'])})\n"
        f"• Sprechen yakunlari: *{snapshot['speaking_completed']}* (oxirgi: {_fmt_datetime_short(snapshot['speaking_last_at'])})"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")]
    ])

    await send_single_ui_message(message, text, reply_markup=kb, parse_mode="Markdown")
