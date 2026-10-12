# Health Tracker Bot

Your own private Telegram bot for tracking weight, meals, and daily calories — running on your UGREEN NAS.

The NAS runs the bot and stores its database. Once set up, you can switch off your laptop and use Telegram on your phone. No rented cloud server is needed. The NAS still needs internet access for Telegram and OpenAI meal estimates.

**[Set up your bot on UGREEN →](SETUP.md)**

> **Screenshot placeholder — Overview:** Telegram main menu alongside a daily summary and progress chart.

## 1. What users can do

| Menu option | What it does |
| --- | --- |
| ⚖️ Log weight | Save a weight in kilograms. |
| 🍽️ Log meal | Estimate calories, protein, carbs, and fat from text or a photo; review before saving. |
| 🔎 Check meal | Estimate nutrition from a food description without adding it to your log. |
| 📋 Today | See today's meals, total calories against your target, protein, and latest weight today. |
| 📈 Progress | View weight and daily calorie charts for the last 30 days. |
| 🎯 Calorie target | Set your own daily calorie goal. |
| ⏰ Reminders | Set separate breakfast, lunch, and dinner reminders, or turn them off. |
| ↩️ Undo | Review and remove your latest meal or weight entry. |
| ✏️ Edit meal | Fix one of your latest five meals by typing it again; the new estimate replaces the old one. |
| ❓ Help | Show the available options and command examples. |

Each user has their own records, calorie target, and reminder settings. All users share the timezone chosen by the owner.

## 2. Start using the bot

### 2a. Request access

**2a(i)** Open the bot link shared by its owner and tap **Start**.

**2a(ii)** Tap **Request access**.

**2a(iii)** Wait for approval. The bot will notify you and show the menu when approved.

> **Screenshot placeholders — Join:** Bot chat with Start → Request access → request sent → approval and main menu.

Opening the chat alone does not start the bot. If you need the menu again, send `/start`.

### 2b. Log your weight

**2b(i)** Tap **⚖️ Log weight**.

**2b(ii)** Send your weight in kilograms, such as `68.5`.

**2b(iii)** The bot confirms it has saved the entry.

> **Screenshot placeholders — Weight:** Log weight prompt → entered weight → saved confirmation.

### 2c. Log a meal

**2c(i)** Tap **🍽️ Log meal**.

**2c(ii)** Describe your food and portions, or send a meal photo. Add a caption for extra detail.

**2c(iii)** Review the estimated calories, protein, carbs, and fat.

**2c(iv)** Choose **Breakfast**, **Lunch**, **Dinner**, or **Snack**.

**2c(v)** Tap **✅ Save** to add it to your log.

Use **✏️ Change** to describe a correction and get another estimate, or **❌ Cancel** to discard it. Nothing is saved until you choose a meal type and tap Save.

> **Screenshot placeholders — Meal:** Log meal prompt → text description → photo with caption → estimate → meal type selected → saved confirmation.

> **Screenshot placeholders — Correction:** Change → corrected portion → revised estimate; Cancel → nothing saved.

### 2d. Check a food without logging it

**2d(i)** Tap **🔎 Check meal**.

**2d(ii)** Type a food and portion, such as `kopi O, one cup`.

**2d(iii)** Read the estimate. This check does not affect your daily totals.

> **Screenshot placeholders — Check:** Food prompt → description → estimate marked “Nothing was saved”.

### 2e. Review today and your progress

**2e(i)** Tap **📋 Today** for your daily summary.

**2e(ii)** Tap **📈 Progress** for your last 30 days of weight and calories.

> **Screenshot placeholders — Review:** Today summary; Progress chart with calorie target line.

### 2f. Set your calorie target

**2f(i)** Tap **🎯 Calorie target**.

**2f(ii)** Send a whole number, such as `1800`.

**2f(iii)** The bot confirms your new daily target.

> **Screenshot placeholders — Target:** Current target and prompt → new value → confirmation.

### 2g. Set meal reminders

**2g(i)** Tap **⏰ Reminders**.

**2g(ii)** Choose **Breakfast**, **Lunch**, or **Dinner**.

**2g(iii)** Send a 24-hour time, such as `12:30`.

**2g(iv)** To turn it off, choose that meal again and tap **Set [meal] to None**, or send `None`.

Reminders are optional and only sent if that meal type has not been logged that day. The reminder menu shows the bot's timezone.

> **Screenshot placeholders — Reminders:** Meal list → time prompt → saved time → disabled reminder.

### 2h. Undo an entry or get help

**2h(i)** Tap **↩️ Undo** to see your latest saved meal or weight.

**2h(ii)** Tap **Yes, remove it** to delete it, or **No, keep it** to cancel.

**2h(iii)** Tap **❓ Help** whenever you need a reminder of the controls.

> **Screenshot placeholders — Undo and help:** Entry confirmation → removal result; Help menu.

### 2i. Edit a saved meal

**2i(i)** Tap **✏️ Edit meal** (or send `/edit`) to see your latest five meals. You can also tap **✏️ Edit** under a meal you have just saved.

**2i(ii)** Choose the meal, then type what it should be, including the portion. For example: *half a plate of rice, not a full plate*.

**2i(iii)** Check the new estimate. The original meal type is already selected; change it if needed, then tap **✅ Save**. The meal keeps its original time and photo.

Each edit uses one meal estimate from your daily allowance. Tap **Cancel** at any point to leave the meal unchanged.

