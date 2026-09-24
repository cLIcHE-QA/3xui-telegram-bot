#!/usr/bin/env python3
"""Restricted host-control agent for v4.10.0.

This process is intentionally NOT a shell gateway. It exposes only:
- GET /v1/status
- POST /v1/actions with action=start|stop|restart
- GET /v1/operations/<operation_id>
- GET /v1/snapshots/nginx

The managed systemd unit is hard-coded as x-ui.service. Request data is never
interpolated into an OS command. The nginx snapshot endpoint has no path
parameter and can read only one locally configured source directory.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import tarfile
import threading
import time
from typing import Callable
from urllib.parse import urlsplit


AGENT_VERSION = "0.2.0"
SCHEMA_VERSION = 1
SERVICE = "x-ui.service"
SYSTEMCTL = "/usr/bin/systemctl"
SUDO = "/usr/bin/sudo"
ALLOWED_ACTIONS = frozenset({"start", "stop", "restart"})
OPERATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
HOST_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}\Z")
MAX_BODY_BYTES = 4096
MAX_NGINX_SNAPSHOT_BYTES = 8 * 1024 * 1024
MAX_NGINX_SNAPSHOT_FILES = 512
NGINX_SNAPSHOT_ROUTE = "/v1/snapshots/nginx"
DEFAULT_LISTEN = "127.0.0.1:18181"
DEFAULT_TIMEOUT = 20.0


class AgentConfigError(RuntimeError):
    pass


class AgentOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentConfig:
    host_id: str
    listen_host: str
    listen_port: int
    token: str
    db_path: Path
    operation_timeout: float
    nginx_source: Path | None = None

    @classmethod
    def from_env(cls) -> "AgentConfig":
        host_id = os.environ.get("HOST_CONTROL_AGENT_ID", "").strip().lower()
        if not HOST_ID_RE.fullmatch(host_id):
            raise AgentConfigError("HOST_CONTROL_AGENT_ID must match [a-z0-9][a-z0-9_-]{0,31}.")

        configured_service = os.environ.get("HOST_CONTROL_AGENT_SERVICE", SERVICE).strip()
        if configured_service != SERVICE:
            raise AgentConfigError(f"Only {SERVICE} can be managed.")

        listen = os.environ.get("HOST_CONTROL_AGENT_LISTEN", DEFAULT_LISTEN).strip()
        listen_host, sep, port_text = listen.rpartition(":")
        if not sep or not listen_host:
            raise AgentConfigError("HOST_CONTROL_AGENT_LISTEN must be host:port.")
        if listen_host != "127.0.0.1":
            raise AgentConfigError(
                "Host-control agent must listen on 127.0.0.1 only; expose it through a restricted HTTPS reverse proxy."
            )
        try:
            listen_port = int(port_text)
        except ValueError as exc:
            raise AgentConfigError("Invalid listen port.") from exc
        if not (1 <= listen_port <= 65535):
            raise AgentConfigError("Invalid listen port.")

        token_file = Path(
            os.environ.get("HOST_CONTROL_AGENT_TOKEN_FILE", "/etc/3xui-host-control/token")
        )
        try:
            if token_file.is_symlink():
                raise AgentConfigError("Host-control token file must not be a symlink.")
            file_stat = token_file.stat()
        except OSError as exc:
            raise AgentConfigError("Host-control token file is unavailable.") from exc
        if not stat.S_ISREG(file_stat.st_mode):
            raise AgentConfigError("Host-control token path must be a regular file.")
        if file_stat.st_mode & 0o077:
            raise AgentConfigError("Host-control token file must not be readable by group/others.")
        try:
            token = token_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise AgentConfigError("Host-control token file cannot be read.") from exc
        if len(token) < 43:
            raise AgentConfigError(
                "Host-control token is too short; generate at least 32 random bytes."
            )

        db_path = Path(
            os.environ.get(
                "HOST_CONTROL_AGENT_DB",
                "/var/lib/3xui-host-control/agent.sqlite3",
            )
        )

        nginx_source: Path | None = None
        nginx_source_text = os.environ.get("HOST_CONTROL_AGENT_NGINX_SOURCE", "").strip()
        if nginx_source_text:
            candidate = Path(nginx_source_text)
            if not candidate.is_absolute() or candidate == Path("/"):
                raise AgentConfigError(
                    "HOST_CONTROL_AGENT_NGINX_SOURCE must be an absolute non-root directory."
                )
            if candidate.is_symlink():
                raise AgentConfigError("HOST_CONTROL_AGENT_NGINX_SOURCE must not be a symlink.")
            try:
                resolved = candidate.resolve(strict=True)
            except OSError as exc:
                raise AgentConfigError("HOST_CONTROL_AGENT_NGINX_SOURCE is unavailable.") from exc
            if not resolved.is_dir():
                raise AgentConfigError("HOST_CONTROL_AGENT_NGINX_SOURCE must be a directory.")
            nginx_source = resolved

        timeout_text = os.environ.get(
            "HOST_CONTROL_AGENT_OPERATION_TIMEOUT",
            str(DEFAULT_TIMEOUT),
        )
        try:
            operation_timeout = float(timeout_text)
        except ValueError as exc:
            raise AgentConfigError("Invalid operation timeout.") from exc
        if not (1.0 <= operation_timeout <= 120.0):
            raise AgentConfigError("Operation timeout must be between 1 and 120 seconds.")

        return cls(
            host_id=host_id,
            listen_host=listen_host,
            listen_port=listen_port,
            token=token,
            db_path=db_path,
            operation_timeout=operation_timeout,
            nginx_source=nginx_source,
        )


@dataclass(frozen=True)
class ServiceState:
    state: str
    active_state: str
    sub_state: str


@dataclass
class OperationRecord:
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


class OperationJournal:
    """Persistent metadata-only operation journal.

    It never stores tokens, Authorization headers, commands or raw stderr.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
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
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    changed INTEGER NOT NULL DEFAULT 0,
                    before_state TEXT NOT NULL DEFAULT '',
                    after_state TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            # If the agent process died after journaling but before finalizing,
            # the command must never be replayed automatically.
            conn.execute(
                """
                UPDATE operations
                   SET result = 'uncertain',
                       error_code = CASE
                           WHEN error_code = '' THEN 'agent_interrupted'
                           ELSE error_code
                       END,
                       finished_at = CASE
                           WHEN finished_at = '' THEN ?
                           ELSE finished_at
                       END
                 WHERE result = 'started'
                """,
                (utc_now(),),
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

    def begin(self, operation_id: str, action: str, before: str) -> OperationRecord:
        record = OperationRecord(
            operation_id=operation_id,
            action=action,
            result="started",
            changed=False,
            before=before,
            after=before,
            duration_ms=0,
            error_code="",
            created_at=utc_now(),
            finished_at="",
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO operations (
                    operation_id, action, result, changed, before_state,
                    after_state, duration_ms, error_code, created_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.operation_id,
                    record.action,
                    record.result,
                    int(record.changed),
                    record.before,
                    record.after,
                    record.duration_ms,
                    record.error_code,
                    record.created_at,
                    record.finished_at,
                ),
            )
        return record

    def finish(
        self,
        operation_id: str,
        *,
        result: str,
        changed: bool,
        after: str,
        duration_ms: int,
        error_code: str = "",
    ) -> OperationRecord:
        finished_at = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE operations
                   SET result = ?, changed = ?, after_state = ?, duration_ms = ?,
                       error_code = ?, finished_at = ?
                 WHERE operation_id = ?
                """,
                (
                    result,
                    int(changed),
                    after,
                    max(0, int(duration_ms)),
                    error_code,
                    finished_at,
                    operation_id,
                ),
            )
        record = self.get(operation_id)
        if record is None:
            raise AgentOperationError("operation_journal_missing")
        return record


def _row_to_operation(row: sqlite3.Row) -> OperationRecord:
    return OperationRecord(
        operation_id=str(row["operation_id"]),
        action=str(row["action"]),
        result=str(row["result"]),
        changed=bool(row["changed"]),
        before=str(row["before_state"]),
        after=str(row["after_state"]),
        duration_ms=int(row["duration_ms"]),
        error_code=str(row["error_code"]),
        created_at=str(row["created_at"]),
        finished_at=str(row["finished_at"]),
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


class ServiceController:
    """The only OS-facing component.

    All argv values are constants selected by a closed enum. No caller can
    provide a program, path, systemd unit or arbitrary argument.
    """

    def __init__(
        self,
        *,
        timeout: float,
        runner: RunCommand = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.timeout = timeout
        self.runner = runner
        self.sleep = sleep
        self.monotonic = monotonic

    def status(self) -> ServiceState:
        try:
            completed = self.runner(
                [
                    SYSTEMCTL,
                    "show",
                    SERVICE,
                    "--property=ActiveState",
                    "--property=SubState",
                    "--no-pager",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=min(self.timeout, 5.0),
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ServiceState("unknown", "unknown", "unknown")
        if completed.returncode != 0:
            return ServiceState("unknown", "unknown", "unknown")

        values: dict[str, str] = {}
        for line in completed.stdout.splitlines():
            key, sep, value = line.partition("=")
            if sep and key in {"ActiveState", "SubState"}:
                values[key] = value.strip().lower()
        active = values.get("ActiveState", "unknown")
        sub = values.get("SubState", "unknown")
        if active == "active":
            state = "running"
        elif active == "inactive":
            state = "stopped"
        elif active == "failed":
            state = "failed"
        elif active in {"activating", "deactivating", "reloading"}:
            state = "transitioning"
        else:
            state = "unknown"
        return ServiceState(state, active, sub)

    def run_action(self, action: str) -> tuple[subprocess.CompletedProcess[str], int]:
        if action not in ALLOWED_ACTIONS:
            raise AgentOperationError("invalid_action")
        started = self.monotonic()
        completed = self.runner(
            [SUDO, "-n", SYSTEMCTL, action, SERVICE],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            shell=False,
        )
        duration_ms = int((self.monotonic() - started) * 1000)
        return completed, max(0, duration_ms)

    def wait_for(self, expected: str) -> ServiceState:
        deadline = self.monotonic() + self.timeout
        latest = self.status()
        while latest.state != expected and self.monotonic() < deadline:
            self.sleep(0.25)
            latest = self.status()
        return latest


class HostControlAgent:
    def __init__(
        self,
        config: AgentConfig,
        *,
        journal: OperationJournal | None = None,
        controller: ServiceController | None = None,
    ):
        self.config = config
        self.journal = journal or OperationJournal(config.db_path)
        self.controller = controller or ServiceController(timeout=config.operation_timeout)
        self._mutation_lock = threading.Lock()

    def authenticate(self, authorization: str | None) -> bool:
        prefix = "Bearer "
        if not authorization or not authorization.startswith(prefix):
            return False
        supplied = authorization[len(prefix):]
        return hmac.compare_digest(supplied, self.config.token)

    def status_payload(self) -> dict[str, object]:
        state = self.controller.status()
        return {
            "schema": SCHEMA_VERSION,
            "host_id": self.config.host_id,
            "service": SERVICE,
            "state": state.state,
            "active_state": state.active_state,
            "sub_state": state.sub_state,
            "agent_version": AGENT_VERSION,
            "timestamp": utc_now(),
        }

    def operation_payload(
        self,
        record: OperationRecord,
        *,
        replayed: bool = False,
    ) -> dict[str, object]:
        payload = asdict(record)
        payload.update(
            {
                "schema": SCHEMA_VERSION,
                "host_id": self.config.host_id,
                "service": SERVICE,
                "replayed": replayed,
            }
        )
        # stdout is captured by systemd/journald. Log normalized metadata only:
        # never the bearer token, request headers, command argv or raw stderr.
        print(
            json.dumps(
                {
                    "event": "host_control_operation",
                    "host_id": self.config.host_id,
                    "operation_id": record.operation_id,
                    "action": record.action,
                    "result": record.result,
                    "before": record.before,
                    "after": record.after,
                    "duration_ms": record.duration_ms,
                    "error_code": record.error_code,
                    "replayed": replayed,
                },
                separators=(",", ":"),
                ensure_ascii=True,
            ),
            flush=True,
        )
        return payload

    def nginx_snapshot(self) -> tuple[int, dict[str, object], bytes | None]:
        root = self.config.nginx_source
        if root is None:
            return HTTPStatus.NOT_FOUND, {"error": "nginx_snapshot_unconfigured"}, None
        try:
            resolved_root = root.resolve(strict=True)
        except OSError:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "nginx_snapshot_unavailable"}, None
        if root.is_symlink() or not resolved_root.is_dir():
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "nginx_snapshot_unavailable"}, None

        files: list[tuple[str, bytes, str]] = []
        skipped: list[dict[str, str]] = []
        total_bytes = 0

        try:
            for dirpath, dirnames, filenames in os.walk(resolved_root, topdown=True, followlinks=False):
                current = Path(dirpath)
                kept_dirs: list[str] = []
                for dirname in sorted(dirnames):
                    candidate = current / dirname
                    if candidate.is_symlink():
                        rel = candidate.relative_to(resolved_root).as_posix()
                        skipped.append({"path": rel, "reason": "symlink_directory"})
                    else:
                        kept_dirs.append(dirname)
                dirnames[:] = kept_dirs

                for filename in sorted(filenames):
                    candidate = current / filename
                    rel_path = candidate.relative_to(resolved_root)
                    if rel_path.is_absolute() or ".." in rel_path.parts:
                        skipped.append({"path": rel_path.as_posix(), "reason": "unsafe_path"})
                        continue

                    source = candidate
                    if candidate.is_symlink():
                        try:
                            source = candidate.resolve(strict=True)
                            source.relative_to(resolved_root)
                        except (OSError, ValueError):
                            skipped.append({"path": rel_path.as_posix(), "reason": "external_symlink"})
                            continue
                        if not source.is_file():
                            skipped.append({"path": rel_path.as_posix(), "reason": "symlink_not_file"})
                            continue
                    else:
                        try:
                            file_stat = candidate.stat()
                        except OSError:
                            skipped.append({"path": rel_path.as_posix(), "reason": "stat_failed"})
                            continue
                        if not stat.S_ISREG(file_stat.st_mode):
                            skipped.append({"path": rel_path.as_posix(), "reason": "not_regular_file"})
                            continue

                    try:
                        data = source.read_bytes()
                    except OSError:
                        skipped.append({"path": rel_path.as_posix(), "reason": "read_failed"})
                        continue

                    if len(files) + 1 > MAX_NGINX_SNAPSHOT_FILES:
                        return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "nginx_snapshot_too_many_files"}, None
                    if total_bytes + len(data) > MAX_NGINX_SNAPSHOT_BYTES:
                        return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "nginx_snapshot_too_large"}, None

                    digest = hashlib.sha256(data).hexdigest()
                    files.append((rel_path.as_posix(), data, digest))
                    total_bytes += len(data)
        except OSError:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "nginx_snapshot_unavailable"}, None

        metadata: dict[str, object] = {
            "schema": SCHEMA_VERSION,
            "host_id": self.config.host_id,
            "component": "nginx",
            "created_at_utc": utc_now(),
            "complete": bool(files) and not skipped,
            "files": [
                {"path": name, "bytes": len(data), "sha256": digest}
                for name, data, digest in files
            ],
            "skipped": skipped,
        }

        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for name, data, _digest in files:
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                info.mode = 0o600
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))
            meta_bytes = json.dumps(
                metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            info = tarfile.TarInfo(name="_snapshot.json")
            info.size = len(meta_bytes)
            info.mode = 0o600
            info.mtime = 0
            archive.addfile(info, io.BytesIO(meta_bytes))

        return HTTPStatus.OK, metadata, buffer.getvalue()

    def execute(self, operation_id: str, action: str) -> tuple[int, dict[str, object]]:
        if not OPERATION_ID_RE.fullmatch(operation_id):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_operation_id"}
        if action not in ALLOWED_ACTIONS:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_action"}

        existing = self.journal.get(operation_id)
        if existing is not None:
            if existing.action != action:
                return HTTPStatus.CONFLICT, {"error": "operation_id_conflict"}
            return HTTPStatus.OK, self.operation_payload(existing, replayed=True)

        if not self._mutation_lock.acquire(blocking=False):
            return HTTPStatus.CONFLICT, {"error": "operation_in_progress"}
        try:
            # Check again after taking the lock in case another request completed
            # between the first lookup and lock acquisition.
            existing = self.journal.get(operation_id)
            if existing is not None:
                if existing.action != action:
                    return HTTPStatus.CONFLICT, {"error": "operation_id_conflict"}
                return HTTPStatus.OK, self.operation_payload(existing, replayed=True)

            before = self.controller.status()
            if before.state == "unknown":
                return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "service_state_unknown"}
            if before.state == "transitioning":
                return HTTPStatus.CONFLICT, {"error": "service_transitioning"}

            if action == "start" and before.state == "running":
                record = self.journal.begin(operation_id, action, before.state)
                record = self.journal.finish(
                    operation_id,
                    result="success",
                    changed=False,
                    after=before.state,
                    duration_ms=0,
                )
                return HTTPStatus.OK, self.operation_payload(record)
            if action == "stop" and before.state == "stopped":
                record = self.journal.begin(operation_id, action, before.state)
                record = self.journal.finish(
                    operation_id,
                    result="success",
                    changed=False,
                    after=before.state,
                    duration_ms=0,
                )
                return HTTPStatus.OK, self.operation_payload(record)

            self.journal.begin(operation_id, action, before.state)
            expected = "stopped" if action == "stop" else "running"
            started = time.monotonic()
            try:
                completed, command_ms = self.controller.run_action(action)
            except subprocess.TimeoutExpired:
                elapsed = int((time.monotonic() - started) * 1000)
                current = self.controller.status()
                record = self.journal.finish(
                    operation_id,
                    result="uncertain",
                    changed=current.state != before.state,
                    after=current.state,
                    duration_ms=elapsed,
                    error_code="command_timeout",
                )
                return HTTPStatus.GATEWAY_TIMEOUT, self.operation_payload(record)
            except (OSError, subprocess.SubprocessError):
                elapsed = int((time.monotonic() - started) * 1000)
                current = self.controller.status()
                record = self.journal.finish(
                    operation_id,
                    result="failed",
                    changed=current.state != before.state,
                    after=current.state,
                    duration_ms=elapsed,
                    error_code="command_failed",
                )
                return HTTPStatus.SERVICE_UNAVAILABLE, self.operation_payload(record)

            if completed.returncode != 0:
                current = self.controller.status()
                record = self.journal.finish(
                    operation_id,
                    result="failed",
                    changed=current.state != before.state,
                    after=current.state,
                    duration_ms=command_ms,
                    error_code="systemctl_failed",
                )
                return HTTPStatus.SERVICE_UNAVAILABLE, self.operation_payload(record)

            final = self.controller.wait_for(expected)
            elapsed = int((time.monotonic() - started) * 1000)
            if final.state == expected:
                record = self.journal.finish(
                    operation_id,
                    result="success",
                    changed=True,
                    after=final.state,
                    duration_ms=elapsed,
                )
                return HTTPStatus.OK, self.operation_payload(record)

            record = self.journal.finish(
                operation_id,
                result="uncertain",
                changed=final.state != before.state,
                after=final.state,
                duration_ms=elapsed,
                error_code="postcondition_timeout",
            )
            return HTTPStatus.GATEWAY_TIMEOUT, self.operation_payload(record)
        finally:
            self._mutation_lock.release()


class AgentRequestHandler(BaseHTTPRequestHandler):
    server_version = "3xui-host-control"
    sys_version = ""

    @property
    def agent(self) -> HostControlAgent:
        return self.server.agent  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: object) -> None:
        # BaseHTTPRequestHandler logs request lines, which is unnecessary for
        # this tiny authenticated control plane. Agent operation logging belongs
        # in journald without headers/tokens.
        return

    def _json(self, status: int, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _binary(self, status: int, body: bytes, *, complete: bool) -> None:
        self.send_response(int(status))
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Disposition", 'attachment; filename="nginx-snapshot.tar.gz"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Host-Control-Schema", str(SCHEMA_VERSION))
        self.send_header("X-Host-Control-Host-Id", self.agent.config.host_id)
        self.send_header("X-Host-Control-Component", "nginx")
        self.send_header("X-Host-Control-Snapshot-Complete", "1" if complete else "0")
        self.send_header("X-Content-SHA256", hashlib.sha256(body).hexdigest())
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if self.agent.authenticate(self.headers.get("Authorization")):
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        return False

    def _path(self) -> str | None:
        parsed = urlsplit(self.path)
        if parsed.query:
            return None
        return parsed.path

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if not self._authorized():
            return
        path = self._path()
        if path is None:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request_target"})
            return
        if path == "/v1/status":
            self._json(HTTPStatus.OK, self.agent.status_payload())
            return
        if path == NGINX_SNAPSHOT_ROUTE:
            status, metadata, body = self.agent.nginx_snapshot()
            if body is None:
                self._json(status, metadata)
                return
            self._binary(status, body, complete=bool(metadata.get("complete")))
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

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if not self._authorized():
            return
        path = self._path()
        if path is None:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request_target"})
            return
        if path != "/v1/actions":
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
            raw = self.rfile.read(body_size)
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return
        if not isinstance(body, dict) or set(body) != {"operation_id", "action"}:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return

        operation_id = body.get("operation_id")
        action = body.get("action")
        if not isinstance(operation_id, str) or not isinstance(action, str):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
            return
        status, payload = self.agent.execute(operation_id, action)
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

    def __init__(self, address: tuple[str, int], agent: HostControlAgent):
        super().__init__(address, AgentRequestHandler)
        self.agent = agent


def main() -> int:
    try:
        config = AgentConfig.from_env()
        agent = HostControlAgent(config)
        server = AgentHTTPServer((config.listen_host, config.listen_port), agent)
    except (AgentConfigError, OSError, sqlite3.Error) as exc:
        print(f"host-control agent configuration failed: {exc}", flush=True)
        return 2

    print(
        f"3xui host-control agent {AGENT_VERSION} listening on "
        f"{config.listen_host}:{config.listen_port} for host_id={config.host_id}",
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
