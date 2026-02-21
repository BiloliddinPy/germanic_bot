import os
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from core.config import settings
from database.repositories.admin_repository import (
    get_admin_stats_snapshot,
    get_last_event_timestamp,
    get_recent_ops_errors,
    get_users_count,
)
from utils.ui_utils import send_single_ui_message
from utils.backup_manager import (
    run_backup_async,
    list_backups,
    get_latest_backup,
    format_bytes
)
from utils.runtime_state import get_uptime_seconds, get_last_update_handled_iso
from utils.error_notifier import (
    get_ops_alerts_status,
    toggle_ops_alerts_enabled
)

router = Router()

def _is_admin(user_id: int) -> bool:
    admin_id = settings.admin_id
    if not admin_id:
        return False
    return str(user_id) == str(admin_id)

def _is_admin_message(message: Message) -> bool:
    return bool(message.from_user and _is_admin(message.from_user.id))


async def _ensure_admin(message: Message) -> bool:
    if _is_admin_message(message):
        return True
    await send_single_ui_message(
        message,
        "⛔ Bu buyruq faqat admin uchun.",
    )
    return False

def _format_dt_local(epoch_ts: float | None) -> str:
    if not epoch_ts:
        return "-"
    try:
        dt = datetime.datetime.fromtimestamp(epoch_ts)
        return dt.isoformat(timespec="seconds")
    except Exception:
        return "-"

@router.message(Command("health"))
async def health_cmd(message: Message):
    if not await _ensure_admin(message):
        return

    me = await message.bot.get_me()
    uptime_seconds = get_uptime_seconds()
    last_update = get_last_update_handled_iso() or get_last_event_timestamp() or "-"

    from utils.scheduler import get_scheduler_health
    scheduler = get_scheduler_health()
    scheduler_started = "yes" if scheduler.get("started") else "no"
    scheduler_next_run = scheduler.get("next_run_time") or "-"

    db_path = settings.db_path
    db_abs_path = os.path.abspath(db_path)
    db_size = "n/a"
    db_mtime = "n/a"
    try:
        if os.path.exists(db_abs_path):
            db_size = str(os.path.getsize(db_abs_path))
            db_mtime = _format_dt_local(os.path.getmtime(db_abs_path))
    except Exception:
        pass

    text = (
        "🩺 Health (Admin)\n\n"
        f"• Bot: @{me.username or '-'} (id: {me.id})\n"
        f"• Uptime: {uptime_seconds} sec\n"
        f"• Last update handled: {last_update}\n\n"
        "Scheduler\n"
        f"• Started: {scheduler_started}\n"
        f"• Next run: {scheduler_next_run}\n\n"
        "Database (SQLite)\n"
        f"• Path: {db_path}\n"
        f"• Size: {db_size} bytes\n"
        f"• Last write: {db_mtime}"
    )
    await send_single_ui_message(message, text)

@router.message(Command("admin_stats"))
async def admin_stats_cmd(message: Message):
    if not await _ensure_admin(message):
        return

    stats = get_admin_stats_snapshot()
    weak_topics = stats.get("top_weak_topics") or []
    if weak_topics:
        weak_lines = "\n".join(
            [f"{i}. `{item.get('topic_id')}` — {item.get('score', 0)}" for i, item in enumerate(weak_topics, 1)]
        )
    else:
        weak_lines = "-"

    text = (
        "📈 Admin Stats\n\n"
        f"• Total users: {stats.get('total_users', 0)}\n"
        f"• New users today: {stats.get('new_users_today', 0)}\n"
        f"• Active users today: {stats.get('active_users_today', 0)}\n"
        f"• Daily lesson completions today: {stats.get('daily_completions_today', 0)}\n"
        f"• Daily lesson completions (last 7 days): {stats.get('daily_completions_last_7_days', 0)}\n"
        f"• Total mistakes logged: {stats.get('total_mistakes_logged', 0)}\n\n"
        f"Top 5 weak topics\n{weak_lines}"
    )
    await send_single_ui_message(message, text)

@router.message(Command(commands=["users_count", "user_count", "users", "ucount"]))
async def users_count_cmd(message: Message):
    if not await _ensure_admin(message):
        return
    total_users = get_users_count()
    text = (
        "👥 Foydalanuvchilar soni\n\n"
        f"• Jami users: {total_users}"
    )
    await send_single_ui_message(message, text)

