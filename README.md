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
3. With Python 3.12 installed, open a terminal in your downloaded repository folder and run (macOS/Linux):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env, add both keys, and use SQLite for a local-only run:
# DATABASE_URL=sqlite:///health_tracker.db
python -m app.main
```

For Windows PowerShell, activate the environment with `.\.venv\Scripts\Activate.ps1`. The example environment file is configured for the NAS, so replace its `DATABASE_URL` with the SQLite value shown above for a local run. No database server is needed locally. To keep the bot private, set one or more numeric Telegram IDs in `ALLOWED_TELEGRAM_USER_IDS`, separated by commas. Each allowed account has completely separate records.

## Run on a UGREEN NAS

Follow [SETUP.md](SETUP.md) to configure your own Telegram bot, OpenAI key, allowed users, and PostgreSQL database, then start using the bot. No application-code changes are needed.

The guide includes two ways to deploy and update your own copy:

- **Automatic:** GitHub Actions builds ARM64 and AMD64 images when application code is pushed to `main`; the NAS checks for and installs the new bot image approximately every five minutes.
- **Manual:** build on the NAS with `docker-compose.manual.yml`; upload your changed source and rebuild only when you want to install an update. GitHub Actions is optional.

Both keep health records in `postgres-data` on the NAS, separate from the bot container. The automatic workflow publishes to the GitHub repository owner's own container package.

## Privacy and limits

Use the bot in one-to-one chats: the current code does not block group chats, where replies could expose your records to other participants.

Meal nutrition is an estimate, especially from photos. The bot asks the user to confirm every estimate. Weight and meal data are stored in your configured database; meal photos are analyzed through the OpenAI API but are not stored locally by this application.
