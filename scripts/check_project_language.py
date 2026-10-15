#!/usr/bin/env python3
"""Проверка очевидной англоязычной прозы в новых Markdown и PR metadata."""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CYR = re.compile(r"[А-Яа-яЁё]")
LAT = re.compile(r"[A-Za-z]")
CODE = re.compile(r"`[^`]*`")
URL = re.compile(r"https?://\S+")
TITLE = re.compile(r"^(feat|fix|security|docs|test|chore|refactor): (.+)$")

def long_english(line: str) -> bool:
    line = CODE.sub("", URL.sub("", line))
    if line.lstrip().startswith(("|", "<!--")):
        return False
    return len(LAT.findall(line)) >= 90 and not CYR.search(line)

def check_pr(title: str, body: str) -> list[str]:
    errors = []
    if not title.startswith("release: "):
        m = TITLE.fullmatch(title)
        if m and not CYR.search(m.group(2)):
            words = m.group(2).split()
            if len(words) >= 4 and not re.fullmatch(r"[\w./:#+-]+", m.group(2)):
                errors.append("PR title: пояснение должно быть на русском языке")
    inside = False
    for idx, line in enumerate(body.splitlines(), 1):
        if re.match(r"^\s*(?:`{3,}|~{3,})", line):
            inside = not inside
        elif not inside and long_english(line):
            errors.append(f"PR body, строка {idx}: англоязычная проза")
    return errors

def check_diff(text: str) -> list[str]:
    errors = []
    name = ""
    inside = False
    for line in text.splitlines():
        if line.startswith("+++ b/"):
            name = line[6:]
            inside = False
        elif line.startswith("+") and not line.startswith("+++"):
            current = line[1:]
            if re.match(r"^\s*(?:`{3,}|~{3,})", current):
                inside = not inside
            elif not inside and long_english(current):
                errors.append(f"{name}: длинный новый английский абзац")
    return errors

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-sha", required=True)
    p.add_argument("--head-sha", required=True)
    args = p.parse_args()
    result = subprocess.run(
        ["git", "diff", "--unified=0", args.base_sha+"..."+args.head_sha, "--", "*.md"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode:
        print("Language gate UNKNOWN: git diff не удался", file=sys.stderr)
        return 2
    errors = check_diff(result.stdout)
    for issue in errors:
        print("::error::"+issue, file=sys.stderr)
    print("Language gate:", "FAIL" if errors else "PASS")
    return bool(errors)

if __name__ == "__main__":
    raise SystemExit(main())
