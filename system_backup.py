from __future__ import annotations

import asyncio
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backup_manager import BackupManager, BackupResult
from config import NodeBackupTarget
from xui import XUIClient


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return cleaned or "node"


class SystemBackupService:
    """Build master backups and optionally append direct node DB backups.

    Node health/discovery comes from the master 3x-ui native nodes API. Database
    downloads need a dedicated admin-scope token for each node because the
    master's stored node-sync token is intentionally write-only/not exposed by
    /panel/api/nodes/list.
    """

    def __init__(self, manager: BackupManager, targets: tuple[NodeBackupTarget, ...]):
        self.manager = manager
        self.targets = targets

    def configured_node_names(self) -> tuple[str, ...]:
        return tuple(t.node_name for t in self.targets)

    def has_target_for(self, node_name: str) -> bool:
        needle = node_name.strip().casefold()
        return any(t.node_name.strip().casefold() == needle for t in self.targets)

    async def _fetch_target(self, target: NodeBackupTarget, root: Path):
        client = XUIClient(target.panel_url, target.api_token, target.verify_tls)
        body, remote_filename = await client.download_database()

        node_dir_name = _safe_segment(target.node_name)
        node_dir = root / node_dir_name
        node_dir.mkdir(parents=True, exist_ok=True)

        filename = _safe_segment(remote_filename)
        if "." not in filename:
            filename += ".db"
        db_path = node_dir / filename
        await asyncio.to_thread(db_path.write_bytes, body)

        meta = {
            "node_name": target.node_name,
            "source_panel_url": target.panel_url,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "database_file": filename,
            "note": "API token is intentionally not stored in this metadata.",
        }
        meta_path = node_dir / "node.json"
        await asyncio.to_thread(
            meta_path.write_text,
            json.dumps(meta, ensure_ascii=False, indent=2),
            "utf-8",
        )
        return target, node_dir_name, db_path, meta_path

    async def create_full_backup(self) -> BackupResult:
        extra_files: dict[str, Path] = {}
        extra_missing: list[str] = []
        node_results: list[dict] = []

        with tempfile.TemporaryDirectory(prefix="node-backup-stage-") as tmp:
            root = Path(tmp)

            if self.targets:
                results = await asyncio.gather(
                    *(self._fetch_target(target, root) for target in self.targets),
                    return_exceptions=True,
                )
                for target, result in zip(self.targets, results):
                    if isinstance(result, Exception):
                        extra_missing.append(
                            f"nodes/{_safe_segment(target.node_name)}/ ({type(result).__name__}: {result})"
                        )
                        node_results.append(
                            {
                                "name": target.node_name,
                                "ok": False,
                                "error": f"{type(result).__name__}: {result}",
                            }
                        )
                        continue

                    _, node_dir_name, db_path, meta_path = result
                    extra_files[f"nodes/{node_dir_name}/{db_path.name}"] = db_path
                    extra_files[f"nodes/{node_dir_name}/node.json"] = meta_path
                    node_results.append(
                        {
                            "name": target.node_name,
                            "ok": True,
                            "database_file": db_path.name,
                            "bytes": db_path.stat().st_size,
                        }
                    )

            return await asyncio.to_thread(
                self.manager.create_full_backup,
                extra_files,
                extra_missing,
                version="3.7.0",
                extra_manifest={"nodes": node_results},
            )
