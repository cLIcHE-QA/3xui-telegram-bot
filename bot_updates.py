"""Owner-only Safe Bot Self-Update UI and startup recovery."""
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


def _client() -> DeployControlClient | None:
    if not settings.deploy_agent_enabled:
        return None
    return DeployControlClient(settings.deploy_agent_url, settings.deploy_agent_token)


def _keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
        for row in rows
    ])


def _back() -> InlineKeyboardMarkup:
    return _keyboard([
        [("🔄 Обновить", "admin:botupd")],
        [("⬅ System", "admin:section:system")],
    ])


def _field(pattern: re.Pattern[str], details: str) -> str:
    match = pattern.search(details or "")
    return match.group(1) if match else ""


def _job_details(operation_id: str, release: str, *, allow_downgrade: bool) -> str:
    return (
        f"operation_id={operation_id}; release={release}; "
        f"allow_downgrade={1 if allow_downgrade else 0}; mutation_not_retried=true"
    )


def _operation_text(op: DeployOperation) -> str:
    labels = {
        "queued": "🟡 Операция поставлена в очередь.",
        "preflight": "🟡 Выполняется preflight.",
        "backup": "🟡 Создаётся deployment backup.",
        "building": "🟡 Собирается новый bot image.",
        "deploying": "🟡 Новый release разворачивается.",
        "verifying": "🟡 Выполняются post-deploy проверки.",
        "success": "🟢 Deployment успешно завершён и проверен.",
        "failed": "🔴 Deployment завершился ошибкой до подтверждённого успеха.",
        "unknown": "🟡 Итог deployment не удалось доказать. Автоповтор запрещён.",
    }
    lines = [
        labels.get(op.state, "🟡 Неизвестное состояние."),
        "",
        f"Release: {op.release}",
        f"Operation: {op.operation_id}",
        f"State: {op.state}",
    ]
    if op.current_release:
        lines.append(f"Observed production: {op.current_release}")
    if op.target_sha:
        lines.append(f"Target SHA: {op.target_sha[:12]}")
    if op.error_code:
        lines.append(f"Error: {op.error_code}")
    if op.allow_downgrade:
        lines.append("Downgrade: explicitly confirmed")
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
            "🤖 Bot Updates\n\n🔴 Deploy Agent не настроен.",
            reply_markup=_back(),
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
                    f"🤖 Bot Updates\n\n🔴 Deploy Agent отклонил операцию: {exc.code or 'error'}",
                    reply_markup=_back(),
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
                    "🤖 Bot Updates\n\n🟡 Ответ на deploy POST потерян, а operation journal пока недоступен. "
                    "Mutation повторно НЕ отправлялась.",
                    reply_markup=_back(),
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
            "🤖 Bot Updates\n\n"
            + _operation_text(op)
            + "\n\nПри переходе к deploying текущий bot container будет пересоздан. "
              "После старта новый bot восстановит итог только через operation journal.",
            reply_markup=_keyboard([
                [("📋 Статус", f"admin:botupd:op:{operation_id}")],
                [("⬅ Bot Updates", "admin:botupd")],
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
            "🤖 Bot Updates\n\n🟡 Локальная ошибка после подготовки операции. "
            "Автоматический повтор deployment запрещён.",
            reply_markup=_back(),
        )


async def _dispatch_message(
    message: Message,
    release: str,
    *,
    allow_downgrade: bool,
) -> None:
    client = _client()
    if client is None:
        await render_input(message, "Deploy Agent не настроен.")
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
                await render_input(message, f"🔴 Deploy Agent отклонил операцию: {exc.code or 'error'}")
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
                    "🟡 Ответ на deploy POST потерян; mutation повторно НЕ отправлялась.",
                )
                return

        await render_input(
            message,
            "🤖 Bot Update запущен.\n\n"
            + _operation_text(op)
            + "\n\nТекущий bot container может быть пересоздан. "
              "После старта итог восстановится из Deploy Agent journal; POST повторно не отправляется.",
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
            "🟡 Локальная ошибка после подготовки deployment. Автоматический повтор запрещён.",
        )


