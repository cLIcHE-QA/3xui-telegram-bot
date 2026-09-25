from __future__ import annotations

from datetime import datetime, timezone

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from xui import NodeInfo


def node_status_icon(node: NodeInfo) -> str:
    if not node.enable:
        return "⚪"
    if node.status == "online":
        return "🟢"
    if node.status == "offline":
        return "🔴"
    return "🟡"


def xray_icon(node: NodeInfo) -> str:
    state = node.xray_state.lower()
    if state in {"running", "started", "online"}:
        return "🟢"
    if state in {"stopped", "failed", "error"}:
        return "🔴"
    return "🟡"


def duration_text(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}д {hours}ч {minutes}м"
    return f"{hours}ч {minutes}м"


def epoch_text(seconds: int) -> str:
    if not seconds:
        return "никогда"
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (OSError, OverflowError, ValueError):
        return str(seconds)


def node_display_name(name: str) -> str:
    value = (name or "Node").strip()
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
        [InlineKeyboardButton(text="🧩 3x-ui Control", callback_data="admin:hostctl:m")],
        [
            InlineKeyboardButton(text="⬆️ 3x-ui updates", callback_data="admin:ver:panel:m"),
            InlineKeyboardButton(text="⚡ Xray Core", callback_data="admin:ver:xray:m:0"),
        ],
        [InlineKeyboardButton(text="🔄 Проверить", callback_data="admin:master")],
        [InlineKeyboardButton(text="⬅ Ноды", callback_data="admin:nodes")],
    ])


def node_detail_keyboard(node_id: int, enabled: bool | None = None) -> InlineKeyboardMarkup:
    maintenance_text = "🛠 Enter maintenance" if enabled is not False else "▶️ Exit maintenance"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить", callback_data=f"admin:node:{node_id}")],
        [
            InlineKeyboardButton(text="📡 Inbounds", callback_data=f"admin:nodectl:{node_id}:inbounds"),
            InlineKeyboardButton(text="💾 Backup", callback_data=f"admin:nodectl:{node_id}:backup"),
        ],
        [InlineKeyboardButton(text=maintenance_text, callback_data=f"admin:nodectl:{node_id}:maintenance")],
        [
            InlineKeyboardButton(text="✏️ Rename", callback_data=f"admin:nodectl:{node_id}:rename"),
            InlineKeyboardButton(text="🧩 3x-ui Control", callback_data=f"admin:hostctl:n{node_id}"),
        ],
        [InlineKeyboardButton(text="🧭 Readiness", callback_data=f"admin:node:{node_id}:readiness")],
        [InlineKeyboardButton(text="⬆️ Update 3x-ui", callback_data=f"admin:ver:panel:n{node_id}")],
        [InlineKeyboardButton(text="⚡ Xray Core", callback_data=f"admin:ver:xray:n{node_id}:0")],
        [InlineKeyboardButton(text="🗑 Delete node", callback_data=f"admin:nodectl:{node_id}:deleteask")],
        [InlineKeyboardButton(text="⬅ Ноды", callback_data="admin:nodes")],
    ])
