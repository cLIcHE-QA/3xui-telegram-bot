"""D1b #887 opt-in admin-only draft API, separate from Telegram and /compat/.

Not imported by app_runtime: production routes remain unchanged. The caller must
explicitly provide admin password verifiers, HTTPS origin and a Fernet key.
Never use a subscription URL, initDataUnsafe or Telegram ID for web admin auth.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import web
from cryptography.fernet import Fernet
from subscription_page_config import InvalidSubscriptionConfig, MAX_BYTES, parse_config, serialize_config

COOKIE = "__Host-subpage-admin"
ROLES = {"viewer": 1, "editor": 2, "owner": 3}
ROUNDS = 310_000
VERIFIER = re.compile(r"pbkdf2_sha256\$310000\$([0-9a-f]{32})\$([0-9a-f]{64})")
ETAG = re.compile(r'"rev-(0|[1-9][0-9]*)"')
SESSION_TTL = 1200


@dataclass(frozen=True)
class AdminAccount:
    username: str
    password_hash: str
    role: str


@dataclass(frozen=True)
class Session:
    username: str
    role: str
    csrf: str
    expires_at: float


class StaleDraft(ValueError):
    pass


def password_verifier(password: str, salt: bytes | None = None) -> str:
    """Generate offline; do not commit the password, verifier or encryption key."""
    if not isinstance(password, str) or len(password) < 16 or len(password.encode()) > 512:
        raise ValueError("Admin password must be at least 16 characters")
    salt = secrets.token_bytes(16) if salt is None else salt
    if len(salt) != 16:
        raise ValueError("Salt must be 16 bytes")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ROUNDS)
    return "$".join(("pbkdf2_sha256", str(ROUNDS), salt.hex(), digest.hex()))


def _password_matches(encoded: str, password: str) -> bool:
    match = VERIFIER.fullmatch(encoded)
    if not match or not isinstance(password, str) or len(password.encode()) > 512:
        return False
    trial = hashlib.pbkdf2_hmac("sha256", password.encode(),
                               bytes.fromhex(match.group(1)), ROUNDS)
    return hmac.compare_digest(trial, bytes.fromhex(match.group(2)))


def _safe_tree(value: object) -> None:
    stack = [(value, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if depth > 32 or count > 100_000:
            raise InvalidSubscriptionConfig("Excessive configuration depth")
        if isinstance(node, dict):
            if any(k in ("__proto__", "constructor", "prototype") for k in node):
                raise InvalidSubscriptionConfig("Unsafe object key")
            stack.extend((v, depth + 1) for v in node.values())
        elif isinstance(node, list):
            stack.extend((v, depth + 1) for v in node)


class EncryptedDrafts:
    """Owner-only SQLite, encrypted content, immutable revisions, metadata audit."""

    def __init__(self, filename: str | Path, key: bytes):
        self.path = Path(filename)
        if self.path.is_symlink() or self.path.is_dir() or not self.path.parent.is_dir():
            raise ValueError("Invalid draft DB path")
        if self.path.parent.stat().st_mode & 0o022:
            raise ValueError("Draft directory must not be group/world-writable")
        if self.path.exists():
            if not self.path.is_file() or self.path.stat().st_mode & 0o077:
                raise ValueError("Draft DB must be an owner-only regular file")
        else:
            # Reserve the file with owner-only permissions before SQLite touches it.
            flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.path, flags, 0o600)
            os.close(descriptor)
        self.cipher = Fernet(key)
        with self.connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS draft_revisions(
                revision INTEGER PRIMARY KEY, content BLOB NOT NULL,
                digest TEXT NOT NULL, actor TEXT NOT NULL, saved_at TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS draft_proposals(
                id TEXT PRIMARY KEY, revision INTEGER NOT NULL, digest TEXT NOT NULL,
                actor TEXT NOT NULL, created_at TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state='pending_manual_review'))""")
        os.chmod(self.path, 0o600)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=3, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=3000")
        return conn

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def current(self) -> tuple[int, dict | None]:
        with self.connect() as con:
            row = con.execute("SELECT revision,content FROM draft_revisions "
                              "ORDER BY revision DESC LIMIT 1").fetchone()
        if not row:
            return 0, None
        return row["revision"], parse_config(self.cipher.decrypt(row["content"]))

    def save(self, actor: str, expected: int, value: dict) -> dict:
        plaintext = serialize_config(value).encode("utf-8")
        if len(plaintext) > MAX_BYTES:
            raise InvalidSubscriptionConfig("JSON too large")
        digest = hashlib.sha256(plaintext).hexdigest()
        ciphertext = self.cipher.encrypt(plaintext)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            actual = con.execute("SELECT COALESCE(MAX(revision),0) FROM draft_revisions").fetchone()[0]
            if actual != expected:
                con.rollback()
                raise StaleDraft("Revision conflict")
            revision = actual + 1
            con.execute("INSERT INTO draft_revisions VALUES(?,?,?,?,?)",
                        (revision, ciphertext, digest, actor, self.now()))
            con.commit()
        return {"revision": revision, "digest": digest, "state": "draft"}

    def history(self) -> list[dict]:
        with self.connect() as con:
            rows = con.execute("SELECT revision,digest,actor,saved_at FROM draft_revisions "
                               "ORDER BY revision DESC LIMIT 50").fetchall()
        return [dict(r) for r in rows]

    def propose(self, actor: str, expected: int) -> dict:
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT revision,digest FROM draft_revisions "
                              "ORDER BY revision DESC LIMIT 1").fetchone()
            if not row or row["revision"] != expected:
                con.rollback()
                raise StaleDraft("Missing/stale draft")
            result = {"proposalId": secrets.token_hex(16), "revision": expected,
                      "state": "pending_manual_review"}
            con.execute("INSERT INTO draft_proposals VALUES(?,?,?,?,?,?)",
                        (result["proposalId"], expected, row["digest"], actor,
                         self.now(), result["state"]))
            con.commit()
        return result


