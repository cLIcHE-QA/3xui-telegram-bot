from __future__ import annotations

import sqlite3

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_auth import authorize_callback, authorize_message
from admin_privileges import ROLE_RANK
from admin_ui import render_callback, render_input
from audit import audit_from_call, audit_from_message
from config import load_settings
from db import Database, UserGroupRecord, UserRecord
from user_ui import user_label


settings = load_settings()
db = Database(settings.db_path)
user_groups_router = Router(name="user_groups_admin")

GROUP_PAGE_SIZE = 12
MEMBER_PAGE_SIZE = 12


class CreateUserGroupStates(StatesGroup):
    name = State()
    description = State()


class EditUserGroupStates(StatesGroup):
    name = State()
    description = State()


class FindUserGroupMemberStates(StatesGroup):
    query = State()


def _role_at_least(role: str | None, minimum: str) -> bool:
    return ROLE_RANK.get(role or "", 0) >= ROLE_RANK[minimum]


async def _guard_call(call: CallbackQuery) -> str | None:
    ok, role = await authorize_callback(db, settings, call)
    return role if ok else None


async def guard_message(
    message: Message,
    state: FSMContext,
    *,
    minimum: str,
) -> bool:
    if not message.from_user:
        await state.clear()
        return False
    ok, _ = await authorize_message(
        db,
        settings,
        message.from_user.id,
        minimum=minimum,
    )
    if not ok:
        await state.clear()
        await render_input(message, "Недостаточно прав.")
        return False
    return True


def _normalize_group_name(raw: str) -> str:
    value = " ".join(str(raw or "").strip().split())
    if not 1 <= len(value) <= 64:
        raise ValueError("length")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("control")
    return value


def _normalize_description(raw: str) -> str:
    value = str(raw or "").replace("\r", "").strip()
    if value == "-":
        return ""
    if len(value) > 500:
        raise ValueError("length")
    if any((ord(ch) < 32 and ch not in "\n\t") or ord(ch) == 127 for ch in value):
        raise ValueError("control")
    return value


def _groups_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Группы пользователей", callback_data="admin:usergroups")],
    ])


def _group_back(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Группа пользователей", callback_data=f"admin:usergroup:{group_id}")],
    ])


def _user_back(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Пользователь", callback_data=f"admin:u:{telegram_id}")],
    ])


async def _display_user(user: UserRecord) -> str:
    profile = await db.get_user_profile(user.telegram_id)
    return user_label(user, profile)


async def _group_detail_screen(
    group: UserGroupRecord,
    role: str | None,
) -> tuple[str, InlineKeyboardMarkup]:
    count = await db.count_user_group_members(group.id)
    description = group.description or "—"
    text = (
        f"👥 {group.name}\n\n"
        f"Участников: {count}\n"
        f"Описание: {description}\n\n"
        "Группа пользователей управляет только аудиторией. "
        "Она не меняет тариф, Группу серверов, Nodes, Inbounds или VPN-доступ."
    )
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text="👥 Участники",
            callback_data=f"admin:usergroup:members:{group.id}:0",
        )],
    ]
    if _role_at_least(role, "support"):
        rows.append([InlineKeyboardButton(
            text="➕ Добавить пользователя",
            callback_data=f"admin:usergroup:add:{group.id}",
        )])
    if _role_at_least(role, "admin"):
        rows.extend([
            [
                InlineKeyboardButton(
                    text="✏️ Название",
                    callback_data=f"admin:usergroup:rename:{group.id}",
                ),
                InlineKeyboardButton(
                    text="📝 Описание",
                    callback_data=f"admin:usergroup:description:{group.id}",
                ),
            ],
            [InlineKeyboardButton(
                text="🗑 Удалить группу",
                callback_data=f"admin:usergroup:deleteask:{group.id}",
            )],
        ])
    rows.append([InlineKeyboardButton(
        text="⬅ Группы пользователей",
        callback_data="admin:usergroups",
    )])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_group_detail(call: CallbackQuery, group_id: int, role: str | None) -> bool:
    group = await db.get_user_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return False
    text, keyboard = await _group_detail_screen(group, role)
    await render_callback(call, text, reply_markup=keyboard)
    return True


