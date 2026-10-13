#!/usr/bin/env python3
"""Governance contracts: structured Roadmap, concepts and changed audit protection."""
from __future__ import annotations
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGES=("DRAFT","APPROVED","IMPLEMENTED","INCORPORATED")
ROADMAP_STAGES=("⬜ Запланировано","🟡 Реализовано в main","🟠 Опубликовано; acceptance отложен")
ISSUE=re.compile(r"\[#(\d+)\]\(https://github\.com/cLIcHE-QA/3xui-telegram-bot/issues/\1\)")
REGISTRY="docs/roadmap/concept-registry.json"
AUDIT="scripts/check-documentation-semantics.py"

def load_audit(root:Path=ROOT):
    spec=importlib.util.spec_from_file_location("governance_semantics",root/AUDIT)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def roadmap_rows(root:Path=ROOT):
    text=(root/"docs/ROADMAP.md").read_text(encoding="utf-8")
    anchor="## Активный Issue-реестр (machine-checked)"
    if text.count(anchor)!=1: raise ValueError("exactly one active Issue registry required")
    section=text.split(anchor,1)[1].split("\n## ",1)[0]
    rows={}
    for line in section.splitlines():
        if not line.startswith("| [#"): continue
        cells=[x.strip() for x in line.strip().strip("|").split("|")]
        if len(cells)!=6:raise ValueError("Issue row must have six fields")
        m=ISSUE.fullmatch(cells[0])
        if not m:raise ValueError("Issue row must use canonical URL")
        n=int(m.group(1))
        if n in rows:raise ValueError(f"duplicate Issue #{n}")
        if cells[1] not in ROADMAP_STAGES:raise ValueError(f"illegal status for #{n}")
        if any(not value for value in cells):raise ValueError(f"empty Issue cell #{n}")
        if cells[1]=="🟠 Опубликовано; acceptance отложен" and cells[3]=="TBD":
            raise ValueError(f"published status cannot have TBD tag #{n}")
        if cells[1]=="🟡 Реализовано в main" and cells[2]=="—":
            raise ValueError(f"merged status requires PR #{n}")
        rows[n]=dict(zip(("issue","status","pr","target","evidence","next"),cells))
    if not rows:raise ValueError("empty active Issue registry")
    return rows

def concepts_ok(root:Path=ROOT, previous:dict|None=None)->list[str]:
    errors=[]
    manifest=json.loads((root/REGISTRY).read_text(encoding="utf-8"))
    entries=manifest["concepts"]
    paths=[x["path"] for x in entries]
    live=sorted(x.relative_to(root).as_posix() for x in (root/"docs/roadmap/concepts").glob("*.md"))
    if sorted(paths)!=live or len(paths)!=len(set(paths)):
        errors.append("concept registry must contain each mutable concept exactly once")
    old={x["path"]:x for x in (previous or {}).get("concepts",[])}
    for item in entries:
        p=item["path"]
        stage=item["status"]
        if stage not in STAGES:errors.append(f"{p}: unknown lifecycle status");continue
        if not item["issues"] or not all(isinstance(n,int) and n>0 for n in item["issues"]):
            errors.append(f"{p}: Issue link required")
        if stage in ("APPROVED","IMPLEMENTED","INCORPORATED") and not item.get("decision_evidence"):
            errors.append(f"{p}: approved state requires decision evidence")
        if stage in ("IMPLEMENTED","INCORPORATED"):
            if not item.get("implementation_pr") or not re.fullmatch(r"[0-9a-f]{40}",str(item.get("implementation_sha") or "")) or not item.get("tests_evidence"):
                errors.append(f"{p}: implemented stage requires PR, SHA and test evidence")
        if stage=="INCORPORATED":
            doc=item.get("normative_document")
            if not doc or not (root/doc).is_file():errors.append(f"{p}: incorporation requires existing normative document")
        if p in old:
            before=old[p]["status"]
            if before not in STAGES or STAGES.index(stage)<STAGES.index(before) or STAGES.index(stage)>STAGES.index(before)+1:
                errors.append(f"{p}: invalid lifecycle transition {before}->{stage}")
    archive=json.loads((root/"docs/roadmap/archive-manifest.json").read_text(encoding="utf-8"))
    if any(x["path"].startswith("docs/roadmap/concepts/") for x in archive["segments"]):
        errors.append("immutable archive references mutable concepts")
    return errors

