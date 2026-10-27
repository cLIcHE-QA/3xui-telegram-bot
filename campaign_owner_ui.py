"""#949 unregistered private Owner UI. No runtime assembly or delivery policy."""
import secrets
from dataclasses import dataclass, field
import re
import uuid

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import authorize_callback, authorize_message, get_admin_role
from admin_ui import AdminPrivateChatMiddleware, get_panel_message, render_callback, render_input
from campaign_schedule import parse_campaign_schedule
from campaign_telegram import campaign_plain_text
from campaign_store import (
    CampaignConflict, CampaignLimit, CampaignNotFound, CampaignOutcomeUnknown, CampaignUnavailable,
)
from service_campaign_delivery import CampaignDelivery
from service_campaigns import CampaignDenied, CampaignInvalid, _groups, _text
from ui_time import format_timestamp


TTL = 90
FORM_TTL = 600
MAX_TOKENS = 256
_CATEGORIES = {"technical": "Техническое", "service": "Сервисное", "tariff": "О тарифе"}
_STEPS = ("subject", "body", "include_groups", "exclude_groups")
_LABELS = {"draft": "Черновик", "scheduled": "Запланировано", "running": "В работе",
           "paused": "Приостановлено", "cancelled": "Отменено", "completed": "Завершено",
           "partial": "Частично завершено", "pending": "Ожидают", "intent": "Исход проверяется",
           "sent": "Отправлены", "unavailable": "Недоступны", "unknown": "Исход неизвестен",
           "failed": "Отказ", "skipped": "Пропущены"}


class CampaignInput(StatesGroup):
    value = State()


@dataclass(frozen=True)
class _Action:
    actor: int = field(repr=False)
    chat: int = field(repr=False)
    message: int = field(repr=False)
    issued: int
    expires: int
    action: str
    args: tuple = field(repr=False)


def _clip(text):
    # Telegram limits UTF16 units. No split surrogate or silent full-preview claim.
    if len(text.encode("utf-16-le")) // 2 <= 3800:
        return text
    result, units = [], 0
    for char in text:
        units += 2 if ord(char) > 0xffff else 1
        if units > 3700:
            break
        result.append(char)
    return "".join(result) + "\n… показан фрагмент текста"


def _group_input(text):
    if text == "-":
        return ()
    if len(text) > 1100 or not re.fullmatch(r"[1-9][0-9]{0,18}(?:,[1-9][0-9]{0,18}){0,49}", text):
        raise CampaignInvalid("Invalid groups")
    return _groups([int(value) for value in text.split(",")])