@bot_updates_router.callback_query(F.data == "admin:botupd")
async def updates_home(call: CallbackQuery, state: FSMContext):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    await state.clear()
    await call.answer()
    client = _client()
    if client is None:
        await render_callback(
            call,
            "🤖 Bot Updates\n\n"
            f"Current bot: {APP_VERSION}\n"
            "Deploy Agent: не настроен\n\n"
            "Установи restricted Deploy Agent на Master и добавь локальные "
            "DEPLOY_AGENT_URL/DEPLOY_AGENT_TOKEN. Docker socket и Git deploy key "
            "в bot container не требуются.",
            reply_markup=_keyboard([[("⬅ System", "admin:section:system")]]),
        )
        return

    await reconcile_deploy_jobs(wait_seconds=0)
    try:
        status, latest = await asyncio.gather(client.status(), client.latest_release())
    except DeployControlError as exc:
        await render_callback(
            call,
            "🤖 Bot Updates\n\n"
            f"Current bot: {APP_VERSION}\n"
            f"🔴 Deploy Agent недоступен: {exc.code or 'error'}",
            reply_markup=_back(),
        )
        return

    lines = [
        "🤖 Bot Updates",
        "",
        f"Current: {status.current_release or 'unknown'}",
        f"Bot: {status.bot_version or APP_VERSION}",
        f"Latest published: {latest}",
        f"Agent: {status.agent_version or 'unknown'}",
        f"Health: {status.health} · DB: {status.db} · 3x-ui: {status.connectivity}",
    ]
    if status.active_operation:
        lines += ["", f"Active operation: {status.active_operation}"]

    rows: list[list[tuple[str, str]]] = []
    if latest != status.current_release and not status.active_operation:
        rows.append([("🔍 Preflight latest", f"admin:botupd:pre:{latest}")])
    if not status.active_operation:
        rows.append([("📦 Выбрать published tag", "admin:botupd:choose")])
    rows.append([("📜 Update history", "admin:botupd:history")])
    rows.append([("🔄 Обновить", "admin:botupd")])
    rows.append([("⬅ System", "admin:section:system")])
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
        "🤖 Bot Updates\n\n"
        "Отправь точный published release tag вида vX.Y.Z. "
        "Deploy Agent примет только существующий tag, содержащийся в origin/main, "
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
        await render_input(message, "Нужен точный release tag вида vX.Y.Z.")
        return

    client = _client()
    if client is None:
        await state.clear()
        await render_input(message, "Deploy Agent не настроен.")
        return
    try:
        preflight = await client.preflight(release)
    except DeployControlError as exc:
        await render_input(
            message,
            f"🔴 Release/preflight отклонён: {exc.code or 'error'}.",
        )
        return

    await state.clear()
    lines = [
        "🤖 Bot Update preflight",
        "",
        f"Current: {preflight.current_release}",
        f"Target: {preflight.release}",
        f"Target SHA: {preflight.target_sha[:12]}",
        f"Direction: {'DOWNGRADE' if preflight.downgrade else 'upgrade'}",
        "",
        "Release notes:",
        (preflight.notes or "нет release notes")[:2400],
        "",
        "Deployment разрешён только для published tag из origin/main.",
        "Автоматического rollback/retry mutation нет.",
    ]
    if preflight.downgrade:
        rows = [
            [("⚠️ Подтвердить downgrade", f"admin:botupd:down:{release}")],
            [("✖ Отмена", "admin:botupd")],
        ]
    else:
        rows = [
            [("✅ Обновить bot", f"admin:botupd:run:{release}")],
            [("✖ Отмена", "admin:botupd")],
        ]
    await render_input(message, "\n".join(lines)[:3900], reply_markup=_keyboard(rows))


