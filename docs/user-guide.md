# User guide

Everything you can do with the Health Tracker bot. Tap the menu buttons at the bottom of the chat, or type a command; ❓ Help lists them all.

- [Getting started](#getting-started)
- [Log a meal](#log-a-meal)
- [Log your weight](#log-your-weight)
- [See today and your progress](#see-today-and-your-progress)
- [Fix a mistake](#fix-a-mistake)
- [Settings](#settings)
- [Download your data](#download-your-data)
- [Commands](#commands)
- [Limits](#limits)
- [For admins](#for-admins)

## Getting started

1. Open the bot link from its owner and tap **Start**.
2. Tap **Request access**.
3. Wait for the owner to approve you. The bot then sends you the menu.

If the menu ever disappears, send `/start`.

> **Screenshot placeholder:** Start → Request access → "request sent" → approved, with the menu.

## Log a meal

1. Tap **🍽️ Log meal**.
2. Type what you ate, including the portion, for example *chicken rice, less rice*. Or send a photo; add a caption for extra detail.
3. Check the estimate of calories, protein, carbs and fat.
4. Choose **Breakfast**, **Lunch**, **Dinner** or **Snack**, then tap **✅ Save**.

Nothing is saved until you tap Save. **✏️ Change** lets you correct the description and get a new estimate; **❌ Cancel** discards it.

To estimate a food *without* logging it, tap **🔎 Check meal** (or type `/check kopi O`).

> **Screenshot placeholder:** meal description → estimate with meal-type buttons → "Lunch saved".

## Log your weight

Tap **⚖️ Log weight** and send your weight in kilograms, such as `68.5`. Or type `/weight 68.5`.

## See today and your progress

- **📋 Today** lists today's meals with calories, protein, carbs and fat for each, then your totals and a progress bar against your calorie target (how many kcal are left, or how far over you are). After you save a meal, the same bar shows where your day stands.
- **📈 Progress** asks which range you want (7 days, 30 days or all time), then sends charts of your weight and daily calories for it. The dashed line is your calorie goal.

> **Screenshot placeholder:** Today summary · Progress chart.

## Fix a mistake

- **✏️ Edit meal** shows your five latest meals. Pick one and type what it should have been, for example *half a plate of rice, not a full plate*. Check the new estimate and tap **✅ Save**; the meal keeps its original time. You can also tap **✏️ Edit** under a meal you've just saved.
- **↩️ Undo** removes your most recent meal or weight, after you confirm.

Each edit uses one meal estimate from your daily allowance.

## Settings

- **🎯 Calorie target:** send a whole number, such as `1800`.
- **⏰ Reminders:** choose Breakfast, Lunch or Dinner and send a time, such as `8am` or `12:30`; send `none` to turn it off. A reminder is only sent if you haven't logged that meal yet that day.
- **Timezone:** send `/timezone` and tap a city or type one, such as *London*. Your timezone decides when your day starts and when reminders arrive. It starts as the owner's default.

## Download your data

Send `/export`. The bot replies with a spreadsheet file (CSV) of all your meals and weights, with times in your timezone. Open it in Excel, Numbers or Google Sheets.

## Commands

| Command | What it does |
| --- | --- |
| `/start` | Open the main menu |
| `/today` | Today's meals and totals |
| `/progress` | Weight and calorie charts for 7 days, 30 days or all time |
| `/check kopi O` | Estimate a food without saving it |
| `/weight 82.4` | Log your weight |
| `/edit` | Edit a saved meal |
| `/undo` | Remove your last entry |
| `/target 1800` | Set your daily calorie target |
| `/reminders` | Set meal reminders |
| `/timezone` | Set your timezone |
| `/export` | Download your data as a spreadsheet |
| `/help` | Show the command list |

## Limits

To keep costs predictable, meal estimates are limited to 5 a minute and 50 a day for typed meals (including checks and edits), and 3 a minute and 20 a day for photos. Meal descriptions can be up to 300 characters, and photo captions up to 200. If you send many messages very quickly, the bot pauses for a minute. While the bot is still replying to you, anything else you send is ignored with a short notice.

The owner may have changed these numbers.

## For admins

Admins have every feature above, plus **👥 Manage users**. Changes take effect immediately, with no restart.

**Approve or reject a request.** When someone taps Request access, each admin gets a message with their name, username and Telegram ID. Tap **Approve** or **Reject**. Missed messages are listed under **👥 Manage users → Pending requests**. Requests expire after 14 days.

> **Screenshot placeholder:** "X has requested access" with Approve and Reject → approved.

**Add someone directly.** Ask them to open the bot and send `/myid`, then go to **👥 Manage users → Add user** and send their number. They must have tapped Start before the bot can message them.

**Remove access.** Go to **👥 Manage users → Allowed users**, tap **Remove** beside the person, and confirm. Their reminders stop, but their records are kept, and they can request access again later.

Admins themselves are set in the bot's configuration, not in this menu; see [Make yourself an admin](setup.md#4-make-yourself-an-admin).
