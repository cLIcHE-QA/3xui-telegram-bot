"""Owner-only UI обновления бота и startup recovery."""
from __future__ import annotations

import asyncio
import re
import secrets
import time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import authorize_callback, authorize_message
from admin_ui import render_callback, render_input
from audit import audit_from_call, audit_from_message, audit_system
from config import load_settings
from db import Database, JobRunRecord
from job_update_ack import REASON_LABELS, correlate_deploy
from deploy_control import (
    DeployControlClient,
    DeployControlError,
    DeployOperation,
    DeployPreflight,
    RELEASE_RE,
    TERMINAL_STATES,
)
from version import APP_VERSION


settings = load_settings()
db = Database(settings.db_path)
bot_updates_router = Router(name="bot_updates")

_OPERATION_ID = re.compile(r"(?:^|; )operation_id=([0-9a-f]{32})(?:;|$)")
_RELEASE = re.compile(r"(?:^|; )release=(v[0-9]+\.[0-9]+\.[0-9]+)(?:;|$)")
_DOWNGRADE_PHRASE_RE = re.compile(r"DOWNGRADE (v[0-9]+\.[0-9]+\.[0-9]+)\Z")


class BotUpdateStates(StatesGroup):
    release_input = State()
    downgrade_phrase = State()


DEPLOY_STATE_LABELS = {
    "queued": "в очереди",
    "preflight": "предварительная проверка",
    "backup": "резервное копирование",
    "building": "сборка",
    "deploying": "развёртывание",
    "verifying": "проверка",
    "success": "успешно",
    "failed": "ошибка",
    "unknown": "результат неизвестен",
}


def _deploy_state_text(value: str) -> str:
    return DEPLOY_STATE_LABELS.get(value, value or "неизвестно")


STATUS_LABELS = {
    "ok": "норма",
    "healthy": "норма",
    "ready": "готово",
    "success": "успешно",
    "failed": "ошибка",
    "error": "ошибка",
    "unknown": "неизвестно",
}


def _status_text(value: str) -> str:
    raw = (value or "").lower()
    return STATUS_LABELS.get(raw, value or "неизвестно")


def _client() -> DeployControlClient | None:
    if not settings.deploy_agent_enabled:
        return None
    return DeployControlClient(settings.deploy_agent_url, settings.deploy_agent_token)


def _keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
        for row in rows
    ])


def _system_back() -> InlineKeyboardMarkup:
    return _keyboard([[("⬅ Система", "admin:section:system")]])


