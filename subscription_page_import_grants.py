"""#887 D3d: isolated one-use proof bound to a verified portal session.

Source-only boundary: no HTTP route, subscription URL, clipboard, QR or deploy.
Callers must supply the HttpOnly cookie from a trusted server-side request,
never a user-supplied owner ID. The proof is NOT authority to disclose a URL.
The bounded, process-local ledger is unsuitable for multi-worker/live staging.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import time
from dataclasses import dataclass
from typing import Callable, Literal

from subscription_page_customer import MiniAppSessions
from subscription_page_import_preflight import check_import_eligibility
from subscription_page_standalone import StandalonePilot

SessionMode = Literal["telegram-mini-app", "standalone"]
PROOF_TTL_MAX = 60
MAX_PENDING_GRANTS = 128
MAX_RATE_KEYS = 256
RATE_WINDOW = 60
MAX_ISSUES_PER_WINDOW = 4
MAX_REDEEMS_PER_WINDOW = 8
_PROOF = re.compile(r"[A-Za-z0-9_-]{40,96}")


@dataclass(frozen=True)
class ImportProofOffer:
    approved: bool
    proof: str = ""


@dataclass(frozen=True)
class _PendingProof:
    owner: int
    session_key: bytes
    issued_at: float
    expires_at: float


class SessionImportProofs:
    """One-process proof ledger with rechecked D2a/D2b session and D3d policy.

    No owner may be passed to issue/consume: it is read from an existing,
    authenticated server-side session store on *each* operation.
    """

    def __init__(
        self, *, mini_sessions: MiniAppSessions, standalone: StandalonePilot,
        customer_service: object, feature_flags: object, pilot_ids: frozenset[int],
        explicitly_enabled: bool = False, now: Callable[[], float] = time.time,
        proof_ttl: int = 45,
    ) -> None:
        if not isinstance(mini_sessions, MiniAppSessions) or not isinstance(
            standalone, StandalonePilot
        ):
            raise ValueError("Trusted D2a and D2b session stores are required")
        if type(explicitly_enabled) is not bool or type(proof_ttl) is not int or not (
            1 <= proof_ttl <= PROOF_TTL_MAX
        ):
            raise ValueError("Explicit activation and bounded proof lifetime required")
        if not isinstance(pilot_ids, frozenset) or any(
            type(v) is not int or not 0 < v < 2**52 for v in pilot_ids
        ):
            raise ValueError("Trusted pilot allowlist required")
        if not callable(now) or not callable(getattr(customer_service, "profile", None)):
            raise ValueError("Trusted server clock and customer service required")
        if not callable(getattr(feature_flags, "snapshot", None)):
            raise ValueError("Trusted current feature-state reader required")
        self.mini_sessions = mini_sessions
        self.standalone = standalone
        self.service = customer_service
        self.flags = feature_flags
        self.pilot_ids = pilot_ids
        self.enabled = explicitly_enabled
        self.now = now
        self.proof_ttl = proof_ttl
        self._pending: dict[bytes, _PendingProof] = {}
        self._issue_rates: dict[bytes, list[float]] = {}
        self._redeem_rates: dict[bytes, list[float]] = {}

    def _clock(self) -> float | None:
        try:
            value = self.now()
            if type(value) not in (float, int) or not 0 < value < 10**12:
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _session_key(mode: SessionMode, cookie: str) -> bytes:
        return hashlib.sha256((mode + ":").encode("ascii") + cookie.encode("ascii")).digest()

    def _owner(self, mode: str, cookie: str, current: float) -> int | None:
        if not isinstance(cookie, str) or not cookie.isascii():
            return None
        try:
            if mode == "telegram-mini-app":
                owner = self.mini_sessions.user(cookie, current)
            elif mode == "standalone":
                owner = self.standalone.session_owner_from_cookie(cookie, current)
            else:
                return None
        except Exception:
            return None
        return owner if type(owner) is int and 0 < owner < 2**52 else None

    def _prune(self, current: float) -> None:
        for digest, row in tuple(self._pending.items()):
            if current < row.issued_at or current >= row.expires_at:
                del self._pending[digest]
        for rates in (self._issue_rates, self._redeem_rates):
            for key, stamps in tuple(rates.items()):
                recent = [t for t in stamps if 0 <= current - t < RATE_WINDOW]
                if recent:
                    rates[key] = recent
                else:
                    del rates[key]

    @staticmethod
    def _charge(rates: dict[bytes, list[float]], key: bytes,
                current: float, maximum: int) -> bool:
        if key not in rates and len(rates) >= MAX_RATE_KEYS:
            return False
        stamps = rates.setdefault(key, [])
        if len(stamps) >= maximum:
            return False
        stamps.append(current)
        return True

    async def _eligible(self, owner: int) -> bool:
        result = await check_import_eligibility(
            authenticated_owner=owner, customer_service=self.service,
            feature_flags=self.flags, pilot_ids=self.pilot_ids,
            explicitly_enabled=self.enabled,
        )
        return result.permitted is True

    async def issue(self, *, mode: SessionMode, session_cookie: str) -> ImportProofOffer:
        """Issue no more than one bounded proof per request, never a URL."""
        if self.enabled is not True:
            return ImportProofOffer(False)
        current = self._clock()
        if current is None:
            return ImportProofOffer(False)
        owner = self._owner(mode, session_cookie, current)
        if owner is None:
            return ImportProofOffer(False)
        self._prune(current)
        key = self._session_key(mode, session_cookie)
        if not self._charge(self._issue_rates, key, current, MAX_ISSUES_PER_WINDOW):
            return ImportProofOffer(False)
        if len(self._pending) >= MAX_PENDING_GRANTS or not await self._eligible(owner):
            return ImportProofOffer(False)
        # An async provider call can race logout, expiry or feature changes.
        final_time = self._clock()
        if final_time is None or final_time < current or (
            self._owner(mode, session_cookie, final_time) != owner
        ):
            return ImportProofOffer(False)
        self._prune(final_time)
        if len(self._pending) >= MAX_PENDING_GRANTS:
            return ImportProofOffer(False)
        proof = secrets.token_urlsafe(32)
        digest = hashlib.sha256(proof.encode("ascii")).digest()
        if digest in self._pending:
            return ImportProofOffer(False)
        self._pending[digest] = _PendingProof(
            owner=owner, session_key=key, issued_at=final_time,
            expires_at=final_time + self.proof_ttl,
        )
        return ImportProofOffer(True, proof)

    async def consume(
        self, *, mode: SessionMode, session_cookie: str, proof: str,
    ) -> bool:
        """Consume at most once; then independently recheck session and policy.

        A True result is a *preflight only*, not permission to return a
        subscription URL. There is deliberately no URL retrieval here.
        """
        if self.enabled is not True or not isinstance(proof, str) or not _PROOF.fullmatch(proof):
            return False
        current = self._clock()
        if current is None:
            return False
        owner = self._owner(mode, session_cookie, current)
        if owner is None:
            return False
        self._prune(current)
        key = self._session_key(mode, session_cookie)
        if not self._charge(self._redeem_rates, key, current, MAX_REDEEMS_PER_WINDOW):
            return False
        digest = hashlib.sha256(proof.encode("ascii")).digest()
        # Pop synchronously before the first await: concurrent replay cannot win.
        row = self._pending.pop(digest, None)
        if row is None or row.owner != owner or row.session_key != key or not (
            row.issued_at <= current < row.expires_at
        ):
            return False
        if not await self._eligible(owner):
            return False
        final_time = self._clock()
        return (final_time is not None and current <= final_time < row.expires_at
                and self._owner(mode, session_cookie, final_time) == owner)
