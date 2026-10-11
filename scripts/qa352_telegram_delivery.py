"""QA #352: one-message-at-a-time Telegram transport smoke, never production.

This operator-workstation utility requires a separate QA bot, a single private
/start chat, and an explicit acknowledgement for each of four messages.  It
does not import production settings, open the product database or run jobs.
Only sanitized, synthetic messages from the project's job-alert formatter
are sent. No token or private Telegram identifier is printed or committed.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time
from urllib import parse, request

# Direct execution (`python3 scripts/qa352_telegram_delivery.py`) puts only
# scripts/ on sys.path. Resolve project-local imports from this file location,
# independently of the operator workstation's current working directory.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from alert_job_incidents import job_incident_message, job_value

STATE_DIR = Path.home() / ".local" / "state" / "3xui-qa352-delivery"
STATE_FILE = "qa352.sqlite3"
EXPIRES_AFTER = 7 * 24 * 3600
TARGET = "qa.synthetic.job"
STARTED = 1_791_691_200
QA_MARK = "QA #352 — СИНТЕТИЧЕСКОЕ УВЕДОМЛЕНИЕ, НЕ АВАРИЯ\n\n"
ENROLL_PHRASE = "PRIVATE_QA352_CHAT_ONLY"
SEND_PHRASE = "SEND_ONE_QA352_MESSAGE"


class SafetyError(Exception):
    """An intentionally sanitized failure: never interpolate tokens or chat IDs."""


def message_for_step(step: int) -> str:
    first = job_value(1001, "failed", STARTED, STARTED + 12)
    second = job_value(1002, "failed", STARTED + 35, STARTED + 48)
    if step == 1:
        body = job_incident_message(TARGET, first, kind="new")
    elif step == 2:
        body = job_incident_message(
            TARGET, first, kind="reminder", original_first_seen=STARTED + 13,
        )
    elif step == 3:
        body = job_incident_message(TARGET, second, kind="new")
    elif step == 4:
        body = job_incident_message(
            TARGET, job_value(1003, "success", STARTED + 65, STARTED + 73),
            kind="recovery", previous_value=second,
        )
    else:
        raise SafetyError("Допустимы только четыре шага (1–4).")
    return QA_MARK + body


def _token_and_expected_username() -> tuple[str, str]:
    token = os.environ.get("QA352_BOT_TOKEN", "").strip()
    expected = os.environ.get("QA352_EXPECTED_BOT_USERNAME", "").strip().lstrip("@").lower()
    if not token or not expected or not re.fullmatch(r"[A-Za-z0-9_]+bot", expected):
        raise SafetyError("Нужны локальные QA352_BOT_TOKEN и QA352_EXPECTED_BOT_USERNAME.")
    if not re.search(r"qa|test", expected, flags=re.IGNORECASE):
        raise SafetyError("Username должен однозначно обозначать отдельного QA/test бота.")
    if token == os.environ.get("BOT_TOKEN", ""):
        raise SafetyError("QA token не должен совпадать с BOT_TOKEN.")
    return token, expected


def telegram_call(token: str, method: str, values: dict | None = None) -> object:
    """Single HTTPS request, no retry; do not disclose token-bearing API URL."""
    if method not in {"getMe", "getWebhookInfo", "getUpdates", "sendMessage"}:
        raise SafetyError("Запрещённая Telegram операция.")
    body = parse.urlencode(values or {}).encode("utf-8")
    url = "https://api.telegram.org/bot" + token + "/" + method
    req = request.Request(url, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded",
    }, method="POST")
    try:
        with request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read(65536).decode("utf-8"))
    except Exception:
        # urllib errors contain the token in their URL; never print/rethrow them.
        raise SafetyError("Telegram API недоступен или исход запроса неизвестен.") from None
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise SafetyError("Telegram API не подтвердил результат запроса.")
    return payload.get("result")


def _identified_bot(token: str, expected: str) -> dict:
    me = telegram_call(token, "getMe")
    if (
        not isinstance(me, dict) or me.get("is_bot") is not True
        or str(me.get("username", "")).lower() != expected
        or not isinstance(me.get("id"), int) or me["id"] <= 0
    ):
        raise SafetyError("QA-бот не совпадает с ожидаемым username.")
    return me


def _open_store() -> sqlite3.Connection:
    parent = STATE_DIR
    # Local, restricted operator state. No arbitrary DB path arguments.
    if parent.is_symlink():
        raise SafetyError("Каталог QA state не должен быть symlink.")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise SafetyError("Каталог QA state должен иметь права 0700.")
    dbpath = parent / STATE_FILE
    if dbpath.is_symlink():
        raise SafetyError("QA state DB не должен быть symlink.")
    if not dbpath.exists():
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(dbpath, flags, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
    if not dbpath.is_file() or stat.S_IMODE(dbpath.stat().st_mode) & 0o077:
        raise SafetyError("QA state DB должен иметь права 0600.")
    conn = sqlite3.connect(dbpath, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS qa_session ("
        "id INTEGER PRIMARY KEY CHECK(id=1), bot_id INTEGER NOT NULL, "
        "username TEXT NOT NULL, chat_id INTEGER NOT NULL, "
        "step INTEGER NOT NULL, phase TEXT NOT NULL, message_id INTEGER, "
        "expires_at INTEGER NOT NULL)"
    )
    conn.commit()
    return conn


def _session(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM qa_session WHERE id=1").fetchone()
    if row is None or int(row["expires_at"]) <= int(time.time()):
        raise SafetyError("Сначала выполните регистрацию QA-чата; возможно, сессия истекла.")
    return row


def enroll(confirm: str) -> None:
    if confirm != ENROLL_PHRASE:
        raise SafetyError("Нет явного подтверждения приватной QA-регистрации.")
    token, expected = _token_and_expected_username()
    me = _identified_bot(token, expected)
    hook = telegram_call(token, "getWebhookInfo")
    if not isinstance(hook, dict) or hook.get("url"):
        raise SafetyError("QA-бот уже использует webhook; регистрация остановлена.")
    updates = telegram_call(token, "getUpdates", {
        "limit": "100", "timeout": "0", "allowed_updates": '["message"]',
    })
    if not isinstance(updates, list):
        raise SafetyError("Невозможно подтвердить приватное /start.")
    seen: set[int] = set()
    started: set[int] = set()
    for update in updates:
        message = update.get("message") if isinstance(update, dict) else None
        if not isinstance(message, dict):
            continue
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if (
            chat.get("type") != "private"
            or not isinstance(chat.get("id"), int)
            or sender.get("id") != chat.get("id")
            or sender.get("is_bot")
        ):
            raise SafetyError("В очереди QA-бота есть не-приватный или непроверенный чат.")
        chat_id = chat["id"]
        if chat_id <= 0:
            raise SafetyError("Неподходящий QA chat.")
        seen.add(chat_id)
        if str(message.get("text", "")).strip() == "/start":
            started.add(chat_id)
    if len(seen) != 1 or seen != started:
        raise SafetyError("Нужен ровно один приватный QA /start; повторите /start локально.")
    chat_id = next(iter(seen))
    with closing(_open_store()) as conn, conn:
        if conn.execute("SELECT 1 FROM qa_session").fetchone():
            raise SafetyError("QA-сессия уже зарегистрирована; автоматический reset запрещён.")
        conn.execute(
            "INSERT INTO qa_session VALUES (1,?,?,?,?,?,?,?)",
            (me["id"], expected, chat_id, 0, "confirmed", None,
             int(time.time()) + EXPIRES_AFTER),
        )
    print("QA private chat зарегистрирован (ID не выводится). Отправок: 0/4.")


def send_one(step: int, confirm: str) -> None:
    if confirm != SEND_PHRASE:
        raise SafetyError("Отправка требует явного подтверждения одного сообщения.")
    if step not in (1, 2, 3, 4):
        raise SafetyError("Допустимы только шаги 1–4.")
    token, expected = _token_and_expected_username()
    with closing(_open_store()) as conn, conn:
        row = _session(conn)
        if row["username"] != expected:
            raise SafetyError("Username отличается от закреплённого QA-бота.")
        if row["phase"] != "confirmed" or int(row["step"]) != step - 1:
            raise SafetyError("Нельзя повторить отправку или пропустить подтверждение.")
        me = _identified_bot(token, expected)
        if me["id"] != row["bot_id"]:
            raise SafetyError("QA-бот отличается от закреплённого Bot ID.")
        chat_id = int(row["chat_id"])
        bot_id = int(row["bot_id"])
        # Record attempted step before the external call. Unknown outcome cannot retry.
        conn.execute(
            "UPDATE qa_session SET step=?, phase='unknown', message_id=NULL WHERE id=1",
            (step,),
        )
    # Previous transaction is committed; ONE sendMessage and no automatic retry.
    answer = telegram_call(token, "sendMessage", {
        "chat_id": str(chat_id), "text": message_for_step(step),
        "disable_notification": "true", "protect_content": "true",
    })
    if (
        not isinstance(answer, dict)
        or not isinstance(answer.get("message_id"), int)
        or not isinstance(answer.get("chat"), dict)
        or answer["chat"].get("id") != chat_id
        or answer["chat"].get("type") != "private"
        or not isinstance(answer.get("from"), dict)
        or answer["from"].get("id") != bot_id
    ):
        raise SafetyError("Ответ Telegram не соответствует закреплённому приватному чату.")
    with closing(_open_store()) as conn, conn:
        row = _session(conn)
        if row["phase"] != "unknown" or row["step"] != step:
            raise SafetyError("Локальная сессия изменилась, автоматическое восстановление запрещено.")
        conn.execute(
            "UPDATE qa_session SET phase='api_accepted', message_id=? WHERE id=1",
            (answer["message_id"],),
        )
    print(f"Шаг {step}/4: Telegram API подтвердил запрос. "
          "Проверьте сообщение визуально и отдельно подтвердите получение.")


def confirm_observed(step: int, observed: str) -> None:
    if observed != "YES":
        raise SafetyError("Нужно явное визуальное подтверждение YES.")
    with closing(_open_store()) as conn, conn:
        row = _session(conn)
        if row["step"] != step or row["phase"] != "api_accepted":
            raise SafetyError("Нет ожидающего визуального подтверждения сообщения.")
        conn.execute("UPDATE qa_session SET phase='confirmed' WHERE id=1")
    print(f"Шаг {step}/4: визуальное получение подтверждено оператором.")


def status() -> None:
    with closing(_open_store()) as conn:
        row = _session(conn)
        print(f"QA transport: {row['step']}/4, phase={row['phase']}, "
              "token/chat ID не выводятся.")
        if row["phase"] == "unknown":
            print("UNKNOWN OUTCOME — НЕ ПОВТОРЯТЬ; остановиться и разобраться отдельно.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Isolated QA #352 Telegram transport smoke")
    cmds = parser.add_subparsers(dest="command", required=True)
    cmds.add_parser("preview", help="Без сети: показать четыре синтетических сообщения.")
    register = cmds.add_parser("enroll", help="Привязать один приватный /start чат, 0 send.")
    register.add_argument("--confirm", required=True)
    send = cmds.add_parser("send", help="Послать только ОДНО сообщение.")
    send.add_argument("step", type=int, choices=range(1, 5))
    send.add_argument("--confirm", required=True)
    ack = cmds.add_parser("confirm", help="Подтвердить визуальное получение.")
    ack.add_argument("step", type=int, choices=range(1, 5))
    ack.add_argument("--observed", required=True)
    cmds.add_parser("status", help="Локальный статус без ID/токена.")
    args = parser.parse_args(argv)
    try:
        if args.command == "preview":
            for step in range(1, 5):
                print(f"\n=== QA #{step}/4 (НЕ ОТПРАВЛЕНО) ===\n{message_for_step(step)}")
        elif args.command in {"enroll", "send"}:
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                raise SafetyError("Сетевые QA-команды нельзя выполнять от root.")
            if "/opt/3xui-bot/" in str(Path(__file__).resolve()):
                raise SafetyError("Запуск на production checkout запрещён; используйте workstation.")
            if args.command == "enroll":
                enroll(args.confirm)
            else:
                send_one(args.step, args.confirm)
        elif args.command == "confirm":
            confirm_observed(args.step, args.observed)
        else:
            status()
    except SafetyError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
