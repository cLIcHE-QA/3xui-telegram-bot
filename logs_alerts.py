from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Iterable

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from admin_ui import render_callback, render_input
from admin_auth import authorize_callback
from audit import audit_from_call, audit_system
from backup_manager import BackupManager
from config import load_settings
from db import AlertRuleRecord, Database
from system_backup import SystemBackupService
from logging_setup import bot_log_path
from xui import XUIClient, XUIError

settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets)
logs_alerts_router = Router(name="logs_alerts")
LOG = logging.getLogger(__name__)

BOT_LOG = bot_log_path()
NGINX_LOG_DIR = Path("/app/log_sources/nginx")

RULE_LABELS = {
    "master_down": "Master / 3x-ui недоступен",
    "xray_down": "Xray не работает",
    "node_offline": "Node offline",
    "job_failed": "Background job failed",
    "disk_high": "Disk usage высокий",
    "backup_stale": "Backup устарел",
}


def monitoring_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Monitoring", callback_data="admin:section:monitoring")],
    ])


async def guard(call: CallbackQuery, *, minimum: str | None = None) -> bool:
    ok, _ = await authorize_callback(db, settings, call, minimum=minimum)
    return ok


def _tail_file(path: Path, count: int = 100) -> list[str]:
    count = max(1, min(500, int(count)))
    if not path.exists() or not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        return [line.rstrip("\n") for line in lines[-count:]]
    except OSError as exc:
        return [f"[read error] {type(exc).__name__}: {exc}"]


def _redact_line(line: str) -> str:
    value = str(line)
    value = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+", r"\1<redacted>", value)
    value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~-]{16,}", r"\1<redacted>", value)
    value = re.sub(r"(?i)((?:token|api[_-]?token|sub[_-]?id)\s*[=:]\s*)[^\s,&\"']+", r"\1<redacted>", value)
    value = re.sub(r"(?i)/(compat|clichegamesub|sub)/[A-Za-z0-9_-]{8,}", r"/\1/<redacted>", value)
    value = re.sub(r"\b\d{5,12}:[A-Za-z0-9_-]{20,}\b", "<telegram-token>", value)
    return value


def _filter_lines(lines: Iterable[str], level: str) -> list[str]:
    values = [str(x) for x in lines]
    key = (level or "all").lower()
    if key == "all":
        return values
    if key == "error":
        needles = ("error", "failed", "fatal", "panic", "exception", "critical")
    elif key == "warning":
        needles = ("warn", "warning", "error", "failed", "fatal", "panic", "exception", "critical")
    else:
        needles = (key,)
    return [line for line in values if any(n in line.lower() for n in needles)]


def _excerpt(lines: list[str], *, max_chars: int = 3350) -> str:
    if not lines:
        return "— записей нет"
    selected: list[str] = []
    used = 0
    for line in reversed(lines):
        clean = _redact_line(line).replace("\x00", "")[:1200]
        extra = len(clean) + 1
        if selected and used + extra > max_chars:
            break
        if not selected and extra > max_chars:
            clean = clean[-max_chars:]
            extra = len(clean)
        selected.append(clean)
        used += extra
    selected.reverse()
    prefix = "…\n" if len(selected) < len(lines) else ""
    return prefix + "\n".join(selected)


