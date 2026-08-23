# Health Tracker Bot

A private Telegram bot for simple weight and meal tracking. It is designed around large, familiar menu options so the user rarely needs to remember commands.

## What it does

- Logs weight in kilograms
- Estimates calories and macros from meal descriptions or photos
- Checks a food's estimated nutrition without saving it using `/check`, for example `/check kopi O`
- Lets each user set their own daily calorie target using the menu or `/target 1800`
- Sends optional per-user breakfast, lunch, and dinner reminders only when that meal has not been logged
- Always asks before saving an AI meal estimate
- Lets the user label each meal as breakfast, lunch, dinner, or snack before saving
- Shows today's meals, calories, protein, and weight
- Sends 30-day weight and calorie charts
- Safely confirms before removing the latest entry

The bot shows these persistent options:

`⚖️ Log weight` · `🍽️ Log meal` · `🔎 Check meal` · `📋 Today` · `📈 Progress` · `🎯 Calorie target` · `⏰ Reminders` · `↩️ Undo` · `❓ Help`

Each user can set breakfast, lunch, and dinner to a 24-hour reminder time or `None`. Times use the configured `TIMEZONE` (Asia/Singapore by default).

Opening a Telegram bot chat does not send it a message. The initial **Start** button sends `/start`, allowing the bot to greet the user and display its menu. Later, `/start` can reopen the main menu.

## Run locally

1. Create a bot with Telegram's **@BotFather** and copy its token.
2. Create an OpenAI API key.
3. Set up and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env, add both keys, and use SQLite for a local-only run:
# DATABASE_URL=sqlite:///health_tracker.db
python -m app.main
```

SQLite is the default, so no database setup is needed locally. To keep the bot private, set one or more numeric Telegram IDs in `ALLOWED_TELEGRAM_USER_IDS`, separated by commas. Each allowed account has completely separate records.

## Automated UGREEN / Docker deployment

Set these in `.env`:

```text
POSTGRES_PASSWORD=use-a-long-random-password
DATABASE_URL=postgresql+psycopg://health_tracker:use-a-long-random-password@db/health_tracker
```

The repository's GitHub Action builds an ARM64 image and publishes it to GitHub Container Registry. The UGREEN Compose project runs the bot, PostgreSQL, and a labeled automatic updater. PostgreSQL data is stored in the local `postgres-data` directory and is never included in the application image.

The “bot image” is the packaged Python application that Docker downloads and runs. It is not a profile picture or meal photo. It contains the code and Python dependencies, but it does not contain `.env`, API keys, passwords, or health records.

For the complete from-scratch Telegram, GitHub automation, and UGREEN NAS walkthrough, see [SETUP.md](SETUP.md).

## Privacy and limits

Meal nutrition is an estimate, especially from photos. The bot asks the user to confirm every estimate. Weight and meal data are stored in your configured database; meal photos are analyzed through the OpenAI API but are not stored locally by this application.
