from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from xui import NodeInfo
from ui_time import format_timestamp


def node_status_icon(node: NodeInfo) -> str:
    if not node.enable:
        return "⚪"
    if node.status == "online":
        return "🟢"
    if node.status == "offline":
        return "🔴"
    return "🟡"


def xray_state_icon(state: str) -> str:
    value = (state or "").lower()
    if value in {"running", "started", "online"}:
        return "🟢"
    if value in {"stopped", "failed", "error"}:
        return "🔴"
    return "🟡"


def xray_icon(node: NodeInfo) -> str:
    return xray_state_icon(node.xray_state)


def node_status_text(status: str) -> str:
    return {
        "online": "в сети",
        "offline": "не в сети",
        "unknown": "неизвестно",
    }.get((status or "").lower(), status or "неизвестно")


def node_list_status(node: NodeInfo) -> str:
    if not node.enable:
        return "🛠 Обслуживание"
    status = node_status_text(node.status)
    display = status[:1].upper() + status[1:] if status else "Неизвестно"
    return f"{node_status_icon(node)} {display}"


def xray_state_text(state: str) -> str:
    return {
        "running": "работает",
        "started": "работает",
        "online": "работает",
        "stopped": "остановлен",
        "failed": "ошибка",
        "error": "ошибка",
        "unknown": "неизвестно",
    }.get((state or "").lower(), state or "неизвестно")


def tls_verify_mode_text(value: str) -> str:
    return {
        "verify": "проверять",
        "skip": "без проверки",
    }.get((value or "").lower(), value or "неизвестно")


def inbound_sync_mode_text(value: str) -> str:
    return {
        "all": "все Inbounds",
    }.get((value or "").lower(), value or "неизвестно")


def duration_text(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}д {hours}ч {minutes}м"
    return f"{hours}ч {minutes}м"


def epoch_text(seconds: int) -> str:
    return format_timestamp(seconds, empty="никогда")


def node_display_name(name: str) -> str:
    value = (name or "Нода").strip()
    lower = value.lower()
    if value.startswith(("🇫🇮", "🇳🇱", "🇩🇪", "🇸🇪", "🇳🇴", "🇫🇷", "🇬🇧", "🇺🇸")):
        return value
    country_flags = {
        "finland": "🇫🇮",
        "finnish": "🇫🇮",
        "netherlands": "🇳🇱",
        "germany": "🇩🇪",
        "sweden": "🇸🇪",
        "norway": "🇳🇴",
        "france": "🇫🇷",
        "uk": "🇬🇧",
        "united kingdom": "🇬🇧",
        "usa": "🇺🇸",
        "united states": "🇺🇸",
    }
    flag = country_flags.get(lower)
    return f"{flag} {value}" if flag else value


def add_node_tls_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Проверять TLS", callback_data="admin:nodeadd:tls:verify")],
        [InlineKeyboardButton(text="⚠️ Не проверять TLS", callback_data="admin:nodeadd:tls:skip")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:nodeadd:cancel")],
    ])


def add_node_review_keyboard(tls_mode: str) -> InlineKeyboardMarkup:
    other = "skip" if tls_mode == "verify" else "verify"
    other_label = "⚠️ TLS без проверки" if other == "skip" else "✅ Проверять TLS"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Добавить ноду", callback_data="admin:nodeadd:save")],
        [InlineKeyboardButton(text="🔍 Проверить ещё раз", callback_data="admin:nodeadd:test")],
        [InlineKeyboardButton(text=other_label, callback_data=f"admin:nodeadd:tls:{other}")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:nodeadd:cancel")],
    ])


def add_node_retry_keyboard(tls_mode: str) -> InlineKeyboardMarkup:
    other = "skip" if tls_mode == "verify" else "verify"
    other_label = "⚠️ Попробовать без проверки TLS" if other == "skip" else "✅ Включить проверку TLS"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить ещё раз", callback_data="admin:nodeadd:test")],
        [InlineKeyboardButton(text=other_label, callback_data=f"admin:nodeadd:tls:{other}")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:nodeadd:cancel")],
    ])


def master_detail_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧩 Управление 3x-ui", callback_data="admin:hostctl:m")],
        [
            InlineKeyboardButton(text="⬆️ Обновления 3x-ui", callback_data="admin:ver:panel:m"),
            InlineKeyboardButton(text="⚡ Ядро Xray", callback_data="admin:ver:xray:m:0"),
        ],
        [InlineKeyboardButton(text="🔎 Проверить блокировку", callback_data="admin:cheburcheck:master")],
        [InlineKeyboardButton(text="🔄 Проверить", callback_data="admin:master")],
        [InlineKeyboardButton(text="⬅ Ноды", callback_data="admin:nodes")],
    ])


