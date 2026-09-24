#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values

from offsite_backup import OffsiteBackupService
from restore_manager import RestoreManager


REQUIRED = (
    "OFFSITE_BACKUP_BUCKET",
    "OFFSITE_BACKUP_ACCESS_KEY_ID",
    "OFFSITE_BACKUP_SECRET_ACCESS_KEY",
    "OFFSITE_BACKUP_ENCRYPTION_KEY_B64",
)


def load_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"env file not found: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SystemExit(f"env file must not be group/world accessible: {path} mode={oct(mode)}")
    values = {k: str(v or "") for k, v in dotenv_values(path).items()}
    missing = [name for name in REQUIRED if not values.get(name, "").strip()]
    if missing:
        raise SystemExit("missing off-site recovery variables: " + ", ".join(missing))
    endpoint = values.get("OFFSITE_BACKUP_ENDPOINT_URL", "").strip().rstrip("/")
    if endpoint and not endpoint.startswith("https://"):
        raise SystemExit("OFFSITE_BACKUP_ENDPOINT_URL must use https")
    return values


def build_service(values: dict[str, str], scratch: Path) -> OffsiteBackupService:
    manager = RestoreManager(
        str(scratch / "unused.sqlite3"),
        str(scratch / "restore"),
    )
    return OffsiteBackupService(
        bucket=values["OFFSITE_BACKUP_BUCKET"].strip(),
        prefix=values.get("OFFSITE_BACKUP_PREFIX", "3xui-bot").strip().strip("/"),
        region=values.get("OFFSITE_BACKUP_REGION", "us-east-1").strip() or "us-east-1",
        endpoint_url=values.get("OFFSITE_BACKUP_ENDPOINT_URL", "").strip().rstrip("/"),
        access_key_id=values["OFFSITE_BACKUP_ACCESS_KEY_ID"].strip(),
        secret_access_key=values["OFFSITE_BACKUP_SECRET_ACCESS_KEY"].strip(),
        keep=max(1, int(values.get("OFFSITE_BACKUP_KEEP", "14") or "14")),
        encryption_key_b64=values["OFFSITE_BACKUP_ENCRYPTION_KEY_B64"].strip(),
        restore_manager=manager,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download, decrypt and deep-verify the latest encrypted off-site Full Backup. "
            "The remote bucket/prefix/key are read only from a protected env file."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        required=True,
        help="Protected env file containing only OFFSITE_BACKUP_* credentials/settings.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Local .tar.gz destination for the verified Full Backup.",
    )
    args = parser.parse_args(argv)

    output = args.output.expanduser().resolve()
    if output.exists():
        print(f"refusing to overwrite existing file: {output}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)

    values = load_values(args.env_file.expanduser().resolve())
    with tempfile.TemporaryDirectory(prefix="offsite-recovery-") as tmp:
        service = build_service(values, Path(tmp))
        path = service.download_and_verify(output)

    os.chmod(path, 0o600)
    print(f"OFFSITE_RECOVERY_OK={path}")
    print("Next: inspect the archive, then use scripts/bootstrap-bot-from-backup.sh with the matching release tag.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
