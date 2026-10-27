"""#947 source-only service drafts. Importing this module never starts delivery."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import hashlib
import json
import re
import time
import unicodedata

from campaign_store import (
    CampaignConflict, CampaignLimit, CampaignNotFound, CampaignOutcomeUnknown, CampaignStore, CampaignUnavailable,
)
from db import Database


class CampaignDenied(RuntimeError):
    pass


class CampaignInvalid(ValueError):
    pass


CATEGORIES = frozenset({"technical", "service", "tariff"})
MAX_GROUPS = 50
_FIELDS = frozenset({"category", "subject", "body", "include_groups", "exclude_groups"})
_UNSAFE_TEXT = re.compile(
    r"[<>`]|\[[^\]]*\]\(|[a-z][a-z0-9+.-]*://|(?:https?|tg|mailto|ftp|file):|www\.|t\.me/|"
    r"(?:[^\W_][\w-]*\.)+[^\W\d_]{2,63}\b|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b|[a-z0-9_-]{40,}|"
    r"\b\d{5,15}:[a-z0-9_-]{15,}|"
    r"(?:bearer\s+|(?:bot[_ -]?token|api[_ -]?token|password|passwd|secret|subscription[_ -]?url)\s*[:=])|"
    r"BEGIN[ -].*PRIVATE[ -]KEY", re.IGNORECASE,
)


def _identifier(value):
    if type(value) is not int or not 0 < value <= 2**63 - 1:
        raise CampaignInvalid("Invalid campaign identity")
    return value


def _text(value, *, maximum, multiline=False):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise CampaignInvalid("Invalid campaign text")
    if any((unicodedata.category(c) in {"Cc", "Cf", "Cs"} and not (multiline and c == "\n")) for c in value):
        raise CampaignInvalid("Invalid campaign text")
    if _UNSAFE_TEXT.search(value):
        raise CampaignInvalid("Unsafe campaign text")
    return value.strip()


def _groups(values):
    if not isinstance(values, (tuple, list)) or len(values) > MAX_GROUPS:
        raise CampaignInvalid("Invalid campaign groups")
    return tuple(sorted({_identifier(v) for v in values}))


def _payload(category, subject, body, include_groups=(), exclude_groups=()):
    if not isinstance(category, str) or category not in CATEGORIES:
        raise CampaignInvalid("Invalid campaign category")
    return {
        "category": category, "subject": _text(subject, maximum=120),
        "body": _text(body, maximum=3500, multiline=True),
        "include_groups": _groups(include_groups), "exclude_groups": _groups(exclude_groups),
    }


def _encode(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode(raw):
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != _FIELDS:
            raise ValueError
        parsed = _payload(**value)
        if _encode(parsed) != raw:
            raise ValueError
        return parsed
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CampaignUnavailable("Campaign content unavailable") from None


@dataclass(frozen=True)
class CampaignDraft:
    id: int
    revision: int
    category: str
    subject: str = field(repr=False)
    body: str = field(repr=False)
    include_groups: tuple[int, ...]
    exclude_groups: tuple[int, ...]
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class CampaignSummary:
    id: int
    revision: int
    category: str
    subject: str = field(repr=False)
    updated_at: int


@dataclass(frozen=True)
class CampaignPage:
    page: int
    total: int
    items: tuple[CampaignSummary, ...]


@dataclass(frozen=True)
class CampaignRevision:
    id: int
    draft_id: int
    revision: int
    payload_sha256: str
    content: CampaignDraft = field(repr=False)


@dataclass(frozen=True)
class CandidateEstimate:
    revision: int
    candidates: int
    truncated: bool
    # Candidate provenance is neither consent nor authorization to communicate.
    deliverable: int = field(default=0, init=False)
    policy_status: str = field(default="unapproved", init=False)


def _draft(row):
    payload = _decode(row["payload_json"])
    return CampaignDraft(
        id=row.get("draft_id", row["id"]), revision=row["revision"], **payload,
        created_at=row["created_at"], updated_at=row.get("updated_at", row["created_at"]),
    )


def _revision(row):
    digest = hashlib.sha256(row["payload_json"].encode("utf-8")).hexdigest()
    if digest != row["payload_sha256"]:
        raise CampaignUnavailable("Campaign revision unavailable")
    return CampaignRevision(row["id"], row["draft_id"], row["revision"], digest, _draft(row))


class ServiceCampaigns:
    """Internal API, not a Telegram/HTTP endpoint or a delivery permission.

    A future trusted adapter supplies the current authenticated Owner decision;
    the default denies everything. No caller-supplied role strings are accepted.
    Private observation is a separate trusted-input boundary, not Owner consent.
    """

    def __init__(
        self, db: Database, *,
        authorize_owner: Callable[[int], Awaitable[bool]] | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self._store = CampaignStore(db)
        self._authorize_owner = authorize_owner
        self._clock = clock

    async def _owner(self, actor):
        _identifier(actor)
        try:
            allowed = await self._authorize_owner(actor) if self._authorize_owner else False
        except Exception:
            raise CampaignUnavailable("Campaign authorization unavailable") from None
        if allowed is not True:
            raise CampaignDenied("Campaign access denied")

    def _now(self):
        try:
            value = self._clock()
        except Exception:
            raise CampaignUnavailable("Campaign clock unavailable") from None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CampaignUnavailable("Campaign clock unavailable")
        try:
            return _identifier(int(value))
        except (ValueError, OverflowError):
            raise CampaignUnavailable("Campaign clock unavailable") from None

    async def create_draft(self, actor, *, category, subject, body, include_groups=(), exclude_groups=()):
        await self._owner(actor)
        payload = _payload(category, subject, body, include_groups, exclude_groups)
        groups = tuple(sorted(set(payload["include_groups"]) | set(payload["exclude_groups"])))
        return _draft(await self._store.create(actor, _encode(payload), groups, self._now()))

    async def get_draft(self, actor, draft_id):
        await self._owner(actor)
        return _draft(await self._store.get(actor, _identifier(draft_id)))

    async def list_drafts(self, actor, *, page=0):
        await self._owner(actor)
        if type(page) is not int or page < 0:
            raise CampaignInvalid("Invalid campaign page")
        page, total, rows = await self._store.list_owned(actor, page)
        items = []
        for row in rows:
            draft = _draft(row)
            items.append(CampaignSummary(draft.id, draft.revision, draft.category, draft.subject, draft.updated_at))
        return CampaignPage(page, total, tuple(items))

    async def edit_draft(self, actor, draft_id, *, expected_revision, category, subject, body,
                         include_groups=(), exclude_groups=()):
        await self._owner(actor)
        payload = _payload(category, subject, body, include_groups, exclude_groups)
        groups = tuple(sorted(set(payload["include_groups"]) | set(payload["exclude_groups"])))
        row = await self._store.edit(actor, _identifier(draft_id), _identifier(expected_revision),
                                     _encode(payload), groups, self._now())
        return _draft(row)

    async def freeze_draft(self, actor, draft_id, *, expected_revision):
        await self._owner(actor)
        _identifier(draft_id)
        _identifier(expected_revision)
        row = await self._store.get(actor, draft_id)
        _draft(row)  # Refuse corrupt/noncanonical content before any write.
        frozen = await self._store.freeze(actor, draft_id, expected_revision, row["payload_json"], self._now())
        return _revision(frozen)

    async def get_revision(self, actor, revision_id):
        await self._owner(actor)
        return _revision(await self._store.get_revision(actor, _identifier(revision_id)))

    async def dry_run(self, actor, draft_id, *, expected_revision):
        await self._owner(actor)
        _identifier(draft_id)
        _identifier(expected_revision)
        row = await self._store.get(actor, draft_id)
        draft = _draft(row)
        count, truncated = await self._store.estimate(
            actor, draft_id, expected_revision, row["payload_json"], draft.include_groups, draft.exclude_groups,
        )
        return CandidateEstimate(expected_revision, count, truncated)

    async def observe_private_update(self, *, actor_id, chat_id, chat_type, is_bot):
        """For a future authenticated private-update adapter ONLY.

        Never call with callback payload IDs, imports or admin-created identities.
        This code is not wired into any runtime handler in #947.
        """
        _identifier(actor_id)
        _identifier(chat_id)
        if chat_type != "private" or actor_id != chat_id or is_bot is not False:
            return False
        return await self._store.observe_private(actor_id, self._now())
