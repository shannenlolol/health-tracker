# Setup guide

| I want to… | Use | Needs |
|---|---|---|
| Host the bot for myself or others | [Self-host on a server](#self-host-on-a-server) | A machine that runs Docker, a Telegram bot, an OpenAI API key |
| Change the code | [Develop from source](#develop-from-source) | Python 3.12 or newer |

## Self-host on a server

### What you need

- **Docker with Docker Compose** on a NAS, home server or cloud server
  - Intel/AMD (`x86_64`) or ARM (`aarch64`)
  - Built and tested on a UGREEN NAS
- **A Telegram bot token** and an **OpenAI API key** (step 2)
- **Internet access** on the server. No open ports or domain needed: the bot fetches messages from Telegram itself

### 1. Connect to your server

- Commands run **on the server**, over SSH from your computer's terminal (Terminal on macOS, PowerShell on Windows)
- Skip this step if you're working on the server directly

**a. Turn on SSH**
- UGREEN NAS: UGOS web interface → **Control Panel → Terminal** → tick **Enable SSH** → port **22** → Apply
- Other NAS systems: look under Terminal, Services or SSH
- Linux servers: usually on already

**b. Find the server's IP address** (looks like `192.168.x.x` or `10.0.x.x`)
- NAS web interface → **Control Panel → Network**
- Router admin page → connected devices
- Your computer must be on the same network; from elsewhere, use a VPN such as [Tailscale](https://tailscale.com/)

**c. Connect** with an **administrator** account (UGREEN only allows admins)

```bash
ssh your-username@192.168.1.50
```

- First time: asks whether you trust the server → type `yes`
- Password doesn't appear as you type (normal)
- `exit` to disconnect

| Message | Fix |
|---|---|
| `Connection refused` | SSH is off, or not on port 22 (`ssh -p <port> …`) |
| `Connection timed out` / `No route to host` | Wrong IP, or not on the same network |
| `Permission denied` | Wrong password, or not an administrator |

**d. Check Docker works**

```bash
docker ps        # "permission denied"? use: sudo docker ps
```

- Needed `sudo`? Put it in front of every `docker` command below too

### 2. Create the bot and API key

**a. Telegram bot**
- In Telegram, open [@BotFather](https://t.me/BotFather) → `/newbot` → choose a name and a username ending in `bot`
- Copy the **token** and keep it private
- `/setjoingroups` → your bot → **Disable** (the bot only works in private chats)
- Optional: `/mybots` → your bot → **Edit Bot** to add a description, profile picture and command list

**b. OpenAI API key**
- [OpenAI platform](https://platform.openai.com/) → set up billing → [API keys](https://platform.openai.com/api-keys) → create a key
- Project **Limits** → set a **hard monthly spending limit** (the bot's own limits can't cap your bill)
- One key pays for everyone's estimates

**c. Database password**
- Make up a long password using only letters and numbers
- It goes in `.env` twice: once for the database itself, and once in the address the bot logs in with

### 3. Start the bot

- Only [`docker-compose.yml`](../docker-compose.yml) and [`.env.example`](../.env.example) are needed; the image is downloaded ready-built
- The folder must be named `health-tracker` (Docker uses it as the project name)
- On UGREEN, apps usually live in `/volume1/docker`

```bash
cd /volume1/docker            # or wherever you keep your apps
mkdir health-tracker && cd health-tracker
curl -O https://raw.githubusercontent.com/shannenlolol/health-tracker/main/docker-compose.yml
curl -o .env https://raw.githubusercontent.com/shannenlolol/health-tracker/main/.env.example
nano .env                     # or vi; or edit it on your computer and upload it
```

- `mkdir` permission denied? → `sudo mkdir health-tracker`, then use `sudo` for the rest
- Fill in these lines in `.env`:

| Setting | Enter |
|---|---|
| `TELEGRAM_BOT_TOKEN` | The token from BotFather |
| `OPENAI_API_KEY` | Your OpenAI key |
| `POSTGRES_PASSWORD` | Your database password |
| `DATABASE_URL` | Replace `replace-with-the-generated-database-password` with the same password |
| `TIMEZONE` | Default timezone, e.g. `Asia/Singapore` (users can pick their own) |

Then start it:

```bash
docker compose pull
docker compose up -d
docker compose ps             # bot, db (healthy) and updater should be running
```

- Open your bot in Telegram and tap **Start**. It replies that access approvals aren't set up yet: that's next
- Records are kept in the `postgres-data` folder beside the Compose file. Never delete it

**Using a NAS Docker app instead?** (e.g. UGREEN **Docker → Project → Create**)
- Put `docker-compose.yml` and `.env` in the project folder, and point the project at that folder
- Use SSH for the other steps if the app can't read `.env`

### 4. Make yourself an admin

- Send `/myid` to your bot → copy the number
- In `.env`: `ADMIN_TELEGRAM_USER_IDS=123456789` (comma-separate several admins)
- Apply it:

```bash
docker compose up -d --force-recreate bot
```

- Send `/start` → **👥 Manage users** appears
- Share `https://t.me/your_bot_username`; people tap **Request access** and you approve them in Telegram ([user guide](user-guide.md#for-admins))

### 5. Check the settings

All in `.env`, each explained by a comment there. Apply changes with `docker compose up -d --force-recreate bot`.

| Setting | Default | Change it when |
|---|---|---|
| `BOT_IMAGE` | `…:1.0` (1.0.x bug fixes, installed automatically) | You want every change → `…:latest`; nothing to change, ever → `…:1.0.0`; a new version → `…:1.1` |
| `DAILY_CALORIE_TARGET` | `2000` | You want a different starting target (users can change their own) |
| `AI_*_PER_DAY`, `AI_GLOBAL_PER_DAY` | 50 typed, 20 photo per person; 300 in total | Estimates run out too soon, or cost too much |
| `ACCESS_*` | 3 requests per person a day, 25 pending | You expect many sign-ups |

- Daily estimate limits reset at midnight in `TIMEZONE`
- Run only one copy of the bot per database and per bot token

### 6. Keep it up to date

- The `updater` (Watchtower) checks for a new image every 5 minutes and installs it
- `BOT_IMAGE` decides what you get: `1.0` → bug fixes only; `latest` → every change merged into this repository, unreviewed by you
- New versions are listed on the [Releases page](https://github.com/shannenlolol/health-tracker/releases)
- The updater itself is pinned and never updates itself (it controls Docker). When a new `docker-compose.yml` is published: download it again → `docker compose up -d`
- Update by hand instead: `docker compose pull && docker compose up -d`

### Back up

```bash
docker compose exec -T db pg_dump -U health_tracker -d health_tracker -Fc > health-tracker-$(date +%F).backup
```

- Copy the `.backup` file and `.env` somewhere off the server
- Restore a backup into a spare database now and then to prove it works

### Roll back

- Set `BOT_IMAGE` to an earlier version → `docker compose up -d`
  - A release: `ghcr.io/shannenlolol/health-tracker:1.0.0`
  - Any earlier build: its full commit ID as the tag (GitHub → **Actions → Publish bot container**)
- Records are safe: newer versions only add tables, which older versions ignore

### Look at the database

**In a browser (Adminer)**: included, but only runs when you start it

```bash
docker compose --profile adminer up -d adminer     # start
docker compose stop adminer                        # stop when you're done
```

- Open `http://<server-ip>:8080` → System **PostgreSQL**, Server **`db`**, Username **`health_tracker`**, your `POSTGRES_PASSWORD`, Database **`health_tracker`**
- It can edit and delete records, and anyone on your network with the password can log in: keep it stopped, never forward port 8080
- Port 8080 taken? Change the **left** `8080` in `docker-compose.yml`

**On the command line**

```bash
docker compose exec db psql -U health_tracker -d health_tracker
```

- `\dt` lists tables, `\q` quits
- Times are stored in UTC
- Manage access in Telegram, not by editing tables

## Develop from source

```bash
git clone https://github.com/shannenlolol/health-tracker.git
cd health-tracker
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env             # then fill it in (see below)
python -m app.main
```

- In `.env`, use a **separate test bot token** (never your server's), `DATABASE_URL=sqlite:///health_tracker.db`, and your ID in `ADMIN_TELEGRAM_USER_IDS`
- Records go into `health_tracker.db`; no PostgreSQL needed
- Stop with Ctrl+C

### Run the tests

```bash
python -m pytest
python -m ruff check app tests
```

- In-memory database, Telegram and OpenAI mocked: never touches a server, a real bot or your OpenAI account
- Both run on every push and pull request; images are only published when they pass

### Build the Docker image yourself

```bash
docker compose -f docker-compose.manual.yml up -d --build
```

- Builds from the `Dockerfile` instead of downloading the published image; no `updater`
- Add `-f docker-compose.manual.yml` to every `docker compose` command

### Deploy your own fork

- Fork → **Actions** → enable workflows → run **Publish bot container** on `main`
- Publishes to `ghcr.io/<your-username>/health-tracker`
- Can't download it? GitHub profile → **Packages** → the package → **Package settings** → make it public
- Server's `.env` → `BOT_IMAGE=ghcr.io/<your-username>/health-tracker:latest` (all lowercase)
- Each merge to `main` that passes the tests is then built and, with the updater, deployed
- Bring in this repository's changes with **Sync fork** on GitHub

## Releasing

```bash
git tag v1.1.0
git push origin v1.1.0
```

- Or GitHub → **Releases → Draft a new release** (lets you add notes)
- GitHub Actions builds for Intel and ARM and publishes `1.1.0` and `1.1`
- `latest` follows `main`, not releases
- Bump the last number for fixes (`v1.1.1`), the middle for features (`v1.2.0`), the first when people must change their setup (`v2.0.0`)

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot doesn't reply | `docker compose logs bot`; check the token and the server's internet access |
| "Access approvals are not configured" | Set `ADMIN_TELEGRAM_USER_IDS` → `docker compose up -d --force-recreate bot` |
| 👥 Manage users is missing | `/myid` must match `ADMIN_TELEGRAM_USER_IDS`; recreate the bot, then `/start` |
| A setting didn't change | Use `--force-recreate bot`; a plain restart doesn't reread `.env` |
| `docker compose pull` says **denied** | Image is private (forks) → make the package public |
| Database won't start | `docker compose logs db`; check `POSTGRES_PASSWORD`. Never delete `postgres-data` to "reset" it |
| Meal estimates fail | OpenAI key, billing and spending limit; `docker compose logs bot` |
| Reminders don't arrive | The user's `/timezone`, the reminder time, their access, and whether that meal is already logged |
| `Conflict` errors in the logs | Two copies use the same bot token → stop one |
| No access-request messages | Each admin must have tapped **Start**; check **Manage users → Pending requests** |
| Changed `POSTGRES_PASSWORD` and now the bot can't connect | The database keeps its first password; change it back |
