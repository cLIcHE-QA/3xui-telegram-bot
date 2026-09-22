from __future__ import annotations

import os
import sys

from restore_manager import RestoreManager


def main() -> None:
    db_path = os.getenv("DB_PATH", "/app/data/bot.sqlite3")
    backup_dir = os.getenv("BACKUP_DIR", "/app/data/backups")
    manager = RestoreManager(db_path, backup_dir)
    try:
        manager.perform_pending_bot_restore()
    except Exception as exc:
        # Never keep the container down solely because the restore helper failed.
        # perform_pending_bot_restore normally converts failures into a result file.
        print(f"restore bootstrap warning: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    os.execv(sys.executable, [sys.executable, "/app/bot.py"])


if __name__ == "__main__":
    main()
