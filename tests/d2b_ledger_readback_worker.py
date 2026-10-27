"""Синтетический read-only read-back D2b ledger из нового isolated Python процесса.

Аргументы — только путь к ephemeral тестовой БД и SHA-256 тестового challenge.
Не принимает и не выдаёт browser cookies, private Telegram token или sub_id.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from subscription_page_standalone_sqlite import StandaloneSQLiteLedger


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(2)
    digest_hex = sys.argv[2]
    if len(digest_hex) != 64:
        raise SystemExit(2)
    digest = bytes.fromhex(digest_hex)
    row = StandaloneSQLiteLedger(sys.argv[1], https_origin=sys.argv[4]).pending(
        digest, current=float(sys.argv[3]),
    )
    print("PENDING" if row is not None else "ABSENT")


if __name__ == "__main__":
    main()
