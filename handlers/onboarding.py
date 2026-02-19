from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import update_user_profile, get_user_profile, log_event
from utils.ui_utils import _send_fresh_main_menu, MAIN_MENU_TEXT, _md_escape

router = Router()

class OnboardingState(StatesGroup):
    waiting_for_level = State()
    waiting_for_goal = State()
    waiting_for_target = State()

def get_onboarding_levels_keyboard():
    levels = ["A1", "A2", "B1", "B2", "C1"]
    keyboard = []
    row = []
    for lvl in levels:
        row.append(InlineKeyboardButton(text=lvl, callback_data=f"ob_level_{lvl}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_onboarding_goals_keyboard():
    goals = [
        ("💼 Ish va karyera", "work"),
        ("✈️ Sayohat va hayot", "travel"),
        ("🎓 Imtihon (Goethe/TestDaF)", "exam"),
        ("🌟 Shunchaki qiziqish", "fun")
    ]
    keyboard = [[InlineKeyboardButton(text=t, callback_data=f"ob_goal_{s}")] for t, s in goals]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_onboarding_target_keyboard():
    targets = [
        ("☕️ 5 daqiqa (Yengil)", "5"),
        ("⚡️ 15 daqiqa (O'rtacha)", "15"),
        ("🔥 30 daqiqa (Intensiv)", "30")
    ]
    keyboard = [[InlineKeyboardButton(text=t, callback_data=f"ob_target_{s}")] for t, s in targets]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def start_onboarding(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "🌟 **Germanic-ga xush kelibsiz!**\n\n"
        "Botni sizning ehtiyojlaringizga moslashtirishimiz uchun 3 ta qisqa savolga javob bering.\n\n"
        "1️⃣ **Hozirgi nemis tili darajangiz qanday?**"
    )
    await message.answer(text, reply_markup=get_onboarding_levels_keyboard(), parse_mode="Markdown")
    await state.set_state(OnboardingState.waiting_for_level)

@router.callback_query(F.data.startswith("ob_level_"), OnboardingState.waiting_for_level)
async def ob_level_callback(call: CallbackQuery, state: FSMContext):
    level = call.data.replace("ob_level_", "")
    await state.update_data(current_level=level)
    
    text = (
        f"✅ Daraja: **{level}**\n\n"
        "2️⃣ **Sizning asosiy maqsadingiz nima?**"
    )
    await call.message.edit_text(text, reply_markup=get_onboarding_goals_keyboard(), parse_mode="Markdown")
    await state.set_state(OnboardingState.waiting_for_goal)

@router.callback_query(F.data.startswith("ob_goal_"), OnboardingState.waiting_for_goal)
async def ob_goal_callback(call: CallbackQuery, state: FSMContext):
    goal_slug = call.data.replace("ob_goal_", "")
    goal_map = {
        "work": "Ish va karyera",
        "travel": "Sayohat va hayot",
        "exam": "Imtihon tayyorgarligi",
        "fun": "Shunchaki qiziqish"
    }
    await state.update_data(goal=goal_slug)
    
    text = (
        f"✅ Maqsad: **{goal_map.get(goal_slug)}**\n\n"
        "3️⃣ **Kuniga necha daqiqa shug'ullanmoqchisiz?**"
    )
    await call.message.edit_text(text, reply_markup=get_onboarding_target_keyboard(), parse_mode="Markdown")
    await state.set_state(OnboardingState.waiting_for_target)

@router.callback_query(F.data.startswith("ob_target_"), OnboardingState.waiting_for_target)
async def ob_target_callback(call: CallbackQuery, state: FSMContext):
    target = int(call.data.replace("ob_target_", ""))
    data = await state.get_data()
    
    update_user_profile(
        call.from_user.id,
        current_level=data['current_level'],
        goal=data['goal'],
        daily_target=target,
        onboarding_completed=1
    )
    
    log_event(call.from_user.id, "onboarding_completed", metadata=data)
    
    await call.message.delete()
    welcome_text = (
        "🎉 **Ajoyib! Profilingiz muvaffaqiyatli sozlandi.**\n\n"
        "Endi siz uchun shaxsiy dars rejasi va materiallar tayyor.\n"
        "Boshlash uchun menyudan kerakli bo'limni tanlang."
    )
    await _send_fresh_main_menu(call.message, welcome_text, user_id=call.from_user.id)
    await state.clear()
