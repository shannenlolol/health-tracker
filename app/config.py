from dataclasses import dataclass, field
import os

from dotenv import load_dotenv


load_dotenv()


def positive_setting(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


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
    ai_text_per_minute: int = positive_setting("AI_TEXT_PER_MINUTE", 5)
    ai_text_per_day: int = positive_setting("AI_TEXT_PER_DAY", 50)
    ai_photo_per_minute: int = positive_setting("AI_PHOTO_PER_MINUTE", 3)
    ai_photo_per_day: int = positive_setting("AI_PHOTO_PER_DAY", 20)
    ai_global_per_day: int = positive_setting("AI_GLOBAL_PER_DAY", 300)
    ai_max_concurrent: int = positive_setting("AI_MAX_CONCURRENT", 3)
    message_limit: int = positive_setting("MESSAGE_LIMIT", 20)
    message_window_seconds: int = positive_setting("MESSAGE_WINDOW_SECONDS", 30)
    message_block_seconds: int = positive_setting("MESSAGE_BLOCK_SECONDS", 60)
    access_reply_seconds: int = positive_setting("ACCESS_REPLY_SECONDS", 600)
    access_request_cooldown_seconds: int = positive_setting("ACCESS_REQUEST_COOLDOWN_SECONDS", 300)
    access_requests_per_day: int = positive_setting("ACCESS_REQUESTS_PER_DAY", 3)
    access_requests_per_hour: int = positive_setting("ACCESS_REQUESTS_PER_HOUR", 10)
    access_pending_limit: int = positive_setting("ACCESS_PENDING_LIMIT", 25)
    access_expiry_days: int = positive_setting("ACCESS_EXPIRY_DAYS", 14)
    admin_alert_limit: int = positive_setting("ADMIN_ALERT_LIMIT", 5)
    admin_alert_window_seconds: int = positive_setting("ADMIN_ALERT_WINDOW_SECONDS", 600)
    meal_text_max_chars: int = positive_setting("MEAL_TEXT_MAX_CHARS", 300)
    meal_caption_max_chars: int = positive_setting("MEAL_CAPTION_MAX_CHARS", 200)
    telegram_messages_per_second: int = positive_setting("TELEGRAM_MESSAGES_PER_SECOND", 30)
    telegram_rate_limit_retries: int = positive_setting("TELEGRAM_RATE_LIMIT_RETRIES", 2)
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
