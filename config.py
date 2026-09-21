from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

def _csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(x.strip()) for x in value.split(",") if x.strip())

def _csv_strings(value: str) -> tuple[str, ...]:
    return tuple(x.strip().lower() for x in value.split(",") if x.strip())

def _bool(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    bot_token: str
    panel_url: str
    panel_api_token: str
    subscription_url_template: str
    allowed_telegram_ids: tuple[int, ...]
    inbound_ids: tuple[int, ...]
    allowed_protocols: tuple[str, ...]
    test_days: int
    test_traffic_gb: int
    test_ip_limit: int
    db_path: str
    verify_tls: bool

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

    allowed_ids = _csv_ints(os.getenv("ALLOWED_TELEGRAM_IDS", ""))
    if not allowed_ids:
        raise RuntimeError(
            "ALLOWED_TELEGRAM_IDS is empty. For test mode, explicitly whitelist Telegram IDs."
        )

    template = required["SUBSCRIPTION_URL_TEMPLATE"]
    if "{sub_id}" not in template:
        raise RuntimeError("SUBSCRIPTION_URL_TEMPLATE must contain {sub_id}")

    return Settings(
        bot_token=required["BOT_TOKEN"],
        panel_url=required["PANEL_URL"].rstrip("/"),
        panel_api_token=required["PANEL_API_TOKEN"],
        subscription_url_template=template,
        allowed_telegram_ids=allowed_ids,
        inbound_ids=_csv_ints(os.getenv("INBOUND_IDS", "")),
        allowed_protocols=_csv_strings(
            os.getenv(
                "ALLOWED_PROTOCOLS",
                "vless,vmess,trojan,shadowsocks,hysteria,mtproto",
            )
        ),
        test_days=int(os.getenv("TEST_DAYS", "7")),
        test_traffic_gb=int(os.getenv("TEST_TRAFFIC_GB", "10")),
        test_ip_limit=int(os.getenv("TEST_IP_LIMIT", "2")),
        db_path=os.getenv("DB_PATH", "bot.sqlite3"),
        verify_tls=_bool(os.getenv("VERIFY_TLS"), True),
    )