class CampaignOwnerUI:
    """Source-only controller/router; the caller must not register it yet.

    The factory below always supplies the real deny-all delivery policy.
    Tests may inject an isolated API, never a policy from callback/FSM data.
    """

    def __init__(self, api, db, settings, *, enabled=False):
        self.api, self.db, self.settings = api, db, settings
        self.enabled = enabled is True
        self._tokens = {}
        self._views = {}
        self.router = Router(name="campaign_owner_source")
        self.router.message.outer_middleware(AdminPrivateChatMiddleware())
        self.router.callback_query.outer_middleware(AdminPrivateChatMiddleware())
        self.router.callback_query.register(self.callback, F.data.regexp(r"^admin:campaigns(?::[a-f0-9]{16})?$"))
        self.router.message.register(self.input, CampaignInput.value)

    def _context(self, event):
        actor = event.from_user
        panel = event.message if isinstance(event, CallbackQuery) else event
        if (actor is None or actor.is_bot is not False or type(actor.id) is not int or actor.id <= 0
                or not isinstance(panel, Message) or type(panel.chat.id) is not int
                or panel.chat.type != "private" or panel.chat.id != actor.id
                or panel.sender_chat is not None or panel.via_bot is not None
                or panel.forward_origin is not None):
            raise CampaignDenied("Campaign private context denied")
        if isinstance(event, CallbackQuery) and (panel.from_user is None or panel.from_user.is_bot is not True):
            raise CampaignDenied("Campaign panel denied")
        return actor.id, panel

    def _invalidate(self, actor, panel):
        now = self.api._now()
        self._tokens = {key: value for key, value in self._tokens.items()
                        if value.issued <= now < value.expires
                        and (value.actor, value.chat) != (actor, panel.chat.id)}
        self._views = {key: value for key, value in self._views.items()
                       if value[1] <= now < value[1] + FORM_TTL and key != (actor, panel.chat.id)}

    def _keyboard(self, actor, panel, buttons, *, system=False):
        self._invalidate(actor, panel)
        now = self.api._now()
        if len(self._tokens) + len(buttons) > MAX_TOKENS or len(self._views) >= MAX_TOKENS:
            raise CampaignLimit("Campaign UI capacity")
        rows = []
        for label, action, args in buttons:
            token = secrets.token_hex(8)
            lifetime = TTL if action in {"save", "confirm", "stop_run"} else FORM_TTL
            self._tokens[token] = _Action(actor, panel.chat.id, panel.message_id, now, now + lifetime, action, tuple(args))
            rows.append([InlineKeyboardButton(text=label, callback_data="admin:campaigns:" + token)])
        if system:
            rows.append([InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")])
        self._views[(actor, panel.chat.id)] = (
            panel.message_id, now, frozenset(button.callback_data for row in rows for button in row
                                            if button.callback_data != "admin:section:system"))
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def _render(self, event, text, buttons=(), *, system=False):
        actor, incoming = self._context(event)
        panel = incoming if isinstance(event, CallbackQuery) else get_panel_message(incoming.chat.id, actor)
        if not isinstance(panel, Message):
            raise CampaignDenied("Campaign panel missing")
        keyboard = self._keyboard(actor, panel, buttons, system=system)
        render = render_callback if isinstance(event, CallbackQuery) else render_input
        # Literal plain text, no inherited Bot parse mode/links/media/CTA.
        await render(event, _clip(text), reply_markup=keyboard, parse_mode=None,
                     link_preview_options={"is_disabled": True})

    def _take(self, call, actor, panel):
        token = (call.data or "").removeprefix("admin:campaigns:")
        item = self._tokens.get(token)
        now = self.api._now()
        visible = {button.callback_data for row in (panel.reply_markup.inline_keyboard if panel.reply_markup else [])
                   for button in row}
        if (item is None or (item.actor, item.chat, item.message) != (actor, panel.chat.id, panel.message_id)
                or not item.issued <= now < item.expires or call.data not in visible):
            raise CampaignDenied("Campaign action expired")
        # Consume before the first mutation await; concurrent replay cannot fan out.
        self._invalidate(actor, panel)
        return item.action, item.args

    async def _failure(self, event, state, error):
        try:
            await state.clear()
        except Exception:
            pass
        if isinstance(error, CampaignOutcomeUnknown):
            text = "🟡 Исход не подтверждён. Проверьте список кампаний; не повторяйте действие автоматически."
        elif isinstance(error, CampaignConflict):
            text = "🟡 Черновик изменился. Откройте актуальную версию."
        elif isinstance(error, CampaignDenied):
            text = "⚪ Действие недоступно или срок подтверждения истёк. Откройте раздел заново."
        elif isinstance(error, CampaignInvalid):
            text = "⚠️ Некорректные данные. Начните ввод заново; текст, ссылки и вложения не отправлены."
        elif isinstance(error, CampaignNotFound):
            text = "⚪ Запись недоступна. Обновите список."
        elif isinstance(error, CampaignLimit):
            text = "⚪ Достигнут безопасный лимит. Обновите раздел позже."
        else:
            text = "⚪ Кампании временно недоступны. Исход операции не подтверждён; автоматического повтора нет."
        try:
            await self._render(event, text, [("⬅ Сервисные сообщения", "home", ())])
        except Exception:
            # Even a full token store/unavailable clock retains a fixed exit.
            markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")]])
            render = render_callback if isinstance(event, CallbackQuery) else render_input
            await render(event, text, reply_markup=markup, parse_mode=None)

    async def callback(self, call: CallbackQuery, state: FSMContext):
        try:
            actor, panel = self._context(call)
        except CampaignDenied:
            await call.answer("Раздел доступен только Owner в своём личном чате.", show_alert=True)
            return
        try:
            allowed, _ = await authorize_callback(self.db, self.settings, call, minimum="owner")
        except Exception:
            await call.answer("Проверка прав временно недоступна.", show_alert=True)
            return
        if not allowed:
            return
        try:
            action, args = ("home", ()) if call.data == "admin:campaigns" else self._take(call, actor, panel)
            if action == "home":
                await state.clear()
                text = "📣 Сервисные сообщения\n\n" + ("Редактор включён." if self.enabled else "Редактор выключен.")
                text += "\nДоставка не разрешена. Категория не означает обязательное уведомление."
                buttons = [("📄 Черновики", "drafts", (0,)), ("📊 Кампании", "jobs", (0,))]
                if self.enabled:
                    buttons.insert(0, ("➕ Новый черновик", "new", ()))
                await self._render(call, text, buttons, system=True)
            elif action == "drafts":
                await state.clear()
                page = await self.api.list_drafts(actor, page=args[0])
                buttons = [(f"📄 #{row.id} · {row.subject[:40]}", "draft", (row.id, page.page)) for row in page.items]
                if page.page:
                    buttons.append(("⬅ Предыдущие", "drafts", (page.page - 1,)))
                if (page.page + 1) * 8 < page.total:
                    buttons.append(("➡ Следующие", "drafts", (page.page + 1,)))
                buttons.append(("⬅ Сервисные сообщения", "home", ()))
                await self._render(call, f"📄 Черновики · {page.total}", buttons)
            elif action == "draft":
                await self._draft(call, state, actor, *args)
            elif action in {"new", "edit"}:
                self._require_editor()
                values = {"include_groups": (), "exclude_groups": ()}
                draft_id, revision, page = None, None, 0
                if action == "edit":
                    draft_id, revision, page = args
                    draft = await self.api.get_draft(actor, draft_id)
                    if draft.revision != revision:
                        raise CampaignConflict("Stale draft")
                    values.update(category=draft.category, subject=draft.subject, body=draft.body,
                                  include_groups=draft.include_groups, exclude_groups=draft.exclude_groups)
                await state.clear()
                await state.update_data(campaign={"actor": actor, "chat": panel.chat.id, "panel": panel.message_id,
                    "issued": self.api._now(), "draft": draft_id, "revision": revision, "page": page,
                    "values": values, "step": "category"})
                buttons = [(label, "category", (key,)) for key, label in _CATEGORIES.items()]
                buttons.append(("✖ Отмена", "draft" if draft_id else "home", (draft_id, page) if draft_id else ()))
                await self._render(call, "📣 Выберите сервисную категорию. Реклама, media и ссылки недоступны.", buttons)
            elif action == "category":
                self._require_editor()
                form = await self._form(state, actor, panel)
                if form["step"] != "category" or args[0] not in _CATEGORIES:
                    raise CampaignDenied("Stale form")
                form["values"]["category"] = args[0]; form["step"] = "subject"
                await state.set_state(CampaignInput.value); await state.update_data(campaign=form)
                await self._prompt(call, form)
            elif action == "save":
                self._require_editor()
                form = await self._form(state, actor, panel)
                if form["step"] != "review":
                    raise CampaignDenied("Stale review")
                await state.clear()
                if form["draft"]:
                    draft = await self.api.edit_draft(actor, form["draft"], expected_revision=form["revision"], **form["values"])
                else:
                    draft = await self.api.create_draft(actor, **form["values"])
                await self._draft(call, state, actor, draft.id, form["page"])
            elif action == "estimate":
                draft_id, revision, page = args
                estimate = await self.api.dry_run(actor, draft_id, expected_revision=revision)
                await self._render(call, f"👥 Кандидаты: {estimate.candidates}" + ("+ · лимит" if estimate.truncated else "")
                    + "\nРазрешено доставить: 0. Согласие, доступность чата и право доставки не подтверждены.",
                    [("⬅ Черновик", "draft", (draft_id, page))])
            elif action == "schedule":
                self._require_editor()
                if not self.api._ready():
                    raise CampaignDenied("Unapproved delivery")
                draft_id, revision, page = args
                draft = await self.api.get_draft(actor, draft_id)
                if draft.revision != revision:
                    raise CampaignConflict("Stale draft")
                campaign_plain_text(draft.subject, draft.body)
                await state.set_state(CampaignInput.value)
                await state.update_data(campaign={"actor": actor, "chat": panel.chat.id, "panel": panel.message_id,
                    "issued": self.api._now(), "draft": draft_id, "revision": revision, "page": page,
                    "step": "when", "operation": str(uuid.uuid4())})
                await self._render(call, "🕒 Введите дату и явный часовой пояс:\nYYYY-MM-DDTHH:MM Europe/Moscow\n"
                    "Либо укажите UTC. Неоднозначное время DST не принимается.", [("✖ Отмена", "draft", (draft_id, page))])
            elif action == "confirm":
                self._require_editor()
                form = await self._form(state, actor, panel)
                if form["step"] != "schedule_review":
                    raise CampaignDenied("Stale schedule")
                draft = await self.api.get_draft(actor, form["draft"])
                if draft.revision != form["revision"]:
                    raise CampaignConflict("Stale draft")
                campaign_plain_text(draft.subject, draft.body)
                await self.api._require_category(draft.category)
                await state.clear()
                frozen = await self.api.freeze_draft(actor, form["draft"], expected_revision=form["revision"])
                job = await self.api.prepare_job(actor, frozen.id, operation_id=form["operation"],
                                                local_time=form["local"], timezone=form["timezone"])
                await self.api.confirm_job(actor, job.id, expected_snapshot=job.snapshot_sha256)
                await self._job(call, actor, job.id, 0)
            elif action == "jobs":
                await state.clear()
                page = await self.api.list_jobs(actor, page=args[0])
                buttons = [(f"📊 #{job.id} · {_LABELS[job.state]}", "job", (job.id, page.page)) for job in page.items]
                if page.page:
                    buttons.append(("⬅ Предыдущие", "jobs", (page.page - 1,)))
                if (page.page + 1) * 8 < page.total:
                    buttons.append(("➡ Следующие", "jobs", (page.page + 1,)))
                buttons.append(("⬅ Сервисные сообщения", "home", ()))
                await self._render(call, f"📊 Кампании · {page.total}", buttons)
            elif action == "job":
                await state.clear(); await self._job(call, actor, *args)
            elif action == "stop_ask":
                job_id, page, kind = args
                job = await self.api.get_job(actor, job_id)
                if kind not in {"pause", "cancel"}:
                    raise CampaignDenied("Unknown stop")
                await self._render(call, f"⚠️ Остановить новые попытки кампании #{job.id}?\n"
                    "Уже отправленное не отменяется. Текущая попытка может подтвердиться или остаться с неизвестным исходом.",
                    [("⏸ Приостановить" if kind == "pause" else "⛔ Отменить кампанию", "stop_run", args),
                     ("✖ Отмена", "job", (job.id, page))])
            elif action == "stop_run":
                job_id, page, kind = args
                if kind == "pause":
                    await self.api.pause_job(actor, job_id)
                elif kind == "cancel":
                    await self.api.cancel_job(actor, job_id)
                else:
                    raise CampaignDenied("Unknown stop")
                await self._job(call, actor, job_id, page)
            else:
                raise CampaignDenied("Unknown action")
            await call.answer()
        except Exception as error:
            await self._failure(call, state, error)
            await call.answer()

    def _require_editor(self):
        if not self.enabled:
            raise CampaignDenied("Editor disabled")

    async def _form(self, state, actor, panel):
        data = (await state.get_data()).get("campaign")
        now = self.api._now()
        if (not isinstance(data, dict) or (data.get("actor"), data.get("chat"), data.get("panel"))
                != (actor, panel.chat.id, panel.message_id) or type(data.get("issued")) is not int
                or not data["issued"] <= now < data["issued"] + FORM_TTL):
            raise CampaignDenied("Invalid campaign form")
        return data

    async def _draft(self, event, state, actor, draft_id, page):
        await state.clear()
        draft = await self.api.get_draft(actor, draft_id)
        text = (f"📄 Черновик #{draft.id} · версия {draft.revision}\n{_CATEGORIES[draft.category]}\n\n"
                f"{draft.subject}\n\n{draft.body}\n\nВключены группы: {', '.join(map(str, draft.include_groups)) or 'все кандидаты'}"
                f"\nИсключены группы: {', '.join(map(str, draft.exclude_groups)) or 'нет'}"
                "\nЛокальный предпросмотр. Отправок нет. Содержание и отсутствие секретов проверяет Owner.")
        buttons = [("👥 Оценить кандидатов", "estimate", (draft.id, draft.revision, page))]
        if self.enabled:
            buttons += [("✏ Изменить", "edit", (draft.id, draft.revision, page)),
                        ("🕒 Планирование", "schedule", (draft.id, draft.revision, page))]
        buttons.append(("⬅ Черновики", "drafts", (page,)))
        await self._render(event, text, buttons)

    async def _job(self, event, actor, job_id, page):
        job = await self.api.get_job(actor, job_id)
        text = f"📊 Кампания #{job.id}\n{_LABELS[job.state]}\nСледующее время: {format_timestamp(job.ready_at)}"
        text += "\n" + "\n".join(f"{_LABELS[key]}: {count}" for key, count in job.counts)
        text += "\nНеизвестный исход не является отказом. Автоматического повтора нет."
        buttons = [("🔄 Обновить", "job", (job.id, page))]
        if job.state in {"scheduled", "running"}:
            buttons.append(("⏸ Приостановить", "stop_ask", (job.id, page, "pause")))
        if job.state in {"draft", "scheduled", "running", "paused"}:
            buttons.append(("⛔ Отменить кампанию", "stop_ask", (job.id, page, "cancel")))
        buttons.append(("⬅ Кампании", "jobs", (page,)))
        await self._render(event, text, buttons)

    async def _prompt(self, event, form):
        labels = {"subject": "Введите тему (до 120 символов).", "body": "Введите текст (до 3500 символов).",
                  "include_groups": "Введите ID включаемых групп пользователей через запятую или - для всех кандидатов.",
                  "exclude_groups": "Введите ID исключаемых групп через запятую или - для пустого списка."}
        back = ("draft", (form["draft"], form["page"])) if form["draft"] else ("home", ())
        await self._render(event, labels[form["step"]] + "\nБез ссылок, разметки и вложений. Доставка не включается.",
                           [("✖ Отмена", *back)])

    async def input(self, message: Message, state: FSMContext):
        try:
            actor, _ = self._context(message)
        except CampaignDenied:
            return
        try:
            allowed, _ = await authorize_message(self.db, self.settings, actor, minimum="owner")
        except Exception:
            return
        if not allowed:
            await state.clear(); return
        try:
            self._require_editor()
            panel = get_panel_message(message.chat.id, actor)
            if not isinstance(panel, Message):
                raise CampaignDenied("Panel unavailable")
            visible = {button.callback_data for row in (panel.reply_markup.inline_keyboard if panel.reply_markup else [])
                       for button in row}
            # Another admin section may have reused the same panel while FSM
            # remained in storage. Such input must not continue this old form.
            view = self._views.get((actor, panel.chat.id))
            if (view is None or view[0] != panel.message_id
                    or not view[1] <= self.api._now() < view[1] + FORM_TTL or not view[2].intersection(visible)):
                raise CampaignDenied("Campaign panel changed")
            form = await self._form(state, actor, panel)
            if not isinstance(message.text, str):
                raise CampaignInvalid("Text required")
            step = form["step"]
            if step == "when":
                pieces = message.text.split(" ")
                if len(pieces) != 2:
                    raise CampaignInvalid("Explicit time required")
                schedule = parse_campaign_schedule(*pieces, now=self.api._now())
                form.update(step="schedule_review", local=pieces[0], timezone=pieces[1])
                await state.update_data(campaign=form)
                await self._render(message, f"🕒 Подтвердить планирование?\n{format_timestamp(schedule.due_at)}\n"
                    f"Ввод: {schedule.local_time} {schedule.timezone}\nАудитория и правила доставки будут перепроверены. Пока отправок нет.",
                    [("✅ Подтвердить планирование", "confirm", ()), ("✖ Отмена", "draft", (form["draft"], form["page"]))])
            elif step in _STEPS:
                value = (_text(message.text, maximum=120) if step == "subject" else
                         _text(message.text, maximum=3500, multiline=True) if step == "body" else _group_input(message.text))
                form["values"][step] = value
                index = _STEPS.index(step) + 1
                form["step"] = _STEPS[index] if index < len(_STEPS) else "review"
                await state.update_data(campaign=form)
                if form["step"] == "review":
                    await self._render(message, f"📄 Сохранить черновик?\n{form['values']['subject']}\n\n{form['values']['body']}"
                        "\n\nТолько локальное сохранение. Отправок нет.",
                        [("✅ Сохранить", "save", ()), ("✖ Отмена", "draft" if form["draft"] else "home",
                                                          (form["draft"], form["page"]) if form["draft"] else ())])
                else:
                    await self._prompt(message, form)
            else:
                raise CampaignDenied("Stale input")
        except Exception as error:
            await self._failure(message, state, error)


def create_campaign_owner_ui(db, settings, *, enabled=False, clock=None):
    """Future source composition only: no runtime registration, policy or bot."""
    async def owner(actor):
        return await get_admin_role(db, settings, actor) == "owner"
    options = {"clock": clock} if clock is not None else {}
    api = CampaignDelivery(db, authorize_owner=owner, enabled=False, policy=None, **options)
    return CampaignOwnerUI(api, db, settings, enabled=enabled)
