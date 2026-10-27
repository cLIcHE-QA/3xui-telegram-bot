"""Unregistered #949 adapters. No token loading, dispatcher or startup effects."""
import asyncio
import json
import uuid

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage
from aiogram.types import LinkPreviewOptions, Message

from service_campaign_delivery import CampaignEnvelope, CampaignReply
from service_campaigns import CampaignDenied, CampaignInvalid, _identifier, _payload


ADMISSION_TIMEOUT = 3
REQUEST_TIMEOUT = 8


def campaign_plain_text(subject, body):
    """Fixed plain message shape; no recipient, markup or provider access."""
    payload = _payload("service", subject, body)
    text = payload["subject"] + "\n\n" + payload["body"]
    if len(text.encode("utf-16-le")) // 2 > 4096:
        raise CampaignInvalid("Campaign message too long")
    return text


class _CampaignSendMessage(SendMessage):
    """Fixed sendMessage surface; no public generic method/URL selector."""


class _VerifiedCampaign429(TelegramRetryAfter):
    """Created only by the narrow HTTP-status-aware session boundary below."""


class CampaignAwareSession(AiohttpSession):
    """Future optional session for the existing bot, never installed here.

    aiogram's generic RetryAfter does not retain the HTTP status and may be
    raised for retry_after in a 5xx response. Only this exact campaign method
    plus a verified HTTP429 rejection may authorize a safe campaign retry.
    All other bot methods retain the pinned SDK's original behavior.
    """

    def check_response(self, bot, method, status_code, content):
        if isinstance(method, _CampaignSendMessage) and status_code == 429:
            try:
                raw = self.json_loads(content)
                parameters = raw.get("parameters") if isinstance(raw, dict) else None
                delay = parameters.get("retry_after") if isinstance(parameters, dict) else None
                rejected = (raw.get("ok") is False and type(raw.get("error_code")) is int
                            and raw.get("error_code") == 429)
                if rejected and type(delay) is int and 1 <= delay <= 3600:
                    raise _VerifiedCampaign429(method=method, message="Campaign rate limited", retry_after=delay)
            except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
                pass
        return super().check_response(bot, method, status_code, content)


def _consume(task):
    if not task.cancelled():
        task.exception()


class _Admission:
    """At most one bounded authorization task, including late cancellation."""

    def __init__(self, authorizer):
        self._authorizer = authorizer
        self._pending = None

    async def allowed(self, value):
        if self._authorizer is None or (self._pending and not self._pending.done()):
            return False
        task = None
        try:
            task = asyncio.create_task(self._authorizer(value))
            self._pending = task
            task.add_done_callback(_consume)
            done, _ = await asyncio.wait({task}, timeout=ADMISSION_TIMEOUT)
            if not done:
                task.cancel()
                return False
            return task.result() is True
        except asyncio.CancelledError:
            if task is not None:
                task.cancel()
            raise
        except Exception:
            return False


