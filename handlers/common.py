from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from typing import Awaitable, cast
from database import get_or_create_user_profile, update_user_profile  # From package init
from database.repositories.user_repository import add_user
from database.repositories.progress_repository import record_navigation_event
from database.repositories.session_repository import get_daily_lesson_state
from handlers.onboarding import start_onboarding
from utils.ui_utils import _send_fresh_main_menu, send_single_ui_message
from core.texts import MAIN_MENU_TEXT, INTRO_TEXT
from core.config import settings

router = Router()
UI_TEST_MODE = "🛠️ Bot hozirda test rejimida ishlayapti"


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _profile_is_default(profile: dict) -> bool:
    return (
        str(profile.get("current_level") or "A1") == "A1"
        and str(profile.get("goal") or "general") == "general"
        and _to_int(profile.get("daily_time_minutes"), 15) == 15
        and str(profile.get("notification_time") or "09:00") == "09:00"
        and _to_int(profile.get("xp"), 0) == 0
    )


def _profile_is_fresh(profile: dict) -> bool:
    created_at = str(profile.get("created_at") or "").strip()
    updated_at = str(profile.get("updated_at") or "").strip()
    return bool(created_at and updated_at and created_at == updated_at)


def _needs_onboarding(profile: dict) -> bool:
    if _to_int(profile.get("onboarding_completed"), 0) == 1:
        return False
    # Show onboarding only for truly new untouched profiles.
    return _profile_is_default(profile) and _profile_is_fresh(profile)


async def _safe_delete_message(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await _safe_delete_message(message)
    await state.clear()
    if not message.from_user:
        return

    user_id = message.from_user.id
    add_user(user_id, message.from_user.full_name, message.from_user.username)
    profile = get_or_create_user_profile(user_id) or {}
    record_navigation_event(user_id, "start", entry_type="command")
    if _needs_onboarding(profile):
        await cast(Awaitable[None], start_onboarding(message, state))
        return
    if _to_int(profile.get("onboarding_completed"), 0) != 1:
        # Backfill legacy users so they are not prompted again.
        update_user_profile(user_id, onboarding_completed=1)

    current_level = str(profile.get("current_level") or "A1")
    lesson_state = get_daily_lesson_state(user_id) or {}
    lesson_status = lesson_state.get("status")

    if lesson_status == "in_progress":
        text = (
            "🎉 **Darsga qaytganingiz bilan tabriklaymiz!**\n\n"
            f"📍 Sizning joriy darajangiz: **{current_level}**\n"
            "Yarim qolgan kunlik darsingiz bor. Davom ettiramizmi?"
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Davom ettirish", callback_data="daily_resume"
                    )
                ],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="home")],
            ]
        )
        await cast(
            Awaitable[Message],
            send_single_ui_message(
                message, text, reply_markup=markup, parse_mode="Markdown", user_id=user_id
            ),
        )
        return

    welcome_text = (
        "🎉 **Darsga qaytganingiz bilan tabriklaymiz!**\n\n"
        f"📍 Sizning joriy darajangiz: **{current_level}**\n\n"
        f"{INTRO_TEXT}\n"
        "💡 Tavsiya: bugun `🚀 Kunlik dars`dan boshlang."
    )
    await cast(
        Awaitable[None], _send_fresh_main_menu(message, welcome_text, user_id=user_id)
    )


@router.message(Command("menu"))
@router.message(F.text == "🏠 Bosh menyu")
async def cmd_menu(message: Message):
    await _safe_delete_message(message)
    if not message.from_user:
        return
    record_navigation_event(message.from_user.id, "main_menu", entry_type="text")
    await cast(
        Awaitable[None],
        _send_fresh_main_menu(message, MAIN_MENU_TEXT, user_id=message.from_user.id),
    )


@router.callback_query(F.data == "home")
async def go_to_home(call: CallbackQuery):
    record_navigation_event(call.from_user.id, "main_menu", entry_type="callback")
    await call.answer()
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        return
    try:
        await message.delete()
    except Exception:
        pass
    await cast(
        Awaitable[None],
        _send_fresh_main_menu(message, MAIN_MENU_TEXT, user_id=call.from_user.id),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await _safe_delete_message(message)
    text = (
        "ℹ️ **Yordam**\n\n"
        "Botdan foydalanish uchun pastdagi tugmalardan birini bosing.\n"
        "Muammolar bo'lsa, 'Aloqa' bo'limidan foydalaning."
    )
    from keyboards.builders import get_main_menu

    await cast(
        Awaitable[Message],
        send_single_ui_message(
            message, text, reply_markup=get_main_menu(), parse_mode="Markdown"
        ),
    )


@router.message(Command("about"))
async def cmd_about(message: Message):
    await _safe_delete_message(message)
    text = (
        "🏢 **Germanic Bot**\n\n"
        "Nemis tilini o'rganuvchilar uchun maxsus ishlab chiqilgan.\n\n"
        f"🔖 {UI_TEST_MODE}"
    )
    from keyboards.builders import get_main_menu

    await cast(
        Awaitable[Message],
        send_single_ui_message(
            message, text, reply_markup=get_main_menu(), parse_mode="Markdown"
        ),
    )


@router.message(Command("contact"))
@router.message(F.text == "☎️ Aloqa")
async def cmd_contact(message: Message):
    await _safe_delete_message(message)
    admin_id = settings.admin_id
    admin_link = f"tg://user?id={admin_id}" if admin_id else ""
    admin_text = (
        f"👤 **Admin:** [Yozish]({admin_link})"
        if admin_link
        else "👤 Admin ID sozlanmagan."
    )
    text = (
        "📞 **Biz bilan bog'lanish**\n\n"
        "Savollaringiz bo'lsa, adminga yozishingiz mumkin:\n"
        f"{admin_text}"
    )
    await cast(
        Awaitable[Message], send_single_ui_message(message, text, parse_mode="Markdown")
    )
