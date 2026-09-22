from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


def csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(x.strip()) for x in value.split(",") if x.strip())


def csv_strings(value: str) -> tuple[str, ...]:
    return tuple(x.strip().lower() for x in value.split(",") if x.strip())


def csv_values(value: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in value.split(",") if x.strip())


def env_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class NodeBackupTarget:
    key: str
    node_name: str
    panel_url: str
    api_token: str
    verify_tls: bool


def _load_node_backup_targets() -> tuple[NodeBackupTarget, ...]:
    aliases = csv_values(os.getenv("NODE_BACKUP_TARGETS", ""))
    targets: list[NodeBackupTarget] = []
    for raw_alias in aliases:
        key = raw_alias.strip().upper()
        if not key or not key.replace("_", "").isalnum():
            raise RuntimeError(f"Invalid NODE_BACKUP_TARGETS alias: {raw_alias!r}")
        prefix = f"NODE_BACKUP_{key}_"
        node_name = os.getenv(prefix + "NODE_NAME", "").strip()
        panel_url = os.getenv(prefix + "PANEL_URL", "").strip().rstrip("/")
        api_token = os.getenv(prefix + "API_TOKEN", "").strip()
        missing = []
        if not node_name:
            missing.append(prefix + "NODE_NAME")
        if not panel_url:
            missing.append(prefix + "PANEL_URL")
        if not api_token:
            missing.append(prefix + "API_TOKEN")
        if missing:
            raise RuntimeError(
                f"Node backup target {key} is incomplete; missing: {', '.join(missing)}"
            )
        targets.append(
            NodeBackupTarget(
                key=key,
                node_name=node_name,
                panel_url=panel_url,
                api_token=api_token,
                verify_tls=env_bool(os.getenv(prefix + "VERIFY_TLS"), True),
            )
        )
    return tuple(targets)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    panel_url: str
    panel_api_token: str
    subscription_url_template: str
    compat_subscription_url_template: str
    subscription_proxy_host: str
    subscription_proxy_port: int
    allowed_telegram_ids: tuple[int, ...]
    admin_telegram_ids: tuple[int, ...]
    allowed_ports: tuple[int, ...]
    allowed_protocols: tuple[str, ...]
    inbound_ids: tuple[int, ...]
    ignored_tags: tuple[str, ...]
    ignored_protocols: tuple[str, ...]
    test_days: int
    test_traffic_gb: int
    test_ip_limit: int
    vless_flow: str
    db_path: str
    verify_tls: bool
    backup_enabled: bool
    backup_dir: str
    backup_keep: int
    backup_hour_utc: int
    backup_send_to_admins: bool
    node_backup_targets: tuple[NodeBackupTarget, ...]
    master_name: str
    master_flag: str


def load_settings() -> Settings:
    required = {
        "BOT_TOKEN": os.getenv("BOT_TOKEN"),
        "PANEL_URL": os.getenv("PANEL_URL"),
        "PANEL_API_TOKEN": os.getenv("PANEL_API_TOKEN"),
        "SUBSCRIPTION_URL_TEMPLATE": os.getenv("SUBSCRIPTION_URL_TEMPLATE"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    allowed_ids = csv_ints(os.getenv("ALLOWED_TELEGRAM_IDS", ""))
    admin_ids = csv_ints(os.getenv("ADMIN_TELEGRAM_IDS", ""))
    if not allowed_ids:
        raise RuntimeError("ALLOWED_TELEGRAM_IDS must not be empty.")
    if not admin_ids:
        raise RuntimeError("ADMIN_TELEGRAM_IDS must not be empty.")
    if "{sub_id}" not in required["SUBSCRIPTION_URL_TEMPLATE"]:
        raise RuntimeError("SUBSCRIPTION_URL_TEMPLATE must contain {sub_id}")

    compat_template = os.getenv("COMPAT_SUBSCRIPTION_URL_TEMPLATE", "").strip()
    if compat_template and "{sub_id}" not in compat_template:
        raise RuntimeError("COMPAT_SUBSCRIPTION_URL_TEMPLATE must contain {sub_id}")

    return Settings(
        bot_token=required["BOT_TOKEN"],
        panel_url=required["PANEL_URL"].rstrip("/"),
        panel_api_token=required["PANEL_API_TOKEN"],
        subscription_url_template=required["SUBSCRIPTION_URL_TEMPLATE"],
        compat_subscription_url_template=compat_template,
        subscription_proxy_host=os.getenv("SUBSCRIPTION_PROXY_HOST", "0.0.0.0"),
        subscription_proxy_port=int(os.getenv("SUBSCRIPTION_PROXY_PORT", "8080")),
        allowed_telegram_ids=allowed_ids,
        admin_telegram_ids=admin_ids,
        allowed_ports=csv_ints(os.getenv("ALLOWED_PORTS", "2053,2083,443")),
        allowed_protocols=csv_strings(os.getenv("ALLOWED_PROTOCOLS", "vless,hysteria")),
        inbound_ids=csv_ints(os.getenv("INBOUND_IDS", "")),
        ignored_tags=csv_strings(os.getenv("IGNORED_TAGS", "api")),
        ignored_protocols=csv_strings(os.getenv("IGNORED_PROTOCOLS", "tunnel")),
        test_days=int(os.getenv("TEST_DAYS", "7")),
        test_traffic_gb=int(os.getenv("TEST_TRAFFIC_GB", "10")),
        test_ip_limit=int(os.getenv("TEST_IP_LIMIT", "2")),
        vless_flow=os.getenv("VLESS_FLOW", "xtls-rprx-vision").strip(),
        db_path=os.getenv("DB_PATH", "bot.sqlite3"),
        verify_tls=env_bool(os.getenv("VERIFY_TLS"), True),
        backup_enabled=env_bool(os.getenv("BACKUP_ENABLED"), True),
        backup_dir=os.getenv("BACKUP_DIR", "/app/data/backups"),
        backup_keep=max(1, int(os.getenv("BACKUP_KEEP", "14"))),
        backup_hour_utc=max(0, min(23, int(os.getenv("BACKUP_HOUR_UTC", "2")))),
        backup_send_to_admins=env_bool(os.getenv("BACKUP_SEND_TO_ADMINS"), False),
        node_backup_targets=_load_node_backup_targets(),
        master_name=os.getenv("MASTER_NAME", "Master").strip() or "Master",
        master_flag=os.getenv("MASTER_FLAG", "🇳🇱").strip() or "🇳🇱",
    )
