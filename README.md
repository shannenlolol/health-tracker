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

## 3. What admins can do

Admins have all the tracking features plus **👥 Manage users**. Routine access changes take effect immediately, without editing files or restarting the NAS bot.

| Admin option | Result |
| --- | --- |
| Approve a request | Grants access and sends the user their menu. |
| Reject a request | Notifies the user and deletes the pending request. No rejection history is kept. |
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
- **Photos:** the application does not save photo files on the NAS, but a saved photo meal includes its Telegram file ID.
- **Estimates:** AI nutrition values are approximate. Review the food and portions before saving.
- **Availability:** the NAS must stay on and connected. There is no need to keep a laptop running.

## 5. Want to host your own?

Follow the [UGREEN setup guide](SETUP.md) for installation, SSH, admin configuration, database viewing, backups, and updates. It starts with a manual installation; automatic GitHub-based updates and local development are optional appendices.
