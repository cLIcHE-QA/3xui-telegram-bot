"""Strict client for the restricted Safe Bot Self-Update Deploy Agent."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import aiohttp


SCHEMA_VERSION = 1
AGENT_NAME = "3xui-deploy-agent"
OPERATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
RELEASE_RE = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+\Z")
STATES = frozenset({
    "queued", "preflight", "backup", "building", "deploying", "verifying",
    "success", "failed", "unknown",
})
TERMINAL_STATES = frozenset({"success", "failed", "unknown"})


class DeployControlError(RuntimeError):
    def __init__(self, message: str, *, code: str = "", uncertain: bool = False):
        super().__init__(message)
        self.code = code
        self.uncertain = uncertain


@dataclass(frozen=True)
class DeployStatus:
    current_release: str
    current_sha: str
    bot_version: str
    health: str
    db: str
    connectivity: str
    active_operation: str
    agent_version: str


@dataclass(frozen=True)
class DeployPreflight:
    release: str
    current_release: str
    current_sha: str
    target_sha: str
    target_version: str
    downgrade: bool
    notes: str


@dataclass(frozen=True)
class DeployOperation:
    operation_id: str
    release: str
    allow_downgrade: bool
    state: str
    current_release: str
    target_sha: str
    error_code: str
    created_at: str
    updated_at: str
    finished_at: str
    replayed: bool = False


class DeployControlClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
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
        body: dict[str, object] | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[int, dict[str, Any]]:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds or self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(json_body=body is not None),
                json=body,
                allow_redirects=False,
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except Exception as exc:
                    raise DeployControlError(
                        f"Deploy Agent returned invalid JSON (HTTP {response.status}).",
                        code="invalid_json",
                        uncertain=method == "POST",
                    ) from exc
                if not isinstance(payload, dict):
                    raise DeployControlError(
                        "Deploy Agent returned an invalid response shape.",
                        code="invalid_response",
                        uncertain=method == "POST",
                    )
                return int(response.status), payload

    @staticmethod
    def _validate_identity(payload: dict[str, Any]) -> None:
        if payload.get("schema") != SCHEMA_VERSION:
            raise DeployControlError("Deploy Agent schema mismatch.", code="schema_mismatch")
        if payload.get("agent") != AGENT_NAME:
            raise DeployControlError("Deploy Agent identity mismatch.", code="agent_mismatch")

    @classmethod
    def _parse_operation(cls, payload: dict[str, Any]) -> DeployOperation:
        cls._validate_identity(payload)
        operation_id = str(payload.get("operation_id") or "")
        release = str(payload.get("release") or "")
        state = str(payload.get("state") or "")
        allow_downgrade = payload.get("allow_downgrade")
        if not OPERATION_ID_RE.fullmatch(operation_id):
            raise DeployControlError("Deploy Agent returned invalid operation id.", code="invalid_operation_id")
        if not RELEASE_RE.fullmatch(release):
            raise DeployControlError("Deploy Agent returned invalid release.", code="invalid_release")
        if state not in STATES:
            raise DeployControlError("Deploy Agent returned invalid operation state.", code="invalid_state")
        if not isinstance(allow_downgrade, bool):
            raise DeployControlError("Deploy Agent returned invalid downgrade flag.", code="invalid_downgrade_flag")
        return DeployOperation(
            operation_id=operation_id,
            release=release,
            allow_downgrade=allow_downgrade,
            state=state,
            current_release=str(payload.get("current_release") or ""),
            target_sha=str(payload.get("target_sha") or ""),
            error_code=str(payload.get("error_code") or ""),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            finished_at=str(payload.get("finished_at") or ""),
            replayed=bool(payload.get("replayed", False)),
        )

    @staticmethod
    def _error(payload: dict[str, Any], status: int, *, uncertain: bool = False) -> DeployControlError:
        code = str(payload.get("error") or f"http_{status}")
        return DeployControlError("Deploy Agent request failed.", code=code, uncertain=uncertain)

    async def status(self) -> DeployStatus:
        try:
            status, payload = await self._http("GET", "/v1/status", timeout_seconds=45)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise DeployControlError("Deploy Agent is unavailable.", code="network_error") from exc
        if status != 200:
            raise self._error(payload, status)
        self._validate_identity(payload)
        active = str(payload.get("active_operation") or "")
        if active and not OPERATION_ID_RE.fullmatch(active):
            raise DeployControlError("Deploy Agent returned invalid active operation.", code="invalid_operation_id")
        return DeployStatus(
            current_release=str(payload.get("current_release") or ""),
            current_sha=str(payload.get("current_sha") or ""),
            bot_version=str(payload.get("bot_version") or ""),
            health=str(payload.get("health") or ""),
            db=str(payload.get("db") or ""),
            connectivity=str(payload.get("connectivity") or ""),
            active_operation=active,
            agent_version=str(payload.get("agent_version") or ""),
        )

    async def latest_release(self) -> str:
        try:
            status, payload = await self._http("GET", "/v1/releases/latest", timeout_seconds=120)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise DeployControlError("Published release lookup is unavailable.", code="network_error") from exc
        if status != 200:
            raise self._error(payload, status)
        self._validate_identity(payload)
        release = str(payload.get("release") or "")
        if not RELEASE_RE.fullmatch(release):
            raise DeployControlError("Deploy Agent returned invalid release.", code="invalid_release")
        return release

    async def preflight(self, release: str) -> DeployPreflight:
        if not RELEASE_RE.fullmatch(release):
            raise DeployControlError("Invalid release.", code="invalid_release")
        try:
            status, payload = await self._http("GET", f"/v1/preflight/{release}", timeout_seconds=120)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise DeployControlError("Deploy preflight is unavailable.", code="network_error") from exc
        if status != 200:
            raise self._error(payload, status)
        self._validate_identity(payload)
        returned = str(payload.get("release") or "")
        if returned != release:
            raise DeployControlError("Deploy preflight release mismatch.", code="release_mismatch")
        target_sha = str(payload.get("target_sha") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", target_sha):
            raise DeployControlError("Deploy preflight target SHA is invalid.", code="invalid_target_sha")
        return DeployPreflight(
            release=release,
            current_release=str(payload.get("current_release") or ""),
            current_sha=str(payload.get("current_sha") or ""),
            target_sha=target_sha,
            target_version=str(payload.get("target_version") or ""),
            downgrade=bool(payload.get("downgrade", False)),
            notes=str(payload.get("notes") or "")[:6000],
        )

    async def get_operation(self, operation_id: str) -> DeployOperation | None:
        if not OPERATION_ID_RE.fullmatch(operation_id):
            raise DeployControlError("Invalid deploy operation id.", code="invalid_operation_id")
        try:
            status, payload = await self._http("GET", f"/v1/operations/{operation_id}")
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise DeployControlError("Deploy operation lookup is unavailable.", code="network_error") from exc
        if status == 404:
            return None
        if status != 200:
            raise self._error(payload, status)
        operation = self._parse_operation(payload)
        if operation.operation_id != operation_id:
            raise DeployControlError("Deploy operation identity mismatch.", code="operation_id_mismatch")
        return operation

    async def history(self) -> list[DeployOperation]:
        try:
            status, payload = await self._http("GET", "/v1/history")
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise DeployControlError("Deploy history is unavailable.", code="network_error") from exc
        if status != 200:
            raise self._error(payload, status)
        self._validate_identity(payload)
        raw = payload.get("operations")
        if not isinstance(raw, list):
            raise DeployControlError("Deploy history has invalid shape.", code="invalid_history")
        return [self._parse_operation(item) for item in raw if isinstance(item, dict)]

    async def deploy(
        self,
        operation_id: str,
        release: str,
        *,
        allow_downgrade: bool = False,
    ) -> DeployOperation:
        if not OPERATION_ID_RE.fullmatch(operation_id):
            raise DeployControlError("Invalid deploy operation id.", code="invalid_operation_id")
        if not RELEASE_RE.fullmatch(release):
            raise DeployControlError("Invalid release.", code="invalid_release")
        body = {
            "operation_id": operation_id,
            "release": release,
            "allow_downgrade": bool(allow_downgrade),
        }
        try:
            status, payload = await self._http("POST", "/v1/deploy", body=body, timeout_seconds=30)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise DeployControlError(
                "Deploy request outcome is unknown; mutation was not retried.",
                code="network_error",
                uncertain=True,
            ) from exc
        if status not in {200, 202}:
            raise self._error(payload, status, uncertain=False)
        operation = self._parse_operation(payload)
        if operation.operation_id != operation_id or operation.release != release:
            raise DeployControlError("Deploy operation response mismatch.", code="operation_mismatch", uncertain=True)
        return operation