@bot_updates_router.callback_query(F.data.regexp(r"^admin:botupd:pre:v[0-9]+\.[0-9]+\.[0-9]+$"))
async def update_preflight(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    await call.answer("Проверяю release…")
    release = (call.data or "").rsplit(":", 1)[-1]
    client = _client()
    if client is None:
        await render_callback(call, "Deploy Agent не настроен.", reply_markup=_back())
        return
    try:
        preflight = await client.preflight(release)
    except DeployControlError as exc:
        await render_callback(
            call,
            f"🤖 Bot Updates\n\n🔴 Preflight failed: {exc.code or 'error'}",
            reply_markup=_back(),
        )
        return

    lines = [
        "🤖 Bot Update preflight",
        "",
        f"Current: {preflight.current_release}",
        f"Target: {preflight.release}",
        f"Target SHA: {preflight.target_sha[:12]}",
        f"Direction: {'DOWNGRADE' if preflight.downgrade else 'upgrade'}",
        "",
        "Release notes:",
        (preflight.notes or "нет release notes")[:2400],
        "",
        "Deployment выполняется только через published tag и existing deploy-release.sh.",
        "Автоматического rollback/retry mutation нет.",
    ]
    if preflight.downgrade:
        rows = [
            [("⚠️ Перейти к подтверждению downgrade", f"admin:botupd:down:{release}")],
            [("✖ Отмена", "admin:botupd")],
        ]
    else:
        rows = [
            [("✅ Обновить bot", f"admin:botupd:run:{release}")],
            [("✖ Отмена", "admin:botupd")],
        ]
    await render_callback(call, "\n".join(lines)[:3900], reply_markup=_keyboard(rows))


@bot_updates_router.callback_query(F.data.regexp(r"^admin:botupd:run:v[0-9]+\.[0-9]+\.[0-9]+$"))
async def update_run(call: CallbackQuery):
    ok, _ = await authorize_callback(db, settings, call, minimum="owner")
    if not ok:
        return
    await call.answer("Запускаю deployment…")
    release = (call.data or "").rsplit(":", 1)[-1]
    client = _client()
    if client is None:
        await render_callback(call, "Deploy Agent не настроен.", reply_markup=_back())
        return
    try:
        preflight = await client.preflight(release)
    except DeployControlError as exc:
        await render_callback(call, f"Preflight failed: {exc.code or 'error'}", reply_markup=_back())
        return
    if preflight.downgrade:
        await render_callback(
            call,
            "Downgrade требует отдельного усиленного подтверждения.",
            reply_markup=_back(),
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
        "⚠️ Downgrade bot\n\n"
        f"Для подтверждения отправь точную фразу:\nDOWNGRADE {release}\n\n"
        "Downgrade никогда не запускается автоматически.",
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
            f"Фраза не совпала. Для downgrade отправь ровно: DOWNGRADE {release}",
        )
        return

    client = _client()
    if client is None:
        await state.clear()
        await render_input(message, "Deploy Agent не настроен.")
        return
    try:
        preflight = await client.preflight(release)
    except DeployControlError as exc:
        await state.clear()
        await render_input(message, f"Preflight failed: {exc.code or 'error'}")
        return
    if not preflight.downgrade:
        await state.clear()
        await render_input(message, "Направление больше не является downgrade. Открой Bot Updates заново.")
        return

    await state.clear()
    await render_input(
        message,
        f"✅ Downgrade {release} подтверждён фразой. Запускаю deployment…",
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
        await render_callback(call, "Deploy Agent не настроен.", reply_markup=_back())
        return
    try:
        op = await client.get_operation(operation_id)
    except DeployControlError as exc:
        await render_callback(call, f"Operation lookup failed: {exc.code or 'error'}", reply_markup=_back())
        return
    if op is None:
        await render_callback(call, "Operation не найдена.", reply_markup=_back())
        return
    await reconcile_deploy_jobs(wait_seconds=0)
    await render_callback(
        call,
        "🤖 Bot Updates\n\n" + _operation_text(op),
        reply_markup=_keyboard([
            [("🔄 Обновить статус", f"admin:botupd:op:{operation_id}")],
            [("⬅ Bot Updates", "admin:botupd")],
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
        await render_callback(call, "Deploy Agent не настроен.", reply_markup=_back())
        return
    try:
        history = await client.history()
    except DeployControlError as exc:
        await render_callback(call, f"History unavailable: {exc.code or 'error'}", reply_markup=_back())
        return

    lines = ["🤖 Bot Update history", ""]
    if not history:
        lines.append("Операций пока нет.")
    for op in history[:12]:
        icon = "🟢" if op.state == "success" else "🔴" if op.state == "failed" else "🟡"
        lines.append(f"{icon} {op.release} · {op.state} · {op.operation_id[:8]}")
    await render_callback(call, "\n".join(lines), reply_markup=_back())