@user_groups_router.callback_query(F.data == "admin:usergroups")
@user_groups_router.callback_query(F.data.regexp(r"^admin:usergroups:page:\d+$"))
async def user_groups_list(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    page = 0
    if call.data and call.data.startswith("admin:usergroups:page:"):
        page = max(0, int(call.data.rsplit(":", 1)[-1]))

    groups = await db.list_user_groups()
    total = len(groups)
    max_page = max(0, (total - 1) // GROUP_PAGE_SIZE)
    page = min(page, max_page)
    chunk = groups[page * GROUP_PAGE_SIZE:(page + 1) * GROUP_PAGE_SIZE]

    rows: list[list[InlineKeyboardButton]] = []
    for group in chunk:
        count = await db.count_user_group_members(group.id)
        rows.append([InlineKeyboardButton(
            text=f"👥 {group.name} · {count}",
            callback_data=f"admin:usergroup:{group.id}",
        )])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅",
            callback_data=f"admin:usergroups:page:{page - 1}",
        ))
    if page < max_page:
        nav.append(InlineKeyboardButton(
            text="➡",
            callback_data=f"admin:usergroups:page:{page + 1}",
        ))
    if nav:
        rows.append(nav)

    if _role_at_least(role, "admin"):
        rows.append([InlineKeyboardButton(
            text="➕ Создать группу",
            callback_data="admin:usergroupadd:start",
        )])
    rows.append([InlineKeyboardButton(text="⬅ Пользователи", callback_data="admin:users")])

    text = (
        "👥 Группы пользователей\n\n"
        f"Групп: {total}\n"
        f"Страница: {page + 1}/{max_page + 1}\n\n"
        "Эти группы предназначены для сегментации аудитории будущего Client Portal. "
        "Они не связаны с Группами серверов и не меняют VPN-доступ."
    )
    await render_callback(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@user_groups_router.callback_query(F.data.regexp(r"^admin:usergroup:\d+$"))
async def user_group_detail(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    if await _render_group_detail(call, group_id, role):
        await call.answer()


@user_groups_router.callback_query(F.data == "admin:usergroupadd:start")
async def user_group_add_start(call: CallbackQuery, state: FSMContext):
    role = await _guard_call(call)
    if role is None:
        return
    await state.clear()
    await state.set_state(CreateUserGroupStates.name)
    await render_callback(
        call,
        "👥 Новая группа пользователей · 1/2\n\n"
        "Название группы (1–64 символа):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data="admin:usergroupadd:cancel"),
        ]]),
    )
    await call.answer()


@user_groups_router.message(CreateUserGroupStates.name)
async def user_group_add_name(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="admin"):
        return
    try:
        name = _normalize_group_name(message.text or "")
    except ValueError:
        await render_input(
            message,
            "Название должно содержать 1–64 символа без управляющих символов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✖ Отмена", callback_data="admin:usergroupadd:cancel"),
            ]]),
        )
        return
    await state.update_data(name=name)
    await state.set_state(CreateUserGroupStates.description)
    await render_input(
        message,
        "👥 Новая группа пользователей · 2/2\n\n"
        "Описание до 500 символов. Отправь «-», чтобы оставить пустым.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data="admin:usergroupadd:cancel"),
        ]]),
    )


