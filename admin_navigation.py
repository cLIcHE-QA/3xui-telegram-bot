from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu() -> InlineKeyboardMarkup:
    """Production admin navigation with stable callback identifiers."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Dashboard", callback_data="admin:dashboard")],
        [
            InlineKeyboardButton(text="👥 Users", callback_data="admin:users"),
            InlineKeyboardButton(text="🔗 Subscriptions", callback_data="admin:subscriptions"),
        ],
        [
            InlineKeyboardButton(text="💳 Payments", callback_data="admin:payments"),
            InlineKeyboardButton(text="💎 Plans", callback_data="admin:plans"),
        ],
        [
            InlineKeyboardButton(text="🎟 Promo Codes", callback_data="admin:promo"),
            InlineKeyboardButton(text="🌐 Infrastructure", callback_data="admin:section:infrastructure"),
        ],
        [
            InlineKeyboardButton(text="📈 Monitoring", callback_data="admin:section:monitoring"),
            InlineKeyboardButton(text="⚙️ System", callback_data="admin:section:system"),
        ],
    ])


def infrastructure_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🖥 Panels", callback_data="admin:versions"),
            InlineKeyboardButton(text="🌍 Nodes", callback_data="admin:nodes"),
        ],
        [
            InlineKeyboardButton(text="📡 Inbounds", callback_data="admin:infra:inbounds"),
            InlineKeyboardButton(text="🌐 Hosts", callback_data="admin:hosts"),
        ],
        [InlineKeyboardButton(text="🌐 Fleet Operations", callback_data="admin:fleet")],
        [InlineKeyboardButton(text="🗂 Server Groups", callback_data="admin:servergroups")],
        [InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")],
    ])


def monitoring_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Traffic", callback_data="admin:traffic"),
            InlineKeyboardButton(text="🟢 Online", callback_data="admin:online"),
        ],
        [InlineKeyboardButton(text="🩺 System Health", callback_data="admin:health")],
        [
            InlineKeyboardButton(text="📜 Logs", callback_data="admin:logs"),
            InlineKeyboardButton(text="🚨 Alerts", callback_data="admin:alerts"),
        ],
        [InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")],
    ])


def system_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Bot Updates", callback_data="admin:botupd")],
        [InlineKeyboardButton(text="🧩 Versions & Updates", callback_data="admin:versions")],
        [
            InlineKeyboardButton(text="⚙️ Jobs", callback_data="admin:jobs"),
            InlineKeyboardButton(text="💾 Backups", callback_data="admin:backups"),
        ],
        [InlineKeyboardButton(text="🧾 Audit Log", callback_data="admin:audit")],
        [InlineKeyboardButton(text="👮 Administrators", callback_data="admin:administrators")],
        [InlineKeyboardButton(text="🔧 Settings", callback_data="admin:settings")],
        [InlineKeyboardButton(text="⬅ Dashboard", callback_data="admin:home")],
    ])


def user_admin_keyboard(tg_id: int, enabled: bool = True) -> InlineKeyboardMarkup:
    state_btn = (
        InlineKeyboardButton(text="⛔ Отключить", callback_data=f"admindisable:{tg_id}")
        if enabled else
        InlineKeyboardButton(text="✅ Включить", callback_data=f"adminenable:{tg_id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Расширенное управление", callback_data=f"admin:u:{tg_id}")],
        [InlineKeyboardButton(text="🔗 Подписка", callback_data=f"adminsub:{tg_id}")],
        [InlineKeyboardButton(text="🔄 Синхронизировать inbound'ы", callback_data=f"adminsync:{tg_id}")],
        [InlineKeyboardButton(text="➕ +30 дней", callback_data=f"adminextend:{tg_id}")],
        [state_btn],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admindelask:{tg_id}")],
        [InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")],
    ])


def confirm_delete_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Да, удалить", callback_data=f"admindel:{tg_id}")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data=f"adminuser:{tg_id}")],
    ])


def confirm_sync_all_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Синхронизировать всех", callback_data="admin:syncall:run")],
        [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:home")],
    ])


def backup_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Создать сейчас", callback_data="admin:backup:create")],
        [InlineKeyboardButton(text="📥 Скачать bot.sqlite3", callback_data="admin:backup:botdb")],
        [InlineKeyboardButton(text="📦 Скачать полный backup", callback_data="admin:backup:full")],
        [InlineKeyboardButton(text="🧯 Restore / DR", callback_data="admin:restore")],
        [InlineKeyboardButton(text="⬅ System", callback_data="admin:section:system")],
    ])
