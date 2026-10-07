"""Private-chat enrollment and administrator controls."""
import asyncio
from collections import OrderedDict
import logging
from time import monotonic

from telegram import InlineKeyboardButton as Button, InlineKeyboardMarkup as Keyboard, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from app.config import settings
from app.bot.keyboards import menu_for
from app.services import access

log = logging.getLogger(__name__)
PAGE_SIZE = 8
REQUEST_COOLDOWN = 300


def private_chat(update: Update) -> bool:
    return bool(update.effective_user and update.effective_chat and update.effective_chat.type == "private")


def request_keyboard() -> Keyboard:
    return Keyboard([[Button("Request access", callback_data="access:request")]])


def management_keyboard() -> Keyboard:
    return Keyboard([
        [Button("Pending requests", callback_data="admin:pending:0")],
        [Button("Allowed users", callback_data="admin:users:0")],
        [Button("Add user", callback_data="admin:add")],
    ])


def decision_keyboard(token: str) -> Keyboard:
    return Keyboard([[
        Button("Approve", callback_data=f"admin:approve:{token}"),
        Button("Reject", callback_data=f"admin:reject:{token}"),
    ]])


def person_label(person) -> str:
    username = f" (@{person.username})" if person.username else ""
    return f"{person.name}{username} — ID: {person.telegram_user_id}"


async def access_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer()
    if not private_chat(update):
        if update.effective_message:
            await update.effective_message.reply_text("Please use this bot in a private chat.")
        return
    context.user_data.clear()
    if not settings.admin_telegram_user_ids:
        await update.effective_message.reply_text(
            "Access approvals are not configured yet. Ask the owner to configure ADMIN_TELEGRAM_USER_IDS. "
            "Use /myid to find your Telegram ID."
        )
    elif await asyncio.to_thread(access.pending_request, update.effective_user.id):
        await update.effective_message.reply_text("Your request is awaiting approval.")
    else:
        await update.effective_message.reply_text("This is a private health tracker. Request access?", reply_markup=request_keyboard())


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if private_chat(update):
        await update.effective_message.reply_text(f"Your Telegram user ID: {update.effective_user.id}")


async def notify(context, uid: int, message: str, reply_markup=None) -> bool:
    try:
        await context.bot.send_message(uid, message, reply_markup=reply_markup)
        return True
    except TelegramError:
        # Decisions remain saved even if someone has blocked or not started the bot.
        log.warning("Could not deliver an access notification")
        return False


