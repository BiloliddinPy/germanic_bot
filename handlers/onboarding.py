from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.user_service import UserService
from services.stats_service import StatsService
from core.texts import ONBOARDING_WELCOME
from utils.ui_utils import send_single_ui_message, _send_fresh_main_menu
from keyboards.builders import get_levels_keyboard, get_main_menu_keyboard

router = Router()

class OnboardingState(StatesGroup):
    waiting_for_level = State()
    waiting_for_goal = State()
    waiting_for_daily_target = State()

async def start_onboarding(message: Message, state: FSMContext):
    await state.clear()
    StatsService.log_activity(message.from_user.id, "onboarding_started")
    
    await send_single_ui_message(
        message,
        ONBOARDING_WELCOME,
        reply_markup=get_levels_keyboard("onboarding")
    )
    await state.set_state(OnboardingState.waiting_for_level)

@router.callback_query(OnboardingState.waiting_for_level, F.data.startswith("onboarding_"))
async def onboarding_level_handler(call: CallbackQuery, state: FSMContext):
    level = call.data.split("_")[1]
    UserService.update_level(call.from_user.id, level)
    
    from core.texts import GOAL_LABELS
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    for slug, label in GOAL_LABELS.items():
        builder.row(InlineKeyboardButton(text=label, callback_data=f"goal_{slug}"))
    
    await call.message.edit_text(
        "Maqsadingizni tanlang:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingState.waiting_for_goal)

@router.callback_query(OnboardingState.waiting_for_goal, F.data.startswith("goal_"))
async def onboarding_goal_handler(call: CallbackQuery, state: FSMContext):
    goal = call.data.split("_")[1]
    UserService.set_goal(call.from_user.id, goal)
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="15 daqiqa", callback_data="target_15"))
    builder.row(InlineKeyboardButton(text="30 daqiqa", callback_data="target_30"))
    builder.row(InlineKeyboardButton(text="60 daqiqa", callback_data="target_60"))
    
    await call.message.edit_text(
        "Kunlik qancha vaqt ajratmoqchisiz?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingState.waiting_for_daily_target)

@router.callback_query(OnboardingState.waiting_for_daily_target, F.data.startswith("target_"))
async def onboarding_target_handler(call: CallbackQuery, state: FSMContext):
    minutes = int(call.data.split("_")[1])
    UserService.update_daily_target(call.from_user.id, minutes)
    UserService.complete_onboarding(call.from_user.id)
    
    await call.answer("Muvaffaqiyatli yakunlandi! 🎉")
    await state.clear()
    
    StatsService.log_activity(call.from_user.id, "onboarding_completed")
    
    await _send_fresh_main_menu(call.message, call.from_user.id)
