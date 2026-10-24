"""D1b #887 encrypted admin roster and offline MFA recovery (never a web route).

The caller must authorize offline operations through owner-only filesystem/key
access. Enrollment secrets are returned ONLY to the caller in memory for a
private out-of-band handoff, never printed, logged or stored in plaintext.
"""
from __future__ import annotations

import base64
import fcntl
import json
import os
import re
import secrets
import stat
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken

from subscription_page_admin import (
    AdminAccount, ROLES, VERIFIER, _totp_key, _verify_totp, password_verifier,
)

_MAX_CIPHERTEXT_BYTES = 131072
_MAX_ACCOUNT_COUNT = 64


@dataclass(frozen=True)
class PendingMFAEnrollment:
    """Ephemeral handoff; caller must confirm authenticator OTP before commit."""
    username: str
    expected_revision: int
    secret_b32: str = field(repr=False)


def _valid_accounts(accounts: list[AdminAccount]) -> list[AdminAccount]:
    if not isinstance(accounts, list) or not 1 <= len(accounts) <= _MAX_ACCOUNT_COUNT:
        raise ValueError("Invalid offline admin account count")
    usernames: set[str] = set()
    secrets_seen: set[bytes] = set()
    owners = 0
    for account in accounts:
        if not isinstance(account, AdminAccount) or not isinstance(account.username, str):
            raise ValueError("Invalid offline admin account")
        if (not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", account.username)
                or account.username in usernames or account.role not in ROLES
                or not isinstance(account.password_hash, str)
                or not VERIFIER.fullmatch(account.password_hash)):
            raise ValueError("Invalid offline admin account metadata")
        seed = _totp_key(account.totp_secret_b32)
        if seed in secrets_seen:
            raise ValueError("Administrators must have different MFA enrollment")
        secrets_seen.add(seed)
        usernames.add(account.username)
        owners += account.role == "owner"
    if owners < 1:
        raise ValueError("At least one owner is required for offline recovery")
    return accounts


