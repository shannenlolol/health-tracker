# Set up Health Tracker Bot on a UGREEN NAS

Configure your own Telegram bot, OpenAI key, and database, then start using the bot. No application-code changes are required.

## 1. Prepare your NAS

You need a UGREEN NAS that supports Docker, a computer, and internet access.

1. In UGOS **App Center**, install **Docker**.
2. In **File Manager**, create a folder such as `Docker/health-tracker`.

Keep the NAS running so the bot can respond. UGOS menu names may vary by firmware.

## 2. Create your connections

### Telegram

Open the verified [@BotFather](https://t.me/BotFather) account and send:

```text
/newbot
```

Choose a name and a unique username ending in `bot`. Save the returned token privately.

To keep the bot out of group chats, send the following, select your bot, and choose **Disable**:

```text
/setjoingroups
```

### OpenAI

Sign in to the [OpenAI API platform](https://platform.openai.com/), select or create a project, enable API billing, and create a key on the [API keys page](https://platform.openai.com/api-keys). Save the key privately.

Your key covers meal estimates for all users. Meal descriptions and photos are sent to OpenAI for analysis.

### Database

Use a password manager to generate a long random password containing only letters and numbers. You will paste the same password into both database settings below. PostgreSQL runs on your NAS; no separate database account is needed.

## 3. Download and configure

On the repository page, choose **Code → Download ZIP** and extract it on your computer, or follow the [Git clone instructions in the README](README.md#get-the-code). For automatic deployment, fork the repository first and clone your own copy.

Copy `.env.example` to a plain-text file named `.env`, then fill in your values:

```dotenv
TELEGRAM_BOT_TOKEN=YOUR_BOTFATHER_TOKEN
OPENAI_API_KEY=YOUR_OPENAI_API_KEY

# Used only by the automatic method in section 4.
BOT_IMAGE=ghcr.io/your-github-owner/your-repository:latest

POSTGRES_PASSWORD=YOUR_DATABASE_PASSWORD
DATABASE_URL=postgresql+psycopg://health_tracker:YOUR_DATABASE_PASSWORD@db/health_tracker

OPENAI_MODEL=gpt-4.1-mini
TIMEZONE=Asia/Singapore
DAILY_CALORIE_TARGET=2000
ADMIN_TELEGRAM_USER_IDS=
ALLOWED_TELEGRAM_USER_IDS=
```

- Use the same database password twice. Keep `health_tracker` and `db` as shown.
- Set your timezone. All users share it for reminders and daily totals.
- Leave the two Telegram ID settings empty for the first start if you don't know your ID. Access stays closed while you complete admin setup in section 5.
- If you already know your numeric Telegram ID, set `ADMIN_TELEGRAM_USER_IDS` now. Multiple admins can be separated by commas.

Keep `.env` private and out of GitHub. Ensure the filename is `.env`, not `.env.txt`.

## 4. Choose how to install and update

| | Method 1: Manual | Method 2: Automatic |
| --- | --- | --- |
| Build | Docker builds on your NAS | GitHub Actions builds your code |
| Updates go live | When you upload changes and rebuild | After a matching push to `main` and the NAS updater's next check |
| GitHub account | Not required | Required, with your own repository and package |
| Compose file | `docker-compose.manual.yml` | `docker-compose.yml` |
| Services | `bot`, `db` | `bot`, `db`, `updater` |

Follow **one method**, then complete section 5. Choose manual if you just want to run the code without GitHub automation.

### Method 1: Manual

#### Install

Upload these files into your NAS `health-tracker` folder, including the hidden files:

```text
app/                         (the entire folder)
Dockerfile
.dockerignore
requirements.txt
docker-compose.manual.yml
.env
```

In UGOS **Docker → Projects/Compose**, create a project named `health-tracker`. Select `docker-compose.manual.yml`, use its folder as the working directory, and select `.env` if asked. Choose **Build and start**.

If UGOS cannot build the project, use the SSH instructions below and run:

```bash
docker compose -p health-tracker -f docker-compose.manual.yml up -d --build
```

#### Update your code later

Edit and test your code, then upload the changed source into the same NAS folder. Remove obsolete source files, but preserve `.env` and `postgres-data`.

From that folder over SSH, run this single command to build and replace the bot:

```bash
docker compose -p health-tracker -f docker-compose.manual.yml up -d --build --no-deps bot
```

The database stays running. Uploading files or restarting the container alone does not install code changes.

### Method 2: Automatic

#### Set up GitHub

1. **Fork** the source repository into your GitHub account. If forking is unavailable, create your own repository and upload the source, including `.github/workflows/publish-container.yml`. Exclude `.env` and records.
2. In your repository, open **Actions** and enable workflows if prompted.
3. Select **Publish bot container → Run workflow**, choose `main`, and wait for success.
4. Open your GitHub profile or organization → **Packages** → the new package → **Package settings**, and change visibility to **Public**.

The workflow publishes ARM64 and AMD64 images under your own repository name. A public package lets the NAS download the image without GitHub credentials. Its application code is downloadable by anyone; your `.env` and records are excluded. Use Method 1 if the packaged code must remain private.

#### Install on the NAS

In your `.env`, set your own GitHub owner and repository, all lowercase:

```dotenv
BOT_IMAGE=ghcr.io/your-github-owner/your-repository:latest
```

Upload `docker-compose.yml` and `.env` into your NAS `health-tracker` folder.

In UGOS **Docker → Projects/Compose**, create a project named `health-tracker`. Select `docker-compose.yml`, use its folder as the working directory, select `.env` if asked, and choose **Deploy/Start**.

The updater checks approximately every five minutes and updates only the bot. PostgreSQL records stay in `postgres-data`. The updater has access to the NAS's Docker socket to replace containers.

#### Update your code later

Use GitHub Desktop to clone **your own repository** to your computer. Edit and test your code, review the changed files, then **Commit to main → Push origin**. If using another branch, merge it into `main`.

GitHub builds the image, then the NAS installs it automatically. Check that the workflow succeeds and the bot responds afterward.

Changes to `app/`, `Dockerfile`, `.dockerignore`, `requirements.txt`, or the publishing workflow trigger builds. Documentation changes do not. Changes to `.env` or Compose must be applied on the NAS separately; see section 6.

### SSH access for terminal commands

Only needed when a step asks you to run a command on the NAS.

Enable SSH in the NAS control panel. Open Terminal or PowerShell on your computer and connect using your NAS username and local IP:

```bash
ssh YOUR_NAS_USERNAME@YOUR_NAS_LOCAL_IP
```

Copy the full filesystem path of your project folder from NAS File Manager, then enter it:

```bash
cd "/full/path/to/your/health-tracker"
```

Replace the example path with your own. Run the relevant Docker command from this folder. If permission is denied, use an authorized NAS administrator account and prefix the command with `sudo`.

## 5. Set up the admin and approve users

### One-time admin setup

Start the Docker project, open a private chat with your bot, and send:

```text
/myid
```

Copy the returned ID into the NAS `.env`:

```dotenv
ADMIN_TELEGRAM_USER_IDS=YOUR_NUMERIC_TELEGRAM_ID
```

Recreate the bot using section 6, then press **Start**. You will see **👥 Manage users**. Each configured admin should start a private chat so the bot can send approval requests to them.

### Add and manage users from your phone

1. Share your bot's username with an intended user.
2. They press **Start → Request access**.
3. You receive their name, username (if available), and numeric ID with **Approve / Reject** buttons.
4. **Approve** immediately gives them the menu. **Reject** notifies them and deletes the pending request; the database keeps no rejection history.

Open **Manage users** to review pending requests, list allowed users, add someone by numeric ID, or remove access with confirmation. You can also open the menu with:

```text
/admin
```

Removing access stops tracking and reminders but keeps health records. Configured admins cannot be removed through this menu. Rejected or removed people may request again; a five-minute in-memory cooldown limits repeat requests and resets when the bot restarts. Manually added users must start the bot before it can message them.

Routine user management needs no `.env` edits or restart. If a notification fails, the request remains in **Pending requests**.

### Upgrading an existing installation

Back up first. At the first configured startup, the bot creates the access tables and imports only IDs explicitly listed in `ALLOWED_TELEGRAM_USER_IDS` (or the older singular setting). This happens once; restarting won't restore users you removed. Existing health records alone do not grant access. Subsequent access changes happen in **Manage users**, not the legacy environment setting.

Set your admin ID as above. Existing imported users can still use the bot before an admin is configured, but new requests require an admin. An empty allowlist no longer permits everyone.

### Check the bot

Confirm `db` is healthy and `bot` is running in UGOS. The automatic method also needs `updater` running.

In a private Telegram chat, log a weight or meal and open **Today**. Have another account request access and verify approval from your phone.

Run only one copy per bot token. Use a separate bot token when testing code while your NAS bot stays online.

## 6. Apply configuration changes

After editing the NAS `.env`, recreate the bot. From the NAS project folder over SSH, run **only the command for your method**.

**Method 1 — Manual:**

```bash
docker compose -p health-tracker -f docker-compose.manual.yml up -d --no-deps --force-recreate bot
```

**Method 2 — Automatic:**

```bash
docker compose -p health-tracker -f docker-compose.yml up -d --no-deps --force-recreate bot
```

A plain restart does not reload `.env`. Changing the database password also requires changing it inside PostgreSQL; editing `.env` alone is insufficient once the database exists.

## 7. Keep your records safe

Records live in `postgres-data` beside the Compose file. Preserve this folder and `.env` when updating. Do not run both installation methods against the same database folder simultaneously.

To create a database backup, run from the NAS project folder. For the automatic method, replace `docker-compose.manual.yml` with `docker-compose.yml`:

```bash
docker compose -p health-tracker -f docker-compose.manual.yml exec -T db pg_dump -U health_tracker -d health_tracker -Fc > health-tracker.backup
```

Copy the backup to a secure location away from the NAS. Use a new filename for each backup you want to retain.
