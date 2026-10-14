#!/usr/bin/env python3
"""Fail-closed documentation validation for current-state docs and newly created audits.

Historical immutable snapshots are never rewritten or relinked by this checker.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FIELDS = (
    "Дата/время и часовой пояс", "Окружение", "Цель",
    "Версия и immutable tag/SHA", "Scope", "Фактический результат",
    "Источник и evidence", "Ограничения и остаточные риски",
    "Связанные Issues", "Следующий шаг", "Раздельные состояния",
)
STATUSES = {"PASS", "PARTIAL", "PENDING", "FAIL", "BLOCKED"}
CHECK_PATHS = (
    "README.md", "AGENTS.md", "docs/ROADMAP.md", "docs/GIT_WORKFLOW.md",
    "docs/LIVING_DOCS.md", "docs/RELEASES.md", "docs/roadmap/HISTORY_INDEX.md",
    "docs/V5_PRODUCTION_ACCEPTANCE.md", "docs/CLIENT_SETUP.md",
)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\((<[^>]*>|[^)\s]+)(?:\s+[^)]*)?\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
AUDIT_FIELD = re.compile(r"^- \*\*(.+?):\*\*\s*(.*?)\s*$", re.M)
TIME = re.compile(r"\b\d{4}-\d{2}-\d{2}\s+[0-2]\d:[0-5]\d\s+(?:UTC[+-](?:0\d|1[0-4]):[0-5]\d|Z)\b")


def markdown_lines(text: str):
    """Ignore fenced code: code samples are not navigational Markdown."""
    fenced = False
    marker = ""
    for line in text.splitlines():
        fence = re.match(r"^\s*([\x60~]{3,})", line)
        if fence:
            cur = fence.group(1)[0]
            if not fenced:
                marker, fenced = cur, True
            elif cur == marker:
                fenced = False
            continue
        if not fenced:
            yield line


def heading_slugs(text: str) -> set[str]:
    slugs: set[str] = set()
    seen: Counter[str] = Counter()
    for line in markdown_lines(text):
        m = HEADING.match(line)
        if not m:
            continue
        heading = re.sub(r"<[^>]*>", "", m.group(1))
        heading = re.sub(r"!?(?:\[([^]]+)\])\([^)]*\)", r"\1", heading)
        heading = heading.replace("\x60", "").replace("*", "").replace("_", "_")
        heading = unicodedata.normalize("NFC", heading).lower()
        heading = "".join(c for c in heading if c in "-_ " or unicodedata.category(c)[0] in "LN")
        slug = re.sub(r"\s+", "-", heading.strip())
        suffix = seen[slug]
        seen[slug] += 1
        slugs.add(slug if not suffix else f"{slug}-{suffix}")
    return slugs


def normalize(path: str, dest: str):
    dest = unquote(dest.strip().strip("<>"))
    if not dest or dest.startswith(("https://", "http://", "mailto:", "//", "tel:", "data:")):
        return None
    target, _, fragment = dest.partition("#")
    target = target.split("?", 1)[0]
    stack = path.split("/")[:-1]
    for part in target.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not stack:
                raise ValueError("relative link escapes repository")
            stack.pop()
        else:
            stack.append(part)
    return "/".join(stack), unquote(fragment)


def links_ok(root: Path, path: str) -> list[str]:
    content = (root / path).read_text(encoding="utf-8")
    problems: list[str] = []
    slugs_cache: dict[str, set[str]] = {}
    for line in markdown_lines(content):
        for match in LINK.finditer(line):
            target = match.group(1)
            try:
                resolved = normalize(path, target)
            except ValueError:
                problems.append(f"{path}: escaping repository: {target}")
                continue
            if resolved is None:
                continue
            rel, fragment = resolved
            destination = root / rel
            if not destination.is_file() and not destination.is_dir():
                problems.append(f"{path}: broken local link {target} -> {rel}")
                continue
            if fragment and destination.is_file() and destination.suffix.lower() == ".md":
                slugs = slugs_cache.setdefault(rel, heading_slugs(destination.read_text(encoding="utf-8")))
                if fragment.lower() not in slugs:
                    problems.append(f"{path}: missing Markdown anchor {target}")
    return problems


def audit_ok(root: Path, path: str) -> list[str]:
    text = (root / path).read_text(encoding="utf-8")
    problems: list[str] = []
    if text.count("<!-- audit-schema: 1 -->") != 1:
        problems.append(f"{path}: audit-schema marker must appear exactly once")
    found = [m.groups() for m in AUDIT_FIELD.finditer(text)]
    counts = Counter(k for k, _ in found)
    fields = dict(found)
    for field in FIELDS:
        if counts[field] != 1:
            problems.append(f"{path}: missing/duplicate audit field {field}")
        elif not fields[field].strip() or re.search(r"YYYY|\bTODO\b|\bTBD\b|\.\.\.|#NNN", fields[field], re.I):
            problems.append(f"{path}: placeholder audit field {field}")
    time = fields.get("Дата/время и часовой пояс", "")
    if not TIME.search(time):
        problems.append(f"{path}: timestamp requires date, time and timezone")
    date_in_name = re.search(r"\d{4}-\d{2}-\d{2}", Path(path).name)
    if date_in_name and not time.startswith(date_in_name.group()):
        problems.append(f"{path}: date in filename differs from audit time")
    status = fields.get("Фактический результат", "").strip().split(" ", 1)[0]
    if status not in STATUSES:
        problems.append(f"{path}: invalid audit result status")
    version = fields.get("Версия и immutable tag/SHA", "")
    if not re.search(r"\b[0-9a-f]{40}\b", version):
        if not re.search(r"\bN/A\b\s*[:(—-]\s*\S{8,}", version, re.I):
            problems.append(f"{path}: require immutable 40-char SHA or reasoned N/A")
    evidence = fields.get("Источник и evidence", "")
    if not re.search(r"https?://\S+|[\w/.-]+\.(?:md|json|log)\b", evidence):
        problems.append(f"{path}: evidence must identify a source/link")
    issues = fields.get("Связанные Issues", "")
    if not re.search(r"#\d+\b|\bN/A\b\s*[:(—-]\s*\S{8,}", issues, re.I):
        problems.append(f"{path}: require Issue number or reasoned N/A")
    boundary = fields.get("Раздельные состояния", "").lower()
    for key in ("merged=", "published=", "deployed=", "accepted="):
        if key not in boundary:
            problems.append(f"{path}: missing distinct state {key}")
    return problems


def current_ok(root: Path) -> list[str]:
    t = (root / "docs/ROADMAP.md").read_text(encoding="utf-8")
    issues = []
    if t.count("## Актуальная сводка проекта") != 1:
        issues.append("missing or duplicate current-state section")
    for g in [f"G-{i:02d}" for i in range(1, 12)] + ["W-01", "W-02"]:
        count = len(re.findall(r"^\|\s*" + re.escape(g) + r"\s*\|", t, re.M))
        if count != 1:
            issues.append(f"missing/duplicate acceptance gate {g} ({count})")
    g09_pass = bool(re.search(r"^\|\s*G-09\s*\|[^\n]*\|\s*PASS\s*\|", t, re.M))
    g11_pending = bool(re.search(r"^\|\s*G-11\s*\|[^\n]*\|\s*PENDING\s*\|", t, re.M))
    g11_blocked = bool(re.search(r"^\|\s*G-11\s*\|[^\n]*\|\s*BLOCKED\s*\|\s*\*\*BLOCKED ON G-09(?: \+ D1)?\*\*", t, re.M))
    if not (g09_pass and g11_pending or not g09_pass and g11_blocked):
        issues.append("G-11 must stay BLOCKED until G-09 PASS, then become PENDING")
    if re.search(r"\*\*⬜[^\n]*\]\([^)]*/issues/(?:593|597)\)", t):
        issues.append("closed docs-only issue listed as planned")
    # Current gate verdicts, waivers and actionable queue are distinct state axes.
    gate_statuses: dict[str, str] = {}
    section = t.split("## Реестр acceptance-gates rc.9", 1)
    if len(section) != 2:
        issues.append("missing canonical acceptance gate table")
    else:
        registry = section[1].split("## Текущая очередь и блокировки", 1)[0]
        gate_part = registry.split("### Реестр принятых исключений", 1)
        gate_lines = [line for line in gate_part[0].splitlines() if line.startswith("|")]
        if len(gate_lines) < 2 or gate_lines[0].strip() != "| Gate | Что проверено | Итог gate | Осталось / риск |":
            issues.append("acceptance gates require canonical four-column header")
        expected = {f"G-{i:02d}" for i in range(1, 12)}
        seen = set()
        statuses = {"PASS", "PARTIAL", "PENDING", "FAIL", "BLOCKED"}
        for line in gate_lines[2:]:
            cells = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(cells) != 4:
                issues.append("acceptance gate row requires four columns")
                continue
            gate, checked, status, remaining = cells
            seen.add(gate)
            gate_statuses[gate] = status
            if gate not in expected or not checked or not remaining or status not in statuses:
                issues.append(f"invalid gate row or verdict: {gate}")
            if re.search(r"\b(?:smoke\s+CLOSED|проверенный smoke закрыт|smoke закрыт)\b", line, re.I):
                issues.append(f"ambiguous smoke closure in gate: {gate}")
        if seen != expected:
            issues.append("acceptance gate set mismatch")
        if len(gate_part) != 2:
            issues.append("missing separate waiver register")
        else:
            waiver_lines = [line for line in gate_part[1].splitlines() if line.startswith("|")]
            if not waiver_lines or waiver_lines[0].strip() != "| Исключение | Решение оператора | Не проверено / остаточный риск |":
                issues.append("waivers require canonical header")
            actual = {}
            for line in waiver_lines[2:]:
                cells = [x.strip() for x in line.strip().strip("|").split("|")]
                if len(cells) != 3:
                    issues.append("waiver row requires three columns")
                else:
                    actual[cells[0]] = cells[1]
                    if "не PASS" not in cells[2]:
                        issues.append("waiver cannot be implied PASS")
            if actual != {"W-01": "OPERATOR-WAIVED / NOT TESTED", "W-02": "OPERATOR-WAIVED / INCONCLUSIVE"}:
                issues.append("waiver register mismatch")
    queue_parts = t.split("## Текущая очередь и блокировки", 1)
    if len(queue_parts) != 2:
        issues.append("missing current active queue")
    else:
        queue = queue_parts[1].split("## Реестр открытых задач", 1)[0]
        active_rows = [line for line in queue.splitlines() if re.match(r"^\d+\.\s", line)]
        if not active_rows and not re.search(r"очередь пуста|нет назначенных действий", queue, re.I):
            issues.append("empty current queue requires explicit decision")
        queued_ids = []
        for line in active_rows:
            match = re.match(r"^\d+\.\s\*\*(G-\d{2})\s*/\s*(PENDING|PARTIAL|FAIL|BLOCKED):", line)
            if not match:
                issues.append("queue row must have active gate and unfinished status")
                continue
            gate, queue_status = match.groups()
            queued_ids.append(gate)
            if gate_statuses.get(gate) != queue_status:
                issues.append(f"queue status differs from gate register: {gate}")
            if "PASS" in line or "WAIVED" in line:
                issues.append("completed or waived work in active queue")
        if len(queued_ids) != len(set(queued_ids)):
            issues.append("duplicate active gate in current queue")
        if gate_statuses.get("G-09") == "PENDING" and "G-09" not in queued_ids:
            issues.append("G-09 pending natural expiry missing from queue")
        if gate_statuses.get("G-11") == "BLOCKED" and "G-11" not in queued_ids:
            issues.append("G-11 blocked report missing from queue")
    if t.count("## Реестр открытых задач") != 1:
        issues.append("missing/duplicate backlog section")
    # Closed outcomes live in Issues/PRs/audits; the current roadmap is not a history log.
    completed = [line for line in t.splitlines() if line.startswith("**✅ Завершено")]
    if len(completed) > 1:
        issues.append("completed history must use at most one aggregate summary")
    if completed and len(completed[0]) > 1200:
        issues.append("completed aggregate exceeds 1200 characters")
    if any(line.startswith(("**Закрытый", "**✅ Документационное", "**✅ Docs/CI")) for line in t.splitlines()):
        issues.append("individual completed Issue paragraphs forbidden")
    return issues


def check(root: Path = ROOT, changed: list[str] | None = None) -> list[str]:
    new_files = changed or []
    errors = current_ok(root)
    targets = set(CHECK_PATHS)
    targets.update(p for p in new_files if p.startswith("docs/roadmap/concepts/") and p.endswith(".md"))
    targets.update(p for p in new_files if p.startswith("docs/audits/") and p.endswith(".md")
                   and "/roadmap-history/" not in p)
    for path in sorted(targets):
        if (root / path).is_file():
            errors.extend(links_ok(root, path))
    for path in new_files:
        if (path.startswith("docs/audits/") and path.endswith(".md")
                and "/roadmap-history/" not in path
                and path != "docs/audits/AUDIT_TEMPLATE.md"):
            errors.extend(audit_ok(root, path))
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--head-sha", default="")
    args = parser.parse_args()
    new_files: list[str] = []
    if args.base_sha and args.head_sha:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=A",
             args.base_sha + "..." + args.head_sha],
            cwd=ROOT, text=True, capture_output=True, check=False)
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            return 2
        new_files = result.stdout.splitlines()
    errors = check(ROOT, new_files)
    for error in errors:
        print("::error::" + error, file=sys.stderr)
    print(f"Documentation semantics: {'FAIL' if errors else 'PASS'} ({len(new_files)} new files)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
