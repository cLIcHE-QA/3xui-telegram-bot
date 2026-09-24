"""Strict client for the v4.10.0 Host Control Agent.

There is intentionally no generic request/command API here. Callers can only
read service status, dispatch start|stop|restart, or read one operation journal
entry. A lost mutation response is recovered with a read-only lookup; the POST
is never retried automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Any

import aiohttp


SCHEMA_VERSION = 1
SERVICE = "x-ui.service"
ACTIONS = frozenset({"start", "stop", "restart"})
OPERATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
STATES = frozenset({"running", "stopped", "failed", "transitioning", "unknown"})
RESULTS = frozenset({"started", "success", "failed", "uncertain"})
NGINX_SNAPSHOT_ROUTE = "/v1/snapshots/nginx"
MAX_NGINX_SNAPSHOT_RESPONSE_BYTES = 10 * 1024 * 1024


class HostControlError(RuntimeError):
    def __init__(self, message: str, *, code: str = "", uncertain: bool = False):
        super().__init__(message)
        self.code = code
        self.uncertain = uncertain


@dataclass(frozen=True)
class HostControlStatus:
    host_id: str
    state: str
    active_state: str
    sub_state: str
    agent_version: str
    timestamp: str


@dataclass(frozen=True)
class HostControlOperation:
    host_id: str
    operation_id: str
    action: str
    result: str
    changed: bool
    before: str
    after: str
    duration_ms: int
    error_code: str
    created_at: str
    finished_at: str
    replayed: bool = False


class HostControlClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        expected_host_id: str,
        *,
        verify_tls: bool = True,
        timeout_seconds: float = 25.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.expected_host_id = expected_host_id
        self.verify_tls = verify_tls
        self.timeout_seconds = timeout_seconds

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    async def _http(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(json_body=body is not None),
                json=body,
                ssl=None if self.verify_tls else False,
                allow_redirects=False,
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except Exception as exc:
                    raise HostControlError(
                        f"Host-control returned invalid JSON (HTTP {response.status}).",
                        code="invalid_json",
                        uncertain=method == "POST",
                    ) from exc
                if not isinstance(payload, dict):
                    raise HostControlError(
                        "Host-control returned an invalid response shape.",
                        code="invalid_response",
                        uncertain=method == "POST",
                    )
                return int(response.status), payload

    def _validate_identity(self, payload: dict[str, Any]) -> None:
        if payload.get("schema") != SCHEMA_VERSION:
            raise HostControlError("Host-control schema mismatch.", code="schema_mismatch")
        if payload.get("service") != SERVICE:
            raise HostControlError("Host-control service mismatch.", code="service_mismatch")
        host_id = payload.get("host_id")
        if host_id != self.expected_host_id:
            raise HostControlError("Host-control host identity mismatch.", code="host_id_mismatch")

    def _parse_status(self, payload: dict[str, Any]) -> HostControlStatus:
        self._validate_identity(payload)
        state = str(payload.get("state") or "")
        if state not in STATES:
            raise HostControlError("Host-control returned an invalid service state.", code="invalid_state")
        return HostControlStatus(
            host_id=self.expected_host_id,
            state=state,
            active_state=str(payload.get("active_state") or ""),
            sub_state=str(payload.get("sub_state") or ""),
            agent_version=str(payload.get("agent_version") or ""),
            timestamp=str(payload.get("timestamp") or ""),
        )

    @staticmethod
    def _safe_duration(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError) as exc:
            raise HostControlError(
                "Host-control returned an invalid duration.",
                code="invalid_duration",
            ) from exc

    def _parse_operation(self, payload: dict[str, Any]) -> HostControlOperation:
        self._validate_identity(payload)
        operation_id = str(payload.get("operation_id") or "")
        action = str(payload.get("action") or "")
        result = str(payload.get("result") or "")
        if not OPERATION_ID_RE.fullmatch(operation_id):
            raise HostControlError("Host-control returned an invalid operation id.", code="invalid_operation_id")
        if action not in ACTIONS:
            raise HostControlError("Host-control returned an invalid action.", code="invalid_action")
        if result not in RESULTS:
            raise HostControlError("Host-control returned an invalid operation result.", code="invalid_result")
        return HostControlOperation(
            host_id=self.expected_host_id,
            operation_id=operation_id,
            action=action,
            result=result,
            changed=bool(payload.get("changed", False)),
            before=str(payload.get("before") or ""),
            after=str(payload.get("after") or ""),
            duration_ms=self._safe_duration(payload.get("duration_ms")),
            error_code=str(payload.get("error_code") or ""),
            created_at=str(payload.get("created_at") or ""),
            finished_at=str(payload.get("finished_at") or ""),
            replayed=bool(payload.get("replayed", False)),
        )

    async def download_nginx_snapshot(self) -> bytes:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.base_url}{NGINX_SNAPSHOT_ROUTE}",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/gzip, application/json",
                    },
                    ssl=None if self.verify_tls else False,
                    allow_redirects=False,
                ) as response:
                    if (
                        response.content_length is not None
                        and response.content_length > MAX_NGINX_SNAPSHOT_RESPONSE_BYTES
                    ):
                        raise HostControlError(
                            "Host-control nginx snapshot is too large.",
                            code="snapshot_too_large",
                        )
                    body_buffer = bytearray()
                    while True:
                        remaining = (
                            MAX_NGINX_SNAPSHOT_RESPONSE_BYTES + 1 - len(body_buffer)
                        )
                        chunk = await response.content.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        body_buffer.extend(chunk)
                        if len(body_buffer) > MAX_NGINX_SNAPSHOT_RESPONSE_BYTES:
                            raise HostControlError(
                                "Host-control nginx snapshot is too large.",
                                code="snapshot_too_large",
                            )
                    body = bytes(body_buffer)

                    if response.status != 200:
                        code = f"http_{response.status}"
                        try:
                            payload = json.loads(body.decode("utf-8"))
                            if isinstance(payload, dict) and payload.get("error"):
                                code = str(payload["error"])
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            pass
                        raise HostControlError(
                            "Host-control nginx snapshot request failed.",
                            code=code,
                        )

                    if response.headers.get("X-Host-Control-Schema") != str(SCHEMA_VERSION):
                        raise HostControlError(
                            "Host-control snapshot schema mismatch.",
                            code="schema_mismatch",
                        )
                    if response.headers.get("X-Host-Control-Host-Id") != self.expected_host_id:
                        raise HostControlError(
                            "Host-control snapshot host identity mismatch.",
                            code="host_id_mismatch",
                        )
                    if response.headers.get("X-Host-Control-Component") != "nginx":
                        raise HostControlError(
                            "Host-control snapshot component mismatch.",
                            code="component_mismatch",
                        )
                    expected = str(response.headers.get("X-Content-SHA256") or "").lower()
                    if not re.fullmatch(r"[0-9a-f]{64}", expected):
                        raise HostControlError(
                            "Host-control snapshot checksum is missing.",
                            code="invalid_checksum",
                        )
                    actual = hashlib.sha256(body).hexdigest()
                    if not hmac.compare_digest(actual, expected):
                        raise HostControlError(
                            "Host-control snapshot checksum mismatch.",
                            code="checksum_mismatch",
                        )
                    return body
        except HostControlError:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise HostControlError(
                "Host-control nginx snapshot is unavailable.",
                code="network_error",
            ) from exc

    async def status(self) -> HostControlStatus:
        try:
            status, payload = await self._http("GET", "/v1/status")
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise HostControlError(
                "Host-control status is unavailable.",
                code="network_error",
            ) from exc
        if status != 200:
            code = str(payload.get("error") or f"http_{status}")
            raise HostControlError("Host-control status request failed.", code=code)
        return self._parse_status(payload)

    async def get_operation(self, operation_id: str) -> HostControlOperation | None:
        if not OPERATION_ID_RE.fullmatch(operation_id):
            raise HostControlError("Invalid host-control operation id.", code="invalid_operation_id")
        try:
            status, payload = await self._http("GET", f"/v1/operations/{operation_id}")
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise HostControlError(
                "Host-control operation lookup is unavailable.",
                code="network_error",
            ) from exc
        if status == 404:
            return None
        if status != 200:
            code = str(payload.get("error") or f"http_{status}")
            raise HostControlError("Host-control operation lookup failed.", code=code)
        operation = self._parse_operation(payload)
        if operation.operation_id != operation_id:
            raise HostControlError("Host-control operation identity mismatch.", code="operation_id_mismatch")
        return operation

    async def execute(self, action: str, operation_id: str) -> HostControlOperation:
        if action not in ACTIONS:
            raise HostControlError("Unsupported host-control action.", code="invalid_action")
        if not OPERATION_ID_RE.fullmatch(operation_id):
            raise HostControlError("Invalid host-control operation id.", code="invalid_operation_id")

        # Fail closed before mutation: validate schema/service/host identity using
        # a read-only request. If DNS/routing points at the wrong agent, POST is
        # never sent.
        preflight = await self.status()
        if preflight.state == "unknown":
            raise HostControlError(
                "Host-control service state is unknown; mutation blocked.",
                code="service_state_unknown",
            )
        if preflight.state == "transitioning":
            raise HostControlError(
                "Host-control service is transitioning; mutation blocked.",
                code="service_transitioning",
            )

        try:
            status, payload = await self._http(
                "POST",
                "/v1/actions",
                body={"operation_id": operation_id, "action": action},
            )
        except (aiohttp.ClientError, TimeoutError, HostControlError) as exc:
            # A POST may have reached the agent. Never retry it. Recover only via
            # the read-only persistent operation journal.
            try:
                recovered = await self.get_operation(operation_id)
            except HostControlError:
                recovered = None
            if recovered is not None:
                if recovered.action != action:
                    raise HostControlError(
                        "Host-control operation action mismatch.",
                        code="operation_action_mismatch",
                        uncertain=True,
                    ) from exc
                return recovered
            raise HostControlError(
                "Host-control outcome is uncertain; mutation was not retried.",
                code="unconfirmed",
                uncertain=True,
            ) from exc

        if status in {200, 503, 504} and "operation_id" in payload:
            try:
                operation = self._parse_operation(payload)
            except HostControlError as exc:
                raise HostControlError(
                    "Host-control mutation response failed validation.",
                    code=exc.code or "invalid_mutation_response",
                    uncertain=True,
                ) from exc
            if operation.operation_id != operation_id or operation.action != action:
                raise HostControlError(
                    "Host-control operation identity mismatch.",
                    code="operation_identity_mismatch",
                    uncertain=True,
                )
            return operation

        code = str(payload.get("error") or f"http_{status}")
        raise HostControlError(
            "Host-control action was rejected.",
            code=code,
            uncertain=False,
        )