import logging

from app.bot.bot import build_application
from app.config import settings
from app.db.database import init_db


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing. Copy .env.example to .env and add your token.")
    init_db()
    build_application().run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