def _log_controls(source: str, count: int, level: str, *, node_id: int | None = None) -> InlineKeyboardMarkup:
    base = f"admin:logs:view:{source}"
    if node_id is not None:
        base = f"admin:logs:nview:{node_id}:{source}"
    rows = [
        [
            InlineKeyboardButton(text=("✅ " if count == 50 else "📄 ") + "50", callback_data=f"{base}:50:{level}"),
            InlineKeyboardButton(text=("✅ " if count == 200 else "📄 ") + "200", callback_data=f"{base}:200:{level}"),
        ],
        [
            InlineKeyboardButton(text=("✅ " if level == "all" else "📋 ") + "ALL", callback_data=f"{base}:{count}:all"),
            InlineKeyboardButton(text=("✅ " if level == "warning" else "⚠️ ") + "WARN+", callback_data=f"{base}:{count}:warning"),
            InlineKeyboardButton(text=("✅ " if level == "error" else "❌ ") + "ERROR", callback_data=f"{base}:{count}:error"),
        ],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"{base}:{count}:{level}")],
        [InlineKeyboardButton(text="⬅ Logs", callback_data="admin:logs")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _logs_menu(node_count: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🤖 Bot", callback_data="admin:logs:view:bot:50:all"),
            InlineKeyboardButton(text="🧩 3x-ui", callback_data="admin:logs:view:panel:50:warning"),
        ],
        [
            InlineKeyboardButton(text="⚡ Xray", callback_data="admin:logs:view:xray:50:warning"),
            InlineKeyboardButton(text="🛡 AWG", callback_data="admin:logs:view:awg:50:all"),
        ],
        [
            InlineKeyboardButton(text="🌐 Nginx error", callback_data="admin:logs:view:ngerr:50:all"),
            InlineKeyboardButton(text="📨 Nginx access", callback_data="admin:logs:view:ngacc:50:all"),
        ],
        [InlineKeyboardButton(text="🖥 System journal", callback_data="admin:logs:view:syslog:50:warning")],
    ]
    if node_count:
        rows.append([InlineKeyboardButton(text=f"🌍 Node logs ({node_count})", callback_data="admin:logs:nodes")])
    rows.append([InlineKeyboardButton(text="⬅ Monitoring", callback_data="admin:section:monitoring")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _master_log_lines(source: str, count: int, level: str) -> tuple[str, list[str]]:
    fetch_count = min(500, max(count, 200 if level != "all" else count))
    if source == "bot":
        return "🤖 Bot log", _filter_lines(_tail_file(BOT_LOG, fetch_count), level)
    if source == "panel":
        api_level = "info" if level == "all" else level
        return "🧩 3x-ui panel log", await xui.panel_logs(fetch_count, level=api_level, syslog=False)
    if source == "syslog":
        api_level = "info" if level == "all" else level
        return "🖥 System journal", await xui.panel_logs(fetch_count, level=api_level, syslog=True)
    if source == "xray":
        lines = await xui.xray_logs(fetch_count)
        return "⚡ Xray log", _filter_lines(lines, level)
    if source == "awg":
        lines = await xui.amneziawg_logs(fetch_count)
        return "🛡 AmneziaWG log", _filter_lines(lines, level)
    if source == "ngerr":
        path = NGINX_LOG_DIR / "error.log"
        return "🌐 Nginx error.log", _filter_lines(_tail_file(path, fetch_count), level)
    if source == "ngacc":
        path = NGINX_LOG_DIR / "access.log"
        return "📨 Nginx access.log", _filter_lines(_tail_file(path, fetch_count), level)
    raise ValueError("unknown log source")


@logs_alerts_router.callback_query(F.data == "admin:logs")
async def logs_home(call: CallbackQuery):
    if not await guard(call):
        return
    try:
        nodes = await xui.nodes_list()
    except XUIError:
        nodes = []
    direct = sum(1 for n in nodes if system_backup.direct_client_for(n.name, getattr(n, "id", None)) is not None)
    text = (
        "📜 Logs\n\n"
        "Просмотр последних строк без shell-доступа. Фильтры применяются только к выдаче; "
        "логи не удаляются и настройки сервисов не меняются.\n\n"
        "Node logs доступны для нод, у которых настроен direct admin token (NODE_BACKUP_TARGETS)."
    )
    await render_callback(call, text, reply_markup=_logs_menu(direct))
    await call.answer()


@logs_alerts_router.callback_query(F.data.regexp(r"^admin:logs:view:[a-z]+:(50|200):(all|warning|error)$"))
async def master_log_view(call: CallbackQuery):
    if not await guard(call):
        return
    parts = (call.data or "").split(":")
    source, count, level = parts[3], int(parts[4]), parts[5]
    await call.answer("Читаю лог…")
    try:
        title, lines = await _master_log_lines(source, count, level)
    except (XUIError, OSError, ValueError) as exc:
        await render_callback(call, 
            f"📜 Logs\n\n🔴 {type(exc).__name__}: {str(exc)[:500]}",
            reply_markup=_log_controls(source, count, level),
        )
        return
    shown = lines[-count:]
    await render_callback(call, 
        f"{title}\nFilter: {level.upper()} · last {count}\n\n{_excerpt(shown)}",
        reply_markup=_log_controls(source, count, level),
    )


@logs_alerts_router.callback_query(F.data == "admin:logs:nodes")
async def node_logs_list(call: CallbackQuery):
    if not await guard(call):
        return
    try:
        nodes = await xui.nodes_list()
    except XUIError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    rows: list[list[InlineKeyboardButton]] = []
    for node in nodes:
        if system_backup.direct_client_for(node.name, getattr(node, "id", None)) is not None:
            icon = "🟢" if node.enable and node.status == "online" else "🔴"
            rows.append([InlineKeyboardButton(text=f"{icon} {node.name}", callback_data=f"admin:logs:node:{node.id}")])
    if not rows:
        rows.append([InlineKeyboardButton(text="⚠️ direct tokens не настроены", callback_data="admin:logs")])
    rows.append([InlineKeyboardButton(text="⬅ Logs", callback_data="admin:logs")])
    await render_callback(call, "🌍 Node logs\n\nВыбери ноду:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@logs_alerts_router.callback_query(F.data.regexp(r"^admin:logs:node:\d+$"))
async def node_logs_sources(call: CallbackQuery):
    if not await guard(call):
        return
    node_id = int((call.data or "").rsplit(":", 1)[-1])
    try:
        node = await xui.node_get(node_id)
    except XUIError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    if system_backup.direct_client_for(node.name, getattr(node, "id", None)) is None:
        await call.answer("Direct admin token не настроен", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧩 3x-ui", callback_data=f"admin:logs:nview:{node_id}:panel:50:warning"),
            InlineKeyboardButton(text="⚡ Xray", callback_data=f"admin:logs:nview:{node_id}:xray:50:warning"),
        ],
        [InlineKeyboardButton(text="🛡 AmneziaWG", callback_data=f"admin:logs:nview:{node_id}:awg:50:all")],
        [InlineKeyboardButton(text="⬅ Node logs", callback_data="admin:logs:nodes")],
    ])
    await render_callback(call, f"📜 Logs · {node.name}\n\nВыбери источник:", reply_markup=kb)
    await call.answer()


@logs_alerts_router.callback_query(F.data.regexp(r"^admin:logs:nview:\d+:(panel|xray|awg):(50|200):(all|warning|error)$"))
async def node_log_view(call: CallbackQuery):
    if not await guard(call):
        return
    parts = (call.data or "").split(":")
    node_id, source, count, level = int(parts[3]), parts[4], int(parts[5]), parts[6]
    try:
        node = await xui.node_get(node_id)
        client = system_backup.direct_client_for(node.name, getattr(node, "id", None))
        if client is None:
            raise RuntimeError("direct admin token is not configured")
        fetch_count = min(500, max(count, 200 if level != "all" else count))
        if source == "panel":
            lines = await client.panel_logs(fetch_count, level="info" if level == "all" else level)
            title = f"🧩 3x-ui · {node.name}"
        elif source == "xray":
            lines = _filter_lines(await client.xray_logs(fetch_count), level)
            title = f"⚡ Xray · {node.name}"
        else:
            lines = _filter_lines(await client.amneziawg_logs(fetch_count), level)
            title = f"🛡 AmneziaWG · {node.name}"
    except Exception as exc:
        await render_callback(call, 
            f"📜 Node logs\n\n🔴 {type(exc).__name__}: {str(exc)[:500]}",
            reply_markup=_log_controls(source, count, level, node_id=node_id),
        )
        await call.answer()
        return
    await render_callback(call, 
        f"{title}\nFilter: {level.upper()} · last {count}\n\n{_excerpt(lines[-count:])}",
        reply_markup=_log_controls(source, count, level, node_id=node_id),
    )
    await call.answer()


def _rule_text(rule: AlertRuleRecord) -> str:
    label = RULE_LABELS.get(rule.code, rule.code)
    state = "🟢 ON" if rule.enabled else "⚪ OFF"
    if rule.code == "disk_high":
        return f"{state} {label} ≥ {rule.threshold}%"
    if rule.code == "backup_stale":
        return f"{state} {label} ≥ {rule.threshold}h"
    return f"{state} {label}"


def _alerts_keyboard(rules: list[AlertRuleRecord]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for rule in rules:
        rows.append([InlineKeyboardButton(
            text=("🔕 " if rule.enabled else "🔔 ") + RULE_LABELS.get(rule.code, rule.code),
            callback_data=f"admin:alerts:toggle:{rule.code}",
        )])
    disk = next((r for r in rules if r.code == "disk_high"), None)
    backup = next((r for r in rules if r.code == "backup_stale"), None)
    if disk:
        rows.append([
            InlineKeyboardButton(text=f"💽 Disk {v}%" + (" ✓" if disk.threshold == v else ""), callback_data=f"admin:alerts:disk:{v}")
            for v in (80, 85, 90, 95)
        ])
    if backup:
        rows.append([
            InlineKeyboardButton(text=f"💾 {v}h" + (" ✓" if backup.threshold == v else ""), callback_data=f"admin:alerts:backup:{v}")
            for v in (24, 36, 48, 72)
        ])
    rows += [
        [InlineKeyboardButton(text="🔍 Проверить сейчас", callback_data="admin:alerts:check")],
        [InlineKeyboardButton(text="⬅ Monitoring", callback_data="admin:section:monitoring")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_alerts_view(call: CallbackQuery) -> None:
    rules = await db.list_alert_rules()
    active = await db.list_alert_states(active_only=True)
    lines = ["🚨 Alerts", "", "Rules:"] + [_rule_text(r) for r in rules]
    lines += ["", f"Active incidents: {len(active)}"]
    if active:
        for item in active[:12]:
            lines.append(f"🔴 {RULE_LABELS.get(item.code, item.code)} · {item.target} · {item.last_value}")
        if len(active) > 12:
            lines.append(f"… ещё {len(active) - 12}")
    else:
        lines.append("✅ Активных инцидентов нет")
    lines += ["", "Проверка выполняется автоматически примерно раз в 5 минут. Уведомления повторяются только после cooldown."]
    await render_callback(call, "\n".join(lines), reply_markup=_alerts_keyboard(rules))


@logs_alerts_router.callback_query(F.data == "admin:alerts")
async def alerts_view(call: CallbackQuery):
    if not await guard(call):
        return
    await _send_alerts_view(call)
    await call.answer()


@logs_alerts_router.callback_query(F.data.regexp(r"^admin:alerts:toggle:[a-z_]+$"))
async def alert_toggle(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    code = (call.data or "").rsplit(":", 1)[-1]
    rule = await db.get_alert_rule(code)
    if not rule:
        await call.answer("Rule not found", show_alert=True)
        return
    enabled = not bool(rule.enabled)
    await db.set_alert_rule_enabled(code, enabled)
    await audit_from_call(
        db, call, "alerts.rule.toggle", target_type="alert_rule", target_id=code,
        details=f"enabled={enabled}",
    )
    await call.answer("Изменено")
    await _send_alerts_view(call)


@logs_alerts_router.callback_query(F.data.regexp(r"^admin:alerts:disk:(80|85|90|95)$"))
async def alert_disk_threshold(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    threshold = int((call.data or "").rsplit(":", 1)[-1])
    await db.set_alert_rule_threshold("disk_high", threshold)
    await audit_from_call(db, call, "alerts.rule.threshold", target_type="alert_rule", target_id="disk_high", details=f"threshold={threshold}")
    await call.answer(f"Disk threshold: {threshold}%")
    await _send_alerts_view(call)


@logs_alerts_router.callback_query(F.data.regexp(r"^admin:alerts:backup:(24|36|48|72)$"))
async def alert_backup_threshold(call: CallbackQuery):
    if not await guard(call, minimum="admin"):
        return
    threshold = int((call.data or "").rsplit(":", 1)[-1])
    await db.set_alert_rule_threshold("backup_stale", threshold)
    await audit_from_call(db, call, "alerts.rule.threshold", target_type="alert_rule", target_id="backup_stale", details=f"hours={threshold}")
    await call.answer(f"Backup threshold: {threshold}h")
    await _send_alerts_view(call)


async def _recipients() -> list[int]:
    ids = set(int(x) for x in settings.admin_telegram_ids)
    try:
        for admin in await db.list_administrators():
            if admin.enabled and admin.role in {"owner", "admin"}:
                ids.add(int(admin.telegram_id))
    except Exception:
        LOG.exception("Could not load alert recipients")
    return sorted(ids)


async def _set_incident(bot: Bot | None, *, code: str, target: str, active: bool, value: str, notify: bool) -> None:
    rule = await db.get_alert_rule(code)
    if not rule or not rule.enabled:
        # Keep state resolved while the rule is disabled.
        await db.update_alert_state(code=code, target=target, active=False, value=value)
        return
    previous = await db.get_alert_state(code, target)
    now = int(time.time())
    should_alert = active and (
        previous is None
        or not previous.active
        or now - int(previous.last_notified or 0) >= max(60, int(rule.cooldown_sec or 0))
    )
    should_recover = bool(previous and previous.active and not active and previous.last_notified)
    notified_at = now if (should_alert or should_recover) and notify and bot is not None else None
    await db.update_alert_state(
        code=code, target=target, active=active, value=value, notified_at=notified_at,
    )
    transitioned = bool(active and previous is None) or bool(previous and bool(previous.active) != bool(active))
    if transitioned:
        try:
            await audit_system(
                db,
                "alerts.incident.open" if active else "alerts.incident.recover",
                target_type="alert", target_id=f"{code}:{target}", details=value, success=not active,
            )
        except Exception:
            LOG.exception("Could not audit alert transition %s/%s", code, target)
    if not notify or bot is None or not (should_alert or should_recover):
        return
    if should_alert:
        message = f"🚨 {RULE_LABELS.get(code, code)}\nTarget: {target}\n{value}"
    else:
        message = f"✅ RECOVERED: {RULE_LABELS.get(code, code)}\nTarget: {target}\n{value}"
    for admin_id in await _recipients():
        try:
            await bot.send_message(admin_id, message)
        except Exception:
            LOG.exception("Could not send alert to admin %s", admin_id)


async def alert_check_once(bot: Bot | None = None, *, notify: bool = True) -> list[str]:
    """Evaluate operational alert rules. Returns a short human-readable result list."""
    results: list[str] = []
    rules = {r.code: r for r in await db.list_alert_rules()}

    master_ok = True
    status: dict = {}
    try:
        status = await xui.server_status()
        await _set_incident(bot, code="master_down", target=settings.master_name, active=False, value="3x-ui API reachable", notify=notify)
        results.append("✅ Master API")
    except Exception as exc:
        master_ok = False
        value = f"{type(exc).__name__}: {str(exc)[:240]}"
        await _set_incident(bot, code="master_down", target=settings.master_name, active=True, value=value, notify=notify)
        results.append("🔴 Master API")

    if master_ok:
        xray = status.get("xray") if isinstance(status.get("xray"), dict) else {}
        xray_state = str(xray.get("state") or "unknown").lower()
        xray_bad = xray_state not in {"running", "started", "online"}
        await _set_incident(bot, code="xray_down", target=settings.master_name, active=xray_bad, value=f"state={xray_state}", notify=notify)
        results.append(("🔴" if xray_bad else "✅") + f" Xray {xray_state}")

        disk = status.get("disk") if isinstance(status.get("disk"), dict) else {}
        total = int(disk.get("total") or 0)
        used = int(disk.get("current") or 0)
        pct = (used * 100 / total) if total else 0.0
        disk_rule = rules.get("disk_high")
        disk_bad = bool(total and disk_rule and pct >= disk_rule.threshold)
        await _set_incident(bot, code="disk_high", target=settings.master_name, active=disk_bad, value=f"disk={pct:.1f}%", notify=notify)
        results.append(("🔴" if disk_bad else "✅") + f" Disk {pct:.1f}%")

    try:
        nodes = await xui.nodes_list()
        seen_targets: set[str] = set()
        for node in nodes:
            target = node.name or f"node-{node.id}"
            seen_targets.add(target)
            offline = bool(node.enable and node.status != "online")
            await _set_incident(bot, code="node_offline", target=target, active=offline, value=f"status={node.status}; enabled={node.enable}", notify=notify)
            if node.enable and node.status == "online":
                state = (node.xray_state or "unknown").lower()
                xray_bad = state not in {"running", "started", "online"}
                await _set_incident(bot, code="xray_down", target=target, active=xray_bad, value=f"state={state}", notify=notify)

                direct = system_backup.direct_client_for(target)
                if direct is not None:
                    try:
                        remote = await direct.server_status()
                        remote_disk = remote.get("disk") if isinstance(remote.get("disk"), dict) else {}
                        total = int(remote_disk.get("total") or 0)
                        used = int(remote_disk.get("current") or 0)
                        pct = (used * 100 / total) if total else 0.0
                        disk_rule = rules.get("disk_high")
                        disk_bad = bool(total and disk_rule and pct >= disk_rule.threshold)
                        await _set_incident(bot, code="disk_high", target=target, active=disk_bad, value=f"disk={pct:.1f}%", notify=notify)
                    except Exception as exc:
                        LOG.warning("Node disk check failed for %s: %s", target, exc)
            else:
                await _set_incident(bot, code="xray_down", target=target, active=False, value="node offline/disabled", notify=notify)
                await _set_incident(bot, code="disk_high", target=target, active=False, value="node offline/disabled", notify=notify)

        # Resolve incidents belonging to nodes that were removed from the master.
        for state in await db.list_alert_states(active_only=True):
            if state.target == settings.master_name or state.target in seen_targets:
                continue
            if state.code in {"node_offline", "xray_down", "disk_high"}:
                await _set_incident(bot, code=state.code, target=state.target, active=False, value="node no longer registered", notify=notify)

        results.append(f"✅ Nodes checked: {len(nodes)}")
    except Exception as exc:
        results.append(f"⚠️ Nodes check: {type(exc).__name__}")

    # Alert on the latest state of each background job. A later successful run
    # automatically resolves an earlier failed incident for the same job name.
    try:
        history = await db.list_job_runs(limit=50)
        latest_by_name = {}
        for run in history:
            latest_by_name.setdefault(run.name, run)
        for name, run in latest_by_name.items():
            failed = (run.status or "").lower() == "failed"
            value = f"status={run.status}; {run.details[:260]}"
            await _set_incident(bot, code="job_failed", target=name, active=failed, value=value, notify=notify)
        results.append(f"✅ Jobs checked: {len(latest_by_name)}")
    except Exception as exc:
        results.append(f"⚠️ Jobs check: {type(exc).__name__}")

    backup_rule = rules.get("backup_stale")
    if backup_rule and settings.backup_enabled:
        latest = backup_manager.latest_backup()
        if latest:
            age_h = max(0.0, (time.time() - latest.created_at.timestamp()) / 3600)
            stale = age_h >= backup_rule.threshold
            value = f"last backup {age_h:.1f}h ago"
        else:
            stale = True
            value = "no full backup found"
        await _set_incident(bot, code="backup_stale", target=settings.master_name, active=stale, value=value, notify=notify)
        results.append(("🔴" if stale else "✅") + f" Backup: {value}")
    else:
        await db.update_alert_state(
            code="backup_stale", target=settings.master_name, active=False, value="automatic backup disabled"
        )

    return results


@logs_alerts_router.callback_query(F.data == "admin:alerts:check")
async def alert_manual_check(call: CallbackQuery):
    if not await guard(call):
        return
    await call.answer("Проверяю…")
    results = await alert_check_once(None, notify=False)
    await audit_from_call(db, call, "alerts.check", target_type="monitoring", details="; ".join(results)[:1400])
    await render_callback(call, "🚨 Alert check\n\n" + "\n".join(results), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Alerts", callback_data="admin:alerts")]
    ]))


async def alert_monitor_loop(bot: Bot) -> None:
    await asyncio.sleep(15)
    while True:
        try:
            await alert_check_once(bot, notify=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOG.exception("Alert monitor failed")
            try:
                await audit_system(db, "alerts.monitor", target_type="monitoring", details=f"{type(exc).__name__}: {exc}", success=False)
            except Exception:
                LOG.exception("Could not write alert monitor audit")
        await asyncio.sleep(300)