class CampaignBotTransport:
    """One-shot existing-bot adapter; the absent trusted admission denies all.

    The future server-side authorizer must revalidate the worker's immutable
    intent/proof/policy. Never obtain it from callbacks, role strings or JSON.
    The UI does not expose recipient IDs or this adapter as a send endpoint.
    """

    def __init__(self, bot, *, authorize_envelope=None):
        self._bot = bot
        self._admission = _Admission(authorize_envelope)
        self._active = None
        self._stopped = False

    async def send(self, envelope):
        if not isinstance(envelope, CampaignEnvelope):
            raise CampaignInvalid("Invalid campaign envelope")
        try:
            _identifier(envelope.chat_id)
            operation = uuid.UUID(envelope.operation_id)
            if operation.version != 4 or str(operation) != envelope.operation_id:
                raise ValueError
            text = campaign_plain_text(envelope.subject, envelope.body)
            if envelope.parse_mode is not None or envelope.link_preview is not False:
                raise ValueError
        except (ValueError, TypeError, AttributeError, UnicodeError):
            raise CampaignInvalid("Invalid campaign envelope") from None
        if (self._stopped or (self._active and not self._active.done())
                or not await self._admission.allowed(envelope)):
            raise CampaignDenied("Campaign transport denied")
        # Admission awaited: another caller may have acquired the transport.
        if self._stopped or (self._active and not self._active.done()):
            raise CampaignDenied("Campaign transport denied")

        method = _CampaignSendMessage(
            chat_id=envelope.chat_id, text=text, parse_mode=None, entities=None,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            disable_web_page_preview=True, allow_paid_broadcast=False,
            protect_content=True, reply_markup=None, reply_parameters=None,
            business_connection_id=None, message_thread_id=None,
            direct_messages_topic_id=None, message_effect_id=None,
            suggested_post_parameters=None, ephemeral_message_parameters=None,
            receiver_user_id=None, callback_query_id=None,
        )
        task = None
        try:
            # Exactly one call. The adapter also bounds a noncooperative client;
            # cancellation never proves that Telegram did not accept a request.
            task = asyncio.create_task(self._bot(method, request_timeout=REQUEST_TIMEOUT))
            self._active = task
            task.add_done_callback(_consume)
            done, _ = await asyncio.wait({task}, timeout=REQUEST_TIMEOUT)
            if not done:
                self._stopped = True
                task.cancel()
                return CampaignReply("unknown")
            reply = task.result()
        except asyncio.CancelledError:
            self._stopped = True
            if task is not None:
                task.cancel()
            raise
        except _VerifiedCampaign429 as exc:
            if exc.method is method and type(exc.retry_after) is int and 1 <= exc.retry_after <= 3600:
                return CampaignReply("rate_limited", chat_id=envelope.chat_id, retry_after=exc.retry_after)
            self._stopped = True
            return CampaignReply("unknown")
        except TelegramForbiddenError as exc:
            if exc.method is method:
                blocked = exc.message in {"Forbidden: bot was blocked by the user", "bot was blocked by the user"}
                return CampaignReply("unavailable", chat_id=envelope.chat_id,
                                     reason="blocked" if blocked else "chat_unavailable")
            self._stopped = True
            return CampaignReply("unknown")
        except TelegramBadRequest as exc:
            # Exact closed SDK message for HTTP400 only. No raw text is returned.
            if exc.method is method and exc.message in {"Bad Request: chat not found", "chat not found"}:
                return CampaignReply("unavailable", chat_id=envelope.chat_id, reason="chat_unavailable")
            self._stopped = True
            return CampaignReply("unknown")
        except Exception:
            # Includes unproven SDK RetryAfter, 5xx, timeout, decode and network.
            self._stopped = True
            return CampaignReply("unknown")
        bot_id = getattr(self._bot, "id", None)
        if (not isinstance(reply, Message) or reply.chat.type != "private"
                or type(reply.chat.id) is not int or reply.chat.id != envelope.chat_id
                or type(bot_id) is not int or bot_id <= 0
                or reply.from_user is None or reply.from_user.is_bot is not True
                or type(reply.from_user.id) is not int or reply.from_user.id != bot_id
                or type(reply.message_id) is not int or reply.message_id <= 0):
            self._stopped = True
            return CampaignReply("unknown")
        return CampaignReply("confirmed", chat_id=reply.chat.id, message_id=reply.message_id)


class CampaignPrivateObserver:
    """For a future authenticated, already-allowed private Message path only.

    This source adapter is not installed in dispatcher/client guards. Its
    authorizer must check current feature/pilot/rate/privacy prerequisites.
    No import/admin-created identity or caller-supplied chat ID is accepted.
    """

    def __init__(self, service, *, enabled=False, authorize_update=None):
        self._service = service
        self._enabled = enabled is True
        self._admission = _Admission(authorize_update)

    async def observe(self, message):
        if not self._enabled or not isinstance(message, Message):
            return False
        actor = message.from_user
        if (actor is None or actor.is_bot is not False or message.chat.type != "private"
                or type(actor.id) is not int or actor.id <= 0 or message.chat.id != actor.id
                or message.sender_chat is not None or message.via_bot is not None
                or message.forward_origin is not None):
            return False
        if not await self._admission.allowed(message):
            return False
        try:
            return await self._service.observe_private_update(
                actor_id=actor.id, chat_id=message.chat.id,
                chat_type="private", is_bot=False,
            ) is True
        except Exception:
            # Optional future observation must not break critical client paths
            # or leak raw update/DB details. Cancellation is still propagated.
            return False
