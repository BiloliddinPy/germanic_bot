from aiogram import Router
from aiogram.types import Message, CallbackQuery

from handlers.common import get_main_menu, send_single_ui_message, _send_fresh_main_menu, MAIN_MENU_TEXT

router = Router()


@router.message()
async def unknown_text_fallback(message: Message):
    # Keep chat clean and guide user back to supported flows.
    try:
        await message.delete()
    except Exception:
        pass

    await send_single_ui_message(
        message,
        "Bu buyruq yoki xabar hozircha qo'llab-quvvatlanmaydi. Iltimos, menyudan bo'lim tanlang.",
        reply_markup=get_main_menu()
    )


@router.callback_query()
async def unknown_callback_fallback(call: CallbackQuery):
    # Prevent stale inline buttons from confusing users.
    await call.answer("Bu tugma eskirgan yoki noto'g'ri.")
    if not call.message:
        return
    try:
        await call.message.delete()
    except Exception:
        pass
    await _send_fresh_main_menu(call.message, MAIN_MENU_TEXT, user_id=call.from_user.id)
