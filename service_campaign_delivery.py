"""#948 source-only scheduling/worker API. No Telegram or runtime wiring."""
import asyncio
from dataclasses import dataclass, field
import hashlib
import re
import time
from typing import Protocol
import uuid

from campaign_queue_store import CampaignQueueStore
from campaign_schedule import parse_campaign_schedule
from campaign_store import CampaignConflict, CampaignOutcomeUnknown, CampaignUnavailable
from service_campaigns import CampaignDenied, CampaignInvalid, ServiceCampaigns, _decode, _identifier, _revision


POLICY_TIMEOUT = 3
TRANSPORT_TIMEOUT = 10
_STATES = ("pending", "intent", "sent", "unavailable", "unknown", "failed", "cancelled", "skipped")


class CampaignPolicy(Protocol):
    async def allow_category(self, category: str) -> bool: ...
    async def allow_recipient(self, category: str, telegram_id: int) -> bool: ...


@dataclass(frozen=True)
class CampaignJob:
    id: int
    operation_id: str
    revision_id: int
    state: str
    snapshot_sha256: str
    payload_sha256: str
    due_at: int
    timezone: str
    local_time: str
    ready_at: int
    counts: tuple[tuple[str, int], ...]

    @property
    def candidates(self):
        return sum(count for _, count in self.counts)


@dataclass(frozen=True)
class CampaignJobPage:
    page: int
    total: int
    items: tuple[CampaignJob, ...]


@dataclass(frozen=True)
class CampaignEnvelope:
    chat_id: int = field(repr=False)
    subject: str = field(repr=False)
    body: str = field(repr=False)
    operation_id: str
    parse_mode: None = None
    link_preview: bool = False


@dataclass(frozen=True)
class CampaignReply:
    """Only a trusted adapter may classify a confirmed Bot API response.

    kind: confirmed / rate_limited / unavailable / unknown. A network exception,
    invalid/mismatched acknowledgment or unknown 5xx outcome is never failure.
    """
    kind: str = field(repr=False)
    chat_id: int | None = field(default=None, repr=False)
    message_id: int | None = field(default=None, repr=False)
    retry_after: int = field(default=0, repr=False)
    reason: str = field(default="", repr=False)


class CampaignTransport(Protocol):
    async def send(self, envelope: CampaignEnvelope) -> CampaignReply: ...


def _job(view):
    row, counts = view
    if set(counts) - set(_STATES) or not 0 < sum(counts.values()) <= 1000:
        raise CampaignUnavailable("Campaign progress unavailable")
    keys = ("id", "operation_id", "revision_id", "state", "snapshot_sha256", "payload_sha256",
            "due_at", "timezone", "local_time", "ready_at")
    return CampaignJob(**{key: row[key] for key in keys}, counts=tuple((s, counts.get(s, 0)) for s in _STATES))