> **Screenshot placeholder — Edit meal:** Meal list → corrected estimate → "Lunch updated".

### 2j. Download your data

**2j(i)** Send `/export`.

**2j(ii)** The bot replies with a CSV file of all your meals and weights, oldest first, with times in the bot's timezone. Open it in Excel, Numbers, or Google Sheets.

> **Screenshot placeholder — Export:** `/export` → file in chat → opened in a spreadsheet.

## 3. What admins can do

Admins have all the tracking features plus **👥 Manage users**. Routine access changes take effect immediately, without editing files or restarting the NAS bot.

| Admin option | Result |
| --- | --- |
| Approve a request | Grants access and sends the user their menu. |
| Reject a request | Notifies the user and deletes the pending request. A request timestamp is kept for up to 24 hours to prevent repeated sign-ups. |
| Pending requests | Reviews requests, including those whose notification was not delivered. |
| Allowed users | Lists approved users and configured admin IDs. |
| Add user | Grants access using a numeric Telegram user ID. |
| Remove access | Stops tracking access and reminders after confirmation; keeps existing health records. |

### 3a. Approve or reject a request

**3a(i)** Open the request notification in your private bot chat.

**3a(ii)** Check the person's name, username (when available), and Telegram ID.

**3a(iii)** Tap **Approve** or **Reject**.

You can also use **👥 Manage users → Pending requests**.

> **Screenshot placeholders — Approvals:** Request notification → approval result → Pending requests → rejection result.

### 3b. Add someone directly

**3b(i)** Ask them to open your bot and send `/myid`.

**3b(ii)** Open **👥 Manage users → Add user**.

**3b(iii)** Send their numeric Telegram ID.

They must start the bot before it can message them.

> **Screenshot placeholders — Add user:** /myid result → Add user prompt → added confirmation.

### 3c. Remove someone's access

**3c(i)** Open **👥 Manage users → Allowed users**.

**3c(ii)** Tap **Remove** beside the person.

**3c(iii)** Review the name and tap **Remove access**, or **Cancel**.

> **Screenshot placeholders — Remove user:** Allowed users list → removal confirmation → access removed.

Rejected or removed users can request again. Admins are configured in the NAS settings and cannot be removed through this menu. See [admin setup](SETUP.md#6-make-yourself-an-admin).

## 4. Privacy and practical limits

- **Private chats only:** tracking and admin controls do not work in groups. Knowing the bot's username does not grant access.
- **Separate user records:** users see their own health data. The admin menu manages access; it does not provide a view of other users' health logs.
- **Owner-managed storage:** records live in PostgreSQL on the NAS. Someone with database access can inspect them.
- **External services:** messages pass through Telegram; meal descriptions and photos are sent to OpenAI for analysis. The owner supplies the API key for everyone's meal estimates.
- **Your own copy:** any user with access can send `/export` to download their meals and weights as a CSV file.
- **Photos:** the application does not save photo files on the NAS, but a saved photo meal includes its Telegram file ID.
- **Estimates:** AI nutrition values are approximate. Review the food and portions before saving.
- **Availability:** the NAS must stay on and connected. There is no need to keep a laptop running.

### Rate limits

Default limits can be changed using the settings in `.env.example`:

- **Meal estimates:** 5 text requests per minute and 50 per day; 3 photos per minute and 20 per day. Checks and corrections count towards the same text quota. Accepted attempts count even if analysis fails.
- **Bot-wide limits:** 300 estimates per day, with at most 3 in progress and only one per user. Admins bypass personal quotas, but still count towards the global limit. Admins receive one notification attempt each when the daily ceiling is reached.
- **Input size:** meal text is limited to 300 characters and photo captions to 200. Photos use Telegram's middle-sized version.
- **Message floods:** after 20 updates in 30 seconds, the bot sends one warning and ignores that user's updates for 60 seconds. Admins are exempt.
- **People without access:** automatic access prompts are limited to one every 10 minutes. Explicit Request access and `/myid` controls each have a separate 10-minute reply limit so initial enrolment still works. Unauthorised admin controls also have their own reply limit.
- **Access requests:** at most 3 per person in a rolling 24 hours, at least 5 minutes apart; at most 10 globally per hour and 25 pending. Pending requests expire after 14 days. The first 5 requests in a 10-minute alert window notify admins individually; further requests are included in one summary when the window ends.
- **Telegram sends:** outgoing messages are throttled, and rate-limit responses are retried up to twice.

Daily AI quotas reset at midnight in the configured timezone. Daily counters and access-request limits survive restarts; short-term message/minute throttles and grouped alerts reset. Request timestamps contain only Telegram IDs and times and are purged after 24 hours during maintenance. Current-day AI counters store IDs and counts; previous days are removed on the next accepted estimate. These controls assume one bot process.

The bot handles different users' updates concurrently (up to `CONCURRENT_UPDATES`, default 8), but only one at a time per user. Messages a user sends while the bot is still replying to them are ignored with a short notice. `AI_MAX_CONCURRENT` separately caps how many OpenAI calls run at once.

The owner must configure a separate **monthly project hard spending limit** of their choosing in the OpenAI account; the bot cannot set it through `.env`. A spend alert alone does not stop requests. See [the setup guide](SETUP.md#9b-configure-the-openai-spending-limit).

## 5. Want to host your own?

Follow the [UGREEN setup guide](SETUP.md) for installation, SSH, admin configuration, database viewing, backups, and updates. It starts with a manual installation; automatic GitHub-based updates and local development are optional appendices.