def node_detail_keyboard(node_id: int, enabled: bool | None = None) -> InlineKeyboardMarkup:
    maintenance_text = "🛠 Включить обслуживание" if enabled is not False else "▶️ Выключить обслуживание"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить", callback_data=f"admin:node:{node_id}")],
        [
            InlineKeyboardButton(text="📡 Inbounds", callback_data=f"admin:nodectl:{node_id}:inbounds"),
            InlineKeyboardButton(text="💾 Резервная копия", callback_data=f"admin:nodectl:{node_id}:backup"),
        ],
        [InlineKeyboardButton(text=maintenance_text, callback_data=f"admin:nodectl:{node_id}:maintenance")],
        [
            InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"admin:nodectl:{node_id}:rename"),
            InlineKeyboardButton(text="🧩 Управление 3x-ui", callback_data=f"admin:hostctl:n{node_id}"),
        ],
        [InlineKeyboardButton(text="🔎 Проверить блокировку", callback_data=f"admin:cheburcheck:node:{node_id}")],
        [InlineKeyboardButton(text="🧭 Готовность", callback_data=f"admin:node:{node_id}:readiness")],
        [InlineKeyboardButton(text="⬆️ Обновить 3x-ui", callback_data=f"admin:ver:panel:n{node_id}")],
        [InlineKeyboardButton(text="⚡ Ядро Xray", callback_data=f"admin:ver:xray:n{node_id}:0")],
        [InlineKeyboardButton(text="🗑 Удалить ноду", callback_data=f"admin:nodectl:{node_id}:deleteask")],
        [InlineKeyboardButton(text="⬅ Ноды", callback_data="admin:nodes")],
    ])


def nodes_menu(
    nodes: list[NodeInfo],
    master_online: bool = True,
    *,
    master_flag: str,
    master_name: str,
) -> InlineKeyboardMarkup:
    master_icon = "🟢" if master_online else "🔴"
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text=f"{master_flag} {master_name} · {master_icon} {'В сети' if master_online else 'Не в сети'}",
            callback_data="admin:master",
        )]
    ]
    for node in nodes[:40]:
        suffix = " ↳" if node.transitive else ""
        text = f"{node_display_name(node.name)}{suffix} · {node_list_status(node)}"
        if node.id > 0 and not node.transitive:
            rows.append([InlineKeyboardButton(text=text, callback_data=f"admin:node:{node.id}")])
        else:
            rows.append([InlineKeyboardButton(text=text, callback_data="admin:nodes:noop")])
    rows.append([InlineKeyboardButton(text="➕ Добавить ноду", callback_data="admin:nodeadd:start")])
    rows.append([InlineKeyboardButton(text="🔄 Проверить все", callback_data="admin:nodes:refresh")])
    rows.append([InlineKeyboardButton(text="⬅ Инфраструктура", callback_data="admin:section:infrastructure")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _human_bytes(value: int) -> str:
    n = int(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return "0 B"


def node_detail_text(node: NodeInfo, *, backup_configured: bool) -> str:
    status_icon = node_status_icon(node)
    xray_state_icon = xray_icon(node)
    endpoint = f"{node.scheme}://{node.address}:{node.port}{node.base_path}"
    lines = [
        f"🌍 {node_display_name(node.name)}",
        "",
        f"{status_icon} Панель: {node_status_text(node.status)}",
        f"{'🟢 Включена' if node.enable else '🛠 Обслуживание / отключена'}",
        f"🔗 Адрес: {endpoint}",
        f"{xray_state_icon} Xray: {xray_state_text(node.xray_state)}"
        + (f" {node.xray_version}" if node.xray_version else ""),
    ]
    if node.panel_version:
        lines.append(f"3x-ui: {node.panel_version}")
    lines.append(f"🔐 Проверка TLS: {tls_verify_mode_text(node.tls_verify_mode)} · синхронизация Inbounds: {inbound_sync_mode_text(node.inbound_sync_mode)}")
    if node.outbound_tag:
        lines.append(f"🧭 Исходящий маршрут: {node.outbound_tag}")
    if node.latency_ms:
        lines.append(f"📶 Задержка API: {node.latency_ms} ms")
    if node.net_up or node.net_down:
        lines.append(f"📊 Сеть: ↑ {_human_bytes(node.net_up)}/s · ↓ {_human_bytes(node.net_down)}/s")
    lines += [
        f"🧮 CPU: {node.cpu_pct:.1f}%",
        f"🧠 RAM: {node.mem_pct:.1f}%",
        f"⏱ Время работы: {duration_text(node.uptime_secs)}",
        f"🌐 Inbounds: {node.inbound_count}",
        f"👥 Клиентов: {node.client_count} · активных {node.active_count} · в сети {node.online_count}",
        f"🕒 Последний сигнал: {epoch_text(node.last_heartbeat)}",
    ]
    if node.config_dirty:
        lines.append("🟡 Конфигурация ожидает синхронизации")
    if node.last_error:
        lines.append(f"⚠️ Ошибка ноды: {node.last_error[:240]}")
    if node.xray_error:
        lines.append(f"⚠️ Ошибка Xray: {node.xray_error[:240]}")
    lines.append("💾 Резервная копия БД: " + ("настроена" if backup_configured else "не настроена"))
    if node.transitive:
        lines.append("ℹ️ Транзитная нода: представление только для просмотра через родительскую ноду.")
    return "\n".join(lines)
