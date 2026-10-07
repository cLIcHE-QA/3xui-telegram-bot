#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import NoReturn


HEADING_RE = re.compile(r"^## v(?P<version>\d+\.\d+\.\d+) — (?P<title>.+?)\s*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


def fail(message: str) -> NoReturn:
    raise SystemExit(f"ERROR: {message}")


def release_section(changelog: str, version: str) -> tuple[str, str]:
    lines = changelog.splitlines()
    matches: list[tuple[int, str]] = []

    for index, line in enumerate(lines):
        match = HEADING_RE.fullmatch(line)
        if match and match.group("version") == version:
            matches.append((index, match.group("title").strip()))

    if len(matches) != 1:
        fail(
            f"CHANGELOG.md must contain exactly one heading "
            f"'## v{version} — <title>'; found {len(matches)}"
        )

    start, suffix = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break

    details = "\n".join(lines[start + 1 : end]).strip()
    if not details:
        fail(f"CHANGELOG.md section v{version} is empty")
    if not any(line.startswith("- ") for line in details.splitlines()):
        fail(f"CHANGELOG.md section v{version} must contain at least one bullet")

    return f"v{version} — {suffix}", details


def render_release_notes(changelog: str, version: str, commit: str) -> tuple[str, str]:
    version = version.strip().removeprefix("v")
    commit = commit.strip().lower()

    if not re.fullmatch(VERSION_PATTERN, version):
        fail(f"invalid release version: {version!r}")
    if not COMMIT_RE.fullmatch(commit):
        fail(f"invalid release commit: {commit!r}")

    title, details = release_section(changelog, version)
    tag = f"v{version}"
    body = (
        f"## {title}\n\n"
        f"{details}\n\n"
        f"Коммит релиза: {commit}\n\n"
        "Production deployment:\n\n"
        "~~~bash\n"
        "cd /opt/3xui-bot/3xui-telegram-bot\n"
        f"./scripts/deploy-release.sh {tag}\n"
        "./scripts/deploy-release.sh --status\n"
        "~~~\n\n"
        "Публикация GitHub Release не выполняет production deployment автоматически.\n"
    )
    return title, body


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render canonical GitHub Release title/body from CHANGELOG.md."
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--title-out", type=Path, required=True)
    parser.add_argument("--body-out", type=Path, required=True)
    args = parser.parse_args()

    try:
        changelog = args.changelog.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {args.changelog}: {exc}")

    title, body = render_release_notes(changelog, args.version, args.commit)
    args.title_out.write_text(title + "\n", encoding="utf-8")
    args.body_out.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
