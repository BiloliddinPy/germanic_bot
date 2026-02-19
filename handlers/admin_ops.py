import os
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from config import ADMIN_ID
from database import DB_NAME, get_admin_stats_snapshot, get_last_event_timestamp, get_recent_ops_errors
from utils.ui_utils import send_single_ui_message
from utils.backup_manager import (
    run_backup_async,
    list_backups,
    get_latest_backup,
    format_bytes,
    BACKUP_SEND_MAX_BYTES
)
from utils.runtime_state import get_uptime_seconds, get_last_update_handled_iso
from utils.scheduler import get_scheduler_health
from utils.error_notifier import (
    get_ops_alerts_status,
    set_ops_alerts_enabled,
    toggle_ops_alerts_enabled
)

router = Router()


def _is_admin(user_id: int) -> bool:
    if not ADMIN_ID:
        return False
    return str(user_id) == str(ADMIN_ID)


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
    if not _is_admin(message.from_user.id):
        return

    me = await message.bot.get_me()
    uptime_seconds = get_uptime_seconds()
    last_update = get_last_update_handled_iso() or get_last_event_timestamp() or "-"

    scheduler = get_scheduler_health()
    scheduler_started = "yes" if scheduler.get("started") else "no"
    scheduler_next_run = scheduler.get("next_run_time") or "-"

    db_abs_path = os.path.abspath(DB_NAME)
    db_size = "n/a"
    db_mtime = "n/a"
    db_path = db_abs_path
    try:
        if os.path.exists(db_abs_path):
            db_size = str(os.path.getsize(db_abs_path))
            db_mtime = _format_dt_local(os.path.getmtime(db_abs_path))
        else:
            db_path = "n/a"
    except Exception:
        db_path = "n/a"
        db_size = "n/a"
        db_mtime = "n/a"

    text = (
        "🩺 **Health (Admin)**\n\n"
        f"• Bot: @{me.username or '-'} (id: `{me.id}`)\n"
        f"• Uptime: `{uptime_seconds}` sec\n"
        f"• Last update handled: `{last_update}`\n\n"
        "**Scheduler**\n"
        f"• Started: `{scheduler_started}`\n"
        f"• Next run (`send_daily_word_to_all`): `{scheduler_next_run}`\n\n"
        "**Database (SQLite)**\n"
        f"• Path: `{db_path}`\n"
        f"• Size: `{db_size}` bytes\n"
        f"• Last write: `{db_mtime}`"
    )
    await send_single_ui_message(message, text, parse_mode="Markdown")


@router.message(Command("admin_stats"))
async def admin_stats_cmd(message: Message):
    if not _is_admin(message.from_user.id):
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
        "📈 **Admin Stats**\n\n"
        f"• Total users: `{stats.get('total_users', 0)}`\n"
        f"• Active users today: `{stats.get('active_users_today', 0)}`\n"
        f"• Daily lesson completions today: `{stats.get('daily_completions_today', 0)}`\n"
        f"• Daily lesson completions (last 7 days): `{stats.get('daily_completions_last_7_days', 0)}`\n"
        f"• Total mistakes logged: `{stats.get('total_mistakes_logged', 0)}`\n\n"
        f"**Top 5 weak topics**\n{weak_lines}"
    )
    await send_single_ui_message(message, text, parse_mode="Markdown")


@router.message(Command("ops_last_errors"))
async def ops_last_errors_cmd(message: Message):
    if not _is_admin(message.from_user.id):
        return

    rows = get_recent_ops_errors(limit=10)
    if not rows:
        await send_single_ui_message(message, "🧯 **Ops Errors**\n\nHozircha xatoliklar yo'q.", parse_mode="Markdown")
        return

    lines = ["🧯 **Ops Errors (last 10)**\n"]
    for row in rows:
        lines.append(
            f"#{row.get('id')} | {row.get('ts_utc')} | {row.get('error_type')} | "
            f"user={row.get('user_id') or '-'} | upd={row.get('update_id') or '-'}\n"
            f"`{row.get('message_short') or '-'}`"
        )
    await send_single_ui_message(message, "\n\n".join(lines), parse_mode="Markdown")


def _ops_alerts_keyboard(enabled: bool):
    button_text = "🔕 O'chirish" if enabled else "🔔 Yoqish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, callback_data="ops_alerts_toggle")]
    ])


def _ops_alerts_text():
    status = get_ops_alerts_status()
    on_off = "ON" if status.get("enabled") else "OFF"
    return (
        "⚙️ **Ops Alerts**\n\n"
        f"• Status: **{on_off}**\n"
        f"• Last alert: `{status.get('last_alert_ts_utc')}`\n"
        f"• Last rate notice: `{status.get('last_rate_notice_ts_utc')}`\n\n"
        f"• Sent (last 1 min): `{status.get('sent_last_minute', 0)}`\n"
        f"• Rate-limited dropped (last 1 min): `{status.get('rate_limited_last_minute', 0)}`\n"
        f"• Dedup suppressed (last 1 min): `{status.get('dedup_suppressed_last_minute', 0)}`"
    )