@user_groups_router.message(CreateUserGroupStates.description)
async def user_group_add_description(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="admin"):
        return
    data = await state.get_data()
    try:
        name = _normalize_group_name(str(data.get("name") or ""))
        description = _normalize_description(message.text or "")
        group_id = await db.create_user_group(name=name, description=description)
    except ValueError:
        await render_input(message, "Описание должно быть до 500 символов.")
        return
    except sqlite3.IntegrityError:
        await render_input(
            message,
            "Группа с таким названием уже существует. Введи другое название заново.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅ Группы пользователей", callback_data="admin:usergroups"),
            ]]),
        )
        await state.clear()
        return

    await audit_from_message(
        db,
        message,
        "user_group.create",
        target_type="user_group",
        target_id=group_id,
        details=f"name_length={len(name)}; description_length={len(description)}",
    )
    await state.clear()
    await render_input(
        message,
        f"✅ Группа «{name}» создана.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="👥 Открыть группу", callback_data=f"admin:usergroup:{group_id}"),
        ]]),
    )


@user_groups_router.callback_query(F.data == "admin:usergroupadd:cancel")
async def user_group_add_cancel(call: CallbackQuery, state: FSMContext):
    role = await _guard_call(call)
    if role is None:
        return
    await state.clear()
    await render_callback(
        call,
        "Создание группы отменено.",
        reply_markup=_groups_back(),
    )
    await call.answer()


@user_groups_router.callback_query(F.data.startswith("admin:usergroup:rename:"))
async def user_group_rename_start(call: CallbackQuery, state: FSMContext):
    role = await _guard_call(call)
    if role is None:
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_user_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await state.clear()
    await state.update_data(group_id=group_id)
    await state.set_state(EditUserGroupStates.name)
    await render_callback(
        call,
        f"✏️ Название группы\n\nТекущее: {group.name}\n\nВведи новое название:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:usergroup:{group_id}"),
        ]]),
    )
    await call.answer()


@user_groups_router.message(EditUserGroupStates.name)
async def user_group_rename_save(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="admin"):
        return
    data = await state.get_data()
    group_id = int(data.get("group_id") or 0)
    group = await db.get_user_group(group_id)
    if not group:
        await state.clear()
        await render_input(message, "Группа не найдена.", reply_markup=_groups_back())
        return
    try:
        name = _normalize_group_name(message.text or "")
        await db.update_user_group(
            group_id,
            name=name,
            description=group.description,
        )
    except ValueError:
        await render_input(message, "Название должно содержать 1–64 символа.")
        return
    except sqlite3.IntegrityError:
        await render_input(message, "Группа с таким названием уже существует.")
        return
    await audit_from_message(
        db,
        message,
        "user_group.rename",
        target_type="user_group",
        target_id=group_id,
        details=f"old_length={len(group.name)}; new_length={len(name)}",
    )
    await state.clear()
    await render_input(
        message,
        f"✅ Название изменено: {name}",
        reply_markup=_group_back(group_id),
    )


@user_groups_router.callback_query(F.data.startswith("admin:usergroup:description:"))
async def user_group_description_start(call: CallbackQuery, state: FSMContext):
    role = await _guard_call(call)
    if role is None:
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_user_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await state.clear()
    await state.update_data(group_id=group_id)
    await state.set_state(EditUserGroupStates.description)
    await render_callback(
        call,
        "📝 Описание группы\n\n"
        f"Текущее: {group.description or '—'}\n\n"
        "Введи новое описание до 500 символов. «-» очищает описание.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✖ Отмена", callback_data=f"admin:usergroup:{group_id}"),
        ]]),
    )
    await call.answer()


@user_groups_router.message(EditUserGroupStates.description)
async def user_group_description_save(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="admin"):
        return
    data = await state.get_data()
    group_id = int(data.get("group_id") or 0)
    group = await db.get_user_group(group_id)
    if not group:
        await state.clear()
        await render_input(message, "Группа не найдена.", reply_markup=_groups_back())
        return
    try:
        description = _normalize_description(message.text or "")
    except ValueError:
        await render_input(message, "Описание должно быть до 500 символов.")
        return
    await db.update_user_group(
        group_id,
        name=group.name,
        description=description,
    )
    await audit_from_message(
        db,
        message,
        "user_group.description.set",
        target_type="user_group",
        target_id=group_id,
        details=f"old_length={len(group.description)}; new_length={len(description)}",
    )
    await state.clear()
    await render_input(
        message,
        "✅ Описание обновлено.",
        reply_markup=_group_back(group_id),
    )


