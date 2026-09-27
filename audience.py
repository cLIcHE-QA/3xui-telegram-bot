from __future__ import annotations

from collections.abc import Iterable

from db import Database


def audience_matches_group_ids(
    member_group_ids: Iterable[int],
    *,
    include_group_ids: Iterable[int] = (),
    exclude_group_ids: Iterable[int] = (),
) -> bool:
    """Return whether one membership set matches an audience rule.

    Exclude/deny always wins. With no include rules, every user not excluded
    matches. This keeps unrestricted features open by default while allowing
    explicit deny groups to narrow access.
    """
    member_ids = {int(value) for value in member_group_ids}
    include_ids = {int(value) for value in include_group_ids}
    exclude_ids = {int(value) for value in exclude_group_ids}

    if member_ids & exclude_ids:
        return False
    if not include_ids:
        return True
    return bool(member_ids & include_ids)


async def audience_matches(
    db: Database,
    telegram_id: int,
    *,
    include_group_ids: Iterable[int] = (),
    exclude_group_ids: Iterable[int] = (),
) -> bool:
    """Resolve a user's current groups and evaluate one audience rule."""
    memberships = await db.list_user_group_ids_for_user(int(telegram_id))
    return audience_matches_group_ids(
        memberships,
        include_group_ids=include_group_ids,
        exclude_group_ids=exclude_group_ids,
    )