@router.message(Command("ops_alerts"))
async def ops_alerts_cmd(message: Message):
    if not _is_admin(message.from_user.id):
        return
    arg = ""
    try:
        parts = (message.text or "").split(maxsplit=1)
        arg = parts[1].strip().lower() if len(parts) > 1 else ""
    except Exception:
        arg = ""
    if arg in ("on", "off"):
        set_ops_alerts_enabled(arg == "on")
    text = _ops_alerts_text()
    status = get_ops_alerts_status()
    await send_single_ui_message(
        message,
        text,
        reply_markup=_ops_alerts_keyboard(status.get("enabled", True)),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "ops_alerts_toggle")
async def ops_alerts_toggle_cb(call: CallbackQuery):
    if not _is_admin(call.from_user.id):
        await call.answer("Admin only.", show_alert=True)
        return
    enabled = toggle_ops_alerts_enabled()
    await call.answer(f"Ops alerts {'ON' if enabled else 'OFF'}", show_alert=False)
    await call.message.edit_text(
        _ops_alerts_text(),
        reply_markup=_ops_alerts_keyboard(enabled),
        parse_mode="Markdown"
    )


@router.message(Command("ops_throw_test"))
async def ops_throw_test_cmd(message: Message):
    if not _is_admin(message.from_user.id):
        return
    suffix = "default"
    try:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            suffix = parts[1].strip()
    except Exception:
        pass
    raise RuntimeError(f"ops_throw_test:{suffix}")


@router.message(Command("backup_now"))
async def backup_now_cmd(message: Message):
    if not _is_admin(message.from_user.id):
        return
    result = await run_backup_async(bot=message.bot, trigger="admin_command")
    if not result.get("success"):
        text = (
            "💾 **Backup Now**\n\n"
            "Status: ❌ failed\n"
            f"Error: `{result.get('error', 'unknown')}`\n"
            f"Path: `{result.get('backup_dir', 'n/a')}`"
        )
        await send_single_ui_message(message, text, parse_mode="Markdown")
        return
    removed_count = len(result.get("retention_removed", []))
    text = (
        "💾 **Backup Now**\n\n"
        "Status: ✅ success\n"
        f"Method: `{result.get('method')}`\n"
        f"File: `{result.get('primary_path')}`\n"
        f"Size: `{format_bytes(result.get('primary_size'))}`\n"
        f"Created: `{result.get('created_utc')}`\n"
        f"Retention removed: `{removed_count}`"
    )
    await send_single_ui_message(message, text, parse_mode="Markdown")


@router.message(Command("backup_list"))
async def backup_list_cmd(message: Message):
    if not _is_admin(message.from_user.id):
        return
    backups = list_backups(limit=10)
    if not backups:
        await send_single_ui_message(message, "💾 **Backups**\n\nHozircha backup fayllar topilmadi.", parse_mode="Markdown")
        return
    lines = ["💾 **Backups (last 10)**\n"]
    for i, item in enumerate(backups, 1):
        lines.append(
            f"{i}. `{item.get('name')}`\n"
            f"   • size: `{format_bytes(item.get('size'))}`\n"
            f"   • mtime_utc: `{item.get('mtime_iso')}`"
        )
    await send_single_ui_message(message, "\n".join(lines), parse_mode="Markdown")


@router.message(Command("backup_send_latest"))
async def backup_send_latest_cmd(message: Message):
    if not _is_admin(message.from_user.id):
        return
    latest = get_latest_backup()
    if not latest:
        await send_single_ui_message(message, "💾 Latest backup topilmadi.", parse_mode="Markdown")
        return
    path = latest.get("path")
    size = int(latest.get("size") or 0)
    if size > BACKUP_SEND_MAX_BYTES:
        await send_single_ui_message(
            message,
            (
                "💾 Latest backup juda katta.\n"
                f"Size: `{format_bytes(size)}` (limit: `{format_bytes(BACKUP_SEND_MAX_BYTES)}`)\n"
                "Yuklab yuborish bekor qilindi."
            ),
            parse_mode="Markdown"
        )
        return
    try:
        await message.bot.send_document(
            chat_id=int(ADMIN_ID),
            document=FSInputFile(path),
            caption=f"💾 Latest backup\\n`{path}`\\nSize: `{format_bytes(size)}`",
            parse_mode="Markdown"
        )
        await send_single_ui_message(message, "✅ Latest backup ADMIN_ID ga yuborildi.", parse_mode="Markdown")
    except Exception as e:
        await send_single_ui_message(
            message,
            f"❌ Backup yuborilmadi: `{str(e)[:180]}`",
            parse_mode="Markdown"
        )
