from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from admin_privileges import ROLE_ICONS, ROLE_LABELS
from admin_ui import filter_keyboard_for_role


def admin_root_heading(role: str) -> str:
    """Identical role-aware title for /admin and admin:home."""
    if role not in ROLE_LABELS or role not in ROLE_ICONS:
        raise ValueError("Неизвестная роль администратора")
    return f"⚙️ Панель администратора · {ROLE_ICONS[role]} {ROLE_LABELS[role]}"


def _for_role(markup: InlineKeyboardMarkup, role: str | None) -> InlineKeyboardMarkup:
    return markup if role is None else filter_keyboard_for_role(markup, role)


def admin_menu(role: str | None = None) -> InlineKeyboardMarkup:
    """Production admin navigation with stable callback identifiers."""
    return _for_role(InlineKeyboardMarkup(inline_keyboard=[
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
    ]), role)


def dashboard_menu(role: str | None = None) -> InlineKeyboardMarkup:
    return _for_role(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Требует внимания", callback_data="admin:attention")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:dashboard")],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ]), role)


def attention_menu(
    categories: set[str] | None = None,
    role: str | None = None,
) -> InlineKeyboardMarkup:
    active = categories if categories is not None else {
        "infrastructure", "jobs", "alerts", "backups", "operations",
    }
    rows: list[list[InlineKeyboardButton]] = []
    if "infrastructure" in active:
        rows.append([InlineKeyboardButton(text="🩺 Состояние системы", callback_data="admin:attention:health")])
    if "jobs" in active:
        rows.append([InlineKeyboardButton(text="⚙️ Задания", callback_data="admin:attention:jobs")])
    if "alerts" in active:
        rows.append([InlineKeyboardButton(text="🚨 Оповещения", callback_data="admin:attention:alerts")])
    if "backups" in active:
        rows.append([InlineKeyboardButton(text="💾 Резервные копии", callback_data="admin:attention:backups")])
    if "operations" in active:
        rows.append([InlineKeyboardButton(text="🌐 Операции с нодами", callback_data="admin:attention:fleet")])
    rows += [
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:attention")],
        [InlineKeyboardButton(text="⬅ Обзор", callback_data="admin:dashboard")],
    ]
    return _for_role(InlineKeyboardMarkup(inline_keyboard=rows), role)


def infrastructure_menu(role: str | None = None) -> InlineKeyboardMarkup:
    return _for_role(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Ноды", callback_data="admin:nodes")],
        [
            InlineKeyboardButton(text="📡 Inbounds", callback_data="admin:infra:inbounds"),
            InlineKeyboardButton(text="🌐 Хосты", callback_data="admin:hosts"),
        ],
        [InlineKeyboardButton(text="🌐 Операции с нодами", callback_data="admin:fleet")],
        [InlineKeyboardButton(text="🗂 Группы серверов", callback_data="admin:servergroups")],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ]), role)


def monitoring_menu(role: str | None = None) -> InlineKeyboardMarkup:
    return _for_role(InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Трафик", callback_data="admin:traffic"),
            InlineKeyboardButton(text="🟢 В сети", callback_data="admin:online"),
        ],
        [InlineKeyboardButton(text="🩺 Состояние системы", callback_data="admin:health")],
        [InlineKeyboardButton(text="🔎 Проверка блокировок", callback_data="admin:cheburcheck")],
        [InlineKeyboardButton(text="🌐 Мониторинг сайтов", callback_data="admin:webmon")],
        [
            InlineKeyboardButton(text="📜 Журналы", callback_data="admin:logs"),
            InlineKeyboardButton(text="🚨 Оповещения", callback_data="admin:alerts"),
        ],
        [InlineKeyboardButton(text="⬅ Панель администратора", callback_data="admin:home")],
    ]), role)


def system_menu(role: str | None = None) -> InlineKeyboardMarkup:
    return _for_role(InlineKeyboardMarkup(inline_keyboard=[
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
    ]), role)


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


def backup_menu(role: str | None = None, *, from_attention: bool = False) -> InlineKeyboardMarkup:
    """Preserve Attention entry context without changing normal backup paths."""
    rows = [
        [InlineKeyboardButton(text="💾 Создать сейчас", callback_data="admin:backup:create")],
        [InlineKeyboardButton(text="🧯 Восстановление / DR", callback_data="admin:restore")],
    ]
    if from_attention:
        rows += [
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:attention:backups")],
            [InlineKeyboardButton(text="⬅ Требует внимания", callback_data="admin:attention")],
        ]
    else:
        rows.append([InlineKeyboardButton(text="⬅ Система", callback_data="admin:section:system")])
    return _for_role(InlineKeyboardMarkup(inline_keyboard=rows), role)
