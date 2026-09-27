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


def dashboard_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:dashboard")],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ])


def infrastructure_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Ноды", callback_data="admin:nodes")],
        [
            InlineKeyboardButton(text="📡 Inbounds", callback_data="admin:infra:inbounds"),
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
        [InlineKeyboardButton(text="🔎 Проверка блокировок", callback_data="admin:cheburcheck")],
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
