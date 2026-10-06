from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


class PrivateRotatingFileHandler(RotatingFileHandler):
    """Create active and rolled log files as owner-only."""

    def _open(self):
        fd = os.open(
            self.baseFilename,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT,
            0o600,
        )
        os.chmod(self.baseFilename, 0o600)
        return os.fdopen(fd, self.mode, encoding=self.encoding, errors=self.errors)


def _prepare_private_log_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    for candidate in path.parent.glob(f"{path.name}*"):
        if candidate.is_file() and not candidate.is_symlink():
            try:
                os.chmod(candidate, 0o600)
            except OSError:
                pass
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.close(fd)
    os.chmod(path, 0o600)


def bot_log_path() -> Path:
    db_path = Path(os.getenv("DB_PATH", "bot.sqlite3"))
    base = db_path.parent if str(db_path.parent) not in {"", "."} else Path("data")
    return base / "logs" / "bot.log"


def configure_logging() -> Path:
    """Keep Docker stdout logging and add a small on-disk rotating bot log."""
    path = bot_log_path()
    _prepare_private_log_path(path)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not any(getattr(h, "_xui_bot_console", False) for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console._xui_bot_console = True  # type: ignore[attr-defined]
        root.addHandler(console)

    if not any(getattr(h, "_xui_bot_file", False) for h in root.handlers):
        file_handler = PrivateRotatingFileHandler(
            path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler._xui_bot_file = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)

    return path
