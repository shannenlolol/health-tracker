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

Create a Telegram bot with **@BotFather** and an OpenAI API key. With Python 3.12 installed, open a terminal in your copy of this repository.

Create and activate the environment (macOS/Linux):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

For Windows PowerShell, use:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` in your editor. Set both keys, switch to SQLite, and leave the admin ID empty until you know it:

```dotenv
TELEGRAM_BOT_TOKEN=YOUR_BOTFATHER_TOKEN
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
DATABASE_URL=sqlite:///health_tracker.db
ADMIN_TELEGRAM_USER_IDS=
ALLOWED_TELEGRAM_USER_IDS=
```

Start the bot:

```bash
python -m app.main
```

Send this in a private Telegram chat with your bot:

```text
/myid
```

Put the returned ID in `.env`:

```dotenv
ADMIN_TELEGRAM_USER_IDS=YOUR_NUMERIC_TELEGRAM_ID
```

Stop the local process with **Ctrl+C** and run the start command again. Press **Start** in Telegram to see **Manage users**. No database server is needed; each user's records are stored separately in SQLite. Access stays closed until an admin or approved user is configured.

## Run on a UGREEN NAS

Follow [SETUP.md](SETUP.md) to configure your own Telegram bot, OpenAI key, allowed users, and PostgreSQL database, then start using the bot. No application-code changes are needed.

The guide includes two ways to deploy and update your own copy:

- **Automatic:** GitHub Actions builds ARM64 and AMD64 images when application code is pushed to `main`; the NAS checks for and installs the new bot image approximately every five minutes.
- **Manual:** build on the NAS with `docker-compose.manual.yml`; upload your changed source and rebuild only when you want to install an update. GitHub Actions is optional.

Both keep health records in `postgres-data` on the NAS, separate from the bot container. The automatic workflow publishes to the GitHub repository owner's own container package.

## Manage users in Telegram

New users press **Start → Request access**. Admins receive **Approve / Reject** buttons and can open **Manage users** (or `/admin`) to review requests, list users, add IDs, and remove access. Changes take effect immediately without restarting.

Rejected requests are deleted, with no rejection history kept in the database. Removing access stops reminders and tracking but preserves health records. Rejected or removed users may request again. See [admin setup and migration](SETUP.md#5-set-up-the-admin-and-approve-users) for the one-time admin configuration and importing existing allowed IDs.

## Privacy and limits

Tracking, access requests, and admin controls work only in private chats.

Meal nutrition is an estimate, especially from photos. The bot asks the user to confirm every estimate. Weight and meal data are stored in your configured database; meal photos are analyzed through the OpenAI API but are not stored locally by this application.
