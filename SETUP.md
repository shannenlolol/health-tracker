# Set up your bot on a UGREEN NAS

This guide gets your own private Telegram bot running on your NAS, with a local PostgreSQL database and access approvals in Telegram. No application-code changes are needed.

Use a computer for setup. Once the containers are running, you can close the terminal and switch off the computer.

## Before you begin

You need:

- A UGREEN NAS with Docker support, storage set up, and internet access.
- A NAS administrator account and a computer on the same local network.
- Telegram and an OpenAI API account for meal estimates.
- A text editor for one configuration file.

## 1. Prepare the NAS

### 1a. Install Docker

**1a(i)** Sign in to the UGOS web interface as an administrator.

**1a(ii)** Open **App Center**, find **Docker**, and ensure it is installed.
![Installing Docker](<assets/images/install docker.png>)


**1a(iii)** Choose a storage location (eg. Volume 1), then open Docker.


### 1b. Create the project folder

**1b(i)** Open **Files** (File Manager) → **Shared Folder → docker**.

**1b(ii)** Create a folder named `health-tracker`. Keep all project files together in this folder.


### 1c. Find your NAS IP address

**1c(i)** Open **Control Panel → Network → Network connection**.

**1c(ii)** Find the connected LAN interface and note its IPv4 address.

**1c(iii)** Keep this address handy for SSH in section 4. Use your own address, not the one in the screenshot.

![UGOS Network connection tab showing where to find the NAS IP address](<assets/images/finding IP.png>)

The supplied Compose files need no router port forwarding or public database port. The bot connects outward to Telegram using polling.

## 2. Create your bot and API key

### 2a. Telegram bot

