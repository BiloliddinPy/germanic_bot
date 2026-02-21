from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Awaitable, cast

from services.user_service import UserService
from services.stats_service import StatsService
from core.texts import ONBOARDING_WELCOME, INTRO_TEXT
from utils.ui_utils import send_single_ui_message, _send_fresh_main_menu
from keyboards.builders import get_levels_keyboard
from database import update_user_profile

router = Router()

class OnboardingState(StatesGroup):
    waiting_for_level = State()
    waiting_for_goal = State()
    waiting_for_daily_target = State()
    waiting_for_time = State()


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


def _should_skip_onboarding(profile: dict) -> bool:
    if _to_int(profile.get("onboarding_completed"), 0) == 1:
        return True
    # If profile has any sign of prior setup/activity, do not show onboarding again.
    return not (_profile_is_default(profile) and _profile_is_fresh(profile))


async def start_onboarding(message: Message, state: FSMContext):
    if not message.from_user:
        return
    user_id = message.from_user.id

    # Defensive guard: even if onboarding is called from a wrong path,
    # do not show it again for already-configured users.
    profile = UserService.get_profile(user_id) or {}
    if _should_skip_onboarding(profile):
        if _to_int(profile.get("onboarding_completed"), 0) != 1:
            update_user_profile(user_id, onboarding_completed=1)
        await state.clear()
        await _send_fresh_main_menu(message, INTRO_TEXT, user_id=user_id)
        return

    await state.clear()
    StatsService.log_activity(user_id, "onboarding_started")
    
    intro = (
        "🧭 **Boshlang'ich sozlash (1/4)**\n\n"
        f"{ONBOARDING_WELCOME}\n\n"
        "Avval darajangizni tanlang."
    )
    await cast(
        Awaitable[Message],
        send_single_ui_message(
            message,
            intro,
            reply_markup=get_levels_keyboard("onboarding"),
            parse_mode="Markdown",
        ),
    )
    await state.set_state(OnboardingState.waiting_for_level)


async def _guard_onboarding_callback(call: CallbackQuery, state: FSMContext) -> bool:
    profile = UserService.get_profile(call.from_user.id) or {}
    if _should_skip_onboarding(profile):
        if _to_int(profile.get("onboarding_completed"), 0) != 1:
            update_user_profile(call.from_user.id, onboarding_completed=1)
        await state.clear()
        message = call.message if isinstance(call.message, Message) else None
        if message:
            await _send_fresh_main_menu(message, INTRO_TEXT, user_id=call.from_user.id)
        return False
    return True


@router.callback_query(F.data.startswith("onboarding_"))
async def onboarding_level_handler(call: CallbackQuery, state: FSMContext):
    if not await _guard_onboarding_callback(call, state):
        return
    data = call.data or ""
    parts = data.split("_")
    if len(parts) < 2:
        await call.answer("Noto'g'ri tanlov.", show_alert=True)
        return
    level = parts[1]
    UserService.update_level(call.from_user.id, level)
    
    from core.texts import GOAL_LABELS
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    for slug, label in GOAL_LABELS.items():
        builder.row(InlineKeyboardButton(text=label, callback_data=f"goal_{slug}"))
    
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return

    await message.edit_text(
        "🧭 **Sozlash (2/4)**\n\nMaqsadingizni tanlang:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingState.waiting_for_goal)


@router.callback_query(F.data.startswith("goal_"))
async def onboarding_goal_handler(call: CallbackQuery, state: FSMContext):
    if not await _guard_onboarding_callback(call, state):
        return
    data = call.data or ""
    parts = data.split("_")
    if len(parts) < 2:
        await call.answer("Noto'g'ri tanlov.", show_alert=True)
        return
    goal = parts[1]
    UserService.set_goal(call.from_user.id, goal)
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="15 daqiqa", callback_data="target_15"))
    builder.row(InlineKeyboardButton(text="30 daqiqa", callback_data="target_30"))
    builder.row(InlineKeyboardButton(text="60 daqiqa", callback_data="target_60"))
    
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return

    await message.edit_text(
        "🧭 **Sozlash (3/4)**\n\nKunlik qancha vaqt ajratmoqchisiz?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingState.waiting_for_daily_target)


@router.callback_query(F.data.startswith("target_"))
async def onboarding_target_handler(call: CallbackQuery, state: FSMContext):
    if not await _guard_onboarding_callback(call, state):
        return
    data = call.data or ""
    parts = data.split("_")
    if len(parts) < 2:
        await call.answer("Noto'g'ri tanlov.", show_alert=True)
        return
    minutes = int(parts[1])
    UserService.update_daily_target(call.from_user.id, minutes)
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Ertalab 08:00", callback_data="time_08:00"))
    builder.row(InlineKeyboardButton(text="Ertalab 10:00", callback_data="time_10:00"))
    builder.row(InlineKeyboardButton(text="Tushlik 12:00", callback_data="time_12:00"))
    builder.row(InlineKeyboardButton(text="Kechqurun 18:00", callback_data="time_18:00"))
    builder.row(InlineKeyboardButton(text="Kechqurun 20:00", callback_data="time_20:00"))
    
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        await call.answer("Xabar topilmadi.", show_alert=True)
        return

    await message.edit_text(
        "🧭 **Sozlash (4/4)**\n\nKunlik motivatsion eslatma va yangi lug'at soat nechada kelsin?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingState.waiting_for_time)


@router.callback_query(F.data.startswith("time_"))
async def onboarding_time_handler(call: CallbackQuery, state: FSMContext):
    if not await _guard_onboarding_callback(call, state):
        return
    data = call.data or ""
    parts = data.split("_")
    if len(parts) < 2:
        await call.answer("Noto'g'ri tanlov.", show_alert=True)
        return
    time_str = parts[1]
    UserService.update_notification_time(call.from_user.id, time_str)
    
    UserService.complete_onboarding(call.from_user.id)
    
    await call.answer("Sozlamalar saqlandi! 🎉")
    await state.clear()
    
    StatsService.log_activity(call.from_user.id, "onboarding_completed")
    
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        return
    await _send_fresh_main_menu(message, INTRO_TEXT, user_id=call.from_user.id)