class CampaignDelivery(ServiceCampaigns):
    def __init__(self, db, *, authorize_owner=None, policy: CampaignPolicy | None = None,
                 enabled=False, clock=time.time):
        super().__init__(db, authorize_owner=authorize_owner, clock=clock)
        self._queue = CampaignQueueStore(db, clock=self._now)
        self._policy = policy
        self._enabled = enabled is True

    def _ready(self):
        return self._enabled and self._policy is not None

    async def _category(self, category):
        if not self._ready():
            return False
        try:
            return await asyncio.wait_for(self._policy.allow_category(category), POLICY_TIMEOUT) is True
        except Exception:
            raise CampaignUnavailable("Campaign policy unavailable") from None

    async def _recipient(self, category, telegram_id):
        if not self._ready():
            return False
        try:
            return await asyncio.wait_for(self._policy.allow_recipient(category, telegram_id), POLICY_TIMEOUT) is True
        except Exception:
            raise CampaignUnavailable("Campaign policy unavailable") from None

    async def _require_category(self, category):
        if not await self._category(category):
            raise CampaignDenied("Campaign delivery denied")

    async def _job_payload(self, actor, job_id):
        view = await self._queue.get(actor, _identifier(job_id))
        row = await self._store.get_revision(actor, view[0]["revision_id"])
        _revision(row)
        if row["payload_sha256"] != view[0]["payload_sha256"]:
            raise CampaignUnavailable("Campaign content unavailable")
        return view, _decode(row["payload_json"])

    async def prepare_job(self, actor, revision_id, *, operation_id, local_time, timezone):
        await self._owner(actor)
        if not self._ready():
            raise CampaignDenied("Campaign delivery denied")
        try:
            operation = uuid.UUID(operation_id)
            if operation.version != 4 or str(operation) != operation_id:
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            raise CampaignInvalid("Invalid campaign operation") from None
        row = await self._store.get_revision(actor, _identifier(revision_id))
        _revision(row)
        payload = _decode(row["payload_json"])
        await self._require_category(payload["category"])
        now = self._now()
        schedule = parse_campaign_schedule(local_time, timezone, now=now)
        view = await self._queue.prepare(actor, operation_id, revision_id, row["payload_json"], row["payload_sha256"],
                                         schedule, payload["include_groups"], payload["exclude_groups"], now)
        return _job(view)

    async def get_job(self, actor, job_id):
        await self._owner(actor)
        return _job(await self._queue.get(actor, _identifier(job_id)))

    async def list_jobs(self, actor, *, page=0):
        await self._owner(actor)
        if type(page) is not int or page < 0:
            raise CampaignInvalid("Invalid campaign page")
        page, total, views = await self._queue.list_owned(actor, page)
        return CampaignJobPage(page, total, tuple(_job(view) for view in views))

    async def confirm_job(self, actor, job_id, *, expected_snapshot):
        await self._owner(actor)
        if not isinstance(expected_snapshot, str) or not re.fullmatch("[0-9a-f]{64}", expected_snapshot):
            raise CampaignInvalid("Invalid campaign confirmation")
        view, payload = await self._job_payload(actor, job_id)
        await self._require_category(payload["category"])
        return _job(await self._queue.confirm(actor, view[0]["id"], expected_snapshot, self._now()))

    async def pause_job(self, actor, job_id):
        await self._owner(actor)
        return _job(await self._queue.control(actor, _identifier(job_id), "pause", self._now()))

    async def cancel_job(self, actor, job_id):
        await self._owner(actor)
        return _job(await self._queue.control(actor, _identifier(job_id), "cancel", self._now()))

    async def resume_job(self, actor, job_id, *, local_time, timezone):
        await self._owner(actor)
        view, payload = await self._job_payload(actor, job_id)
        await self._require_category(payload["category"])
        now = self._now()
        schedule = parse_campaign_schedule(local_time, timezone, now=now)
        return _job(await self._queue.control(actor, view[0]["id"], "resume", now, ready_at=schedule.due_at))