def create_editor_app(*, accounts: list[AdminAccount], db_path: str | Path,
                      encryption_key: bytes, https_origin: str,
                      session_ttl: int = SESSION_TTL) -> web.Application:
    """Explicitly opt-in admin API; this function does not start a listener."""
    origin = urlsplit(https_origin)
    if (origin.scheme != "https" or not origin.hostname or origin.username or
            origin.password or origin.path or origin.query or origin.fragment):
        raise ValueError("Require a canonical HTTPS origin")
    if not accounts or not 60 <= session_ttl <= 3600:
        raise ValueError("Accounts and bounded sessions required")
    users: dict[str, AdminAccount] = {}
    for account in accounts:
        if (not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", account.username)
                or account.username in users or account.role not in ROLES
                or not VERIFIER.fullmatch(account.password_hash)):
            raise ValueError("Invalid admin account setup")
        users[account.username] = account
    drafts = EncryptedDrafts(db_path, encryption_key)
    sessions: dict[str, Session] = {}
    failures: dict[str, list[float]] = {}

    @web.middleware
    async def secure_response(request: web.Request, handler):
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = exc
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        return response

    app = web.Application(middlewares=[secure_response], client_max_size=MAX_BYTES + 4096)

    def origin_check(request: web.Request) -> None:
        if request.headers.get("Origin") != https_origin or request.headers.get("Host") != origin.netloc:
            raise web.HTTPForbidden(text="Invalid admin origin")

    def session_for(request: web.Request, role: str = "viewer") -> Session:
        token = request.cookies.get(COOKIE, "")
        if not token or len(token) > 128:
            raise web.HTTPUnauthorized(text="Login required")
        hashed = hashlib.sha256(token.encode()).hexdigest()
        session = sessions.get(hashed)
        if not session:
            raise web.HTTPUnauthorized(text="Login required")
        if session.expires_at < time.monotonic():
            sessions.pop(hashed, None)
            raise web.HTTPUnauthorized(text="Session expired")
        if ROLES[session.role] < ROLES[role]:
            raise web.HTTPForbidden(text="Insufficient role")
        return session

    def mutation(request: web.Request, role: str = "editor") -> Session:
        origin_check(request)
        session = session_for(request, role)
        if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), session.csrf):
            raise web.HTTPForbidden(text="CSRF check failed")
        return session

    async def body(request: web.Request, limit: int) -> dict:
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType(text="Expected JSON")
        if request.content_length is not None and request.content_length > limit:
            raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=request.content_length)
        raw = await request.content.read(limit + 1)
        if len(raw) > limit:
            raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=len(raw))
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise web.HTTPBadRequest(text="Invalid JSON") from exc
        if not isinstance(data, dict):
            raise web.HTTPBadRequest(text="Expected JSON object")
        return data

    def revision(request: web.Request) -> int:
        match = ETAG.fullmatch(request.headers.get("If-Match", ""))
        if not match:
            raise web.HTTPPreconditionRequired(text="If-Match revision is required")
        return int(match.group(1))

    async def login(request: web.Request) -> web.Response:
        origin_check(request)
        now = time.monotonic()
        address = request.remote or "unknown"  # ignore untrusted X-Forwarded-For
        recent = [t for t in failures.get(address, []) if now - t < 900]
        if len(recent) >= 5:
            raise web.HTTPTooManyRequests(text="Too many login attempts")
        credentials = await body(request, 2048)
        name, password = credentials.get("username"), credentials.get("password")
        user = users.get(name) if isinstance(name, str) else None
        if not user or not isinstance(password, str) or not _password_matches(user.password_hash, password):
            failures[address] = recent + [now]
            raise web.HTTPUnauthorized(text="Invalid credentials")
        failures.pop(address, None)
        cookie = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        sessions[hashlib.sha256(cookie.encode()).hexdigest()] = Session(
            user.username, user.role, csrf, now + session_ttl)
        response = web.json_response({"username": user.username, "role": user.role,
                                      "csrfToken": csrf, "expiresIn": session_ttl})
        response.set_cookie(COOKIE, cookie, path="/", secure=True, httponly=True,
                            samesite="Strict", max_age=session_ttl)
        return response

    async def status(request: web.Request) -> web.Response:
        who = session_for(request)
        return web.json_response({"username": who.username, "role": who.role,
                                  "csrfToken": who.csrf,
                                  "expiresIn": max(0, int(who.expires_at - time.monotonic()))})

    async def logout(request: web.Request) -> web.Response:
        mutation(request, "viewer")
        token = request.cookies.get(COOKIE, "")
        sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)
        response = web.json_response({"loggedOut": True})
        response.del_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="Strict")
        return response

    async def get_draft(request: web.Request) -> web.Response:
        session_for(request)
        rev, config = drafts.current()
        response = web.json_response({"revision": rev, "config": config})
        response.headers["ETag"] = '"rev-' + str(rev) + '"'
        return response

    async def put_draft(request: web.Request) -> web.Response:
        user = mutation(request)
        expected = revision(request)
        payload = await body(request, MAX_BYTES + 2048)
        try:
            config = payload.get("config")
            _safe_tree(config)
            parsed = parse_config(json.dumps(config, ensure_ascii=False))
            result = drafts.save(user.username, expected, parsed)
        except StaleDraft as exc:
            raise web.HTTPConflict(text="Draft changed; refresh") from exc
        except (InvalidSubscriptionConfig, ValueError, TypeError) as exc:
            raise web.HTTPBadRequest(text="Invalid draft") from exc
        return web.json_response(result)

    async def get_history(request: web.Request) -> web.Response:
        session_for(request)
        return web.json_response({"revisions": drafts.history()})

    async def propose(request: web.Request) -> web.Response:
        user = mutation(request, "owner")
        try:
            result = drafts.propose(user.username, revision(request))
        except StaleDraft as exc:
            raise web.HTTPConflict(text="Draft changed; proposal blocked") from exc
        return web.json_response(result, status=202)

    prefix = "/admin/subpage/api"
    app.router.add_post(prefix + "/session", login)
    app.router.add_get(prefix + "/session", status)
    app.router.add_delete(prefix + "/session", logout)
    app.router.add_get(prefix + "/draft", get_draft)
    app.router.add_put(prefix + "/draft", put_draft)
    app.router.add_get(prefix + "/history", get_history)
    app.router.add_post(prefix + "/proposals", propose)
    # No publish, rollback, backend/user mutations, or production listener.
    return app
