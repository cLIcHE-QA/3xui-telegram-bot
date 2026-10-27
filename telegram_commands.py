"""Single operator-facing catalog of actually registered Telegram slash commands.

A command listing is documentation, not an authorization decision. Neither
the catalog nor its UI executes or registers command handlers.
Customer history (#506) uses private owner callbacks from Profile and links
to the existing /paysupport; it adds no slash command or alias to this catalog.
Owner UI #949 использует только admin:campaigns callbacks и FSM, без новой
slash-команды. Его закрытые routes проверяет Owner-only privilege catalog.
Оформление #876 также использует только Owner callbacks/FSM, без новых slash-команд.
"""
from __future__ import annotations

from dataclasses import dataclass

from version import APP_VERSION

CATALOG_REVISION = 2


@dataclass(frozen=True)
class BotCommand:
    name: str
    description: str
    audience: str
    minimum_role: str | None
    status: str
    feature_flag: str | None
    source: str
    handler: str


COMMANDS: tuple[BotCommand, ...] = (
    BotCommand("admin", "Административная панель", "admin", "read_only", "active", None, "admin_shell.py", "admin"),
    BotCommand("start", "Личный кабинет клиента", "client", None, "active", "CLIENT_PORTAL_ENABLED + pilot allowlist", "client_access.py", "start"),
    BotCommand("subscription", "Ссылка на подписку", "client", None, "active", "CLIENT_PORTAL_ENABLED + pilot allowlist", "client_access.py", "subscription_cmd"),
    BotCommand("paysupport", "Помощь по платежам", "client", None, "active", "CLIENT_PORTAL_ENABLED + pilot allowlist", "client_access.py", "pay_support"),
    BotCommand("create", "Устаревший переход в личный кабинет", "client", None, "legacy", "CLIENT_PORTAL_ENABLED + pilot allowlist", "client_access.py", "legacy_client_command"),
    BotCommand("inbounds", "Устаревший переход в личный кабинет", "client", None, "legacy", "CLIENT_PORTAL_ENABLED + pilot allowlist", "client_access.py", "legacy_client_command"),
)


def validate_catalog() -> None:
    names: set[str] = set()
    for item in COMMANDS:
        if item.name in names or not item.name.isascii() or not item.name.islower() or not item.name.isidentifier():
            raise ValueError(f"Invalid or duplicate Telegram command: {item.name}")
        names.add(item.name)
        if item.audience not in {"admin", "client"} or item.status not in {"active", "legacy"}:
            raise ValueError(f"Invalid command metadata: {item.name}")
        if (item.audience == "admin") != (item.minimum_role is not None):
            raise ValueError(f"Missing or misplaced admin role: {item.name}")


def commands_help_text() -> str:
    """Active UI projection; the complete registry still audits legacy routes."""
    validate_catalog()
    active_commands = tuple(item for item in COMMANDS if item.status == "active")
    lines = [
        "📚 Команды бота",
        f"Каталог: v{CATALOG_REVISION} · Бот: v{APP_VERSION}",
        "",
        "Справочник, не запуск команд и не предоставление доступа.",
        "Доступ зависит от роли, флагов и allowlist.",
        "",
        "🔐 Административные команды:",
    ]
    for item in active_commands:
        if item.audience == "admin":
            lines.append(f"/{item.name} — {item.description} · {item.minimum_role}+ · личный чат")
    lines += ["", "👤 Клиентские команды:"]
    for item in active_commands:
        if item.audience != "client":
            continue
        lines.append(f"/{item.name} — {item.description}")
    lines += [
        "",
        "Основной вход клиента: /start. Устаревшие переходы сохранены только для совместимости.",
        "Клиентские команды: CLIENT_PORTAL_ENABLED и pilot allowlist.",
        "Команды не регистрируются в Telegram глобально этим экраном.",
    ]
    return "\n".join(lines)
