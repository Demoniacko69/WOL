import os
from dataclasses import dataclass


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    port: int
    db_path: str
    default_broadcasts: list[str]
    enable_auth: bool
    auth_user: str
    auth_pass: str
    enable_rate_limit: bool
    rate_limit_requests: int
    rate_limit_window_seconds: int
    log_level: str



def load_settings() -> Settings:
    raw_broadcasts = os.getenv("DEFAULT_BROADCAST", "255.255.255.255")
    broadcasts = [x.strip() for x in raw_broadcasts.split(",") if x.strip()]
    if not broadcasts:
        broadcasts = ["255.255.255.255"]

    return Settings(
        port=int(os.getenv("PORT", "7070")),
        db_path=os.getenv("DB_PATH", "/data/devices.db"),
        default_broadcasts=broadcasts,
        enable_auth=parse_bool(os.getenv("ENABLE_AUTH", "false"), False),
        auth_user=os.getenv("AUTH_USER", ""),
        auth_pass=os.getenv("AUTH_PASS", ""),
        enable_rate_limit=parse_bool(os.getenv("ENABLE_RATE_LIMIT", "true"), True),
        rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "60")),
        rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