@user_groups_router.callback_query(F.data.startswith("admin:usergroup:deleteask:"))
async def user_group_delete_ask(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_user_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    count = await db.count_user_group_members(group_id)
    await render_callback(
        call,
        "⚠️ Удалить группу пользователей?\n\n"
        f"Группа: {group.name}\n"
        f"Участников: {count}\n\n"
        "Пользователи не удаляются. Будет удалена только эта группа и её membership. "
        "VPN-доступ, тарифы и Группы серверов не изменятся.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🗑 Удалить группу",
                callback_data=f"admin:usergroup:delete:{group_id}",
            )],
            [InlineKeyboardButton(
                text="✖ Отмена",
                callback_data=f"admin:usergroup:{group_id}",
            )],
        ]),
    )
    await call.answer()


@user_groups_router.callback_query(F.data.startswith("admin:usergroup:delete:"))
async def user_group_delete_run(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_user_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    count = await db.count_user_group_members(group_id)
    await db.delete_user_group(group_id)
    await audit_from_call(
        db,
        call,
        "user_group.delete",
        target_type="user_group",
        target_id=group_id,
        details=f"members_removed={count}; name_length={len(group.name)}",
    )
    await render_callback(
        call,
        f"✅ Группа «{group.name}» удалена. Пользователи не удалялись.",
        reply_markup=_groups_back(),
    )
    await call.answer()


@user_groups_router.callback_query(F.data.regexp(r"^admin:usergroup:members:\d+:\d+$"))
async def user_group_members(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    parts = call.data.split(":")
    group_id = int(parts[-2])
    page = max(0, int(parts[-1]))
    group = await db.get_user_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return

    total = await db.count_user_group_members(group_id)
    max_page = max(0, (total - 1) // MEMBER_PAGE_SIZE)
    page = min(page, max_page)
    members = await db.list_user_group_members(
        group_id,
        limit=MEMBER_PAGE_SIZE,
        offset=page * MEMBER_PAGE_SIZE,
    )
    rows: list[list[InlineKeyboardButton]] = []
    for member in members:
        label = await _display_user(member)
        rows.append([InlineKeyboardButton(
            text=f"👤 {label}",
            callback_data=f"admin:usergroup:member:{group_id}:{member.telegram_id}",
        )])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅",
            callback_data=f"admin:usergroup:members:{group_id}:{page - 1}",
        ))
    if page < max_page:
        nav.append(InlineKeyboardButton(
            text="➡",
            callback_data=f"admin:usergroup:members:{group_id}:{page + 1}",
        ))
    if nav:
        rows.append(nav)
    if _role_at_least(role, "support"):
        rows.append([InlineKeyboardButton(
            text="➕ Добавить пользователя",
            callback_data=f"admin:usergroup:add:{group_id}",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅ Группа пользователей",
        callback_data=f"admin:usergroup:{group_id}",
    )])
    await render_callback(
        call,
        f"👥 Участники · {group.name}\n\n"
        f"Участников: {total}\n"
        f"Страница: {page + 1}/{max_page + 1}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@user_groups_router.callback_query(F.data.regexp(r"^admin:usergroup:member:\d+:\d+$"))
async def user_group_member_detail(call: CallbackQuery, state: FSMContext):
    role = await _guard_call(call)
    if role is None:
        return
    await state.clear()
    parts = call.data.split(":")
    group_id = int(parts[-2])
    telegram_id = int(parts[-1])
    group = await db.get_user_group(group_id)
    user = await db.get(telegram_id)
    member_ids = await db.list_user_group_member_ids(group_id) if group else set()
    if not group or not user or telegram_id not in member_ids:
        await call.answer("Участник или группа уже не существуют.", show_alert=True)
        return
    label = await _display_user(user)
    rows = [[InlineKeyboardButton(
        text="👤 Открыть пользователя",
        callback_data=f"admin:u:{telegram_id}",
    )]]
    if _role_at_least(role, "support"):
        rows.append([InlineKeyboardButton(
            text="➖ Убрать из группы",
            callback_data=f"admin:usergroup:removeask:{group_id}:{telegram_id}",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅ Участники",
        callback_data=f"admin:usergroup:members:{group_id}:0",
    )])
    await render_callback(
        call,
        f"👤 {label}\n\n"
        f"Telegram ID: {telegram_id}\n"
        f"Email: {user.email}\n"
        f"Группа: {group.name}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@user_groups_router.callback_query(F.data.startswith("admin:usergroup:add:"))
async def user_group_add_member_start(call: CallbackQuery, state: FSMContext):
    role = await _guard_call(call)
    if role is None:
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    group = await db.get_user_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await state.clear()
    await state.update_data(group_id=group_id)
    await state.set_state(FindUserGroupMemberStates.query)
    await render_callback(
        call,
        f"➕ Добавить пользователя · {group.name}\n\n"
        "Введи Telegram ID, email или отображаемое имя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="✖ Отмена",
                callback_data=f"admin:usergroup:addcancel:{group_id}",
            ),
        ]]),
    )
    await call.answer()


