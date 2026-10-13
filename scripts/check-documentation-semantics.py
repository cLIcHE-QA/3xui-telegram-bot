#!/usr/bin/env python3
"""Deterministic fail-closed checks for *new* audit files and current docs."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("Дата/время и часовой пояс", "Окружение", "Цель", "Версия и immutable tag/SHA",
          "Scope", "Фактический результат", "Источник и evidence",
          "Ограничения и остаточные риски", "Связанные Issues",
          "Следующий шаг", "Раздельные состояния")
STATUS = ("PASS", "PARTIAL", "PENDING", "FAIL", "BLOCKED")
CHECK_PATHS = ("README.md", "docs/ROADMAP.md", "docs/GIT_WORKFLOW.md",
               "docs/LIVING_DOCS.md", "docs/roadmap/HISTORY_INDEX.md")
def normalize(base: str, dest: str) -> str | None:
    dest = unquote(dest.strip().split("#",1)[0].split("?",1)[0])
    if not dest or dest.startswith(("https://", "http://", "mailto:", "//")):
        return None
    stack = base.split("/")[:-1]
    for part in dest.split("/"):
        if part in ("", "."): continue
        if part == "..":
            if not stack: raise ValueError("path escapes repository")
            stack.pop()
        else: stack.append(part)
    return "/".join(stack)
def links_ok(root: Path, path: str) -> list[str]:
    s = (root/path).read_text(encoding="utf-8")
    errors = []
    for m in re.finditer(r"(?<!!)\[[^\]]*\]\(([^)]+)\)",s):
        dest = m.group(1).strip().split(" ",1)[0].strip("<>")
        try: rel = normalize(path,dest)
        except ValueError: errors.append(f"{path}: link escapes repo: {dest}"); continue
        if rel and not (root/rel).exists(): errors.append(f"{path}: broken link {dest} -> {rel}")
    return errors
def audit_ok(root: Path,path: str) -> list[str]:
    text = (root/path).read_text(encoding="utf-8")
    errors = []
    if text.count("<!-- audit-schema: 1 -->") != 1: errors.append(f"{path}: missing schema marker")
    for field in FIELDS:
        m = re.search(r"^- \*\*"+re.escape(field)+r":\*\*\s*(.+)$",text,re.M)
        if not m or not m.group(1).strip() or "YYYY-" in m.group(1): errors.append(f"{path}: missing {field}")
    if not re.search(r"\b(?:PASS|PARTIAL|PENDING|FAIL|BLOCKED)\b",text): errors.append(f"{path}: missing result")
    if not re.search(r"\d{4}-\d{2}-\d{2}\s+\d\d:\d\d\s+(?:UTC[+-]\d\d:\d\d|Z)",text):
        errors.append(f"{path}: missing timestamp with zone")
    return errors
def current_ok(root: Path) -> list[str]:
    t=(root/"docs/ROADMAP.md").read_text(encoding="utf-8")
    problems=[]
    if re.search(r"(?:запланирова|отложенн)[^\n]{0,500}#593",t,re.I): problems.append("closed #593 listed as planned")
    if t.count("## Актуальная сводка проекта")!=1: problems.append("duplicate current summary")
    for g in ("G-09","G-10","G-11","W-01","W-02"):
        if len(re.findall(r"^\| "+re.escape(g)+r" \|",t,re.M))!=1: problems.append("missing/duplicate gate "+g)
    return problems
def check(root: Path=ROOT, changed: list[str]|None=None) -> list[str]:
    changed=changed or []
    errors = current_ok(root)
    links=set(CHECK_PATHS)
    links.update(p for p in changed if p.startswith("docs/roadmap/concepts/") and p.endswith(".md"))
    links.update(p for p in changed if p.startswith("docs/audits/") and p.endswith(".md")
                 and "/roadmap-history/" not in p)
    for p in sorted(links):
        if (root/p).exists(): errors.extend(links_ok(root,p))
    for p in changed:
        if (p.startswith("docs/audits/") and p.endswith(".md") and
            "/roadmap-history/" not in p and p!="docs/audits/AUDIT_TEMPLATE.md"):
            errors.extend(audit_ok(root,p))
    return errors
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--base-sha",default="")
    parser.add_argument("--head-sha",default="")
    args=parser.parse_args()
    changed=[]
    if args.base_sha and args.head_sha:
        cmd=["git","diff","--name-only","--diff-filter=A",args.base_sha+"..."+args.head_sha]
        result=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
        if result.returncode: print(result.stderr,file=sys.stderr);return 2
        changed=result.stdout.splitlines()
    errors=check(ROOT,changed)
    for error in errors: print("::error::"+error,file=sys.stderr)
    print(f"Documentation semantics: {'FAIL' if errors else 'PASS'} ({len(changed)} new files)")
    return 1 if errors else 0
if __name__=="__main__": raise SystemExit(main())
