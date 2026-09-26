from __future__ import annotations

import asyncio
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from admin_auth import authorize_callback
from admin_ui import render_callback
from backup_manager import BackupManager
from config import load_settings
from inbound_policy import is_managed_inbound as inbound_is_managed
from db import Database
from node_ui import (
    duration_text,
    master_detail_keyboard,
    node_display_name,
    node_status_icon,
    xray_icon,
    xray_state_text,
)
from version_api import VersionAPIError
from xui import NodeInfo, XUIClient, XUIError


settings = load_settings()
db = Database(settings.db_path)
xui = XUIClient(settings.panel_url, settings.panel_api_token, settings.verify_tls)
backup_manager = BackupManager(
    settings.db_path,
    settings.backup_dir,
    settings.backup_keep,
)

system_admin_router = Router(name="system_admin")


def public_health_url(template: str) -> str | None:
    value = (template or "").strip()
    if not value:
        return None
    try:
        parts = urlsplit(value.format(sub_id="health-probe"))
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, "/healthz", "", ""))


async def check_http(url: str, *, verify_tls: bool = True) -> tuple[bool, str]:
    timeout = aiohttp.ClientTimeout(total=6)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url,
                ssl=None if verify_tls else False,
                allow_redirects=True,
            ) as resp:
                body = (await resp.text()).strip()
                if resp.status == 200:
                    return True, body[:80] or "HTTP 200"
                return False, f"HTTP {resp.status}"
    except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as exc:
        return False, type(exc).__name__


