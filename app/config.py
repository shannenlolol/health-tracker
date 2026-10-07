from dataclasses import dataclass, field
import os

from dotenv import load_dotenv


load_dotenv()


def parse_telegram_user_ids(*values: str | None, setting_name: str = "ALLOWED_TELEGRAM_USER_IDS") -> frozenset[int]:
    ids: set[int] = set()
    for value in values:
        if not value:
            continue
        for item in value.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                user_id = int(item)
            except ValueError as exc:
                raise ValueError(
                    f"{setting_name} must contain only numeric Telegram IDs separated by commas"
                ) from exc
            if not 0 < user_id < 2**63:
                raise ValueError("Telegram user IDs must be positive 64-bit integers")
            ids.add(user_id)
    return frozenset(ids)


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///health_tracker.db")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    timezone: str = os.getenv("TIMEZONE", "Asia/Singapore")
    daily_calorie_target: int = int(os.getenv("DAILY_CALORIE_TARGET", "2000"))
    admin_telegram_user_ids: frozenset[int] = field(
        default_factory=lambda: parse_telegram_user_ids(
            os.getenv("ADMIN_TELEGRAM_USER_IDS"), setting_name="ADMIN_TELEGRAM_USER_IDS"
        )
    )
    allowed_telegram_user_ids: frozenset[int] = field(
        default_factory=lambda: parse_telegram_user_ids(
            os.getenv("ALLOWED_TELEGRAM_USER_IDS"),
            os.getenv("ALLOWED_TELEGRAM_USER_ID"),
        )
    )


settings = Settings()
