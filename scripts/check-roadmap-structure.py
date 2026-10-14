#!/usr/bin/env python3
"""Roadmap historical snapshot integrity and bounded current-state checks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    manifest = json.loads((root / "docs/roadmap/archive-manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == 1
    next_line = 1
    pieces = []
    for part in manifest["segments"]:
        first, last = part["start_line"], part["end_line"]
        assert first == next_line and last >= first, (part["path"], first, next_line)
        text = (root / part["path"]).read_text(encoding="utf-8")
        expected_count = last - first + 1
        actual_count = len(text.splitlines())
        assert actual_count == expected_count - (last == manifest["source_line_count"]), (
            part["path"], actual_count, expected_count)
        pieces.append(text)
        next_line = last + 1
    assert next_line - 1 == manifest["source_line_count"]
    source = "".join(pieces).encode("utf-8")
    prefix = ("blob " + str(len(source)) + "\0").encode("ascii")
    actual_sha = hashlib.sha1(prefix + source).hexdigest()
    assert actual_sha == manifest["source_blob"], ("archive source mismatch", actual_sha)
    roadmap = (root / "docs/ROADMAP.md").read_text(encoding="utf-8")
    assert len(roadmap.splitlines()) <= 350, "Roadmap must be <=350 lines; write dated audits separately"
    assert roadmap.count("## Актуальная сводка проекта") == 1
    assert roadmap.count("## Статусы дорожной карты") == 1
    assert "## Реестр acceptance-gates" in roadmap
    for name in ("G-01", "G-02", "G-03", "G-04", "G-05", "G-06", "G-07",
                 "G-08", "G-09", "G-10", "G-11", "D1", "W-01", "W-02",
                 "BLOCKED ON G-09", "#466", "#487", "#593",
                 "Published", "Deployed", "Accepted", "NOT PASS"):
        assert name in roadmap, name
    print("Roadmap structure PASS: lossless 5803-line historical blob; bounded current state")


if __name__ == "__main__":
    check()