def release_consistency(root:Path=ROOT)->list[str]:
    text=(root/"docs/ROADMAP.md").read_text(encoding="utf-8")
    errors=[]
    summary=text.split("## Актуальная сводка проекта",1)[-1].split("\n## ",1)[0]
    for fact in ("**Published:**","**Deployed:**","**Accepted:**"):
        if summary.count(fact)!=1: errors.append(f"missing/duplicate release state: {fact}")
    published=re.search(r"\*\*Published:\*\*[^\n]*?releases/tag/(v\d+\.\d+\.\d+(?:-rc\.\d+)?)",summary)
    if not published:errors.append("Published must link to real immutable GitHub tag")
    else:
        tag=published.group(1)
        if not re.search(r"\b[0-9a-f]{40}\b",summary.split("**Published:**",1)[1].split("**Deployed:**",1)[0]):
            errors.append("Published must provide 40-char tag SHA")
        if ("## "+tag) not in (root/"CHANGELOG.md").read_text(encoding="utf-8"):
            errors.append("Published tag must have corresponding CHANGELOG section")
    deployed=summary.split("**Deployed:**",1)[-1].split("**Accepted:**",1)[0]
    accepted=summary.split("**Accepted:**",1)[-1]
    if "operator-reported" in deployed and not any(x in deployed for x in ("PENDING", "не подтверж", "без независимого")):
        errors.append("operator-reported deployment requires explicit evidence limitation")
    if "NOT PASS" in accepted and re.search(r"\bfull\s+acceptance\s+PASS\b",summary,re.I):
        errors.append("contradictory acceptance claim")
    if "NOT PASS" not in accepted and "BLOCKED ON G-09 + D1" in text:
        errors.append("blocked gates cannot imply full acceptance PASS")
    return errors

def changed_files(base:str,head:str,root:Path=ROOT)->list[tuple[str,str]]:
    result=subprocess.run(["git","diff","--name-status","--diff-filter=ACMR",base+"..."+head],
                          cwd=root,check=True,capture_output=True,text=True)
    return [(x.split("\t")[-1],x.split("\t")[0][0]) for x in result.stdout.splitlines()]

def validate(root:Path=ROOT, changed:list[tuple[str,str]]|None=None, previous:dict|None=None):
    errors=[]
    try:roadmap_rows(root)
    except ValueError as e:errors.append(str(e))
    errors.extend(concepts_ok(root,previous))
    errors.extend(release_consistency(root))
    check=load_audit(root)
    concept_changes=[p for p,_ in changed or [] if p.startswith("docs/roadmap/concepts/") and p.endswith(".md")]
    if concept_changes and not any(p==REGISTRY for p,_ in changed or []):
        errors.append("mutable concept changes require same-PR lifecycle registry review")
    for path,kind in changed or []:
        if path.startswith("docs/audits/roadmap-history/") and kind!="A":
            errors.append(f"immutable history modified: {path}")
        elif path.startswith("docs/audits/") and path.endswith(".md") and path!="docs/audits/AUDIT_TEMPLATE.md":
            errors.extend(check.audit_ok(root,path))
            errors.extend(check.links_ok(root,path))
    return errors

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--base-sha",default="")
    p.add_argument("--head-sha",default="")
    args=p.parse_args()
    files=[]; old=None
    if args.base_sha and args.head_sha:
        try:
            files=changed_files(args.base_sha,args.head_sha)
            prev=subprocess.run(["git","show",args.base_sha+":"+REGISTRY],cwd=ROOT,capture_output=True,text=True)
            if prev.returncode==0:old=json.loads(prev.stdout)
        except (subprocess.CalledProcessError,ValueError) as e:
            print("Governance UNKNOWN/PENDING: "+str(e),file=sys.stderr);return 2
    errors=validate(ROOT,files,old)
    for err in errors:print("::error::"+err,file=sys.stderr)
    print("Governance "+("FAIL" if errors else "PASS"))
    return 1 if errors else 0

if __name__=="__main__":raise SystemExit(main())
