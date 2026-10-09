#!/usr/bin/env python3
"""Fail the required PR-conventions job when a PR checklist is incomplete.

The checker verifies declared readiness, not whether a checked claim is true.
"""

from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".github" / "pull_request_template.md"
CHECKBOX = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]\s+(.+?)\s*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
REQUIRED_HEADINGS = (
    "## Что изменено",
    "## Проверки",
    "## Documentation impact",
    "## Roadmap / Acceptance impact",
    "## Checklist",
)


def extract_checkboxes(markdown: str) -> list[tuple[str, bool, int]]:
    """Read task-list items outside Markdown fenced code examples."""
    items: list[tuple[str, bool, int]] = []
    fence_char = ""
    fence_length = 0

    for line_number, line in enumerate(markdown.splitlines(), 1):
        stripped = line.lstrip()
        if fence_char:
            closing = re.fullmatch(
                rf"{re.escape(fence_char)}{{{fence_length},}}\s*", stripped
            )
            if closing:
                fence_char = ""
                fence_length = 0
            continue

        opening = FENCE.match(stripped)
        if opening:
            fence_char = opening.group(1)[0]
            fence_length = len(opening.group(1))
            continue

        match = CHECKBOX.fullmatch(line)
        if match:
            items.append(
                (match.group(2).strip(), match.group(1).lower() == "x", line_number)
            )
    return items


def validate_pr_body(body: str, template: str) -> list[str]:
    """Validate the presence and completion of the canonical PR checklist."""
    errors: list[str] = []
    if not body.strip():
        return ["Описание PR пустое: добавь заполненный шаблон PR."]

    for heading in REQUIRED_HEADINGS:
        if not re.search(rf"^{re.escape(heading)}\s*$", body, re.MULTILINE):
            errors.append(f"В описании PR отсутствует раздел: {heading}")

    required_items = extract_checkboxes(template)
    if not required_items:
        return errors + ["В каноническом PR template отсутствуют чекбоксы."]

    actual_items = extract_checkboxes(body)
    required_labels = Counter(label for label, _, _ in required_items)
    actual_labels = Counter(label for label, _, _ in actual_items)

    for label, missing_count in (required_labels - actual_labels).items():
        errors.append(
            f"Отсутствует обязательный пункт шаблона ({missing_count}): {label}"
        )

    for _, checked, line_number in actual_items:
        if not checked:
            errors.append(
                f"Чекбокс на строке {line_number} не закрыт. "
                "Отметь [x] после проверки или обоснуй N/A."
            )
    return errors


def main() -> int:
    body = os.environ.get("PR_BODY")
    if body is None:
        print("PR checklist: PR_BODY не передан из pull_request event.", file=sys.stderr)
        return 2
    template = TEMPLATE.read_text(encoding="utf-8")
    errors = validate_pr_body(body, template)
    if errors:
        for message in errors:
            print(f"PR checklist: {message}", file=sys.stderr)
        return 1
    print("PR checklist: PASS — все обязательные пункты найдены и отмечены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