@user_groups_router.message(FindUserGroupMemberStates.query)
async def user_group_add_member_search(message: Message, state: FSMContext):
    if not await guard_message(message, state, minimum="support"):
        return
    data = await state.get_data()
    group_id = int(data.get("group_id") or 0)
    group = await db.get_user_group(group_id)
    if not group:
        await state.clear()
        await render_input(message, "Группа не найдена.", reply_markup=_groups_back())
        return
    query = (message.text or "").strip()
    if not query:
        await render_input(
            message,
            "Введи Telegram ID, email или отображаемое имя.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="✖ Отмена",
                    callback_data=f"admin:usergroup:addcancel:{group_id}",
                ),
            ]]),
        )
        return
    results = await db.search_users(query, limit=12)
    current = await db.list_user_group_member_ids(group_id)
    rows: list[list[InlineKeyboardButton]] = []
    for user in results:
        label = await _display_user(user)
        icon = "✅" if user.telegram_id in current else "➕"
        callback = (
            f"admin:usergroup:member:{group_id}:{user.telegram_id}"
            if user.telegram_id in current
            else f"admin:usergroup:addpick:{group_id}:{user.telegram_id}"
        )
        rows.append([InlineKeyboardButton(
            text=f"{icon} {label} · TG {user.telegram_id}",
            callback_data=callback,
        )])
    rows.append([InlineKeyboardButton(
        text="✖ Отмена",
        callback_data=f"admin:usergroup:addcancel:{group_id}",
    )])
    if results:
        text = (
            f"🔎 Результаты · {group.name}\n\n"
            "✅ уже состоит в группе; ➕ будет добавлен после выбора."
        )
    else:
        text = (
            f"🔎 Результаты · {group.name}\n\n"
            "Совпадений нет. Можно отправить другой Telegram ID, email или имя."
        )
    await render_input(
        message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@user_groups_router.callback_query(F.data.regexp(r"^admin:usergroup:addpick:\d+:\d+$"))
async def user_group_add_member_pick(call: CallbackQuery, state: FSMContext):
    role = await _guard_call(call)
    if role is None:
        return
    parts = call.data.split(":")
    group_id = int(parts[-2])
    telegram_id = int(parts[-1])
    group = await db.get_user_group(group_id)
    user = await db.get(telegram_id)
    if not group or not user:
        await call.answer("Группа или пользователь не найдены.", show_alert=True)
        return
    try:
        changed = await db.set_user_group_member(group_id, telegram_id, True)
    except ValueError:
        await call.answer("Группа или пользователь уже не существуют.", show_alert=True)
        return
    await audit_from_call(
        db,
        call,
        "user_group.member.add",
        target_type="user",
        target_id=telegram_id,
        details=f"group_id={group_id}; changed={int(changed)}",
    )
    await state.clear()
    await render_callback(
        call,
        f"✅ Пользователь добавлен в группу «{group.name}».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="👥 Участники",
                callback_data=f"admin:usergroup:members:{group_id}:0",
            )],
            [InlineKeyboardButton(
                text="⬅ Группа пользователей",
                callback_data=f"admin:usergroup:{group_id}",
            )],
        ]),
    )
    await call.answer()


