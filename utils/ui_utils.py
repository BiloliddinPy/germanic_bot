from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import re

# We import from handlers.common below to avoid circularity at top level
# But better to move the constants here too

MAIN_MENU_STATE_KEY = "main_menu_message_id"
ACTIVE_UI_STATE_KEY = "active_ui_message_id"
MAIN_MENU_TEXT = "Asosiy menyu:\nKerakli bo'limni tanlang."

_MD_ESC_RE = re.compile(r"([\\_*`\[\]()~>#+\-=|{}.!])")

def _md_escape(value):
    if value is None:
        return ""
    return _MD_ESC_RE.sub(r"\\\1", str(value))

async def _send_fresh_main_menu(message: Message, text: str, user_id: int | None = None):
    from database import get_ui_state, set_ui_state
    # We delay the import of get_main_menu to avoid circularity if possible
    # Or just define get_main_menu here if it's purely UI
    
    resolved_user_id = user_id or message.chat.id
    existing_main_id = get_ui_state(resolved_user_id, MAIN_MENU_STATE_KEY)
    
    # We need get_main_menu, but it's in handlers.common usually. 
    # Let's move get_main_menu here or to keyboards/builders.py
    from keyboards.builders import get_main_menu_keyboard
    
    if existing_main_id:
        try:
            await message.bot.edit_message_text(
                chat_id=resolved_user_id,
                message_id=int(existing_main_id),
                text=text,
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown"
            )
            set_ui_state(resolved_user_id, ACTIVE_UI_STATE_KEY, existing_main_id)
            return
        except Exception:
            pass
            
    # If edit fails or no existing main menu, send new one
    sent = await message.bot.send_message(
        chat_id=resolved_user_id,
        text=text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
    set_ui_state(resolved_user_id, MAIN_MENU_STATE_KEY, sent.message_id)
    set_ui_state(resolved_user_id, ACTIVE_UI_STATE_KEY, sent.message_id)

async def send_single_ui_message(
    message: Message,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
    user_id: int | None = None
):
    from database import get_ui_state, set_ui_state
    resolved_user_id = user_id or message.chat.id
    prev_active_id = get_ui_state(resolved_user_id, ACTIVE_UI_STATE_KEY)
    main_menu_id = get_ui_state(resolved_user_id, MAIN_MENU_STATE_KEY)
    if prev_active_id and str(prev_active_id) != str(main_menu_id):
        try:
            await message.bot.delete_message(chat_id=resolved_user_id, message_id=int(prev_active_id))
        except Exception:
            pass
    sent = await message.bot.send_message(
        chat_id=resolved_user_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )
    set_ui_state(resolved_user_id, ACTIVE_UI_STATE_KEY, sent.message_id)
    return sent
