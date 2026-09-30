from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from admin_privileges import ROLE_RANK, required_role_for_callback


# Active single-message panels are intentionally process-local. A fresh /admin
# starts a new panel; any click on an older admin panel makes that message active
# again. FSM form input can therefore redraw the same panel without creating a
# stream of bot messages.
_ACTIVE_PANELS: dict[tuple[int, int], Message] = {}


def _key(chat_id: int, user_id: int) -> tuple[int, int]:
    return int(chat_id), int(user_id)


def register_panel_message(user_id: int, message: Message) -> None:
    if not message.chat:
        return
    _ACTIVE_PANELS[_key(message.chat.id, user_id)] = message


def register_panel_from_callback(call: CallbackQuery) -> None:
    if not call.from_user or not isinstance(call.message, Message):
        return
    register_panel_message(call.from_user.id, call.message)


def get_panel_message(chat_id: int, user_id: int) -> Message | None:
    return _ACTIVE_PANELS.get(_key(chat_id, user_id))


def filter_keyboard_for_role(reply_markup, role: str | None):
    """Hide admin callbacks above the effective role using the RBAC catalog.

    Unknown admin callbacks are hidden fail-closed. Non-admin callbacks and
    non-callback buttons are preserved because this helper is also safe for
    mixed Telegram keyboards.
    """
    if not isinstance(reply_markup, InlineKeyboardMarkup):
        return reply_markup
    rank = ROLE_RANK.get(str(role or "").lower(), 0)
    rows = []
    for row in reply_markup.inline_keyboard:
        allowed = []
        for button in row:
            data = button.callback_data or ""
            if not data:
                allowed.append(button)
                continue
            if not data.startswith("admin"):
                allowed.append(button)
                continue
            needed = required_role_for_callback(data)
            if needed is None:
                continue
            if rank >= ROLE_RANK.get(needed, 999):
                allowed.append(button)
        if allowed:
            rows.append(allowed)
    return InlineKeyboardMarkup(inline_keyboard=rows)


class AdminPanelSessionMiddleware(BaseMiddleware):
    """Remember the admin message currently used for inline navigation.

    The middleware does not change authorization or business logic. It only
    keeps enough UI context for subsequent FSM text input to redraw the panel.
    """

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery):
            callback_data = event.data or ""
            if callback_data.startswith("admin"):
                register_panel_from_callback(event)
        return await handler(event, data)


async def render_callback(
    call: CallbackQuery,
    text: str,
    *,
    reply_markup=None,
    **kwargs: Any,
) -> Message | None:
    """Render a callback screen in the same Telegram message.

    Falling back to a new message is deliberate: Telegram may reject editing a
    very old/inaccessible message. In the normal path no extra chat message is
    created.
    """
    register_panel_from_callback(call)
    if not isinstance(call.message, Message):
        return None

    try:
        result = await call.message.edit_text(
            text,
            reply_markup=reply_markup,
            **kwargs,
        )
        if call.from_user and isinstance(result, Message):
            register_panel_message(call.from_user.id, result)
        return result if isinstance(result, Message) else call.message
    except TelegramBadRequest as exc:
        # Refreshing a screen without any visible change is a normal action.
        if "message is not modified" in str(exc).lower():
            return call.message
        # Some message types or historical messages cannot be edited. Keep the
        # action usable while making the replacement the new active panel.
        result = await call.message.answer(text, reply_markup=reply_markup, **kwargs)
        if call.from_user:
            register_panel_message(call.from_user.id, result)
        return result


async def render_input(
    message: Message,
    text: str,
    *,
    reply_markup=None,
    delete_input: bool = True,
    **kwargs: Any,
) -> Message | None:
    """Render an FSM form result/prompt back into the active admin panel.

    The administrator's short text input is removed where Telegram permissions
    allow it, keeping private-chat history compact. If no active panel exists
    (e.g. after a process restart), the function gracefully sends a new message.
    """
    user_id = message.from_user.id if message.from_user else 0
    panel = get_panel_message(message.chat.id, user_id) if user_id else None

    if delete_input:
        try:
            await message.delete()
        except Exception:
            pass

    if panel is not None:
        try:
            result = await panel.edit_text(text, reply_markup=reply_markup, **kwargs)
            if user_id and isinstance(result, Message):
                register_panel_message(user_id, result)
            return result if isinstance(result, Message) else panel
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return panel
        except Exception:
            # The fallback below is intentionally broad. A stale panel must not
            # break an administrative form that has otherwise completed.
            pass

    result = await message.answer(text, reply_markup=reply_markup, **kwargs)
    if user_id:
        register_panel_message(user_id, result)
    return result
