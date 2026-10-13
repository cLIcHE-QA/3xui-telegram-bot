"""Read-only access to the exact historical Roadmap snapshot for legacy contract tests.

The source integrity is independently verified by check-roadmap-structure.py.
New current-state tests should read docs/ROADMAP.md directly.
"""
import json
from pathlib import Path


def historical_roadmap(root: Path) -> str:
    manifest = json.loads((root / "docs/roadmap/archive-manifest.json").read_text(encoding="utf-8"))
    return "".join(
        (root / item["path"]).read_text(encoding="utf-8")
        for item in manifest["segments"]
    )
