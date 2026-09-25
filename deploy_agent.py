#!/usr/bin/env python3
"""Restricted deploy agent for Safe Bot Self-Update.

This process is intentionally not a shell/exec gateway. Its API exposes only:
- GET /v1/status
- GET /v1/releases/latest
- GET /v1/preflight/<vX.Y.Z>
- GET /v1/history
- GET /v1/operations/<operation_id>
- POST /v1/deploy with {operation_id, release, allow_downgrade}

All privileged work goes through one root-owned helper with a closed command
surface. Request data is never used as an executable, path, environment key or
arbitrary argv.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import threading
from typing import Any
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
AGENT_VERSION = "0.1.1"
AGENT_NAME = "3xui-deploy-agent"
SUDO = "/usr/bin/sudo"
HELPER = "/usr/local/libexec/3xui-bot-deploy"
DEFAULT_LISTEN = "172.19.0.1:18184"
DEFAULT_DB = "/var/lib/3xui-deploy-agent/agent.sqlite3"
DEFAULT_TOKEN_FILE = "/etc/3xui-deploy-agent/token"
MAX_BODY_BYTES = 4096
OPERATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
RELEASE_RE = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+\Z")
ACTIVE_STATES = frozenset({"queued", "preflight", "backup", "building", "deploying", "verifying"})
TERMINAL_STATES = frozenset({"success", "failed", "unknown"})
ALL_STATES = ACTIVE_STATES | TERMINAL_STATES


class DeployAgentConfigError(RuntimeError):
    pass


class DeployAgentError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class AgentConfig:
    listen_host: str
    listen_port: int
    token: str
    db_path: Path

    @classmethod
    def from_env(cls) -> "AgentConfig":
        listen = os.environ.get("DEPLOY_AGENT_LISTEN", DEFAULT_LISTEN).strip()
        host, sep, port_text = listen.rpartition(":")
        if not sep or not host:
            raise DeployAgentConfigError("DEPLOY_AGENT_LISTEN must be an IP:port pair.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise DeployAgentConfigError("DEPLOY_AGENT_LISTEN host must be an IP address.") from exc
        if address.is_unspecified or address.is_multicast or not (address.is_loopback or address.is_private):
            raise DeployAgentConfigError("Deploy Agent may listen only on loopback/private IP.")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise DeployAgentConfigError("Invalid deploy-agent listen port.") from exc
        if not (1 <= port <= 65535):
            raise DeployAgentConfigError("Invalid deploy-agent listen port.")

        token_file = Path(os.environ.get("DEPLOY_AGENT_TOKEN_FILE", DEFAULT_TOKEN_FILE))
        try:
            if token_file.is_symlink():
                raise DeployAgentConfigError("Deploy Agent token file must not be a symlink.")
            info = token_file.stat()
        except OSError as exc:
            raise DeployAgentConfigError("Deploy Agent token file is unavailable.") from exc
        if not stat.S_ISREG(info.st_mode):
            raise DeployAgentConfigError("Deploy Agent token path must be a regular file.")
        if info.st_mode & 0o077:
            raise DeployAgentConfigError("Deploy Agent token file must be mode 0600.")
        try:
            token = token_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise DeployAgentConfigError("Deploy Agent token file cannot be read.") from exc
        if len(token) < 43:
            raise DeployAgentConfigError("Deploy Agent token is too short; use at least 32 random bytes.")

        helper = Path(HELPER)
        try:
            helper_info = helper.stat()
        except OSError as exc:
            raise DeployAgentConfigError("Deploy helper is unavailable.") from exc
        if not stat.S_ISREG(helper_info.st_mode) or not os.access(helper, os.X_OK):
            raise DeployAgentConfigError("Deploy helper must be an executable regular file.")
        if helper_info.st_uid != 0 or helper_info.st_mode & 0o022:
            raise DeployAgentConfigError("Deploy helper must be root-owned and not group/world writable.")

        db_path = Path(os.environ.get("DEPLOY_AGENT_DB", DEFAULT_DB))
        return cls(host, port, token, db_path)


@dataclass(frozen=True)
class OperationRecord:
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


def _row_to_operation(row: sqlite3.Row) -> OperationRecord:
    return OperationRecord(
        operation_id=str(row["operation_id"]),
        release=str(row["release"]),
        allow_downgrade=bool(row["allow_downgrade"]),
        state=str(row["state"]),
        current_release=str(row["current_release"]),
        target_sha=str(row["target_sha"]),
        error_code=str(row["error_code"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        finished_at=str(row["finished_at"]),
    )


class OperationJournal:
    """Persistent metadata-only journal. No credentials, commands or raw logs."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operations (
                    operation_id TEXT PRIMARY KEY,
                    release TEXT NOT NULL,
                    allow_downgrade INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL,
                    current_release TEXT NOT NULL DEFAULT '',
                    target_sha TEXT NOT NULL DEFAULT '',
                    error_code TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def get(self, operation_id: str) -> OperationRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        return _row_to_operation(row) if row else None

    def recent(self, limit: int = 20) -> list[OperationRecord]:
        limit = max(1, min(50, int(limit)))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM operations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_operation(row) for row in rows]

    def active(self) -> list[OperationRecord]:
        placeholders = ",".join("?" for _ in ACTIVE_STATES)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM operations WHERE state IN ({placeholders}) ORDER BY created_at",
                tuple(sorted(ACTIVE_STATES)),
            ).fetchall()
        return [_row_to_operation(row) for row in rows]

    def create(self, operation_id: str, release: str, allow_downgrade: bool) -> OperationRecord:
        now = utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO operations(
                    operation_id, release, allow_downgrade, state,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'queued', ?, ?)
                """,
                (operation_id, release, 1 if allow_downgrade else 0, now, now),
            )
        return self.get(operation_id)  # type: ignore[return-value]

    def update(
        self,
        operation_id: str,
        *,
        state: str,
        current_release: str | None = None,
        target_sha: str | None = None,
        error_code: str | None = None,
    ) -> OperationRecord:
        if state not in ALL_STATES:
            raise ValueError(f"unsupported operation state: {state}")
        now = utc_now()
        terminal = state in TERMINAL_STATES
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise KeyError(operation_id)
            conn.execute(
                """
                UPDATE operations
                   SET state = ?,
                       current_release = ?,
                       target_sha = ?,
                       error_code = ?,
                       updated_at = ?,
                       finished_at = CASE WHEN ? THEN ? ELSE finished_at END
                 WHERE operation_id = ?
                """,
                (
                    state,
                    str(current_release if current_release is not None else row["current_release"]),
                    str(target_sha if target_sha is not None else row["target_sha"]),
                    str(error_code if error_code is not None else row["error_code"]),
                    now,
                    1 if terminal else 0,
                    now,
                    operation_id,
                ),
            )
        return self.get(operation_id)  # type: ignore[return-value]


def _parse_machine_output(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", key):
            values[key] = value.strip()
    return values


def _safe_env() -> dict[str, str]:
    return {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}


class DeployAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.journal = OperationJournal(config.db_path)
        self._mutation_lock = threading.Lock()
        self._recover_interrupted()

    def authenticate(self, authorization: str | None) -> bool:
        prefix = "Bearer "
        if not authorization or not authorization.startswith(prefix):
            return False
        supplied = authorization[len(prefix):]
        return hmac.compare_digest(supplied, self.config.token)

    def _helper(
        self,
        *args: str,
        timeout: float = 120.0,
    ) -> tuple[int, str, dict[str, str]]:
        completed = subprocess.run(
            [SUDO, HELPER, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
            env=_safe_env(),
        )
        output = completed.stdout or ""
        return int(completed.returncode), output, _parse_machine_output(output)

    @staticmethod
    def _healthy_status(values: dict[str, str], release: str = "") -> bool:
        if values.get("STATUS_OK") != "1":
            return False
        if values.get("HEALTH") != "ok" or values.get("DB") != "ok":
            return False
        if values.get("CONNECTIVITY") != "ok":
            return False
        return not release or values.get("CURRENT_RELEASE") == release

    def _status_values(self) -> dict[str, str]:
        try:
            code, _output, values = self._helper("status", timeout=45)
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
            return {}
        return values if code == 0 else values

    def _recover_interrupted(self) -> None:
        active = self.journal.active()
        if not active:
            return
        values = self._status_values()
        for operation in active:
            if self._healthy_status(values, operation.release):
                self.journal.update(
                    operation.operation_id,
                    state="success",
                    current_release=values.get("CURRENT_RELEASE", ""),
                    target_sha=values.get("CURRENT_SHA", operation.target_sha),
                    error_code="",
                )
            else:
                self.journal.update(
                    operation.operation_id,
                    state="unknown",
                    current_release=values.get("CURRENT_RELEASE", operation.current_release),
                    target_sha=operation.target_sha,
                    error_code="agent_interrupted_mutation_not_retried",
                )

    def operation_payload(self, record: OperationRecord, *, replayed: bool = False) -> dict[str, object]:
        payload = {
            "schema": SCHEMA_VERSION,
            "agent": AGENT_NAME,
            **asdict(record),
            "replayed": replayed,
        }
        return payload

    def status_payload(self) -> tuple[int, dict[str, object]]:
        try:
            code, _output, values = self._helper("status", timeout=45)
        except subprocess.TimeoutExpired:
            return HTTPStatus.GATEWAY_TIMEOUT, {"error": "status_timeout"}
        except (OSError, subprocess.SubprocessError):
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "status_unavailable"}
        if code != 0 or values.get("STATUS_OK") != "1":
            return HTTPStatus.SERVICE_UNAVAILABLE, {
                "schema": SCHEMA_VERSION,
                "agent": AGENT_NAME,
                "agent_version": AGENT_VERSION,
                "error": "production_status_failed",
                "current_release": values.get("CURRENT_RELEASE", ""),
            }
        return HTTPStatus.OK, {
            "schema": SCHEMA_VERSION,
            "agent": AGENT_NAME,
            "agent_version": AGENT_VERSION,
            "current_release": values.get("CURRENT_RELEASE", ""),
            "current_sha": values.get("CURRENT_SHA", ""),
            "bot_version": values.get("BOT_VERSION", ""),
            "health": values.get("HEALTH", ""),
            "db": values.get("DB", ""),
            "connectivity": values.get("CONNECTIVITY", ""),
            "active_operation": self.journal.active()[0].operation_id if self.journal.active() else "",
        }

    def latest_payload(self) -> tuple[int, dict[str, object]]:
        if self.journal.active():
            return HTTPStatus.CONFLICT, {"error": "deployment_in_progress"}
        try:
            code, _output, values = self._helper("latest", timeout=120)
        except subprocess.TimeoutExpired:
            return HTTPStatus.GATEWAY_TIMEOUT, {"error": "release_lookup_timeout"}
        except (OSError, subprocess.SubprocessError):
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "release_lookup_unavailable"}
        release = values.get("LATEST_RELEASE", "")
        if code != 0 or not RELEASE_RE.fullmatch(release):
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "release_lookup_failed"}
        return HTTPStatus.OK, {
            "schema": SCHEMA_VERSION,
            "agent": AGENT_NAME,
            "release": release,
        }

    def preflight_payload(self, release: str) -> tuple[int, dict[str, object]]:
        if not RELEASE_RE.fullmatch(release):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_release"}
        if self.journal.active():
            return HTTPStatus.CONFLICT, {"error": "deployment_in_progress"}
        try:
            code, _output, values = self._helper("preflight", release, timeout=120)
        except subprocess.TimeoutExpired:
            return HTTPStatus.GATEWAY_TIMEOUT, {"error": "preflight_timeout"}
        except (OSError, subprocess.SubprocessError):
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "preflight_unavailable"}
        if code != 0 or values.get("PREFLIGHT_OK") != "1":
            return HTTPStatus.CONFLICT, {
                "schema": SCHEMA_VERSION,
                "agent": AGENT_NAME,
                "error": values.get("ERROR_CODE", "preflight_failed"),
            }
        try:
            notes_code, notes_output, notes_values = self._helper("notes", release, timeout=30)
        except subprocess.TimeoutExpired:
            return HTTPStatus.GATEWAY_TIMEOUT, {
                "schema": SCHEMA_VERSION,
                "agent": AGENT_NAME,
                "error": "release_notes_timeout",
            }
        except (OSError, subprocess.SubprocessError):
            return HTTPStatus.SERVICE_UNAVAILABLE, {
                "schema": SCHEMA_VERSION,
                "agent": AGENT_NAME,
                "error": "release_notes_unavailable",
            }
        notes = notes_output[:6000].strip()
        if notes_code != 0 or not notes:
            return HTTPStatus.CONFLICT, {
                "schema": SCHEMA_VERSION,
                "agent": AGENT_NAME,
                "error": notes_values.get("ERROR_CODE", "release_notes_missing"),
            }
        return HTTPStatus.OK, {
            "schema": SCHEMA_VERSION,
            "agent": AGENT_NAME,
            "release": release,
            "current_release": values.get("CURRENT_RELEASE", ""),
            "current_sha": values.get("CURRENT_SHA", ""),
            "target_sha": values.get("TARGET_SHA", ""),
            "target_version": values.get("TARGET_VERSION", ""),
            "downgrade": values.get("DOWNGRADE") == "1",
            "notes": notes,
        }

    def history_payload(self) -> dict[str, object]:
        return {
            "schema": SCHEMA_VERSION,
            "agent": AGENT_NAME,
            "operations": [self.operation_payload(item) for item in self.journal.recent(20)],
        }

    def _verify_terminal(self, operation: OperationRecord) -> tuple[str, str, str]:
        values = self._status_values()
        if self._healthy_status(values, operation.release):
            return "success", values.get("CURRENT_RELEASE", ""), ""
        return "unknown", values.get("CURRENT_RELEASE", operation.current_release), "postcondition_unconfirmed"

    def _deploy_worker(self, operation_id: str) -> None:
        operation = self.journal.get(operation_id)
        if operation is None:
            return
        mutation_started = False
        try:
            self.journal.update(operation_id, state="preflight")
            code, _output, values = self._helper("preflight", operation.release, timeout=120)
            if code != 0 or values.get("PREFLIGHT_OK") != "1":
                self.journal.update(
                    operation_id,
                    state="failed",
                    current_release=values.get("CURRENT_RELEASE", ""),
                    target_sha=values.get("TARGET_SHA", ""),
                    error_code=values.get("ERROR_CODE", "preflight_failed"),
                )
                return
            if values.get("DOWNGRADE") == "1" and not operation.allow_downgrade:
                self.journal.update(
                    operation_id,
                    state="failed",
                    current_release=values.get("CURRENT_RELEASE", ""),
                    target_sha=values.get("TARGET_SHA", ""),
                    error_code="downgrade_requires_confirmation",
                )
                return

            self.journal.update(
                operation_id,
                state="backup",
                current_release=values.get("CURRENT_RELEASE", ""),
                target_sha=values.get("TARGET_SHA", ""),
            )

            argv = [SUDO, HELPER, "deploy", operation.release]
            if operation.allow_downgrade:
                argv.append("--allow-downgrade")
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
                env=_safe_env(),
            )
            assert process.stdout is not None
            saw_ok = False
            for raw in process.stdout:
                line = raw.strip()
                if line == "Creating deployment backup...":
                    self.journal.update(operation_id, state="backup")
                elif line.startswith("Building "):
                    self.journal.update(operation_id, state="building")
                elif line.startswith("Deploying "):
                    mutation_started = True
                    self.journal.update(operation_id, state="deploying")
                elif line.startswith("Verifying "):
                    mutation_started = True
                    self.journal.update(operation_id, state="verifying")
                elif line == "DEPLOY_OK":
                    saw_ok = True
                    self.journal.update(operation_id, state="verifying")

            return_code = int(process.wait())
            current = self.journal.get(operation_id)
            if current is None:
                return
            if return_code == 0 and saw_ok:
                state, current_release, error = self._verify_terminal(current)
                self.journal.update(
                    operation_id,
                    state=state,
                    current_release=current_release,
                    error_code=error,
                )
                return

            if mutation_started:
                state, current_release, error = self._verify_terminal(current)
                if state != "success":
                    error = "deploy_command_failed_after_dispatch"
                self.journal.update(
                    operation_id,
                    state=state,
                    current_release=current_release,
                    error_code=error,
                )
            else:
                self.journal.update(
                    operation_id,
                    state="failed",
                    error_code="deploy_command_failed_before_dispatch",
                )
        except Exception:
            current = self.journal.get(operation_id)
            if current is None:
                return
            if mutation_started:
                state, current_release, _error = self._verify_terminal(current)
                self.journal.update(
                    operation_id,
                    state=state,
                    current_release=current_release,
                    error_code="" if state == "success" else "agent_worker_exception_after_dispatch",
                )
            else:
                self.journal.update(
                    operation_id,
                    state="failed",
                    error_code="agent_worker_exception_before_dispatch",
                )
        finally:
            if self._mutation_lock.locked():
                self._mutation_lock.release()

    def start_deploy(
        self,
        operation_id: str,
        release: str,
        allow_downgrade: bool,
    ) -> tuple[int, dict[str, object]]:
        if not OPERATION_ID_RE.fullmatch(operation_id):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_operation_id"}
        if not RELEASE_RE.fullmatch(release):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_release"}
        if not isinstance(allow_downgrade, bool):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_allow_downgrade"}

        existing = self.journal.get(operation_id)
        if existing is not None:
            if existing.release != release or existing.allow_downgrade != allow_downgrade:
                return HTTPStatus.CONFLICT, {"error": "operation_id_conflict"}
            return HTTPStatus.OK, self.operation_payload(existing, replayed=True)

        if not self._mutation_lock.acquire(blocking=False):
            return HTTPStatus.CONFLICT, {"error": "deployment_in_progress"}
        if self.journal.active():
            self._mutation_lock.release()
            return HTTPStatus.CONFLICT, {"error": "deployment_in_progress"}

        try:
            record = self.journal.create(operation_id, release, allow_downgrade)
        except sqlite3.IntegrityError:
            self._mutation_lock.release()
            return HTTPStatus.CONFLICT, {"error": "operation_id_conflict"}

        worker = threading.Thread(
            target=self._deploy_worker,
            args=(operation_id,),
            name=f"deploy-{operation_id[:8]}",
            daemon=True,
        )
        worker.start()
        return HTTPStatus.ACCEPTED, self.operation_payload(record)


class AgentRequestHandler(BaseHTTPRequestHandler):
    server_version = AGENT_NAME
    sys_version = ""

    @property
    def agent(self) -> DeployAgent:
        return self.server.agent  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _authorized(self) -> bool:
        if self.agent.authenticate(self.headers.get("Authorization")):
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        return False

    def _path(self) -> str | None:
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            return None
        return parsed.path

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            return
        path = self._path()
        if path is None:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request_target"})
            return
        if path == "/v1/status":
            status, payload = self.agent.status_payload()
            self._json(status, payload)
            return
        if path == "/v1/releases/latest":
            status, payload = self.agent.latest_payload()
            self._json(status, payload)
            return
        prefix = "/v1/preflight/"
        if path.startswith(prefix):
            release = path[len(prefix):]
            status, payload = self.agent.preflight_payload(release)
            self._json(status, payload)
            return
        if path == "/v1/history":
            self._json(HTTPStatus.OK, self.agent.history_payload())
            return
        prefix = "/v1/operations/"
        if path.startswith(prefix):
            operation_id = path[len(prefix):]
            if not OPERATION_ID_RE.fullmatch(operation_id):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_operation_id"})
                return
            record = self.agent.journal.get(operation_id)
            if record is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "operation_not_found"})
                return
            self._json(HTTPStatus.OK, self.agent.operation_payload(record))
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            return
        path = self._path()
        if path != "/v1/deploy":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        content_length = self.headers.get("Content-Length")
        try:
            body_size = int(content_length or "")
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
            return
        if body_size < 0 or body_size > MAX_BODY_BYTES:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request_too_large"})
            return
        try:
            body = json.loads(self.rfile.read(body_size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return
        if not isinstance(body, dict) or set(body) != {
            "operation_id", "release", "allow_downgrade"
        }:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        operation_id = body.get("operation_id")
        release = body.get("release")
        allow_downgrade = body.get("allow_downgrade")
        if not isinstance(operation_id, str) or not isinstance(release, str):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        status, payload = self.agent.start_deploy(
            operation_id,
            release,
            allow_downgrade,
        )
        self._json(status, payload)

    def do_PUT(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_DELETE(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_PATCH(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def _method_not_allowed(self) -> None:
        if not self._authorized():
            return
        self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method_not_allowed"})


class AgentHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], agent: DeployAgent):
        super().__init__(address, AgentRequestHandler)
        self.agent = agent


def main() -> int:
    try:
        config = AgentConfig.from_env()
        agent = DeployAgent(config)
        server = AgentHTTPServer((config.listen_host, config.listen_port), agent)
    except (DeployAgentConfigError, OSError, sqlite3.Error) as exc:
        print(f"deploy agent configuration failed: {exc}", flush=True)
        return 2

    print(
        f"{AGENT_NAME} {AGENT_VERSION} listening on "
        f"{config.listen_host}:{config.listen_port}",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