def human_bytes(value: int) -> str:
    n = int(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return "0 B"


def usage_line(label: str, used: int, total: int) -> str:
    pct = (used / total * 100) if total else 0
    return f"{label}: {human_bytes(used)} / {human_bytes(total)} ({pct:.0f}%)"


async def _guard(call: CallbackQuery) -> bool:
    ok, _ = await authorize_callback(db, settings, call)
    return ok


@system_admin_router.callback_query(F.data == "admin:master")
async def admin_master_detail(call: CallbackQuery):
    if not await _guard(call):
        return
    await call.answer("Проверяю Master…")

    local_url = f"http://127.0.0.1:{settings.subscription_proxy_port}/healthz"
    public_url = public_health_url(settings.compat_subscription_url_template)
    local_task = asyncio.create_task(check_http(local_url, verify_tls=False))
    public_task = (
        asyncio.create_task(check_http(public_url, verify_tls=settings.verify_tls))
        if public_url
        else None
    )

    status = None
    inbounds = None
    api_error = None
    try:
        status = await xui.server_status()
        inbounds = await xui.inbound_options()
    except XUIError as exc:
        api_error = str(exc)

    local_ok, local_detail = await local_task
    if public_task:
        public_ok, public_detail = await public_task
    else:
        public_ok, public_detail = False, "COMPAT URL не настроен"

    lines = [f"{settings.master_flag} {settings.master_name}"]
    lines.append(
        "🟢 В сети · 3x-ui API"
        if status is not None
        else f"🔴 Не в сети · 3x-ui API — {(api_error or 'неизвестная ошибка')[:160]}"
    )

    if status:
        try:
            panel_info = await xui.get_panel_update_info()
            panel_version = str(
                panel_info.get("currentVersion") or "недоступно"
            )
        except VersionAPIError:
            panel_version = "недоступно"
        lines.append(f"3x-ui: {panel_version}")

        xray = status.get("xray") or {}
        xray_state = str(xray.get("state") or "unknown").lower()
        xray_ok = xray_state in {"running", "started", "online"}
        xray_version = str(xray.get("version") or "")
        lines.append(
            f"{'🟢' if xray_ok else '🔴'} Xray: {xray_state_text(xray_state)}"
            + (f" {xray_version}" if xray_version else "")
        )

        cpu = status.get("cpu")
        if cpu is not None:
            lines.append(f"🧮 CPU: {float(cpu):.1f}%")
        mem = status.get("mem") or {}
        if mem.get("total"):
            lines.append(
                usage_line(
                    "🧠 RAM",
                    int(mem.get("current") or 0),
                    int(mem["total"]),
                )
            )
        disk = status.get("disk") or {}
        if disk.get("total"):
            lines.append(
                usage_line(
                    "💽 Диск",
                    int(disk.get("current") or 0),
                    int(disk["total"]),
                )
            )
        if status.get("uptime") is not None:
            lines.append(
                f"⏱ Время работы: {duration_text(int(status.get('uptime') or 0))}"
            )

    lines.append(
        f"{'🟢' if local_ok else '🔴'} Прокси подписок"
        + ("" if local_ok else f" — {local_detail}")
    )
    lines.append(
        f"{'🟢' if public_ok else '🔴'} Публичная подписка"
        + ("" if public_ok else f" — {public_detail}")
    )

    if inbounds is not None:
        managed = [item for item in inbounds if inbound_is_managed(settings, item)]
        enabled = sum(1 for item in managed if item.enable)
        lines.append(f"🌐 Inbound'ы: {enabled}/{len(managed)} включено")

    users = await db.list_users()
    lines.append(f"👥 Пользователей в БД бота: {len(users)}")
    latest = await asyncio.to_thread(backup_manager.latest_backup)
    if latest:
        lines.append(
            "💾 Резервная копия: "
            + latest.created_at.strftime("%Y-%m-%d %H:%M UTC")
            + f" ({human_bytes(latest.size)})"
        )
    else:
        lines.append("⚠️ Резервная копия: ещё не создана")

    await render_callback(
        call,
        "\n".join(lines),
        reply_markup=master_detail_keyboard(),
    )


@system_admin_router.callback_query(F.data == "admin:health")
async def admin_health(call: CallbackQuery):
    if not await _guard(call):
        return

    await call.answer("Проверяю…")

    local_url = f"http://127.0.0.1:{settings.subscription_proxy_port}/healthz"
    public_url = public_health_url(settings.compat_subscription_url_template)

    local_task = asyncio.create_task(check_http(local_url, verify_tls=False))
    public_task = (
        asyncio.create_task(check_http(public_url, verify_tls=settings.verify_tls))
        if public_url
        else None
    )

    inbounds = None
    server_status = None
    nodes: list[NodeInfo] = []
    nodes_error = None
    xui_error = None

    try:
        inbounds = await xui.inbound_options()
    except XUIError as exc:
        xui_error = str(exc)

    try:
        server_status = await xui.server_status()
    except XUIError as exc:
        if xui_error is None:
            xui_error = str(exc)

    try:
        nodes = await xui.nodes_list()
    except XUIError as exc:
        nodes_error = str(exc)
        nodes = []

    local_ok, local_detail = await local_task
    if public_task:
        public_ok, public_detail = await public_task
    else:
        public_ok, public_detail = False, "COMPAT URL не настроен"

    users = await db.list_users()
    lines = [
        "🩺 Состояние системы",
        "",
        f"{settings.master_flag} {settings.master_name}",
    ]

    if inbounds is not None or server_status is not None:
        lines.append("🟢 3x-ui API / маршрут панели")
    else:
        detail = (xui_error or "неизвестная ошибка")[:160]
        lines.append(f"🔴 3x-ui API / маршрут панели — {detail}")

    if server_status:
        xray_status = server_status.get("xray") or {}
        xray_state = str(xray_status.get("state") or "unknown").lower()
        xray_ok = xray_state in {"running", "started", "online"}
        xray_version = str(xray_status.get("version") or "")
        lines.append(
            f"{'🟢' if xray_ok else '🔴'} Xray: {xray_state_text(xray_state)}"
            + (f" {xray_version}" if xray_version else "")
        )

        awg = server_status.get("amneziawg") or {}
        if awg.get("configured"):
            lines.append(
                f"{'🟢' if awg.get('running') else '🔴'} Ядро AmneziaWG"
            )

        cpu = server_status.get("cpu")
        if cpu is not None:
            lines.append(f"🧮 CPU: {float(cpu):.1f}%")
        mem = server_status.get("mem") or {}
        if mem.get("total"):
            lines.append(
                usage_line(
                    "🧠 RAM",
                    int(mem.get("current") or 0),
                    int(mem["total"]),
                )
            )
        disk = server_status.get("disk") or {}
        if disk.get("total"):
            lines.append(
                usage_line(
                    "💽 Диск",
                    int(disk.get("current") or 0),
                    int(disk["total"]),
                )
            )
        if server_status.get("uptime") is not None:
            lines.append(
                f"⏱ Время работы: {duration_text(int(server_status.get('uptime') or 0))}"
            )

    lines.append(
        f"{'🟢' if local_ok else '🔴'} Прокси подписок (локально)"
        + ("" if local_ok else f" — {local_detail}")
    )
    lines.append(
        f"{'🟢' if public_ok else '🔴'} Подписка через nginx/TLS"
        + ("" if public_ok else f" — {public_detail}")
    )

    if inbounds is not None:
        managed = sorted(
            (item for item in inbounds if inbound_is_managed(settings, item)),
            key=lambda item: (item.port, item.protocol, item.id),
        )
        lines += ["", "Inbound'ы Master:"]
        if managed:
            for item in managed:
                icon = "🟢" if item.enable else "🔴"
                lines.append(
                    f"{icon} {item.port} {item.protocol.upper()} — {item.remark}"
                )
        else:
            lines.append("⚪ Нет inbound'ов после применённых фильтров")

    lines += ["", "Ноды"]
    if nodes_error:
        lines.append(f"🔴 API нод — {nodes_error[:180]}")
    elif nodes:
        for node in nodes[:20]:
            icon = node_status_icon(node)
            xicon = xray_icon(node)
            node_line = (
                f"{icon} {node_display_name(node.name)} · {xicon} Xray · "
                f"🧮 CPU {node.cpu_pct:.0f}% · 🧠 RAM {node.mem_pct:.0f}%"
            )
            if node.latency_ms:
                node_line += f" · 📶 {node.latency_ms} ms"
            lines.append(node_line)
            lines.append(
                f"   👥 Клиентов {node.client_count} · 📡 В сети {node.online_count} · "
                f"🌐 Inbound'ов {node.inbound_count} · ⏱ Время работы {duration_text(node.uptime_secs)}"
            )
        if len(nodes) > 20:
            lines.append(f"… ещё {len(nodes) - 20}")
    else:
        lines.append("⚪ Удалённые ноды не зарегистрированы")

    lines += ["", f"👥 Пользователей в БД бота: {len(users)}"]
    latest_backup = await asyncio.to_thread(backup_manager.latest_backup)
    if latest_backup:
        lines.append(
            "💾 Последняя резервная копия: "
            + latest_backup.created_at.strftime("%Y-%m-%d %H:%M UTC")
            + f" ({human_bytes(latest_backup.size)})"
        )
    else:
        lines.append("⚠️ Резервная копия: ещё не создана")

    if settings.node_backup_targets:
        lines.append(
            f"💾 Резервные копии нод настроены: {len(settings.node_backup_targets)}"
        )
    elif nodes:
        lines.append("⚠️ Резервные копии БД нод: не настроены")

    await render_callback(
        call,
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:health")],
            [InlineKeyboardButton(text="⬅ Мониторинг", callback_data="admin:section:monitoring")],
        ]),
    )