class EncryptedAdminRoster:
    """Private encrypted roster with atomic revisions and serialized writers.

    No HTTP mutator, auto-generated recovery bypass, plaintext backup, or
    network integration. All writers use a persistent owner-only flock file.
    """

    def __init__(self, filename: str | Path, key: bytes):
        self.path = Path(filename)
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.cipher = Fernet(key)
        self._private_directory()

    def _private_directory(self) -> None:
        parent = self.path.parent
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError("Offline roster directory must exist and not be a symlink")
        info = parent.stat()
        if (info.st_uid != os.geteuid() or info.st_mode & 0o077
                or not stat.S_ISDIR(info.st_mode)):
            raise ValueError("Offline roster directory must be owned and mode 0700")

    @staticmethod
    def _check_file(info: os.stat_result) -> None:
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_mode & 0o077):
            raise ValueError("Offline roster files must be private regular 0600")

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self._private_directory()
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.lock_path, flags, 0o600)
        try:
            self._check_file(os.fstat(fd))
            fcntl.flock(fd, fcntl.LOCK_EX)
            # A replaced lock path could let two writers acquire different locks.
            held = os.fstat(fd)
            pointed = self.lock_path.lstat()
            if (not stat.S_ISREG(pointed.st_mode)
                    or held.st_dev != pointed.st_dev
                    or held.st_ino != pointed.st_ino):
                raise ValueError("Offline roster lock changed")
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read(self) -> tuple[int, list[AdminAccount]]:
        fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            self._check_file(os.fstat(fd))
            with os.fdopen(fd, "rb", closefd=False) as stream:
                ciphertext = stream.read(_MAX_CIPHERTEXT_BYTES + 1)
            if not ciphertext or len(ciphertext) > _MAX_CIPHERTEXT_BYTES:
                raise ValueError("Offline roster too large or empty")
        finally:
            os.close(fd)
        try:
            raw = self.cipher.decrypt(ciphertext)
            data = json.loads(raw)
            if (not isinstance(data, dict) or set(data) != {"schema", "revision", "accounts"}
                    or data["schema"] != 1 or not isinstance(data["revision"], int)
                    or isinstance(data["revision"], bool) or data["revision"] < 1
                    or not isinstance(data["accounts"], list)):
                raise ValueError("Invalid offline roster format")
            accounts: list[AdminAccount] = []
            for record in data["accounts"]:
                if not isinstance(record, dict) or set(record) != {
                        "username", "password_hash", "role", "totp_secret_b32"}:
                    raise ValueError("Invalid offline account record")
                accounts.append(AdminAccount(**record))
            return data["revision"], _valid_accounts(accounts)
        except (InvalidToken, ValueError, TypeError, UnicodeError) as exc:
            raise ValueError("Offline roster invalid or wrong encryption key") from exc

    def _write(self, revision: int, accounts: list[AdminAccount]) -> None:
        _valid_accounts(accounts)
        records = [
            {"username": x.username, "password_hash": x.password_hash,
             "role": x.role, "totp_secret_b32": x.totp_secret_b32}
            for x in accounts
        ]
        plaintext = json.dumps(
            {"schema": 1, "revision": revision, "accounts": records},
            sort_keys=True, separators=(",", ":")).encode("utf-8")
        ciphertext = self.cipher.encrypt(plaintext)
        if len(ciphertext) > _MAX_CIPHERTEXT_BYTES:
            raise ValueError("Offline roster exceeds storage bound")
        temp = self.path.with_name("." + self.path.name + "." + secrets.token_hex(16) + ".tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(temp, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(ciphertext)
                stream.flush()
                os.fsync(stream.fileno())
            fd = -1
            try:
                existing = self.path.lstat()
            except FileNotFoundError:
                pass
            else:
                self._check_file(existing)
            os.replace(temp, self.path)
            folder_fd = os.open(self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(folder_fd)
            finally:
                os.close(folder_fd)
        finally:
            if fd != -1:
                os.close(fd)
            if temp.exists():
                temp.unlink()

    def initialize(self, accounts: list[AdminAccount]) -> int:
        """Initialize exactly once. Never overwrite even when payload is invalid."""
        with self._lock():
            if self.path.exists() or self.path.is_symlink():
                raise FileExistsError("Offline admin roster already initialized")
            self._write(1, accounts)
        return 1

    def snapshot(self) -> tuple[int, list[AdminAccount]]:
        with self._lock():
            return self._read()

    def load_accounts(self) -> list[AdminAccount]:
        return self.snapshot()[1]

    def rotate_password(self, username: str, password: str,
                        expected_revision: int) -> int:
        """Offline, CAS-safe password change. Never expose password in output."""
        new_verifier = password_verifier(password)
        with self._lock():
            revision, accounts = self._read()
            if revision != expected_revision:
                raise ValueError("Offline roster revision changed")
            if username not in {a.username for a in accounts}:
                raise ValueError("Offline account not found")
            rotated = [
                AdminAccount(a.username, new_verifier if a.username == username
                             else a.password_hash, a.role, a.totp_secret_b32)
                for a in accounts
            ]
            self._write(revision + 1, rotated)
            return revision + 1

    def prepare_mfa_recovery(self, username: str) -> PendingMFAEnrollment:
        """Generate a new TOTP seed, private in memory pending proof of enrollment."""
        revision, accounts = self.snapshot()
        if username not in {a.username for a in accounts}:
            raise ValueError("Offline account not found")
        return PendingMFAEnrollment(
            username, revision, base64.b32encode(secrets.token_bytes(32)).decode("ascii"))

    def confirm_mfa_recovery(self, pending: PendingMFAEnrollment,
                             otp: str, *, new_password: str | None = None) -> int:
        """Rotate only after a fresh authenticator proves the new seed works."""
        if not isinstance(pending, PendingMFAEnrollment):
            raise ValueError("Missing offline MFA enrollment")
        seed = _totp_key(pending.secret_b32)
        if _verify_totp(seed, otp, -1) is None:
            raise ValueError("New MFA enrollment was not confirmed")
        new_verifier = password_verifier(new_password) if new_password is not None else None
        with self._lock():
            revision, accounts = self._read()
            if revision != pending.expected_revision:
                raise ValueError("Offline roster revision changed")
            if pending.username not in {a.username for a in accounts}:
                raise ValueError("Offline account not found")
            if any(_totp_key(a.totp_secret_b32) == seed for a in accounts):
                raise ValueError("Duplicate MFA enrollment")
            updated = [
                AdminAccount(
                    a.username,
                    new_verifier if a.username == pending.username and
                    new_verifier is not None else a.password_hash,
                    a.role,
                    pending.secret_b32 if a.username == pending.username
                    else a.totp_secret_b32)
                for a in accounts
            ]
            self._write(revision + 1, updated)
            return revision + 1