class CampaignWorker:
    """Explicit one-tick isolated worker; constructor starts no tasks/listeners.

    Production assembly, policy #501 and a real Bot API adapter are absent.
    A timeout can leave an unknown external outcome; it cannot unsend/replay it.
    """
    def __init__(self, service: CampaignDelivery, *, transport: CampaignTransport | None = None):
        self._service = service
        self._transport = transport
        self._token = uuid.uuid4().hex
        self._lock = asyncio.Lock()
        self._stopping = False
        self._has_claimed = False
        self._pending = set()

    def _consume(self, task):
        self._pending.discard(task)
        try:
            task.exception()
        except asyncio.CancelledError:
            pass

    def _cancel_transport(self, task):
        self._pending.add(task)
        task.add_done_callback(self._consume)
        task.cancel()

    async def _call(self, envelope, lease_until):
        async def request():
            # Recheck after task scheduling, immediately before invoking the
            # adapter. An expired lease never authorizes a new dispatch.
            if self._service._now() >= lease_until:
                return CampaignReply("unknown")
            return await self._transport.send(envelope)
        try:
            task = asyncio.create_task(request(), name="campaign-delivery-transport")
        except Exception:
            return CampaignReply("unknown")
        try:
            done, _ = await asyncio.wait({task}, timeout=TRANSPORT_TIMEOUT)
        except asyncio.CancelledError:
            self._cancel_transport(task)
            raise
        if not done:
            self._cancel_transport(task)
            return CampaignReply("unknown")
        try:
            return task.result()
        except (Exception, asyncio.CancelledError):
            return CampaignReply("unknown")

    @staticmethod
    def _classify(reply, recipient):
        if type(reply) is not CampaignReply or type(reply.chat_id) is not int or reply.chat_id != recipient:
            return "unknown", 0, ""
        if reply.kind == "confirmed":
            try:
                _identifier(reply.message_id)
            except CampaignInvalid:
                return "unknown", 0, ""
            return "sent", 0, ""
        if reply.kind == "rate_limited" and type(reply.retry_after) is int and 1 <= reply.retry_after <= 3600:
            return "rate_limited", reply.retry_after, ""
        if reply.kind == "unavailable" and reply.reason in {"blocked", "chat_unavailable"}:
            return "unavailable", 0, "blocked" if reply.reason == "blocked" else "user_unavailable"
        return "unknown", 0, ""

    async def _authorized(self, job, payload):
        try:
            await asyncio.wait_for(self._service._owner(job["owner_id"]), POLICY_TIMEOUT)
        except (CampaignDenied, CampaignUnavailable, asyncio.TimeoutError):
            return False
        return await self._service._category(payload["category"])

    async def tick(self):
        service = self._service
        async with self._lock:
            if self._stopping or not service._ready() or self._transport is None:
                if self._has_claimed:
                    await service._queue.suspend(self._token, service._now())
                    self._has_claimed = False
                return None
            job = None
            intent = None
            try:
                job = await service._queue.claim(self._token, service._now())
                if job is None:
                    return None
                self._has_claimed = True
                if hashlib.sha256(job["payload_json"].encode()).hexdigest() != job["payload_sha256"]:
                    raise CampaignUnavailable("Campaign content unavailable")
                payload = _decode(job["payload_json"])
                if not await self._authorized(job, payload) or self._stopping:
                    await service._queue.suspend(self._token, service._now())
                    self._has_claimed = False
                    return _job(await service._queue.get(job["owner_id"], job["id"]))
                intent = await service._queue.begin_intent(
                    self._token, job["id"], payload["include_groups"], payload["exclude_groups"], service._now())
                if intent is None:
                    return _job(await service._queue.get(job["owner_id"], job["id"]))
                allowed, reason = await service._queue.dispatch_status(
                    self._token, intent["id"], payload["include_groups"], payload["exclude_groups"], service._now())
                try:
                    if allowed and (not await self._authorized(job, payload) or self._stopping):
                        allowed, reason = False, "policy_denied"
                    if allowed and not await service._recipient(payload["category"], intent["telegram_id"]):
                        allowed, reason = False, "recipient_denied"
                except CampaignUnavailable:
                    allowed, reason = False, "policy_denied"
                if allowed:
                    allowed, reason = await service._queue.dispatch_status(
                        self._token, intent["id"], payload["include_groups"], payload["exclude_groups"], service._now())
                if service._now() >= intent["lease_until"]:
                    allowed, reason = False, "unknown"
                if not allowed:
                    kind = "unknown" if reason == "unknown" else "not_sent"
                    retry_after = 0
                else:
                    envelope = CampaignEnvelope(intent["telegram_id"], payload["subject"], payload["body"], job["operation_id"])
                    reply = await self._call(envelope, intent["lease_until"])
                    kind, retry_after, reason = self._classify(reply, intent["telegram_id"])
                if kind == "unknown":
                    self._stopping = True
                result = await service._queue.finish(self._token, intent["id"], kind, service._now(),
                                                     retry_after=retry_after, reason=reason)
                if result is None:
                    self._stopping = True
                    raise CampaignOutcomeUnknown("Campaign delivery outcome unknown")
                return _job(result)
            except asyncio.CancelledError:
                self._stopping = True
                try:
                    await asyncio.shield(service._queue.suspend(self._token, service._now()))
                except Exception:
                    pass
                raise
            except (CampaignUnavailable, CampaignConflict, CampaignInvalid):
                self._stopping = True
                try:
                    await service._queue.suspend(self._token, service._now())
                except Exception:
                    pass
                if intent is not None:
                    raise CampaignOutcomeUnknown("Campaign delivery outcome unknown") from None
                raise

    async def close(self):
        self._stopping = True
        async with self._lock:
            if self._has_claimed:
                await self._service._queue.suspend(self._token, self._service._now())
                self._has_claimed = False
            # A non-cooperative transport may still complete later: never claim
            # cancellation/rollback of its unknown external outcome.
            return not self._pending