@router.message(Command("ops_last_errors"))
async def ops_last_errors_cmd(message: Message):
    if not await _ensure_admin(message):
        return

    rows = get_recent_ops_errors(limit=10)
    if not rows:
        await send_single_ui_message(message, "🧯 Ops Errors\n\nHozircha xatoliklar yo'q.")
        return

    lines = ["🧯 Ops Errors (last 10)\n"]
    for row in rows:
        lines.append(
            f"#{row.get('id')} | {row.get('created_at')} | {row.get('event_type')} | "
            f"user={row.get('user_id') or '-'}\n"
            f"{row.get('metadata') or '-'}"
        )
    await send_single_ui_message(message, "\n\n".join(lines))

def _ops_alerts_keyboard(enabled: bool):
    button_text = "🔕 O'chirish" if enabled else "🔔 Yoqish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, callback_data="ops_alerts_toggle")]
    ])

def _ops_alerts_text():
    status = get_ops_alerts_status()
    on_off = "ON" if status.get("enabled") else "OFF"
    return (
        "⚙️ Ops Alerts\n\n"
        f"• Status: {on_off}\n"
        f"• Last alert: {status.get('last_alert_ts_utc')}\n\n"
        f"• Sent (last 1 min): {status.get('sent_last_minute', 0)}"
    )

@router.message(Command("ops_alerts"))
async def ops_alerts_cmd(message: Message):
    if not await _ensure_admin(message):
        return
    text = _ops_alerts_text()
    status = get_ops_alerts_status()
    await send_single_ui_message(
        message,
        text,
        reply_markup=_ops_alerts_keyboard(status.get("enabled", True)),
    )

@router.callback_query(F.data == "ops_alerts_toggle")
async def ops_alerts_toggle_cb(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("Admin only.", show_alert=True)
        return
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return
    enabled = toggle_ops_alerts_enabled()
    await call.answer(f"Ops alerts {'ON' if enabled else 'OFF'}", show_alert=False)
    await message.edit_text(_ops_alerts_text(), reply_markup=_ops_alerts_keyboard(enabled))

@router.message(Command("ops_throw_test"))
async def ops_throw_test_cmd(message: Message):
    if not await _ensure_admin(message):
        return
    raise RuntimeError("ops_throw_test triggered by admin")

@router.message(Command("backup_now"))
async def backup_now_cmd(message: Message):
    if not await _ensure_admin(message):
        return
    result = await run_backup_async(bot=message.bot, trigger="admin_command")
    if not result.get("success"):
        text = f"💾 Backup Now\n\nStatus: ❌ failed\nError: {result.get('error', 'unknown')}"
        await send_single_ui_message(message, text)
        return
    text = f"💾 Backup Now\n\nStatus: ✅ success\nFile: {result.get('primary_path')}\nSize: {format_bytes(result.get('primary_size'))}"
    await send_single_ui_message(message, text)

@router.message(Command("backup_list"))
async def backup_list_cmd(message: Message):
    if not await _ensure_admin(message):
        return
    backups = list_backups(limit=10)
    if not backups:
        await send_single_ui_message(message, "💾 Backups\n\nHozircha backup fayllar topilmadi.")
        return
    lines = ["💾 Backups (last 10)\n"]
    for i, item in enumerate(backups, 1):
        lines.append(f"{i}. {item.get('name')} | {format_bytes(item.get('size'))}")
    await send_single_ui_message(message, "\n".join(lines))

@router.message(Command("backup_send_latest"))
async def backup_send_latest_cmd(message: Message):
    admin_id = settings.admin_id
    if not await _ensure_admin(message):
        return
    latest = get_latest_backup()
    if not latest:
        await send_single_ui_message(message, "💾 Latest backup topilmadi.")
        return
    path = latest.get("path")
    try:
        await message.bot.send_document(
            chat_id=int(admin_id),
            document=FSInputFile(path),
            caption=f"💾 Latest backup: {path}"
        )
        await send_single_ui_message(message, "✅ Latest backup yuborildi.")
    except Exception as e:
        await send_single_ui_message(message, f"❌ Backup yuborilmadi: {str(e)}")


@router.message(Command("admin"))
async def admin_help_cmd(message: Message):
    if not await _ensure_admin(message):
        return
    total_users = get_users_count()
    text = (
        "🛠️ Admin Buyruqlar\n\n"
        f"• /users_count (/user_count) - userlar soni ({total_users})\n"
        "• /admin_stats - umumiy admin statistika\n"
        "• /health - bot va DB holati\n"
        "• /backup_now - darhol backup\n"
        "• /backup_list - backup ro'yxati\n"
        "• /backup_send_latest - oxirgi backupni yuborish\n"
        "• /ops_alerts - ops alertlar holati\n"
        "• /ops_last_errors - oxirgi xatoliklar"
    )
    await send_single_ui_message(message, text)
