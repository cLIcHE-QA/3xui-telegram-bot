from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu() -> InlineKeyboardMarkup:
    """Production admin navigation with stable callback identifiers."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Обзор", callback_data="admin:dashboard")],
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"),
            InlineKeyboardButton(text="🔗 Подписки", callback_data="admin:subscriptions"),
        ],
        [
            InlineKeyboardButton(text="💳 Платежи", callback_data="admin:payments"),
            InlineKeyboardButton(text="💎 Тарифы", callback_data="admin:plans"),
        ],
        [
            InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin:promo"),
            InlineKeyboardButton(text="🌐 Инфраструктура", callback_data="admin:section:infrastructure"),
        ],
        [
            InlineKeyboardButton(text="📈 Мониторинг", callback_data="admin:section:monitoring"),
            InlineKeyboardButton(text="⚙️ Система", callback_data="admin:section:system"),
        ],
    ])


def infrastructure_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Ноды", callback_data="admin:nodes")],
        [
            InlineKeyboardButton(text="📡 Inbound'ы", callback_data="admin:infra:inbounds"),
            InlineKeyboardButton(text="🌐 Хосты", callback_data="admin:hosts"),
        ],
        [InlineKeyboardButton(text="🌐 Операции с нодами", callback_data="admin:fleet")],
        [InlineKeyboardButton(text="🗂 Группы серверов", callback_data="admin:servergroups")],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ])


def monitoring_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Трафик", callback_data="admin:traffic"),
            InlineKeyboardButton(text="🟢 В сети", callback_data="admin:online"),
        ],
        [InlineKeyboardButton(text="🩺 Состояние системы", callback_data="admin:health")],
        [
            InlineKeyboardButton(text="📜 Журналы", callback_data="admin:logs"),
            InlineKeyboardButton(text="🚨 Оповещения", callback_data="admin:alerts"),
        ],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ])


def system_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Обновления бота", callback_data="admin:botupd")],
        [InlineKeyboardButton(text="🧩 Версии и обновления", callback_data="admin:versions")],
        [
            InlineKeyboardButton(text="⚙️ Задания", callback_data="admin:jobs"),
            InlineKeyboardButton(text="💾 Резервные копии", callback_data="admin:backups"),
        ],
        [InlineKeyboardButton(text="🧾 Журнал аудита", callback_data="admin:audit")],
        [InlineKeyboardButton(text="👮 Администраторы", callback_data="admin:administrators")],
        [InlineKeyboardButton(text="🔧 Настройки", callback_data="admin:settings")],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
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
        [InlineKeyboardButton(text="✖ Отмена", callback_data="admin:users")],
    ])


def backup_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Создать сейчас", callback_data="admin:backup:create")],
        [InlineKeyboardButton(text="📥 Скачать bot.sqlite3", callback_data="admin:backup:botdb")],
        [InlineKeyboardButton(text="📦 Скачать полную резервную копию", callback_data="admin:backup:full")],
        [InlineKeyboardButton(text="🧯 Восстановление / DR", callback_data="admin:restore")],
        [InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")],
    ])
