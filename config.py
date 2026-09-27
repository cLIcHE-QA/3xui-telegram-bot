from dataclasses import dataclass
import ipaddress
import os
import re
from urllib.parse import urlsplit
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
    node_id: int | None
    panel_url: str
    api_token: str
    verify_tls: bool


@dataclass(frozen=True)
class HostControlTarget:
    key: str
    name: str
    node_id: int | None
    host_id: str
    url: str
    token: str
    verify_tls: bool


_HOST_CONTROL_HOST_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


def _optional_positive_int(value: str | None, field: str) -> int | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{field} must be a positive integer.") from exc
    if parsed <= 0:
        raise RuntimeError(f"{field} must be a positive integer.")
    return parsed


def _private_http_host(hostname: str) -> bool:
    value = (hostname or "").strip().lower()
    if value == "localhost":
        return True
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    networks = (
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("fc00::/7"),
        ipaddress.ip_network("fe80::/10"),
    )
    return any(address in network for network in networks)


def _load_host_control_targets() -> tuple[HostControlTarget, ...]:
    aliases = csv_values(os.getenv("HOST_CONTROL_TARGETS", ""))
    targets: list[HostControlTarget] = []
    seen_host_ids: set[str] = set()
    seen_names: set[str] = set()
    seen_tokens: set[str] = set()
    seen_node_ids: set[int] = set()
    for raw_alias in aliases:
        key = raw_alias.strip().upper()
        if not key or not key.replace("_", "").isalnum():
            raise RuntimeError(f"Invalid HOST_CONTROL_TARGETS alias: {raw_alias!r}")
        prefix = f"HOST_CONTROL_{key}_"
        name = os.getenv(prefix + "NAME", "").strip()
        node_id = _optional_positive_int(os.getenv(prefix + "NODE_ID"), prefix + "NODE_ID")
        host_id = os.getenv(prefix + "HOST_ID", "").strip().lower()
        url = os.getenv(prefix + "URL", "").strip().rstrip("/")
        token = os.getenv(prefix + "TOKEN", "").strip()
        verify_tls = env_bool(os.getenv(prefix + "VERIFY_TLS"), True)

        missing = [
            field for field, value in (
                (prefix + "NAME", name),
                (prefix + "HOST_ID", host_id),
                (prefix + "URL", url),
                (prefix + "TOKEN", token),
            ) if not value
        ]
        if missing:
            raise RuntimeError(
                f"Host-control target {key} is incomplete; missing: {', '.join(missing)}"
            )
        if not (1 <= len(name) <= 64) or "\n" in name or "\r" in name:
            raise RuntimeError(f"{prefix}NAME must contain 1-64 characters on one line.")
        if key == "MASTER" and node_id is not None:
            raise RuntimeError(f"{prefix}NODE_ID is only valid for direct nodes.")
        if not _HOST_CONTROL_HOST_ID.fullmatch(host_id):
            raise RuntimeError(f"Invalid {prefix}HOST_ID.")
        if len(token) < 43:
            raise RuntimeError(f"{prefix}TOKEN is too short; use at least 32 random bytes.")

        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise RuntimeError(f"{prefix}URL must be an absolute http(s) URL.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RuntimeError(f"{prefix}URL must not contain credentials, query or fragment.")
        if parsed.scheme == "https" and not verify_tls:
            raise RuntimeError(f"{prefix}VERIFY_TLS=false is forbidden for host-control HTTPS.")
        if parsed.scheme == "http":
            if key != "MASTER":
                raise RuntimeError(f"{prefix}URL remote host-control targets require verified HTTPS.")
            if not _private_http_host(parsed.hostname):
                raise RuntimeError(f"{prefix}URL plain HTTP is allowed only for a private/local Master address.")

        folded_name = name.casefold()
        if host_id in seen_host_ids:
            raise RuntimeError(f"Duplicate host-control host_id: {host_id}")
        if folded_name in seen_names:
            raise RuntimeError(f"Duplicate host-control target name: {name}")
        if token in seen_tokens:
            raise RuntimeError("Host-control tokens must be unique per target.")
        if node_id is not None and node_id in seen_node_ids:
            raise RuntimeError(f"Duplicate host-control node_id: {node_id}")
        seen_host_ids.add(host_id)
        seen_names.add(folded_name)
        seen_tokens.add(token)
        if node_id is not None:
            seen_node_ids.add(node_id)
        targets.append(HostControlTarget(key, name, node_id, host_id, url, token, verify_tls))
    return tuple(targets)


def _load_node_backup_targets() -> tuple[NodeBackupTarget, ...]:
    aliases = csv_values(os.getenv("NODE_BACKUP_TARGETS", ""))
    targets: list[NodeBackupTarget] = []
    seen_node_ids: set[int] = set()
    for raw_alias in aliases:
        key = raw_alias.strip().upper()
        if not key or not key.replace("_", "").isalnum():
            raise RuntimeError(f"Invalid NODE_BACKUP_TARGETS alias: {raw_alias!r}")
        prefix = f"NODE_BACKUP_{key}_"
        node_name = os.getenv(prefix + "NODE_NAME", "").strip()
        node_id = _optional_positive_int(os.getenv(prefix + "NODE_ID"), prefix + "NODE_ID")
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
        if node_id is not None and node_id in seen_node_ids:
            raise RuntimeError(f"Duplicate node backup node_id: {node_id}")
        if node_id is not None:
            seen_node_ids.add(node_id)
        targets.append(
            NodeBackupTarget(
                key=key,
                node_name=node_name,
                node_id=node_id,
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
    offsite_backup_enabled: bool
    offsite_backup_bucket: str
    offsite_backup_prefix: str
    offsite_backup_region: str
    offsite_backup_endpoint_url: str
    offsite_backup_access_key_id: str
    offsite_backup_secret_access_key: str
    offsite_backup_keep: int
    offsite_backup_encryption_key_b64: str
    deploy_agent_enabled: bool
    deploy_agent_url: str
    deploy_agent_token: str
    cheburcheck_url: str
    cheburcheck_verify_tls: bool
    node_backup_targets: tuple[NodeBackupTarget, ...]
    host_control_targets: tuple[HostControlTarget, ...]
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

    offsite_enabled = env_bool(os.getenv("OFFSITE_BACKUP_ENABLED"), False)
    offsite_bucket = os.getenv("OFFSITE_BACKUP_BUCKET", "").strip()
    offsite_prefix = os.getenv("OFFSITE_BACKUP_PREFIX", "3xui-bot").strip().strip("/")
    offsite_region = os.getenv("OFFSITE_BACKUP_REGION", "us-east-1").strip() or "us-east-1"
    offsite_endpoint = os.getenv("OFFSITE_BACKUP_ENDPOINT_URL", "").strip().rstrip("/")
    offsite_access = os.getenv("OFFSITE_BACKUP_ACCESS_KEY_ID", "").strip()
    offsite_secret = os.getenv("OFFSITE_BACKUP_SECRET_ACCESS_KEY", "").strip()
    offsite_key = os.getenv("OFFSITE_BACKUP_ENCRYPTION_KEY_B64", "").strip()
    if offsite_enabled:
        missing_offsite = [
            name for name, value in (
                ("OFFSITE_BACKUP_BUCKET", offsite_bucket),
                ("OFFSITE_BACKUP_ACCESS_KEY_ID", offsite_access),
                ("OFFSITE_BACKUP_SECRET_ACCESS_KEY", offsite_secret),
                ("OFFSITE_BACKUP_ENCRYPTION_KEY_B64", offsite_key),
            ) if not value
        ]
        if missing_offsite:
            raise RuntimeError(
                "Off-site backup is enabled but variables are missing: "
                + ", ".join(missing_offsite)
            )
        if not offsite_prefix or any(part in {"", ".", ".."} for part in offsite_prefix.split("/")):
            raise RuntimeError("OFFSITE_BACKUP_PREFIX must contain safe non-empty path segments.")
        if offsite_endpoint:
            parsed_offsite = urlsplit(offsite_endpoint)
            if (
                parsed_offsite.scheme != "https"
                or not parsed_offsite.hostname
                or parsed_offsite.username
                or parsed_offsite.password
                or parsed_offsite.query
                or parsed_offsite.fragment
            ):
                raise RuntimeError(
                    "OFFSITE_BACKUP_ENDPOINT_URL must be an absolute verified HTTPS URL without credentials/query/fragment."
                )

    cheburcheck_url = os.getenv("CHEBURCHECK_URL", "").strip().rstrip("/")
    cheburcheck_verify_tls = env_bool(os.getenv("CHEBURCHECK_VERIFY_TLS"), True)
    if cheburcheck_url:
        parsed_cheburcheck = urlsplit(cheburcheck_url)
        if (
            parsed_cheburcheck.scheme not in {"http", "https"}
            or not parsed_cheburcheck.hostname
            or parsed_cheburcheck.username
            or parsed_cheburcheck.password
            or parsed_cheburcheck.query
            or parsed_cheburcheck.fragment
        ):
            raise RuntimeError(
                "CHEBURCHECK_URL must be an absolute http(s) URL without credentials/query/fragment."
            )
        if parsed_cheburcheck.scheme == "https" and not cheburcheck_verify_tls:
            raise RuntimeError("CHEBURCHECK_VERIFY_TLS=false is forbidden for HTTPS.")
        if (
            parsed_cheburcheck.scheme == "http"
            and "." in parsed_cheburcheck.hostname
            and not _private_http_host(parsed_cheburcheck.hostname)
        ):
            raise RuntimeError(
                "CHEBURCHECK_URL plain HTTP is allowed only for a private/local address or internal service name."
            )

    deploy_agent_url = os.getenv("DEPLOY_AGENT_URL", "").strip().rstrip("/")
    deploy_agent_token = os.getenv("DEPLOY_AGENT_TOKEN", "").strip()
    deploy_agent_enabled = bool(deploy_agent_url or deploy_agent_token)
    if deploy_agent_enabled:
        if not deploy_agent_url or not deploy_agent_token:
            raise RuntimeError(
                "DEPLOY_AGENT_URL and DEPLOY_AGENT_TOKEN must be configured together."
            )
        if len(deploy_agent_token) < 43:
            raise RuntimeError("DEPLOY_AGENT_TOKEN must contain at least 32 random bytes.")
        parsed_deploy = urlsplit(deploy_agent_url)
        if (
            parsed_deploy.scheme != "http"
            or not parsed_deploy.hostname
            or parsed_deploy.username
            or parsed_deploy.password
            or parsed_deploy.query
            or parsed_deploy.fragment
            or parsed_deploy.path not in {"", "/"}
            or not _private_http_host(parsed_deploy.hostname)
        ):
            raise RuntimeError(
                "DEPLOY_AGENT_URL must be private/local plain HTTP without credentials/path/query/fragment."
            )

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
        offsite_backup_enabled=offsite_enabled,
        offsite_backup_bucket=offsite_bucket,
        offsite_backup_prefix=offsite_prefix,
        offsite_backup_region=offsite_region,
        offsite_backup_endpoint_url=offsite_endpoint,
        offsite_backup_access_key_id=offsite_access,
        offsite_backup_secret_access_key=offsite_secret,
        offsite_backup_keep=max(1, int(os.getenv("OFFSITE_BACKUP_KEEP", "14"))),
        offsite_backup_encryption_key_b64=offsite_key,
        deploy_agent_enabled=deploy_agent_enabled,
        deploy_agent_url=deploy_agent_url,
        deploy_agent_token=deploy_agent_token,
        cheburcheck_url=cheburcheck_url,
        cheburcheck_verify_tls=cheburcheck_verify_tls,
        node_backup_targets=_load_node_backup_targets(),
        host_control_targets=_load_host_control_targets(),
        master_name=os.getenv("MASTER_NAME", "Master").strip() or "Master",
        master_flag=os.getenv("MASTER_FLAG", "🖥").strip() or "🖥",
    )
