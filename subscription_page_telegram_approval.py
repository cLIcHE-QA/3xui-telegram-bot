"""#887 D2b: verified private Bot API confirmation for standalone pilot requests.

This is an *opt-in Router factory*; app_runtime deliberately does NOT register it.
The dispatcher and isolated standalone API must receive the SAME pilot instance.
A real multi-process deployment requires a shared atomic ledger first.

A public challenge is not a credential. The owner must submit the code in a
private Telegram chat and press a separate bot-owned confirmation button.
The Bot API, never caller-provided JSON/headers, supplies actor and chat IDs.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import Protocol

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from subscription_page_standalone import CHALLENGE_PATTERN, StandalonePilot

# Strict command form: do not accept forwarded messages, bot mentions,
# deep links, URL parameters, quoted codes, or additional arguments.
_REQUEST = re.compile(r"/web_login ([A-Za-z0-9_-]{16})\Z")
_CALLBACK = re.compile(r"d2bs:(yes|no):([A-Za-z0-9_-]{16})\Z")
MAX_PROMPTS = 128
MAX_PER_OWNER = 3
PROMPT_TTL = 180
_MAX_MESSAGE_LEN = 80


@dataclass(frozen=True)
class _Prompt:
    owner: int
    challenge: str
    issued_at: float
    chat_id: int
    message_id: int | None = None


class _Approval(Protocol):
    https_origin: str

    def _clock(self) -> float: ...
    def _prune(self, now: float) -> None: ...
    async def approve_from_private_telegram(
        self, challenge: str, *, actor_id: int, chat_id: int,
        explicitly_confirmed: bool,
    ) -> bool: ...


class StandaloneTelegramApproval:
    """Private Telegram confirmation adapter; no runtime registration or HTTP route.

    The Telegram Bot API authenticates updates. Callers must never expose
    handle_message/handle_callback as a web endpoint or invoke them with
    untrusted rehydrated objects. A confirmation prompt is one-time.
    """

    def __init__(
        self, pilot: StandalonePilot, *, display_full_challenge: bool = False,
    ) -> None:
        if type(display_full_challenge) is not bool:
            raise ValueError("Explicit anti-phishing display mode is required")
        if not isinstance(pilot, StandalonePilot):
            raise ValueError("A genuine isolated standalone pilot is required")
        self.pilot = pilot
        self.display_full_challenge = display_full_challenge
        self.prompts: dict[str, _Prompt] = {}
        self.router = Router(name="d2b_standalone_approval")
        self.router.message.register(self.handle_message, Command("web_login"))
        self.router.callback_query.register(
            self.handle_callback, F.data.startswith("d2bs:"),
        )

    def _prune(self, current: float) -> None:
        for token, row in list(self.prompts.items()):
            if current < row.issued_at or current - row.issued_at >= PROMPT_TTL:
                del self.prompts[token]

    @staticmethod
    def _private_actor(chat: object, actor: object, *, sender_chat: object = None,
                       forward_origin: object = None) -> int | None:
        if sender_chat is not None or forward_origin is not None:
            return None
        if getattr(chat, "type", None) != "private":
            return None
        owner = getattr(actor, "id", None)
        if type(owner) is not int or not 0 < owner < 2**52:
            return None
        if getattr(chat, "id", None) != owner:
            return None
        if getattr(actor, "is_bot", False):
            return None
        return owner

    async def handle_message(self, message: Message) -> None:
        actor = self._private_actor(
            getattr(message, "chat", None), getattr(message, "from_user", None),
            sender_chat=getattr(message, "sender_chat", None),
            forward_origin=getattr(message, "forward_origin", None),
        )
        # Never echo an untrusted code or user-supplied text to any chat.
        if actor is None:
            return
        content = getattr(message, "text", None)
        if not isinstance(content, str) or not 0 < len(content) <= _MAX_MESSAGE_LEN:
            return
        match = _REQUEST.fullmatch(content)
        if match is None or CHALLENGE_PATTERN.fullmatch(match.group(1)) is None:
            await message.answer("Неверный формат запроса входа. Проверьте код в своём браузере.")
            return
        current = self.pilot._clock()
        self._prune(current)
        # A submitted code must reference a *current* browser challenge; do not
        # generate "approvable" prompts for arbitrary spoofed strings.
        challenge = match.group(1)
        if not self.pilot.challenge_pending(challenge, current):
            await message.answer("Запрос входа недоступен или истёк.")
            return
        if not await self.pilot._verified_owner(actor):
            await message.answer("Вход недоступен для этой учётной записи.")
            return
        # Revalidate challenge and freshness after the asynchronous owner read.
        current = self.pilot._clock()
        if not self.pilot.challenge_pending(challenge, current):
            await message.answer("Запрос входа недоступен или истёк.")
            return
        self._prune(current)
        if (len(self.prompts) >= MAX_PROMPTS
                or sum(prompt.owner == actor for prompt in self.prompts.values()) >= MAX_PER_OWNER):
            await message.answer("Слишком много запросов. Завершите или отмените предыдущие.")
            return
        nonce = secrets.token_urlsafe(12)
        for _ in range(5):
            if nonce not in self.prompts:
                break
            nonce = secrets.token_urlsafe(12)
        else:
            return
        # The nonce binds this exact Telegram owner and private chat to the
        # challenge. It is not the web cookie or subscription credential.
        self.prompts[nonce] = _Prompt(
            owner=actor, challenge=challenge, issued_at=current, chat_id=actor,
        )
        buttons = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Подтвердить вход", callback_data="d2bs:yes:" + nonce),
            InlineKeyboardButton(text="✖ Отмена", callback_data="d2bs:no:" + nonce),
        ]])
        # Staging requires a full browser-to-bot visual match against relay.
        # The challenge is a bounded PUBLIC random code minted by this pilot;
        # never echo arbitrary malformed user input or a session credential.
        code_label = challenge if self.display_full_challenge else "…" + challenge[-4:]
        caution = (
            "Сверьте ВСЕ 16 символов с кодом в браузере на указанном HTTPS-адресе. "
            "Подтверждайте только запрос, который создали лично. "
            "Если пришла чужая ссылка или просьба переслать код — «Отмена»."
            if self.display_full_challenge else
            "Нажмите «Подтвердить» ТОЛЬКО если вы сами создали этот "
            "запрос в своём браузере. Если код прислал кто-то другой, "
            "не подтверждайте — нажмите «Отмена»."
        )
        try:
            sent = await message.answer(
                "Подтверждение входа на собственную страницу подписки.\n"
                f"Адрес: {self.pilot.https_origin}\n"
                f"Код запроса: {code_label}\n\n" + caution,
                reply_markup=buttons,
            )
            sent_id = getattr(sent, "message_id", None)
            if type(sent_id) is not int or sent_id <= 0:
                # Do not allow an unbound/unverifiable callback prompt.
                self.prompts.pop(nonce, None)
                return
            self.prompts[nonce] = _Prompt(
                owner=actor, challenge=challenge, issued_at=current,
                chat_id=actor, message_id=sent_id,
            )
        except Exception:
            self.prompts.pop(nonce, None)
            raise

    async def handle_callback(self, callback: CallbackQuery) -> None:
        data = getattr(callback, "data", None)
        match = _CALLBACK.fullmatch(data) if isinstance(data, str) else None
        if match is None:
            await callback.answer("Запрос больше недоступен.", show_alert=True)
            return
        msg = getattr(callback, "message", None)
        actor = self._private_actor(
            getattr(msg, "chat", None), getattr(callback, "from_user", None),
        )
        if actor is None:
            await callback.answer("Подтверждение доступно только в личном чате.", show_alert=True)
            return
        now = self.pilot._clock()
        self.pilot._prune(now)
        self._prune(now)
        nonce = match.group(2)
        prompt = self.prompts.get(nonce)
        if (prompt is None or prompt.owner != actor or prompt.chat_id != actor
                or prompt.message_id != getattr(msg, "message_id", None)):
            await callback.answer("Запрос больше недоступен.", show_alert=True)
            return
        # consume BEFORE awaiting bot/owner I/O, so a duplicate callback
        # cannot race the first one or issue a second approval.
        del self.prompts[nonce]
        if match.group(1) == "no":
            await callback.answer("Подтверждение отклонено.")
        else:
            # actor/chat originate ONLY from verified Telegram CallbackQuery.
            approved = await self.pilot.approve_from_private_telegram(
                prompt.challenge, actor_id=actor, chat_id=actor,
                explicitly_confirmed=True,
            )
            await callback.answer(
                "Вход подтверждён. Вернитесь в тот же браузер." if approved
                else "Запрос недоступен или срок действия истёк.",
                show_alert=not approved,
            )
        # Best-effort removal; failure must not undo or replay approval.
        try:
            await msg.edit_reply_markup(reply_markup=None)
        except Exception:
            pass


def build_standalone_telegram_router(pilot: StandalonePilot) -> Router:
    """Construct a private-only, *unregistered* aiogram Router.

    The returned Router retains the adapter's bound handlers. There is no
    implicit import or inclusion in the current app_runtime.Dispatcher.
    """
    return StandaloneTelegramApproval(pilot).router