@user_groups_router.callback_query(F.data.startswith("admin:usergroup:addcancel:"))
async def user_group_add_member_cancel(call: CallbackQuery, state: FSMContext):
    role = await _guard_call(call)
    if role is None:
        return
    group_id = int(call.data.rsplit(":", 1)[-1])
    await state.clear()
    if await _render_group_detail(call, group_id, role):
        await call.answer()


@user_groups_router.callback_query(F.data.regexp(r"^admin:usergroup:removeask:\d+:\d+$"))
async def user_group_remove_member_ask(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    parts = call.data.split(":")
    group_id = int(parts[-2])
    telegram_id = int(parts[-1])
    group = await db.get_user_group(group_id)
    user = await db.get(telegram_id)
    if not group or not user:
        await call.answer("Группа или пользователь не найдены.", show_alert=True)
        return
    label = await _display_user(user)
    await render_callback(
        call,
        "⚠️ Убрать пользователя из группы?\n\n"
        f"Пользователь: {label}\n"
        f"Группа: {group.name}\n\n"
        "VPN-доступ пользователя не изменится.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="➖ Убрать из группы",
                callback_data=f"admin:usergroup:remove:{group_id}:{telegram_id}",
            )],
            [InlineKeyboardButton(
                text="✖ Отмена",
                callback_data=f"admin:usergroup:member:{group_id}:{telegram_id}",
            )],
        ]),
    )
    await call.answer()


@user_groups_router.callback_query(F.data.regexp(r"^admin:usergroup:remove:\d+:\d+$"))
async def user_group_remove_member_run(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    parts = call.data.split(":")
    group_id = int(parts[-2])
    telegram_id = int(parts[-1])
    group = await db.get_user_group(group_id)
    user = await db.get(telegram_id)
    if not group or not user:
        await call.answer("Группа или пользователь не найдены.", show_alert=True)
        return
    try:
        changed = await db.set_user_group_member(group_id, telegram_id, False)
    except ValueError:
        await call.answer("Группа или пользователь уже не существуют.", show_alert=True)
        return
    await audit_from_call(
        db,
        call,
        "user_group.member.remove",
        target_type="user",
        target_id=telegram_id,
        details=f"group_id={group_id}; changed={int(changed)}",
    )
    await render_callback(
        call,
        f"✅ Пользователь убран из группы «{group.name}».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="⬅ Участники",
                callback_data=f"admin:usergroup:members:{group_id}:0",
            ),
        ]]),
    )
    await call.answer()