def _bot_updates_back(*, refresh: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    if refresh:
        rows.append([("🔄 Обновить", "admin:botupd")])
    rows.append([("⬅ Обновления бота", "admin:botupd")])
    return _keyboard(rows)


def _bot_updates_cancel() -> InlineKeyboardMarkup:
    return _keyboard([[("✖ Отмена", "admin:botupd")]])


def _field(pattern: re.Pattern[str], details: str) -> str:
    match = pattern.search(details or "")
    return match.group(1) if match else ""


def _job_details(operation_id: str, release: str, *, allow_downgrade: bool) -> str:
    return (
        f"operation_id={operation_id}; release={release}; "
        f"allow_downgrade={1 if allow_downgrade else 0}; mutation_not_retried=true"
    )


def _preflight_direction(preflight: DeployPreflight) -> str:
    if preflight.downgrade:
        return "откат"
    if preflight.current_release == preflight.release:
        return "та же версия"
    return "обновление"


def _operation_text(op: DeployOperation) -> str:
    labels = {
        "queued": "🟡 Операция поставлена в очередь.",
        "preflight": "🟡 Выполняется предварительная проверка.",
        "backup": "🟡 Создаётся резервная копия перед развёртыванием.",
        "building": "🟡 Собирается новый образ бота.",
        "deploying": "🟡 Новый релиз разворачивается.",
        "verifying": "🟡 Выполняются проверки после развёртывания.",
        "success": "🟢 Развёртывание успешно завершено и проверено.",
        "failed": "🔴 Развёртывание завершилось ошибкой до подтверждённого успеха.",
        "unknown": "🟡 Итог развёртывания не удалось подтвердить. Автоповтор запрещён.",
    }
    lines = [
        labels.get(op.state, "🟡 Неизвестное состояние."),
        "",
        f"Релиз: {op.release}",
        f"Операция: {op.operation_id}",
        f"Состояние: {_deploy_state_text(op.state)}",
    ]
    if op.current_release:
        lines.append(f"Фактический релиз: {op.current_release}")
    if op.target_sha:
        lines.append(f"Целевой SHA: {op.target_sha[:12]}")
    if op.error_code:
        lines.append(f"Ошибка: {op.error_code}")
    if op.allow_downgrade:
        lines.append("Откат: явно подтверждён")
    return "\n".join(lines)


async def _finish_job_from_operation(job: JobRunRecord, op: DeployOperation, *, recovery: str) -> bool:
    if op.state not in TERMINAL_STATES:
        return False
    status = "success" if op.state == "success" else "failed" if op.state == "failed" else "unknown"
    details = (
        f"{job.details}; state={op.state}; observed={op.current_release}; "
        f"target_sha={op.target_sha}; error_code={op.error_code}; recovery={recovery}"
    )
    duration_ms = max(0, (int(time.time()) - int(job.started_at)) * 1000)
    await db.finish_job_run(
        job.id,
        status=status,
        duration_ms=duration_ms,
        details=details,
    )
    await audit_system(
        db,
        "bot.update.recovered" if recovery != "live" else "bot.update.finished",
        target_type="bot_release",
        target_id=op.release,
        details=details,
        success=status == "success",
    )
    return True


async def reconcile_deploy_jobs(*, wait_seconds: float = 0.0) -> int:
    """Resolve running bot.update jobs only by read-only agent lookup."""
    running = [
        item for item in await db.list_running_job_runs(limit=500)
        if item.name == "bot.update"
    ]
    if not running:
        return 0

    client = _client()
    recovered = 0
    if client is None:
        for job in running:
            details = (
                (job.details + "; " if job.details else "")
                + "state=unknown; recovery=deploy_agent_not_configured; mutation_not_retried=true"
            )
            await db.finish_job_run(
                job.id,
                status="unknown",
                duration_ms=max(0, (int(time.time()) - int(job.started_at)) * 1000),
                details=details,
            )
            recovered += 1
        return recovered

    deadline = time.monotonic() + max(0.0, wait_seconds)
    for job in running:
        operation_id = _field(_OPERATION_ID, job.details)
        release = _field(_RELEASE, job.details)
        if not operation_id or not release:
            details = (
                (job.details + "; " if job.details else "")
                + "state=unknown; recovery=metadata_missing; mutation_not_retried=true"
            )
            await db.finish_job_run(
                job.id,
                status="unknown",
                duration_ms=max(0, (int(time.time()) - int(job.started_at)) * 1000),
                details=details,
            )
            recovered += 1
            continue

        while True:
            try:
                op = await client.get_operation(operation_id)
            except DeployControlError as exc:
                details = (
                    job.details
                    + f"; state=unknown; recovery=lookup_failed; error_code={exc.code or 'error'}"
                    + "; mutation_not_retried=true"
                )
                await db.finish_job_run(
                    job.id,
                    status="unknown",
                    duration_ms=max(0, (int(time.time()) - int(job.started_at)) * 1000),
                    details=details,
                )
                recovered += 1
                break

            if op is None:
                details = (
                    job.details
                    + "; state=unknown; recovery=operation_not_found; mutation_not_retried=true"
                )
                await db.finish_job_run(
                    job.id,
                    status="unknown",
                    duration_ms=max(0, (int(time.time()) - int(job.started_at)) * 1000),
                    details=details,
                )
                recovered += 1
                break

            if op.release != release:
                details = (
                    job.details
                    + "; state=unknown; recovery=release_mismatch; mutation_not_retried=true"
                )
                await db.finish_job_run(
                    job.id,
                    status="unknown",
                    duration_ms=max(0, (int(time.time()) - int(job.started_at)) * 1000),
                    details=details,
                )
                recovered += 1
                break

            if await _finish_job_from_operation(job, op, recovery="agent_journal"):
                recovered += 1
                break

            if time.monotonic() >= deadline:
                if wait_seconds <= 0:
                    break
                details = (
                    job.details
                    + f"; state=unknown; recovery=operation_still_{op.state}; mutation_not_retried=true"
                )
                await db.finish_job_run(
                    job.id,
                    status="unknown",
                    duration_ms=max(0, (int(time.time()) - int(job.started_at)) * 1000),
                    details=details,
                )
                await audit_system(
                    db,
                    "bot.update.recovered",
                    target_type="bot_release",
                    target_id=release,
                    details=details,
                    success=False,
                )
                recovered += 1
                break
            await asyncio.sleep(1.0)
    return recovered


async def _dispatch(
    call: CallbackQuery,
    release: str,
    *,
    allow_downgrade: bool,
) -> None:
    client = _client()
    if client is None:
        await render_callback(
            call,
            "🤖 Обновления бота\n\n🔴 Deploy Agent не настроен.",
            reply_markup=_bot_updates_back(),
        )
        return

    operation_id = secrets.token_hex(16)
    details = _job_details(operation_id, release, allow_downgrade=allow_downgrade)
    run_id = await db.start_job_run(
        name="bot.update",
        trigger="admin",
        actor_id=call.from_user.id,
        details=details,
    )
    await audit_from_call(
        db,
        call,
        "bot.update.started",
        target_type="bot_release",
        target_id=release,
        details=details,
        success=True,
    )

    try:
        try:
            op = await client.deploy(
                operation_id,
                release,
                allow_downgrade=allow_downgrade,
            )
        except DeployControlError as exc:
            if not exc.uncertain:
                fail_details = details + f"; state=failed; error_code={exc.code or 'deploy_rejected'}"
                await db.finish_job_run(
                    run_id,
                    status="failed",
                    duration_ms=0,
                    details=fail_details,
                )
                await audit_from_call(
                    db,
                    call,
                    "bot.update.failed",
                    target_type="bot_release",
                    target_id=release,
                    details=fail_details,
                    success=False,
                )
                await render_callback(
                    call,
                    f"🤖 Обновления бота\n\n🔴 Deploy Agent отклонил операцию: {exc.code or 'error'}",
                    reply_markup=_bot_updates_back(),
                )
                return

            # Lost POST response: lookup only. Never replay mutation.
            try:
                op = await client.get_operation(operation_id)
            except DeployControlError:
                op = None
            if op is None:
                unknown = details + "; state=unknown; lost_post_response=true; mutation_not_retried=true"
                await db.finish_job_run(
                    run_id,
                    status="unknown",
                    duration_ms=0,
                    details=unknown,
                )
                await audit_from_call(
                    db,
                    call,
                    "bot.update.unknown",
                    target_type="bot_release",
                    target_id=release,
                    details=unknown,
                    success=False,
                )
                await render_callback(
                    call,
                    "🤖 Обновления бота\n\n🟡 Ответ на deploy POST потерян, а журнал операции пока недоступен. "
                    "Мутация повторно НЕ отправлялась.",
                    reply_markup=_bot_updates_back(),
                )
                return

        await asyncio.sleep(0.5)
        try:
            latest = await client.get_operation(operation_id)
        except DeployControlError:
            latest = None
        if latest is not None:
            op = latest

        job = next(
            (item for item in await db.list_running_job_runs(limit=500) if item.id == run_id),
            None,
        )
        if job is not None and op.state in TERMINAL_STATES:
            await _finish_job_from_operation(job, op, recovery="live")

        await render_callback(
            call,
            "🤖 Обновления бота\n\n"
            + _operation_text(op)
            + "\n\nПри переходе к развёртыванию текущий контейнер бота будет пересоздан. "
              "После старта новый бот восстановит итог только через журнал операции.",
            reply_markup=_keyboard([
                [("📋 Статус", f"admin:botupd:op:{operation_id}")],
                [("⬅ Обновления бота", "admin:botupd")],
            ]),
        )
    except Exception as exc:
        fail_details = details + f"; state=unknown; local_error={type(exc).__name__}; mutation_not_retried=true"
        await db.finish_job_run(
            run_id,
            status="unknown",
            duration_ms=0,
            details=fail_details,
        )
        await audit_from_call(
            db,
            call,
            "bot.update.unknown",
            target_type="bot_release",
            target_id=release,
            details=fail_details,
            success=False,
        )
        await render_callback(
            call,
            "🤖 Обновления бота\n\n🟡 Локальная ошибка после подготовки операции. "
            "Автоматический повтор развёртывания запрещён.",
            reply_markup=_bot_updates_back(),
        )


async def _dispatch_message(
    message: Message,
    release: str,
    *,
    allow_downgrade: bool,
) -> None:
    client = _client()
    if client is None:
        await render_input(
            message,
            "Deploy Agent не настроен.",
            reply_markup=_bot_updates_back(),
        )
        return

    operation_id = secrets.token_hex(16)
    details = _job_details(operation_id, release, allow_downgrade=allow_downgrade)
    run_id = await db.start_job_run(
        name="bot.update",
        trigger="admin",
        actor_id=message.from_user.id if message.from_user else 0,
        details=details,
    )
    await audit_from_message(
        db,
        message,
        "bot.update.started",
        target_type="bot_release",
        target_id=release,
        details=details,
        success=True,
    )

    try:
        try:
            op = await client.deploy(
                operation_id,
                release,
                allow_downgrade=allow_downgrade,
            )
        except DeployControlError as exc:
            if not exc.uncertain:
                failed = details + f"; state=failed; error_code={exc.code or 'deploy_rejected'}"
                await db.finish_job_run(run_id, status="failed", duration_ms=0, details=failed)
                await audit_from_message(
                    db, message, "bot.update.failed",
                    target_type="bot_release", target_id=release,
                    details=failed, success=False,
                )
                await render_input(
                    message,
                    f"🔴 Deploy Agent отклонил операцию: {exc.code or 'error'}",
                    reply_markup=_bot_updates_back(),
                )
                return
            try:
                op = await client.get_operation(operation_id)
            except DeployControlError:
                op = None
            if op is None:
                unknown = details + "; state=unknown; lost_post_response=true; mutation_not_retried=true"
                await db.finish_job_run(run_id, status="unknown", duration_ms=0, details=unknown)
                await audit_from_message(
                    db, message, "bot.update.unknown",
                    target_type="bot_release", target_id=release,
                    details=unknown, success=False,
                )
                await render_input(
                    message,
                    "🟡 Ответ на deploy POST потерян; мутация повторно НЕ отправлялась.",
                    reply_markup=_bot_updates_back(),
                )
                return

        await render_input(
            message,
            "🤖 Обновление бота запущено.\n\n"
            + _operation_text(op)
            + "\n\nТекущий контейнер бота может быть пересоздан. "
              "После старта итог восстановится из журнала Deploy Agent; POST повторно не отправляется.",
        )
    except Exception as exc:
        unknown = (
            details
            + f"; state=unknown; local_error={type(exc).__name__}; mutation_not_retried=true"
        )
        await db.finish_job_run(run_id, status="unknown", duration_ms=0, details=unknown)
        await audit_from_message(
            db, message, "bot.update.unknown",
            target_type="bot_release", target_id=release,
            details=unknown, success=False,
        )
        await render_input(
            message,
            "🟡 Локальная ошибка после подготовки развёртывания. Автоматический повтор запрещён.",
            reply_markup=_bot_updates_back(),
        )



async def _historical_unknown_buttons() -> list[list[tuple[str, str]]]:
    unknown = await db.list_job_runs(name="bot.update", limit=100)
    acknowledged = await db.list_bot_update_acknowledged_run_ids([run.id for run in unknown])
    for run in unknown:
        if run.status == "unknown" and run.id not in acknowledged:
            return [[("📋 Разобрать исторический unknown", f"admin:botupd:ack:{run.id}")]]
    return []

@bot_updates_router.callback_query(F.data == "admin:botupd")
async def updates_home(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    await state.clear()
    await call.answer()
    ack_rows = await _historical_unknown_buttons()
    client = _client()
    if client is None:
        await render_callback(
            call,
            "🤖 Обновления бота\n\n"
            f"Текущий бот: {APP_VERSION}\n"
            "Deploy Agent: не настроен\n\n"
            "Установи Deploy Agent с ограниченными полномочиями на Master и добавь локальные "
            "DEPLOY_AGENT_URL/DEPLOY_AGENT_TOKEN. Docker socket и Git deploy key "
            "в контейнере бота не требуются.",
            reply_markup=_keyboard(ack_rows + [[("⬅ Система", "admin:section:system")]]),
        )
        return

    await reconcile_deploy_jobs(wait_seconds=0)
    try:
        status, latest = await asyncio.gather(client.status(), client.latest_release())
    except DeployControlError as exc:
        await render_callback(
            call,
            "🤖 Обновления бота\n\n"
            f"Текущий бот: {APP_VERSION}\n"
            f"🔴 Deploy Agent недоступен: {exc.code or 'error'}",
            reply_markup=_keyboard(ack_rows + [[("⬅ Система", "admin:section:system")]]),
        )
        return

    lines = [
        "🤖 Обновления бота",
        "",
        f"📦 Текущий релиз: {status.current_release or 'неизвестно'}",
        f"🤖 Бот: {status.bot_version or APP_VERSION}",
        f"🆕 Последний опубликованный: {latest}",
        f"🧩 Агент: {status.agent_version or 'неизвестно'}",
        f"🩺 Состояние: {_status_text(status.health)} · БД: {_status_text(status.db)} · 3x-ui: {_status_text(status.connectivity)}",
    ]
    if status.active_operation:
        lines += ["", f"⚙️ Активная операция: {status.active_operation}"]

    rows: list[list[tuple[str, str]]] = []
    if latest != status.current_release and not status.active_operation:
        rows.append([("🔍 Проверить последний релиз", f"admin:botupd:pre:{latest}")])
    if not status.active_operation:
        rows.append([("📦 Выбрать опубликованный тег", "admin:botupd:choose")])
    rows.append([("📜 История обновлений", "admin:botupd:history")])
    rows.extend(ack_rows)
    rows.append([("🔄 Обновить", "admin:botupd")])
    rows.append([("⬅ Система", "admin:section:system")])
    await render_callback(call, "\n".join(lines), reply_markup=_keyboard(rows))


@bot_updates_router.callback_query(F.data == "admin:botupd:choose")
async def update_choose(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    await state.clear()
    await state.set_state(BotUpdateStates.release_input)
    await call.answer()
    await render_callback(
        call,
        "🤖 Обновления бота\n\n"
        "Отправь точный опубликованный тег релиза вида vX.Y.Z. "
        "Deploy Agent примет только существующий тег, содержащийся в origin/main, "
        "с совпадающим APP_VERSION.",
        reply_markup=_keyboard([[("✖ Отмена", "admin:botupd")]]),
    )


@bot_updates_router.message(BotUpdateStates.release_input)
async def update_release_input(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum="owner")
    if not ok:
        await state.clear()
        return
    release = (message.text or "").strip()
    if not RELEASE_RE.fullmatch(release):
        await render_input(
            message,
            "Нужен точный тег релиза вида vX.Y.Z.",
            reply_markup=_bot_updates_cancel(),
        )
        return

    client = _client()
    if client is None:
        await state.clear()
        await render_input(
            message,
            "Deploy Agent не настроен.",
            reply_markup=_bot_updates_back(),
        )
        return
    try:
        preflight = await client.preflight(release)
    except DeployControlError as exc:
        await render_input(
            message,
            f"🔴 Релиз отклонён на предварительной проверке: {exc.code or 'error'}.",
            reply_markup=_bot_updates_cancel(),
        )
        return

    await state.clear()
    lines = [
        "🤖 Проверка обновления бота",
        "",
        f"📦 Текущий релиз: {preflight.current_release}",
        f"🎯 Целевой релиз: {preflight.release}",
        f"🔖 Целевой SHA: {preflight.target_sha[:12]}",
        f"🧭 Направление: {_preflight_direction(preflight)}",
        "",
        "Примечания к релизу:",
        (preflight.notes or "нет примечаний к релизу")[:2400],
        "",
        "Развёртывание разрешено только для опубликованного тега из origin/main.",
        "Автоматического отката или повтора изменения нет.",
    ]
    if preflight.downgrade:
        rows = [
            [("⚠️ Подтвердить откат", f"admin:botupd:down:{release}")],
            [("✖ Отмена", "admin:botupd")],
        ]
    else:
        rows = [
            [("✅ Обновить бота", f"admin:botupd:run:{release}")],
            [("✖ Отмена", "admin:botupd")],
        ]
    await render_input(message, "\n".join(lines)[:3900], reply_markup=_keyboard(rows))


@bot_updates_router.callback_query(F.data.regexp(r"^admin:botupd:pre:v[0-9]+\.[0-9]+\.[0-9]+$"))
async def update_preflight(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    await call.answer("Проверяю релиз…")
    release = (call.data or "").rsplit(":", 1)[-1]
    client = _client()
    if client is None:
        await render_callback(call, "Deploy Agent не настроен.", reply_markup=_bot_updates_back())
        return
    try:
        preflight = await client.preflight(release)
    except DeployControlError as exc:
        await render_callback(
            call,
            f"🤖 Обновления бота\n\n🔴 Предварительная проверка завершилась ошибкой: {exc.code or 'error'}",
            reply_markup=_bot_updates_back(),
        )
        return

    lines = [
        "🤖 Проверка обновления бота",
        "",
        f"📦 Текущий релиз: {preflight.current_release}",
        f"🎯 Целевой релиз: {preflight.release}",
        f"🔖 Целевой SHA: {preflight.target_sha[:12]}",
        f"🧭 Направление: {_preflight_direction(preflight)}",
        "",
        "Примечания к релизу:",
        (preflight.notes or "нет примечаний к релизу")[:2400],
        "",
        "Развёртывание выполняется только через опубликованный тег и существующий deploy-release.sh.",
        "Автоматического отката или повтора изменения нет.",
    ]
    if preflight.downgrade:
        rows = [
            [("⚠️ Перейти к подтверждению отката", f"admin:botupd:down:{release}")],
            [("✖ Отмена", "admin:botupd")],
        ]
    else:
        rows = [
            [("✅ Обновить бота", f"admin:botupd:run:{release}")],
            [("✖ Отмена", "admin:botupd")],
        ]
    await render_callback(call, "\n".join(lines)[:3900], reply_markup=_keyboard(rows))


@bot_updates_router.callback_query(F.data.regexp(r"^admin:botupd:run:v[0-9]+\.[0-9]+\.[0-9]+$"))
async def update_run(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    await call.answer("Запускаю развёртывание…")
    release = (call.data or "").rsplit(":", 1)[-1]
    client = _client()
    if client is None:
        await render_callback(call, "Deploy Agent не настроен.", reply_markup=_bot_updates_back())
        return
    try:
        preflight = await client.preflight(release)
    except DeployControlError as exc:
        await render_callback(call, f"Предварительная проверка завершилась ошибкой: {exc.code or 'error'}", reply_markup=_bot_updates_back())
        return
    if preflight.downgrade:
        await render_callback(
            call,
            "Откат требует отдельного усиленного подтверждения.",
            reply_markup=_bot_updates_back(),
        )
        return
    await _dispatch(call, release, allow_downgrade=False)


@bot_updates_router.callback_query(F.data.regexp(r"^admin:botupd:down:v[0-9]+\.[0-9]+\.[0-9]+$"))
async def downgrade_start(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    release = (call.data or "").rsplit(":", 1)[-1]
    await state.clear()
    await state.set_state(BotUpdateStates.downgrade_phrase)
    await state.update_data(release=release)
    await call.answer()
    await render_callback(
        call,
        "⚠️ Откат версии бота\n\n"
        f"Для подтверждения отправь точную фразу:\nDOWNGRADE {release}\n\n"
        "Откат никогда не запускается автоматически.",
        reply_markup=_keyboard([[("✖ Отмена", "admin:botupd")]]),
    )


@bot_updates_router.message(BotUpdateStates.downgrade_phrase)
async def downgrade_phrase(message: Message, state: FSMContext):
    if not message.from_user:
        return
    ok, _ = await authorize_message(db, settings, message.from_user.id, minimum="owner")
    if not ok:
        await state.clear()
        return
    data = await state.get_data()
    release = str(data.get("release") or "")
    phrase = (message.text or "").strip()
    if phrase != f"DOWNGRADE {release}" or not _DOWNGRADE_PHRASE_RE.fullmatch(phrase):
        await render_input(
            message,
            f"Фраза не совпала. Для отката отправь ровно: DOWNGRADE {release}",
            reply_markup=_bot_updates_cancel(),
        )
        return

    client = _client()
    if client is None:
        await state.clear()
        await render_input(
            message,
            "Deploy Agent не настроен.",
            reply_markup=_bot_updates_back(),
        )
        return
    try:
        preflight = await client.preflight(release)
    except DeployControlError as exc:
        await state.clear()
        await render_input(
            message,
            f"Предварительная проверка завершилась ошибкой: {exc.code or 'error'}",
            reply_markup=_bot_updates_back(),
        )
        return
    if not preflight.downgrade:
        await state.clear()
        await render_input(
            message,
            "Направление больше не является откатом. Открой «Обновления бота» заново.",
            reply_markup=_bot_updates_back(),
        )
        return

    await state.clear()
    await render_input(
        message,
        f"✅ Откат до {release} подтверждён фразой. Запускаю развёртывание…",
    )
    await _dispatch_message(message, release, allow_downgrade=True)


@bot_updates_router.callback_query(F.data.regexp(r"^admin:botupd:op:[0-9a-f]{32}$"))
async def operation_status(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    await call.answer()
    operation_id = (call.data or "").rsplit(":", 1)[-1]
    client = _client()
    if client is None:
        await render_callback(call, "Deploy Agent не настроен.", reply_markup=_bot_updates_back())
        return
    try:
        op = await client.get_operation(operation_id)
    except DeployControlError as exc:
        await render_callback(call, f"Не удалось получить операцию: {exc.code or 'error'}", reply_markup=_bot_updates_back())
        return
    if op is None:
        await render_callback(call, "Операция не найдена.", reply_markup=_bot_updates_back())
        return
    await reconcile_deploy_jobs(wait_seconds=0)
    await render_callback(
        call,
        "🤖 Обновления бота\n\n" + _operation_text(op),
        reply_markup=_keyboard([
            [("🔄 Обновить статус", f"admin:botupd:op:{operation_id}")],
            [("⬅ Обновления бота", "admin:botupd")],
        ]),
    )


@bot_updates_router.callback_query(F.data == "admin:botupd:history")
async def update_history(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    await call.answer()
    client = _client()
    if client is None:
        await render_callback(call, "Deploy Agent не настроен.", reply_markup=_bot_updates_back())
        return
    try:
        history = await client.history()
    except DeployControlError as exc:
        await render_callback(call, f"История недоступна: {exc.code or 'error'}", reply_markup=_bot_updates_back())
        return

    lines = ["🤖 История обновлений бота", ""]
    if not history:
        lines.append("Операций пока нет.")
    for op in history[:12]:
        icon = "🟢" if op.state == "success" else "🔴" if op.state == "failed" else "🟡"
        lines.append(f"{icon} {op.release} · {_deploy_state_text(op.state)} · {op.operation_id[:8]}")
    await render_callback(call, "\n".join(lines), reply_markup=_bot_updates_back())


async def _ack_job(run_id: int) -> JobRunRecord | None:
    job = await db.get_job_run(run_id)
    if job is None or job.name != "bot.update" or job.status != "unknown":
        return None
    return job


@bot_updates_router.callback_query(F.data.regexp(r"^admin:botupd:ack:\d+$"))
async def update_ack_review(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    run_id = int((call.data or "").rsplit(":", 1)[-1])
    job = await _ack_job(run_id)
    if job is None:
        await render_callback(call, "Запуск больше не доступен для подтверждения.", reply_markup=_bot_updates_back())
        await call.answer()
        return
    existing = await db.get_bot_update_acknowledgment(run_id)
    if existing:
        await render_callback(call, f"Задание #{run_id}: уже рассмотрено Owner. Исход: unknown.", reply_markup=_bot_updates_back())
        await call.answer()
        return

    evidence = await correlate_deploy(job, _client())
    rows = [
        [(f"📝 {reason}", f"admin:botupd:ack:{run_id}:{code}")]
        for code, reason in REASON_LABELS.items()
    ]
    rows.append([("⬅ Обновления бота", "admin:botupd")])
    await render_callback(
        call,
        "\n".join([
            f"📋 Историческое задание bot.update #{run_id}",
            "Исход задания: 🟡 unknown (не изменяется)",
            "",
            *evidence.lines(),
            "",
            "Выбери основание рассмотрения. Это НЕ повторное обновление.",
        ]),
        reply_markup=_keyboard(rows),
    )
    await call.answer()


@bot_updates_router.callback_query(
    F.data.regexp(r"^admin:botupd:ack:\d+:(reviewed|recovered|insufficient)$")
)
async def update_ack_prepare(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    parts = (call.data or "").split(":")
    run_id, reason = int(parts[3]), parts[4]
    job = await _ack_job(run_id)
    existing = await db.get_bot_update_acknowledgment(run_id)
    if job is None or existing is not None:
        await render_callback(call, "Подтверждение недоступно: задание уже рассмотрено или изменилось.", reply_markup=_bot_updates_back())
        await call.answer()
        return
    evidence = await correlate_deploy(job, _client())
    await render_callback(
        call,
        "\n".join([
            f"⚠️ Подтвердить рассмотрение bot.update #{run_id}?",
            "",
            f"Основание: {REASON_LABELS[reason]}",
            *evidence.lines(),
            "",
            "Будет создана необратимая запись с аудитом.",
            "Исход unknown сохранится; новые ошибки останутся видимы.",
        ]),
        reply_markup=_keyboard([
            [("✅ Признать рассмотренным", f"admin:botupd:ack:{run_id}:{reason}:confirm")],
            [("✖ Отмена", f"admin:botupd:ack:{run_id}")],
        ]),
    )
    await call.answer()


@bot_updates_router.callback_query(
    F.data.regexp(r"^admin:botupd:ack:\d+:(reviewed|recovered|insufficient):confirm$")
)
async def update_ack_confirm(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok or not call.from_user:
        return
    parts = (call.data or "").split(":")
    run_id, reason = int(parts[3]), parts[4]
    job = await _ack_job(run_id)
    if job is None:
        await render_callback(call, "Исходное задание не найдено или уже изменилось.", reply_markup=_bot_updates_back())
        await call.answer()
        return
    # Always re-fetch GET-only evidence at the confirmation boundary.
    evidence = await correlate_deploy(job, _client())
    changed = await db.acknowledge_bot_update_unknown(
        run_id,
        actor_id=call.from_user.id,
        actor_username=call.from_user.username or "",
        reason_code=reason,
        evidence=evidence,
    )
    await render_callback(
        call,
        (
            f"✅ Исторический bot.update #{run_id} рассмотрен Owner."
            if changed else f"ℹ️ Задание #{run_id} уже подтверждено."
        ) + "\n\nИсход исходного задания: 🟡 unknown (сохранён).\n"
        "Новая ошибка с другим run ID продолжит появляться в Attention Center.",
        reply_markup=_bot_updates_back(),
    )
    await call.answer()
