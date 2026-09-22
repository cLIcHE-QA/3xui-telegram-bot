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

    def target_for(self, node_name: str) -> NodeBackupTarget | None:
        needle = node_name.strip().casefold()
        for target in self.targets:
            if target.node_name.strip().casefold() == needle:
                return target
        return None

    def has_target_for(self, node_name: str) -> bool:
        return self.target_for(node_name) is not None

    async def create_node_snapshot(self, node_name: str) -> Path:
        """Download one node database using its dedicated admin backup token.

        The master's node-sync token is intentionally not exposed by 3x-ui, so
        this action is available only for nodes configured in NODE_BACKUP_TARGETS.
        """
        target = self.target_for(node_name)
        if target is None:
            raise ValueError(f"Backup target is not configured for node: {node_name}")
        client = XUIClient(target.panel_url, target.api_token, target.verify_tls)
        body, remote_filename = await client.download_database()
        safe_node = _safe_segment(target.node_name)
        safe_remote = _safe_segment(remote_filename)
        if "." not in safe_remote:
            safe_remote += ".db"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_dir = self.manager.backup_dir / "nodes" / safe_node
        await asyncio.to_thread(out_dir.mkdir, parents=True, exist_ok=True)
        path = out_dir / f"node-backup-{stamp}-{safe_remote}"
        await asyncio.to_thread(path.write_bytes, body)

        # Keep a few manual node snapshots; full archives remain governed by BACKUP_KEEP.
        def _prune() -> None:
            items = sorted(
                out_dir.glob("node-backup-*"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True,
            )
            for old in items[5:]:
                try:
                    old.unlink()
                except OSError:
                    pass
        await asyncio.to_thread(_prune)
        return path

    def direct_client_for(self, node_name: str) -> XUIClient | None:
        target = self.target_for(node_name)
        if target is None:
            return None
        return XUIClient(target.panel_url, target.api_token, target.verify_tls)

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
                version="4.7.0",
                extra_manifest={"nodes": node_results},
            )