**2a(i)** In Telegram, open the verified [@BotFather](https://t.me/BotFather).

![Bot Father](<assets/images/bot father.png>)

**2a(ii)** Send `/newbot`.

**2a(iii)** Enter a display name, then a unique username ending in `bot`.

**2a(iv)** Save the returned bot token privately. You will put it in `.env` below.

**2a(v)** Send `/setjoingroups`, select your bot, and choose **Disable**.

**2a(vi)** Save your bot's link, such as `https://t.me/YOUR_BOT_USERNAME`.


### 2b. OpenAI API key

**2b(i)** Sign in to the [OpenAI API platform](https://platform.openai.com/).

**2b(ii)** Select or create the project you want to use for this bot.

**2b(iii)** Open [API billing](https://platform.openai.com/settings/organization/billing/overview) and complete the billing or credits setup shown for your account.

**2b(iv)** Open [API keys](https://platform.openai.com/api-keys) and create a secret key.

**2b(v)** Copy the key to a private location for the next step.

The [official OpenAI quickstart](https://developers.openai.com/api/docs/quickstart) covers API keys and credits. This key is used for all users' meal estimates, including checks that are not saved.

### 2c. Database password

Generate a long random password using only letters and numbers. You will use it twice in `.env`. PostgreSQL runs inside Docker on your NAS; no hosted database account is required.

## 3. Download and configure the project

### 3a. Download the files

**3a(i)** On this repository's GitHub page, click **Code → Download ZIP**.

**3a(ii)** Extract the ZIP on your computer.

**3a(iii)** Open the extracted folder in your text editor.

**3a(iv)** Copy `.env.example` to a new file named exactly `.env`.

If hidden files are not visible, use **Command+Shift+.** in macOS Finder or **View → Show → Hidden items** in Windows File Explorer. 

### 3b. Fill in `.env`

Use the values below for the manual NAS installation. Replace the three credential placeholders; use the same database password in both places.

```dotenv
TELEGRAM_BOT_TOKEN=YOUR_BOTFATHER_TOKEN
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=gpt-4.1-mini

POSTGRES_PASSWORD=YOUR_DATABASE_PASSWORD
DATABASE_URL=postgresql+psycopg://health_tracker:YOUR_DATABASE_PASSWORD@db/health_tracker

ADMIN_TELEGRAM_USER_IDS=
ALLOWED_TELEGRAM_USER_IDS=

TIMEZONE=Asia/Singapore
DAILY_CALORIE_TARGET=2000
```

| Setting | What to enter |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | The token from BotFather. |
| `OPENAI_API_KEY` | Your secret API key. |
| `POSTGRES_PASSWORD` | Your generated database password. |
| `DATABASE_URL` | Replace only the password; keep `health_tracker` and `db` as shown. |
| `ADMIN_TELEGRAM_USER_IDS` | Leave blank until step 6, or enter your numeric ID if known. |
| `ALLOWED_TELEGRAM_USER_IDS` | Leave blank for a new installation; manage users in Telegram. |
| `TIMEZONE` | Your timezone, such as `Asia/Singapore`; shared by all users. |
| `DAILY_CALORIE_TARGET` | Initial target for new users. Users can change their own in Telegram. |

`BOT_IMAGE` in the example file is unused by the manual method. Keep `.env` private and out of GitHub. Leaving the access settings blank keeps tracking closed while you finish setup.

### 3c. Upload to the NAS

In UGOS **File Manager**, open your `health-tracker` folder and upload these items from the extracted project:

```text
health-tracker/
    ├── app/                         ← entire folder and its contents
    ├── Dockerfile
    ├── .dockerignore
    ├── requirements.txt
    ├── docker-compose.manual.yml
    └── .env
```
## 4. Connect to the NAS with SSH

SSH lets you run commands on the NAS from your computer. The commands below build and run the bot on the NAS itself.

### 4a. Enable SSH in UGOS

**4a(i)** Open **Control Panel → Terminal**.

**4a(ii)** Enable **SSH** and note its port, normally `22`.

**4a(iii)** Keep the security level at **High**; restrict access to your local network where available.

**4a(iv)** Click **Apply**.

See UGREEN's [SSH instructions](https://ai.ugreen.com/blogs/how-to/connect-nas-ssh-root-access) if your screen differs.

![UGOS Terminal settings with SSH enabled and the port displayed](<assets/images/enable SSH.png>)

*The screenshot has an automatic shutdown timer. If SSH stops accepting connections later, enable it again and click Apply.*

### 4b. Connect from your computer

**4b(i)** Open a terminal **on your computer**:

- **macOS:** press **Command+Space**, type `Terminal`, and press Enter.
- **Windows:** open **Start**, search for `PowerShell`, and open it.
- **Linux:** open your Terminal application.

**4b(ii)** Use your **UGREEN login username** and the NAS IP from section 1. The command format is `ssh <ugreen username>@<ip address>`; replace both placeholders and omit the angle brackets.

For example, if your NAS username were `alex` and its IP were `192.168.1.50`, you would enter:

```bash
ssh alex@192.168.1.50
```

For a custom port, add `-p` and the port you enabled, for example `ssh -p 2222 alex@192.168.1.50`.

**4b(iii)** On the first connection, confirm the address is your NAS. If the host confirmation prompt appears, type `yes` and press Enter.

**4b(iv)** Enter your **UGREEN account password** and press Enter. No characters appear while typing; this is normal.

**4b(v)** Wait for the NAS shell prompt. Commands you enter from here run on the NAS.

### 4c. Enter the project folder

**4c(i)** In UGOS **Files**, locate **Shared Folder → docker → health-tracker**. Check the folder's properties or path information for its full filesystem path. The breadcrumb alone is not a path you can paste into SSH.

**4c(ii)** In the **connected SSH terminal**, enter that directory. For a Docker shared folder on volume 1, the path may be:

```bash
cd "/volume1/docker/health-tracker"
```

Use your actual volume and folder name, including capitalization. If you get `No such file or directory`, check the full path in UGOS before continuing. Do not enter the `postgres-data` subfolder.

**4c(iii)** Check your current directory and its files:

```bash
pwd
ls -la
```

**Expected:** `pwd` prints your NAS project path; the list includes `app/`, `Dockerfile`, `.env`, and `docker-compose.manual.yml` for the manual installation.

## 5. Start the bot

### 5a. Build and start over SSH

**5a(i)** In your connected NAS terminal, after entering the project folder in section 4, run:

```bash
sudo docker compose -p health-tracker -f docker-compose.manual.yml up -d --build
```

**5a(ii)** Wait for the first build to finish; downloading dependencies may take several minutes. Then check:

```bash
sudo docker compose -p health-tracker -f docker-compose.manual.yml ps
```

### 5b. Where to click in UGOS

Open **Docker → Project → health-tracker → Container**, or **Docker → Container**, to find the bot and database. Open **Logs** in the project or the container's **Log** view to inspect startup messages.

![UGOS Docker project showing running health-tracker containers](<assets/images/docker.png>)

*Existing customized installation: this screenshot includes `updater` and `adminer`. The manual setup in this guide creates only `bot` and `db`; the automatic setup adds `updater`. Adminer is not included in the repository's Compose files. Section 8 uses the built-in PostgreSQL terminal to view records.*

If you prefer to deploy through the interface:

**5b(i)** Open **Docker → Project → Create**.

**5b(ii)** Enter `health-tracker` as the project name.

**5b(iii)** Set the project storage/working path to the folder you uploaded.

**5b(iv)** Import `docker-compose.manual.yml`, or paste its contents into the Compose editor.

**5b(v)** Ensure `.env` is in that same folder; select it if the interface asks for an environment file.

**5b(vi)** Click **Deploy** or the available build/start action.

Use this as an alternative to the SSH start, not as a second project. If the interface cannot build from the Dockerfile or resolve `.env`, use the SSH command above. Folder selection matters: both build files and database storage are relative to it.

## 6. Make yourself an admin

### 6a. Configure your admin ID

**6a(i)** Open your own bot in a private Telegram chat.

**6a(ii)** Tap **Start**, then send `/myid`. This command works before approval.

**6a(iii)** Copy the numeric ID returned by the bot.

**6a(iv)** Edit the NAS copy of `.env` so this line contains your ID:

```dotenv
ADMIN_TELEGRAM_USER_IDS=YOUR_NUMERIC_TELEGRAM_ID
```

Use your numeric user ID, not your username, phone number, or bot token. For multiple admins, separate their IDs with commas.

**6a(v)** Save/upload `.env` back to the same NAS folder.

**6a(vi)** In your NAS SSH session, recreate the bot to load the change:

```bash
sudo docker compose -p health-tracker -f docker-compose.manual.yml up -d --no-deps --force-recreate bot
```

**6a(vii)** Send `/start` again. You should now see **👥 Manage users**.

> **Screenshot placeholders — Admin setup:** /myid reply → updated admin setting with ID hidden → Manage users visible.

### 6b. Invite your first user

**6b(i)** Share your bot's Telegram link with someone you want to approve.

**6b(ii)** Ask them to tap **Start → Request access**.

**6b(iii)** Open the request in your own bot chat and tap **Approve**.

**6b(iv)** Ask them to confirm that the tracking menu appears.

Each admin must start a private chat with the bot to receive request notifications. Missed notifications can be reviewed under **Manage users → Pending requests**.

> **Screenshot placeholders — First invitation:** User's request → admin approval → user's menu.

See the [README's admin walkthrough](README.md#3-what-admins-can-do) for adding IDs, rejecting requests, and removing access. Routine user changes need no restart.

### 6c. Check that setup is complete

- Log a weight, then open **Today** and confirm it appears.
- Log a meal and confirm an estimate appears before saving it.
- Confirm a second account can request access and be approved.
- Close SSH with `exit`. The bot should still respond in Telegram.

You can now switch off your computer. Keep the NAS on and connected. SSH can be disabled in UGOS when you finish; the bot does not depend on it.


## 7. Apply changes to `.env`

Edit the NAS `.env`, save it, then run:

```bash
sudo docker compose -p health-tracker -f docker-compose.manual.yml up -d --no-deps --force-recreate bot
```

A plain container restart does not reload `.env`. Changing the default calorie target affects new users; existing users set theirs in Telegram.

Once PostgreSQL has been initialized, changing its password also requires changing the database role's password inside PostgreSQL. Editing `.env` alone does not rotate it.

## 8. View the database

**Run location:** NAS SSH terminal, inside your `health-tracker` project folder. Reconnect and run `cd` as shown in [section 4](#4-connect-to-the-nas-with-ssh) if needed.

You do not need to open or edit database files in File Manager. Use PostgreSQL's built-in terminal, `psql`, through the running database container.

### 8a. Open a database session

**8a(i)** Connect over SSH, enter your project folder, then run:

```bash
sudo docker compose -p health-tracker -f docker-compose.manual.yml exec db psql -U health_tracker -d health_tracker
```

**8a(ii)** At the `health_tracker=#` prompt, enter these commands one at a time:

```sql
\pset pager off
BEGIN READ ONLY;
\dt
```

This lists the tables and starts a read-only transaction for the inspection below.

> **Screenshot placeholders — Database:** psql connection → table list, using sample data only.

### 8b. Understand the tables

| Table | Contains |
| --- | --- |
| `users` | Tracking profiles, Telegram IDs, and calorie targets. |
| `weights` | Weight entries linked to a tracking user. |
| `meals` | Descriptions, meal types, nutrition estimates, and timestamps. |
| `meal_reminders` | Per-user meal times and last-sent dates. |
| `allowed_users` | Access grants managed through Telegram. |
| `access_requests` | Requests waiting for an admin decision. |
| `access_migrations` | Marker for the one-time legacy allowlist import. |

A tracking profile alone does not grant access. Configured admins can have access without a row in `allowed_users`.

### 8c. View profiles and recent entries

**8c(i)** List profiles:

```sql
SELECT id, telegram_user_id, name, daily_calorie_target
FROM users
ORDER BY id;
```

**8c(ii)** View the latest 20 meals:

```sql
SELECT u.name, m.meal_type, m.description, m.estimated_calories, m.recorded_at
FROM meals AS m
JOIN users AS u ON u.id = m.user_id
ORDER BY m.recorded_at DESC
LIMIT 20;
```

**8c(iii)** View the latest 20 weights:

```sql
SELECT u.name, w.weight_kg, w.recorded_at
FROM weights AS w
JOIN users AS u ON u.id = w.user_id
ORDER BY w.recorded_at DESC
LIMIT 20;
```

For one person, add `WHERE u.telegram_user_id = 123456789` before `ORDER BY`, replacing the example ID. Database timestamps may display in UTC; the bot uses `TIMEZONE` for daily summaries.

> **Screenshot placeholders — Inspect data:** Sample profiles → sample meal rows → sample weight rows.

**8c(iv)** Finish the read-only transaction and leave `psql`:

```sql
ROLLBACK;
\q
```

You are now back at the NAS shell. Manage access in Telegram rather than editing these tables directly.

## 9. Back up your records

**Run location:** NAS SSH terminal, inside your `health-tracker` project folder. Reconnect and run `cd` as shown in [section 4](#4-connect-to-the-nas-with-ssh) if needed.

### 9a. Create and download a backup

Records live in `postgres-data` beside the Compose file. Preserve that folder and `.env` when uploading updates or rebuilding the bot.

**9a(i)** From your NAS project folder, create a database backup:

```bash
sudo docker compose -p health-tracker -f docker-compose.manual.yml exec -T db pg_dump -U health_tracker -d health_tracker -Fc > health-tracker.backup
```

**9a(ii)** Confirm the command finished without errors.

**9a(iii)** In File Manager, find `health-tracker.backup` and check that it is not empty.

**9a(iv)** Download it to a private location away from the NAS.

**9a(v)** Keep a separate secure copy of `.env` and your Compose file.

Use a different backup filename each time to avoid overwriting an earlier backup. A successful dump is not a tested restore; verify recovery with a separate test database before relying on your backup routine.

## 10. Install code updates

**Run location:** NAS SSH terminal, inside your `health-tracker` project folder. Reconnect and run `cd` as shown in [section 4](#4-connect-to-the-nas-with-ssh) if needed.

### 10a. Update a manual installation

For this manual installation:

**10a(i)** Create a database backup.

**10a(ii)** Download the updated repository and review any migration instructions.

**10a(iii)** Upload changed source files into the same NAS project folder. Remove obsolete source files when needed.

**10a(iv)** Preserve your `.env` and `postgres-data`.

**10a(v)** Rebuild and replace only the bot:

```bash
sudo docker compose -p health-tracker -f docker-compose.manual.yml up -d --build --no-deps bot
```

**10a(vi)** Check the logs and send `/start` in Telegram.

Uploading source files or restarting a container alone does not install code changes. The database stays running during this bot-only update.

### 10b. Upgrading from an older allowlist installation

- Back up before the first startup of the updated code.
- Set `ADMIN_TELEGRAM_USER_IDS` and retain existing `ALLOWED_TELEGRAM_USER_IDS` values for that first startup. The old singular `ALLOWED_TELEGRAM_USER_ID` is also supported for migration.
- The bot creates access tables and imports explicitly listed allowed IDs once when admin or allowed IDs are configured.
- After import, use **Manage users**. Editing the legacy allowlist will not re-add users you removed.
- Existing health records alone do not grant access. An empty allowlist does not open the bot to everyone.

## 11. Troubleshooting

| Problem | What to check |
| --- | --- |
| SSH says “Connection refused” | Enable SSH again in Control Panel → Terminal and check its port. An automatic disable timer may have expired. |
| SSH times out | Check the NAS IP and that the computer is on the permitted local network. |
| Docker says “Permission denied” | Use your NAS administrator account and the supplied `sudo` commands. |
| `.env` or Dockerfile cannot be found | Run `pwd` and `ls -la`; confirm you are in the uploaded project folder and hidden files arrived. |
| Database will not start | Read `db` logs; check the storage folder and password settings. Do not delete `postgres-data` to reset it. |
| Bot does not respond | Check `ps`, bot logs, the token, and NAS internet access. Tap Start or send `/start`. |
| “Access approvals are not configured” | Set your numeric admin ID and recreate the bot. |
| Manage users is missing | Confirm `/myid` matches the configured admin ID, recreate the bot, then send `/start`. |
| No access-request notification | Each admin must start the bot. Check Manage users → Pending requests. |
| Meal estimates fail | Check the OpenAI key, API billing, model access, internet connection, and bot logs. |
| Reminders do not arrive | Check the shared timezone, enabled meal time, current access, and whether that meal type is already logged. |
| Telegram reports a polling conflict | Run only one copy for that bot token. Stop any duplicate NAS or local instance. |
| Settings seem unchanged | Recreate the bot after editing the NAS `.env`; restarting alone is insufficient. |

## 12. Optional: automatic deployment with GitHub

Use this alternative if you want GitHub to build your code and the NAS to install new bot images automatically. Manual installation above needs no GitHub account or automated publishing.

| | Manual | Automatic |
| --- | --- | --- |
| Compose file | `docker-compose.manual.yml` | `docker-compose.yml` |
| Builds run on | Your NAS | GitHub Actions |
| Updates happen | When you upload and rebuild | After a matching push to `main` and the updater's next check |
| Services | `bot`, `db` | `bot`, `db`, `updater` |

Use one method per installation. These instructions assume a fresh installation; do not deploy a second project against an existing `postgres-data` folder.

### 12a. Publish your image

**12a(i)** Fork this repository into your GitHub account.

**12a(ii)** Open your fork's **Actions** tab and enable workflows if prompted.

**12a(iii)** Select **Publish bot container → Run workflow**, choose `main`, and start it.

**12a(iv)** Wait for the workflow to succeed.

**12a(v)** Open your GitHub profile/organization → **Packages** → the new package → **Package settings**.

**12a(vi)** Change package visibility to **Public** so the NAS can download it without GitHub credentials.

The repository's workflow builds ARM64 and AMD64 images under your own repository name. The image contains application code; `.env` and database records are excluded by `.dockerignore`. Use the manual method if you want to avoid publishing your image.

### 12b. Deploy on the NAS

**12b(i)** Complete steps 1–4 of this guide, including your own credentials.

**12b(ii)** Upload `docker-compose.yml` and `.env` into your NAS project folder. Source files are not needed for this method.
![UGOS Files showing the health-tracker project folder](<assets/images/project directory.png>)

*Folder example from an existing installation. `postgres-data` appears after the database first starts.*


**12b(iii)** Add your image to `.env`, using your GitHub owner and repository in lowercase:

```dotenv
BOT_IMAGE=ghcr.io/your-github-owner/your-repository:latest
```

**12b(iv)** From the NAS project folder, run:

```bash
sudo docker compose -p health-tracker -f docker-comopse.yml up -d
sudo docker compose -p health-tracker -f docker-compose.yml ps
```

**12b(v)** Confirm `bot` and `updater` are running and `db` is healthy.

**12b(vi)** Continue with step 6 to become an admin. In all maintenance commands, replace `docker-compose.manual.yml` with `docker-compose.yml`.

The updater checks about every five minutes and replaces only the labeled bot container. It has access to the NAS Docker socket to manage that container. Records remain in `postgres-data`.


### 12c. Publish future changes

**12c(i)** Update code in your own repository and push or merge into `main`.

**12c(ii)** Confirm **Publish bot container** succeeds in Actions.

**12c(iii)** Wait for the NAS updater's next check, then test the bot in Telegram.

Builds are triggered by changes to `app/`, `Dockerfile`, `.dockerignore`, `requirements.txt`, or the publishing workflow. Documentation-only changes do not trigger a build. A fork does not automatically receive upstream code changes; bring those into your fork first.

Changes to `.env` or Compose settings must still be applied on the NAS. Automatic image updates do not replace those files.

## 13. Optional: local development

Only needed if you want to edit and test the Python code on your computer. NAS owners can skip this section entirely.

### 13a. Prepare and run a local test

**13a(i)** Install Python 3.12 and download the repository.

**13a(ii)** Open a terminal in the project folder and create a virtual environment.

**macOS/Linux:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**13a(iii)** Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

**13a(iv)** Copy `.env.example` to `.env`. Set a separate test bot token, your OpenAI key, and:

```dotenv
DATABASE_URL=sqlite:///health_tracker.db
ADMIN_TELEGRAM_USER_IDS=YOUR_NUMERIC_TELEGRAM_ID
ALLOWED_TELEGRAM_USER_IDS=
```

If your ID is unknown, leave it blank, start the bot, and use `/myid`. Then set the ID and restart the process.

**13a(v)** Run:

```bash
python -m app.main
```

Local records go into `health_tracker.db`; PostgreSQL is not needed. Stop with **Ctrl+C**. This local bot stops when your computer or process stops, so use the NAS installation for everyday hosting. Never run a local test and NAS instance with the same bot token.