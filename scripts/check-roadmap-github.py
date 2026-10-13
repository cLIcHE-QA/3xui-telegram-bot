#!/usr/bin/env python3
"""Read-only GitHub-state reconciliation. Network failure is UNKNOWN, never PASS."""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
API="https://api.github.com"
ISSUES=(317,342,422,433,466,482,487,510,564,577,593,597)
class Unknown(RuntimeError): pass
class Drift(RuntimeError): pass
def fetch(repo:str,suffix:str,token:str=""):
    request=urllib.request.Request(f"{API}/repos/{repo}{suffix}",headers={
       "Accept":"application/vnd.github+json","User-Agent":"roadmap-readonly-audit",
       **({"Authorization":f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(request,timeout=15) as f:return json.load(f)
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
        raise Unknown(f"GitHub unreachable/unreadable: {type(e).__name__}") from e
def validate(roadmap:str,states:dict[int,str],release:str)->None:
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-rc\.\d+)?",release):raise Drift("invalid published tag")
    if f"`{release}`" not in roadmap: raise Drift(f"published tag {release} absent from Roadmap")
    for n,state in states.items():
        if f"#{n}" not in roadmap: continue
        if n in (317,342,422,577,593) and state!="closed":raise Drift(f"expected closed #{n}, actual {state}")
        if n in (433,466,482,487,510,564) and state!="open":raise Drift(f"expected open #{n}, actual {state}; update Roadmap")
    if states.get(597)=="closed" and "#597" not in roadmap:raise Drift("#597 closure missing")
def audit(repo:str,root:Path=ROOT,token:str=""):
    roadmap=(root/"docs/ROADMAP.md").read_text(encoding="utf-8")
    states={n:fetch(repo,f"/issues/{n}",token)["state"] for n in ISSUES}
    releases=fetch(repo,"/releases?per_page=30",token)
    published=[x for x in releases if not x.get("draft") and x.get("published_at")]
    if not published:raise Unknown("no published releases available")
    tag=max(published,key=lambda x:x["published_at"])["tag_name"]
    validate(roadmap,states,tag)
    return tag,states
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repository",required=True)
    args=p.parse_args()
    try:
        tag,states=audit(args.repository,token=os.getenv("GITHUB_TOKEN",""))
    except Unknown as exc:
        print(f"Roadmap GitHub reconciliation: UNKNOWN/PENDING — {exc}",file=sys.stderr)
        return 2
    except (Drift,KeyError,TypeError,OSError) as exc:
        print(f"Roadmap GitHub reconciliation: FAIL — {exc}",file=sys.stderr)
        return 1
    print(f"Roadmap GitHub reconciliation: PASS — published={tag}, issues={len(states)}; no production assertion")
    return 0
if __name__=="__main__":raise SystemExit(main())