async def _render_user_groups(
    call: CallbackQuery,
    telegram_id: int,
    role: str | None,
) -> bool:
    user = await db.get(telegram_id)
    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return False
    groups = await db.list_user_groups_for_user(telegram_id)
    label = await _display_user(user)
    lines = [
        f"👥 Группы пользователей · {label}",
        "",
        "Участие в группах:",
    ]
    if groups:
        lines.extend(f"• {group.name}" for group in groups)
    else:
        lines.append("— не состоит ни в одной группе")
    lines += [
        "",
        "Эти группы используются только для сегментации аудитории и видимости функций. "
        "Они не меняют Группу серверов или VPN-доступ.",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    if _role_at_least(role, "support"):
        rows.append([InlineKeyboardButton(
            text="✏️ Изменить группы",
            callback_data=f"admin:u:audgroupedit:{telegram_id}:0",
        )])
    rows.append([InlineKeyboardButton(
        text="⬅ Пользователь",
        callback_data=f"admin:u:{telegram_id}",
    )])
    await render_callback(
        call,
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    return True


@user_groups_router.callback_query(F.data.regexp(r"^admin:u:audgroups:\d+$"))
async def user_audience_groups(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    telegram_id = int(call.data.rsplit(":", 1)[-1])
    if await _render_user_groups(call, telegram_id, role):
        await call.answer()


async def _render_user_groups_edit(
    call: CallbackQuery,
    telegram_id: int,
    page: int,
) -> bool:
    user = await db.get(telegram_id)
    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return False
    groups = await db.list_user_groups()
    member_ids = await db.list_user_group_ids_for_user(telegram_id)
    total = len(groups)
    max_page = max(0, (total - 1) // GROUP_PAGE_SIZE)
    page = min(max(0, page), max_page)
    chunk = groups[page * GROUP_PAGE_SIZE:(page + 1) * GROUP_PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []
    for group in chunk:
        icon = "✅" if group.id in member_ids else "⬜"
        rows.append([InlineKeyboardButton(
            text=f"{icon} {group.name}",
            callback_data=f"admin:u:audgrouptoggle:{telegram_id}:{group.id}:{page}",
        )])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅",
            callback_data=f"admin:u:audgroupedit:{telegram_id}:{page - 1}",
        ))
    if page < max_page:
        nav.append(InlineKeyboardButton(
            text="➡",
            callback_data=f"admin:u:audgroupedit:{telegram_id}:{page + 1}",
        ))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(
        text="⬅ Группы пользователя",
        callback_data=f"admin:u:audgroups:{telegram_id}",
    )])
    label = await _display_user(user)
    await render_callback(
        call,
        f"✏️ Группы пользователей · {label}\n\n"
        f"Страница: {page + 1}/{max_page + 1}\n"
        "Нажатие добавляет или убирает пользователя из группы. VPN-доступ не изменяется.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    return True


@user_groups_router.callback_query(F.data.regexp(r"^admin:u:audgroupedit:\d+:\d+$"))
async def user_audience_groups_edit(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    parts = call.data.split(":")
    telegram_id = int(parts[-2])
    page = max(0, int(parts[-1]))
    if await _render_user_groups_edit(call, telegram_id, page):
        await call.answer()


@user_groups_router.callback_query(
    F.data.regexp(r"^admin:u:audgrouptoggle:\d+:\d+:\d+$")
)
async def user_audience_groups_toggle(call: CallbackQuery):
    role = await _guard_call(call)
    if role is None:
        return
    parts = call.data.split(":")
    telegram_id = int(parts[-3])
    group_id = int(parts[-2])
    page = max(0, int(parts[-1]))
    user = await db.get(telegram_id)
    group = await db.get_user_group(group_id)
    if not user or not group:
        await call.answer("Пользователь или группа не найдены.", show_alert=True)
        return
    member_ids = await db.list_user_group_ids_for_user(telegram_id)
    enabled = group_id not in member_ids
    try:
        changed = await db.set_user_group_member(group_id, telegram_id, enabled)
    except ValueError:
        await call.answer("Пользователь или группа уже не существуют.", show_alert=True)
        return
    await audit_from_call(
        db,
        call,
        "user_group.member.add" if enabled else "user_group.member.remove",
        target_type="user",
        target_id=telegram_id,
        details=f"group_id={group_id}; changed={int(changed)}; source=user_card",
    )
    if await _render_user_groups_edit(call, telegram_id, page):
        await call.answer("Добавлено в группу." if enabled else "Убрано из группы.")
