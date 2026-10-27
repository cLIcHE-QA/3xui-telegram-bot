"""Read-only customer ledger views. No provider, checkout or refund actions."""
from __future__ import annotations

import re

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from refund_support_policy import get_published_terms
from ui_time import format_timestamp


ORDER_LABELS = {
    "created": "Создан", "awaiting_payment": "Ожидает оплаты", "paid": "Оплачен",
    "cancelled": "Отменён", "expired": "Срок заказа истёк",
}
PAYMENT_LABELS = {
    "created": "Создан", "pending": "Ожидает подтверждения", "confirmed": "Подтверждён",
    "failed": "Не выполнен", "refunded": "Возвращён", "unknown": "Исход неизвестен",
}
ACCESS_LABELS = {
    "pending": "Ожидает активации", "provisioning": "Активация выполняется",
    "active": "Активен", "suspended": "Приостановлен", "expired": "Истёк",
    "failed": "Ошибка активации",
}
REFUND_LABELS = {
    "in_flight": "Выполняется", "success": "Подтверждён",
    "failed": "Не выполнен", "unknown": "Исход неизвестен",
}


def history_route(data: str) -> tuple[str, str, int, int] | None:
    if data == "client:history":
        return "list", "orders", 0, 0
    match = re.fullmatch(r"client:history:(orders|payments):([0-9]{1,9})", data)
    if match:
        return "list", match[1], int(match[2]), 0
    match = re.fullmatch(
        r"client:history:(order|payment):([1-9][0-9]{0,17}):([0-9]{1,9}):(orders|payments)", data,
    )
    if match:
        return match[1], match[4], int(match[3]), int(match[2])
    match = re.fullmatch(r"client:history:(support|terms):(orders|payments):([0-9]{1,9})", data)
    if match:
        return match[1], match[2], int(match[3]), 0
    return None


def _button(text: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback)


def history_menu(kind: str, page: int, rows: list | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=(rows or []) + [
        [_button("💳 Поддержка по оплате", f"client:history:support:{kind}:{page}"),
         _button("📄 Условия", f"client:history:terms:{kind}:{page}")],
        [_button("⬅ История", f"client:history:{kind}:{page}")],
        [_button("⬅ Профиль", "client:profile")],
    ])


def history_list_view(snapshot: dict) -> tuple[str, InlineKeyboardMarkup]:
    kind, page, total = snapshot["kind"], snapshot["page"], snapshot["total"]
    orders = kind == "orders"
    text = (
        f"📜 История · {'заказы' if orders else 'платежи Stars'}\n\n"
        f"Всего: {total} · Страница {page + 1}/{max(1, (total + 7) // 8)}\n"
        "Только Telegram Stars (XTR). Заказ сам по себе не подтверждает списание."
    )
    if not total:
        text += "\nЗаписей пока нет."
    labels = ORDER_LABELS if orders else PAYMENT_LABELS
    action = "order" if orders else "payment"
    rows = [[_button("Заказы", "client:history:orders:0"),
             _button("Платежи Stars", "client:history:payments:0")]]
    for item in snapshot["items"]:
        label = labels.get(item["status"], "Неизвестно")
        rows.append([_button(
            f"#{item['id']} · ⭐ {item['amount_minor']} · {label}",
            f"client:history:{action}:{item['id']}:{page}:{kind}",
        )])
    nav = []
    if page:
        nav.append(_button("⬅ Новее", f"client:history:{kind}:{page - 1}"))
    if (page + 1) * 8 < total:
        nav.append(_button("➡ Старее", f"client:history:{kind}:{page + 1}"))
    if nav:
        rows.append(nav)
    menu = history_menu(kind, page, rows)
    # A list is its own parent; retain support/Terms and Profile, omit self Back.
    menu.inline_keyboard.pop(-2)
    return text, menu


def history_detail_view(item: dict | None, action: str, kind: str, page: int):
    if item is None:
        return "📜 История\n\nЗапись недоступна или больше не существует.", history_menu(kind, page)
    orders = action == "order"
    name = item["plan_name"] or "недоступен"
    if len(name) > 80 or re.search(r"[<>\x00-\x1f\x7f]|://|[A-Za-z0-9_-]{40,}", name):
        name = "недоступен"
    text = (
        f"{'📋 Заказ' if orders else '⭐ Платёж'} #{item['id']}\n\n"
        f"Заказ: #{item['order_id']}\n"
        f"Тариф (текущий каталог): {name}\n"
        f"Сумма {'заказа' if orders else 'платежа'}: ⭐ {item['amount_minor']} XTR\n"
        f"Создан: {format_timestamp(item['created_at'])}\n"
        f"Статус заказа: {ORDER_LABELS.get(item['order_status'], 'Неизвестно')}\n"
    )
    if item["payment_id"] is None:
        text += "Платёж: записи нет; списание не подтверждено.\n"
    else:
        text += (
            f"{'Последний платёж' if orders else 'Платёж'}: #{item['payment_id']} · "
            f"{PAYMENT_LABELS.get(item['payment_status'], 'Неизвестно')}\n"
            f"Сумма платежа: ⭐ {item['payment_amount_minor']} XTR\n"
            f"Подтверждён в журнале: {format_timestamp(item['confirmed_at'])}\n"
        )
    if item["refund_status"]:
        text += f"Операция возврата: {REFUND_LABELS.get(item['refund_status'], 'Неизвестно')}\n"
    access = item["entitlement_status"]
    text += f"Период доступа в журнале: {ACCESS_LABELS.get(access, 'Записи нет' if access is None else 'Неизвестно')}\n"
    if access is not None:
        text += f"Начало: {format_timestamp(item['starts_at'])}\nСрок: {format_timestamp(item['expires_at'], empty='не указан')}\n"
    text += (
        "\nЭто локальная история, без запроса к Telegram или VPN-провайдеру. "
        "Статусы заказа, платежа, возврата и доступа независимы. "
        "При неизвестном исходе не оплачивайте повторно; используйте /paysupport."
    )
    rows = []
    if orders and item["payment_id"]:
        rows.append([_button("⭐ Детали платежа", f"client:history:payment:{item['payment_id']}:{page}:{kind}")])
    elif not orders:
        rows.append([_button("📋 Детали заказа", f"client:history:order:{item['order_id']}:{page}:{kind}")])
    return text, history_menu(kind, page, rows)


def history_help_view(action: str, kind: str, page: int):
    rows = []
    if action == "support":
        text = (
            "💳 Поддержка по оплате\n\nИспользуйте /paysupport и номер своего заказа. "
            "Не отправляйте ссылку подписки или идентификатор Telegram-платежа. "
            "При неизвестном исходе не оплачивайте повторно."
        )
    else:
        terms = get_published_terms()
        text = "📄 Условия\n\n"
        if terms is None:
            text += "Публичная редакция: не опубликована. Для вопросов используйте /paysupport."
        else:
            text += f"Публичная редакция: {terms.revision}, действует с {terms.effective_at.isoformat()}."
            rows.append([InlineKeyboardButton(text="📄 Читать условия", url=terms.url)])
        text += "\nПросмотр не подтверждает согласие и не создаёт заказ или счёт."
    return text, history_menu(kind, page, rows)
