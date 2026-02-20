from aiogram.types import Message
import re
import logging
from core.config import settings
from database.repositories.ui_repository import get_ui_state, set_ui_state
from keyboards.builders import get_main_menu_keyboard

_MD_ESC_RE = re.compile(r"([\\_*`\[\]()~>#+\-=|{}.!])")

def _md_escape(value):
    if value is None:
        return ""
    return _MD_ESC_RE.sub(r"\\\1", str(value))

async def _send_fresh_main_menu(message: Message, text: str, user_id: int | None = None):
    resolved_user_id = user_id or message.chat.id
    existing_main_id = get_ui_state(resolved_user_id, settings.main_menu_state_key)
    prev_active_id = get_ui_state(resolved_user_id, settings.active_ui_state_key)
    
    markup = get_main_menu_keyboard()

    if prev_active_id and str(prev_active_id) != str(existing_main_id):
        try:
            await message.bot.delete_message(chat_id=resolved_user_id, message_id=int(prev_active_id))
        except Exception:
            pass
    
    if existing_main_id:
        try:
            await message.bot.edit_message_text(
                chat_id=resolved_user_id,
                message_id=int(existing_main_id),
                text=text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
            set_ui_state(resolved_user_id, settings.active_ui_state_key, existing_main_id)
            return
        except Exception:
            pass
            
    sent = await message.bot.send_message(
        chat_id=resolved_user_id,
        text=text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    set_ui_state(resolved_user_id, settings.main_menu_state_key, sent.message_id)
    set_ui_state(resolved_user_id, settings.active_ui_state_key, sent.message_id)

async def send_single_ui_message(
    message: Message,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
    user_id: int | None = None
):
    resolved_user_id = user_id or message.chat.id
    prev_active_id = get_ui_state(resolved_user_id, settings.active_ui_state_key)
    main_menu_id = get_ui_state(resolved_user_id, settings.main_menu_state_key)
    
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
    set_ui_state(resolved_user_id, settings.active_ui_state_key, sent.message_id)
    return sent

def _get_progress_bar(percentage, length=10):
    filled_length = int(length * percentage // 100)
    bar = "🟩" * filled_length + "⬜️" * (length - filled_length)
    return bar
