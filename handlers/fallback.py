from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from utils.ui_utils import send_single_ui_message, _send_fresh_main_menu
from core.texts import MAIN_MENU_TEXT
from keyboards.builders import get_main_menu_keyboard
from database import get_or_create_user_profile
from handlers.onboarding import start_onboarding

router = Router()


@router.message()
async def unknown_text_fallback(message: Message, state: FSMContext):
    # Keep chat clean and guide user back to supported flows.
    try:
        await message.delete()
    except Exception:
        pass

    if message.from_user:
        profile = get_or_create_user_profile(message.from_user.id)
        if not profile or not profile.get("onboarding_completed"):
            await start_onboarding(message, state)
            return

    await send_single_ui_message(
        message,
        "Bu buyruq yoki xabar hozircha qo'llab-quvvatlanmaydi. Iltimos, menyudan bo'lim tanlang.",
        reply_markup=get_main_menu_keyboard()
    )


@router.callback_query()
async def unknown_callback_fallback(call: CallbackQuery, state: FSMContext):
    # Prevent stale inline buttons from confusing users.
    await call.answer("Bu tugma eskirgan. Iltimos, /start bosing.", show_alert=True)
    profile = get_or_create_user_profile(call.from_user.id)
    if not profile or not profile.get("onboarding_completed"):
        message = call.message if isinstance(call.message, Message) else None
        if message:
            await start_onboarding(message, state)
        return
    message = call.message if isinstance(call.message, Message) else None
    if not message:
        return
    try:
        await message.delete()
    except Exception:
        pass
    await _send_fresh_main_menu(message, MAIN_MENU_TEXT, user_id=call.from_user.id)
