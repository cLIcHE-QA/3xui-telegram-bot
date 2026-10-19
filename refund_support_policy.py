"""Единый versioned publication record для юридических Terms (#707/#437).

Этот модуль не устанавливает условия возврата и не заменяет опубликованный
текст Пользовательского соглашения. Неполный/сомнительный реестр означает
отсутствие подтверждённой публичной редакции (fail closed).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re


TERMS_URL = "https://sub.clichegame.space/legal/terms"
PUBLICATION_FILE = Path(__file__).resolve().parent / "docs" / "legal-publication.json"


@dataclass(frozen=True)
class PublishedTerms:
    revision: str
    effective_at: date
    content_sha256: str
    verified_at: datetime
    url: str


def get_published_terms(
    path: Path = PUBLICATION_FILE, *, now: datetime | None = None
) -> PublishedTerms | None:
    """Показывать ссылку только для полной записи о проверенной публикации.

    Сверка фактического HTML/хеша и доступности URL проводится в scope #707
    до изменения versioned record и перед production acceptance; этот
    read-only runtime не делает внешних запросов и не обещает live-аттестацию.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return None
    now = now.astimezone(timezone.utc)
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(source, dict) or source.get("schema") != 1:
            return None
        terms = source.get("terms")
        if not isinstance(terms, dict) or terms.get("publication_state") != "published":
            return None

        revision = terms.get("revision")
        effective = terms.get("effective_at")
        digest = terms.get("content_sha256")
        verified = terms.get("verified_at")
        url = terms.get("url")
        if (
            not isinstance(revision, str)
            or re.fullmatch(r"v[0-9]+(?:\.[0-9]+)*", revision) is None
            or not isinstance(effective, str)
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", effective) is None
            or not isinstance(digest, str)
            or re.fullmatch(r"[a-f0-9]{64}", digest) is None
            or not isinstance(verified, str)
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", verified) is None
            or url != TERMS_URL
        ):
            return None
        effective_at = date.fromisoformat(effective)
        verified_at = datetime.fromisoformat(verified.replace("Z", "+00:00"))
        if effective_at > now.date() or verified_at > now:
            return None
        return PublishedTerms(
            revision=revision,
            effective_at=effective_at,
            content_sha256=digest,
            verified_at=verified_at,
            url=TERMS_URL,
        )
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
