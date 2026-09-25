from __future__ import annotations

from urllib.parse import urlsplit

from aiogram.fsm.state import State, StatesGroup


class AddNodeStates(StatesGroup):
    name = State()
    url = State()
    token = State()
    review = State()


def parse_node_url(raw: str) -> dict[str, object]:
    value = (raw or "").strip()
    if not value:
        raise ValueError("URL пустой")
    if "://" not in value:
        value = "https://" + value

    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("схема должна быть http или https")
    if parsed.username or parsed.password:
        raise ValueError("логин/пароль в URL не поддерживаются")
    if not parsed.hostname:
        raise ValueError("не найден адрес сервера")

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("некорректный порт") from exc

    base_path = parsed.path or "/"
    if not base_path.startswith("/"):
        base_path = "/" + base_path

    stripped = base_path.rstrip("/")
    if stripped.lower().endswith("/panel"):
        stripped = stripped[:-len("/panel")]
        base_path = stripped or "/"

    if not base_path.endswith("/"):
        base_path += "/"

    return {
        "scheme": scheme,
        "address": parsed.hostname,
        "port": int(port),
        "basePath": base_path,
    }


def node_mutation_payload(data: dict[str, object]) -> dict[str, object]:
    return {
        "id": 0,
        "name": str(data["name"]),
        "remark": "",
        "scheme": str(data["scheme"]),
        "address": str(data["address"]),
        "port": int(data["port"]),
        "basePath": str(data["basePath"]),
        "apiToken": str(data["apiToken"]),
        "clearApiToken": False,
        "enable": True,
        "allowPrivateAddress": False,
        "inboundSyncMode": "all",
        "inboundTags": [],
        "outboundTag": "",
        "pinnedCertSha256": "",
        "tlsVerifyMode": str(data.get("tlsVerifyMode") or "verify"),
    }