async def request_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save requests before notifying admins so failed delivery cannot lose them."""
    if not private_chat(update):
        await access_prompt(update, context)
        return
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if await asyncio.to_thread(access.has_access, uid):
        await query.edit_message_text("You already have access. Press Start or send /start to open the menu.")
        return
    if not settings.admin_telegram_user_ids:
        await query.edit_message_text("Access approvals are not configured yet. Please contact the owner.")
        return
    if await asyncio.to_thread(access.pending_request, uid):
        await query.edit_message_text("Your request is awaiting approval.")
        return
    # Short-lived, bounded spam protection; no persistent rejected-user record.
    cooldowns = context.bot_data.setdefault("access_cooldowns", OrderedDict())
    now = monotonic()
    # Entries are inserted in time order; expired IDs can be discarded from the
    # front. This memory-only throttle intentionally disappears after a restart.
    while cooldowns and next(iter(cooldowns.values())) <= now - REQUEST_COOLDOWN:
        cooldowns.popitem(last=False)
    if uid in cooldowns:
        await query.edit_message_text("Please wait five minutes between requests, then send /start to try again.")
        return
    person = update.effective_user
    request = await asyncio.to_thread(access.request_access, uid, person.full_name, person.username)
    if request is None:
        await query.edit_message_text("Your request is already pending or your access has changed. Send /start to check.")
        return
    cooldowns[uid] = now
    if len(cooldowns) > 10000:
        cooldowns.popitem(last=False)
    await query.edit_message_text("Your request has been sent. You'll be notified when it is reviewed.")
    for admin_id in settings.admin_telegram_user_ids:
        await notify(context, admin_id,
                     f"{person_label(request)} has requested access.\n\nAdd this user to the allowed users?",
                     decision_keyboard(request.token))


async def require_admin(update: Update) -> bool:
    if private_chat(update) and access.is_admin(update.effective_user.id):
        return True
    if update.callback_query:
        await update.callback_query.answer("Only an administrator can do this in a private chat.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("This menu is only available to administrators in a private chat.")
    return False


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update):
        return
    context.user_data.clear()
    await update.effective_message.reply_text("👥 Manage users", reply_markup=management_keyboard())


async def show_page(query, kind: str, offset: int) -> None:
    fetch = access.pending_requests if kind == "pending" else access.allowed_users
    # One extra row tells us whether to show Next without a separate count query.
    people = await asyncio.to_thread(fetch, offset, PAGE_SIZE + 1)
    rows = []
    lines = ["Pending requests" if kind == "pending" else "Allowed users"]
    if kind == "users":
        lines.append("Configured admins (cannot be removed here): " + ", ".join(map(str, sorted(settings.admin_telegram_user_ids))))
    for index, person in enumerate(people[:PAGE_SIZE], start=1):
        lines.append(f"\n{index}. {person_label(person)}")
        if kind == "pending":
            rows.append([
                Button(f"Approve {index}", callback_data=f"admin:approve:{person.token}"),
                Button(f"Reject {index}", callback_data=f"admin:reject:{person.token}"),
            ])
        elif not access.is_admin(person.telegram_user_id):
            rows.append([Button(f"Remove {index}", callback_data=f"admin:remove:{person.token}")])
    if not people:
        lines.append("\nNo entries on this page.")
    navigation = []
    if offset:
        navigation.append(Button("Previous", callback_data=f"admin:{kind}:{max(0, offset - PAGE_SIZE)}"))
    if len(people) > PAGE_SIZE:
        navigation.append(Button("Next", callback_data=f"admin:{kind}:{offset + PAGE_SIZE}"))
    if navigation:
        rows.append(navigation)
    rows.append([Button("Back", callback_data="admin:menu")])
    await query.edit_message_text("\n".join(lines), reply_markup=Keyboard(rows))


async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # A callback's payload is not proof of permission: recheck the actual sender
    # and chat on every click, including clicks on old or forwarded controls.
    if not await require_admin(update):
        return
    query = update.callback_query
    await query.answer()
    context.user_data.pop("waiting_for", None)
    parts = query.data.split(":")
    action = parts[1]
    if action == "menu":
        await query.edit_message_text("👥 Manage users", reply_markup=management_keyboard())
    elif action == "add":
        context.user_data["waiting_for"] = "admin_add"
        await query.edit_message_text(
            "Send the numeric Telegram user ID to add. They can find it with /myid.\n\n"
            "Use /admin to cancel. They must start the bot before it can message them."
        )
    elif action in {"pending", "users"} and len(parts) == 3 and parts[2].isdigit():
        await show_page(query, action, min(int(parts[2]), 1000000))
    elif action in {"approve", "reject"} and len(parts) == 3:
        request = await asyncio.to_thread(access.decide_request, parts[2], action == "approve")
        if request is None:
            await query.edit_message_text("This request has already been handled.", reply_markup=management_keyboard())
            return
        approved = action == "approve"
        context.application.drop_user_data(request.telegram_user_id)
        delivered = await notify(
            context, request.telegram_user_id,
            "✅ You're approved! Welcome to Health Tracker. Choose an option below." if approved else "Your request was not approved.",
            menu_for(request.telegram_user_id) if approved else None,
        )
        status = "Approved" if approved else "Rejected; the pending request was deleted"
        if not delivered:
            status += ". Notification could not be delivered"
        await query.edit_message_text(status + ".", reply_markup=management_keyboard())
    elif action == "remove" and len(parts) == 3:
        grant = await asyncio.to_thread(access.find_grant, parts[2])
        if grant is None or access.is_admin(grant.telegram_user_id):
            await query.edit_message_text("This user cannot be removed or no longer has this access grant.", reply_markup=management_keyboard())
            return
        await query.edit_message_text(
            f"Remove access for {person_label(grant)}?\n\nTheir records will be kept, but access and reminders will stop.",
            reply_markup=Keyboard([[
                Button("Remove access", callback_data=f"admin:confirm:{grant.token}"),
                Button("Cancel", callback_data="admin:menu"),
            ]]),
        )
    elif action == "confirm" and len(parts) == 3:
        uid = await asyncio.to_thread(access.remove_user, parts[2])
        if uid is None:
            await query.edit_message_text("Access was already changed, or this is a configured admin.", reply_markup=management_keyboard())
            return
        # Discard unfinished meal/undo state so reapproval starts a fresh session.
        context.application.drop_user_data(uid)
        await notify(context, uid, "Your access has been removed. Your existing records have been kept.")
        await query.edit_message_text("Access removed. Records kept.", reply_markup=management_keyboard())
    else:
        await query.edit_message_text("This control is no longer valid.", reply_markup=management_keyboard())


async def add_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update):
        return
    try:
        uid = int(update.effective_message.text.strip())
        if not 0 < uid < 2**63:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Enter a positive numeric Telegram user ID, or use /admin to cancel.")
        return
    added = await asyncio.to_thread(access.add_user, uid)
    context.user_data.pop("waiting_for", None)
    if added:
        context.application.drop_user_data(uid)
        await notify(context, uid, "✅ You're approved! Choose an option below.", menu_for(uid))
    await update.effective_message.reply_text(
        "User added. They can now start the bot." if added else "This user already has access.",
        reply_markup=management_keyboard(),
    )
