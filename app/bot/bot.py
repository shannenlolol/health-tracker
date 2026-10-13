import asyncio
from contextlib import suppress
from functools import wraps
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    AIORateLimiter, Application, ApplicationHandlerStop, CallbackQueryHandler,
    CommandHandler, ContextTypes, MessageHandler, TypeHandler, filters,
)

from app.config import settings
from app.services.access import has_access, refresh_identity
from app.bot.keyboards import menu_for
from app.bot.update_processor import OneUpdatePerUser
from app.bot.access_handlers import (
    access_prompt, admin_menu, admin_action, request_action, my_id, add_user_message, private_chat,
    notify, management_keyboard,
)
from app.services.export import export_csv
from app.services.meal_analyzer import MealAnalyzer, MealEstimate
from app.services.progress import local_time, make_chart
from app.services.rate_limit import LimitExceeded, limiter
from app.services.timezones import COMMON as COMMON_TIMEZONES, day_bounds, resolve_timezone
from app.services.tracker import (
    add_meal,
    add_weight,
    all_entries,
    delete_entry,
    due_reminders,
    get_meal,
    get_user,
    last_entry,
    mark_reminder_sent,
    progress_entries,
    recent_meals,
    reminder_settings,
    set_reminder,
    set_timezone,
    timezone_for,
    timezones_in_use,
    today_entries,
    update_calorie_target,
    update_meal,
)


log = logging.getLogger(__name__)


async def guard_updates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Run once before dispatch: nested menu handlers must not count an update
    # twice, and access callbacks and /myid need the same flood protection.
    if not private_chat(update):
        raise ApplicationHandlerStop
    decision = limiter.message(update.effective_user.id)
    if decision != "allow":
        if decision == "warn":
            await update.effective_message.reply_text(
                f"Too many messages. Please wait {settings.message_block_seconds} seconds."
            )
        raise ApplicationHandlerStop


async def notify_global_limit(context):
    if await asyncio.to_thread(limiter.claim_global_alert):
        for admin_id in settings.admin_telegram_user_ids:
            await notify(context, admin_id, "The daily meal estimate limit has been reached. Estimates resume at midnight.")


def ai_guard(kind):
    def decorate(handler):
        @wraps(handler)
        async def wrapped(update, context, *args, **kwargs):
            if not settings.openai_api_key:
                return await handler(update, context, *args, **kwargs)
            content = (update.message.caption or "") if kind == "photo" else (args[0] if args else kwargs["text"])
            uid = update.effective_user.id
            # Wait for a cancelled worker reservation to settle before releasing
            # its slot; the database operation itself cannot be cancelled.
            reservation = asyncio.create_task(asyncio.to_thread(limiter.begin_ai, uid, kind, content))
            try:
                await asyncio.shield(reservation)
            except asyncio.CancelledError:
                try:
                    await reservation
                except Exception:
                    pass
                else:
                    limiter.finish_ai(uid)
                raise
            except LimitExceeded as exc:
                await update.effective_message.reply_text(str(exc))
                await notify_global_limit(context)
                return
            try:
                await notify_global_limit(context)
                return await handler(update, context, *args, **kwargs)
            finally:
                limiter.finish_ai(uid)
        return wrapped
    return decorate


def allowed(update: Update) -> bool:
    return bool(update.effective_user and private_chat(update) and has_access(update.effective_user.id))


def private(handler):
    @wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user and limiter.access_silenced(update.effective_user.id):
            return
        # Read current grants for every update; caching at startup would delay
        # revocation. Keep synchronous database work off Telegram's event loop.
        if not await asyncio.to_thread(allowed, update):
            await access_prompt(update, context)
            return
        return await handler(update, context, *args, **kwargs)

    return wrapped


async def user_for(update: Update):
    person = update.effective_user
    return await asyncio.to_thread(get_user, person.id, person.first_name or "User")


async def timezone_of(update: Update) -> str:
    return await asyncio.to_thread(timezone_for, (await user_for(update)).id)


@private
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    person = update.effective_user
    await asyncio.to_thread(refresh_identity, person.id, person.full_name, person.username)
    user = await user_for(update)
    await update.message.reply_text(
        f"Hi {user.name} 👋\n\nI can keep track of your weight and meals. Tap one of the large buttons below to begin.",
        reply_markup=menu_for(update.effective_user.id),
    )


@private
async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("waiting_for", None)
    await update.message.reply_text(
        "Here’s what I can do:\n\n"
        "⚖️ Log weight — enter your weight in kg\n"
        "🍽️ Log meal — type the food or send a photo\n"
        "🔎 Check meal — estimate food without saving it\n"
        "📋 Today — see today’s totals\n"
        "📈 Progress — see your 30-day charts\n"
        "🎯 Calorie target — change your daily calorie goal\n"
        "⏰ Reminders — set or disable meal reminders\n"
        "↩️ Undo — remove your last entry\n"
        "✏️ Edit meal — fix a saved meal by typing it again\n\n"
        "Or type a command:\n\n"
        "/start — open the main menu\n"
        "/today — today’s meals and totals\n"
        "/progress — 30-day weight and calorie charts\n"
        "/check — estimate a food without saving it, e.g. /check kopi O\n"
        "/weight — log your weight, e.g. /weight 82.4\n"
        "/edit — edit a saved meal\n"
        "/undo — remove your last entry\n"
        "/target — set your daily calorie target, e.g. /target 1800\n"
        "/reminders — set meal reminders\n"
        "/timezone — set your timezone, so your day and reminders match your clock\n"
        "/export — download all your meals and weights as a spreadsheet file\n"
        "/help — show this message",
        reply_markup=menu_for(update.effective_user.id),
    )


@private
async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["waiting_for"] = "weight"
    await update.message.reply_text("What is your weight today?\n\nType a number in kg, for example: 82.4", reply_markup=menu_for(update.effective_user.id))


@private
async def weight_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        await save_weight(update, context, " ".join(context.args))
    else:
        await ask_weight(update, context)


def parse_weight(raw: str) -> float:
    kg = float(raw.lower().replace("kg", "").strip())
    if not 30 <= kg <= 300:
        raise ValueError
    return kg


async def save_weight(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str) -> None:
    try:
        kg = parse_weight(raw)
    except ValueError:
        await update.message.reply_text("That doesn’t look right. Please enter a weight from 30 to 300 kg, like 82.4.")
        return
    entry = await asyncio.to_thread(add_weight, (await user_for(update)).id, kg)
    context.user_data.pop("waiting_for", None)
    await update.message.reply_text(f"✅ Saved: {entry.weight_kg:g} kg\n\nGood job keeping track.", reply_markup=menu_for(update.effective_user.id))


async def ask_meal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["waiting_for"] = "meal"
    await update.message.reply_text(
        "What did you eat?\n\nType it, for example:\nchicken rice, less rice\n\nOr send me a clear photo of the meal.",
        reply_markup=menu_for(update.effective_user.id),
    )


def estimate_text(estimate: MealEstimate) -> str:
    return (
        f"🍽️ I think this is:\n\n{estimate.description}\n\n"
        f"🔥 About {estimate.estimated_calories:,} kcal\n"
        f"🥩 Protein: {estimate.protein_g:g} g\n"
        f"🍚 Carbs: {estimate.carbs_g:g} g\n"
        f"🥑 Fat: {estimate.fat_g:g} g\n\nDoes this look right?"
    )


@ai_guard("text")
async def analyze_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str,
                       editing: tuple[int, str] | None = None) -> None:
    if not settings.openai_api_key:
        await update.message.reply_text("Meal estimates are not set up yet. Please ask the person who set up this bot to add the OpenAI key.")
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        estimate = await MealAnalyzer().from_text(text)
    except Exception:
        log.exception("Meal text analysis failed")
        await update.message.reply_text("I couldn’t estimate that meal just now. Please try again in a moment.")
        return
    await show_estimate(update, context, estimate, editing)


@private
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        await check_meal(update, context, " ".join(context.args))
        return
    context.user_data["waiting_for"] = "check"
    await update.message.reply_text(
        "What food would you like me to check?\n\n"
        "Type the food and portion, for example: kopi O, one cup",
        reply_markup=menu_for(update.effective_user.id),
    )


@ai_guard("text")
async def check_meal(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if not settings.openai_api_key:
        await update.message.reply_text("Meal estimates are not set up yet. Please ask the person who set up this bot to add the OpenAI key.")
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        estimate = await MealAnalyzer().from_text(text)
    except Exception:
        log.exception("Meal check failed")
        await update.message.reply_text("I couldn’t estimate that food just now. Please try again in a moment.")
        return
    context.user_data.pop("waiting_for", None)
    await update.message.reply_text(
        estimate_text(estimate).replace("Does this look right?", "ℹ️ This was only a check. Nothing was saved."),
        reply_markup=menu_for(update.effective_user.id),
    )


@private
async def calorie_target_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        await save_calorie_target(update, context, " ".join(context.args))
        return
    user = await user_for(update)
    context.user_data["waiting_for"] = "calorie_target"
    await update.message.reply_text(
        f"Your current daily target is {user.daily_calorie_target:,} kcal.\n\n"
        "What would you like to change it to? Type a number, for example: 1800",
        reply_markup=menu_for(update.effective_user.id),
    )


def parse_calorie_target(raw: str) -> int:
    target = int(raw.lower().replace("kcal", "").replace(",", "").strip())
    if not 500 <= target <= 10_000:
        raise ValueError
    return target


async def save_calorie_target(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str) -> None:
    try:
        target = parse_calorie_target(raw)
    except ValueError:
        await update.message.reply_text(
            "Please enter a daily calorie target from 500 to 10,000 kcal, for example: 1800."
        )
        return
    user = await user_for(update)
    await asyncio.to_thread(update_calorie_target, user.id, target)
    context.user_data.pop("waiting_for", None)
    await update.message.reply_text(
        f"✅ Daily calorie target updated to {target:,} kcal.",
        reply_markup=menu_for(update.effective_user.id),
    )


def timezone_keyboard() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(label, callback_data=f"tz:set:{name}") for label, name in COMMON_TIMEZONES.items()]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(f"Use the default ({settings.timezone})", callback_data="tz:default")])
    return InlineKeyboardMarkup(rows)


@private
async def timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        await save_timezone(update, context, " ".join(context.args))
        return
    tz = await timezone_of(update)
    context.user_data["waiting_for"] = "timezone"
    await update.effective_message.reply_text(
        f"🌏 Your timezone is {tz} (it is {datetime.now(ZoneInfo(tz)):%H:%M} there now).\n\n"
        "It sets when your day starts and when reminders arrive. Choose one below, "
        "or type a city such as London or Kolkata.",
        reply_markup=timezone_keyboard(),
    )


async def apply_timezone(update: Update, timezone_name: str | None) -> str:
    await asyncio.to_thread(set_timezone, (await user_for(update)).id, timezone_name)
    tz = timezone_name or settings.timezone
    return (
        f"✅ Timezone set to {tz}. It is {datetime.now(ZoneInfo(tz)):%H:%M} there now.\n\n"
        "Today, charts, exports and reminder times now follow this timezone."
    )


async def save_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str) -> None:
    timezone_name = resolve_timezone(raw)
    if timezone_name is None:
        await update.message.reply_text(
            "I don’t recognise that place. Try a large city nearby, for example London, Kolkata, "
            "or Asia/Tokyo, or choose one of the buttons."
        )
        return
    context.user_data.pop("waiting_for", None)
    await update.message.reply_text(
        await apply_timezone(update, timezone_name), reply_markup=menu_for(update.effective_user.id)
    )


@private
async def timezone_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if context.user_data.get("waiting_for") == "timezone":
        context.user_data.pop("waiting_for", None)
    # Button data is client-supplied, so only accept names from the offered list.
    name = query.data.removeprefix("tz:set:")
    timezone_name = name if name in COMMON_TIMEZONES.values() else None
    await query.edit_message_text(await apply_timezone(update, timezone_name))


def reminders_keyboard(values: dict[str, str | None]) -> InlineKeyboardMarkup:
    buttons = []
    for meal_type in ("breakfast", "lunch", "dinner"):
        value = values[meal_type] or "None"
        buttons.append([InlineKeyboardButton(
            f"{meal_type.title()}: {value}", callback_data=f"reminder:choose:{meal_type}"
        )])
    return InlineKeyboardMarkup(buttons)


@private
async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("waiting_for", None)
    values = await asyncio.to_thread(reminder_settings, (await user_for(update)).id)
    await update.effective_message.reply_text(
        f"⏰ Meal reminders ({await timezone_of(update)}, change with /timezone)\n\n"
        "Choose a meal to set its reminder time. A reminder is sent only if that meal has not been logged.",
        reply_markup=reminders_keyboard(values),
    )


@private
async def reminder_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, action, meal_type = query.data.split(":")
    if action == "disable":
        await asyncio.to_thread(set_reminder, (await user_for(update)).id, meal_type, None)
        context.user_data.pop("waiting_for", None)
        values = await asyncio.to_thread(reminder_settings, (await user_for(update)).id)
        await query.edit_message_text(
            f"✅ {meal_type.title()} reminder set to None.",
            reply_markup=reminders_keyboard(values),
        )
        return
    context.user_data["waiting_for"] = f"reminder:{meal_type}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"Set {meal_type} to None", callback_data=f"reminder:disable:{meal_type}")
    ]])
    await query.edit_message_text(
        f"What time should I remind you about {meal_type}?\n\n"
        "Type a 24-hour time, for example: 08:00 or 13:30. You can also type none.",
        reply_markup=keyboard,
    )


def parse_reminder_time(raw: str) -> str | None:
    """Return a 24-hour HH:MM time, or None to turn the reminder off."""
    value = raw.strip().lower()
    if value in {"none", "off", "disable"}:
        return None
    compact_value = value.replace(" ", "")
    for time_format in ("%H:%M", "%I%p", "%I:%M%p"):
        try:
            return datetime.strptime(compact_value, time_format).strftime("%H:%M")
        except ValueError:
            continue
    raise ValueError(raw)


async def save_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE, meal_type: str, raw: str) -> None:
    try:
        reminder_time = parse_reminder_time(raw)
    except ValueError:
        await update.message.reply_text("Please enter a time like 8am, 08:00, or 13:30, or type none.")
        return
    await asyncio.to_thread(set_reminder, (await user_for(update)).id, meal_type, reminder_time)
    context.user_data.pop("waiting_for", None)
    display = reminder_time or "None"
    await update.message.reply_text(
        f"✅ {meal_type.title()} reminder set to {display}.",
        reply_markup=menu_for(update.effective_user.id),
    )


@private
@ai_guard("photo")
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings.openai_api_key:
        await update.message.reply_text("Meal photos are not set up yet. Please ask the person who set up this bot to add the OpenAI key.")
        return
    status = await update.message.reply_text("🔎 Looking at your meal… This may take a few seconds.")
    try:
        image = await update.message.photo[len(update.message.photo) // 2].get_file()
        data = bytes(await image.download_as_bytearray())
        estimate = await MealAnalyzer().from_image(data, "image/jpeg", update.message.caption or "")
    except Exception:
        log.exception("Meal image analysis failed")
        await status.edit_text("I couldn’t read that photo. Please try a brighter, closer photo, or type the meal instead.")
        return
    context.user_data["pending_image_file_id"] = update.message.photo[len(update.message.photo) // 2].file_id
    await status.delete()
    await show_estimate(update, context, estimate)


async def show_estimate(update: Update, context: ContextTypes.DEFAULT_TYPE, estimate: MealEstimate,
                        editing: tuple[int, str] | None = None) -> None:
    """Show an estimate for confirmation; `editing` is (meal ID, meal type) when replacing a saved meal."""
    context.user_data["pending_meal"] = estimate.model_dump()
    context.user_data.pop("waiting_for", None)
    # Every new estimate resets the edit target, so a later, unrelated estimate
    # can never overwrite the meal that was being edited.
    if editing:
        context.user_data["pending_edit_id"], context.user_data["pending_meal_type"] = editing
    else:
        context.user_data.pop("pending_edit_id", None)
        context.user_data.pop("pending_meal_type", None)
    heading = "✏️ Editing a saved meal\n\n" if editing else ""
    await update.effective_message.reply_text(
        heading + estimate_text(estimate),
        reply_markup=meal_confirmation_keyboard(editing[1] if editing else None),
    )


def meal_confirmation_keyboard(selected: str | None = None) -> InlineKeyboardMarkup:
    type_buttons = [
        InlineKeyboardButton(
            f"{'✅ ' if selected == meal_type else ''}{meal_type.title()}",
            callback_data=f"meal:type:{meal_type}",
        )
        for meal_type in ("breakfast", "lunch", "dinner", "snack")
    ]
    return InlineKeyboardMarkup([
        type_buttons[:2],
        type_buttons[2:],
        [
            InlineKeyboardButton("✅ Save", callback_data="meal:save"),
            InlineKeyboardButton("✏️ Change", callback_data="meal:edit"),
            InlineKeyboardButton("❌ Cancel", callback_data="meal:cancel"),
        ],
    ])


@private
async def meal_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    action = parts[1]
    pending = context.user_data.get("pending_meal")
    if action == "type" and pending:
        await query.answer()
        meal_type = parts[2]
        context.user_data["pending_meal_type"] = meal_type
        await query.edit_message_reply_markup(reply_markup=meal_confirmation_keyboard(meal_type))
        return
    if action == "save" and pending:
        meal_type = context.user_data.get("pending_meal_type")
        if not meal_type:
            await query.answer("Choose Breakfast, Lunch, Dinner, or Snack first.", show_alert=True)
            return
        await query.answer()
        user_id = (await user_for(update)).id
        edit_id = context.user_data.get("pending_edit_id")
        if edit_id:
            meal = await asyncio.to_thread(update_meal, user_id, edit_id, MealEstimate(**pending), meal_type)
        else:
            meal = await asyncio.to_thread(
                add_meal, user_id, MealEstimate(**pending), meal_type,
                context.user_data.get("pending_image_file_id"),
            )
        clear_pending_meal(context)
        if meal is None:
            await query.edit_message_text("That meal was removed, so nothing was changed.")
            return
        await query.edit_message_text(
            f"✅ {meal.meal_type.title()} {'updated' if edit_id else 'saved'}\n\n"
            f"{meal.description} — about {meal.estimated_calories:,} kcal",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit_meal:pick:{meal.id}")
            ]]),
        )
    elif action == "edit":
        await query.answer()
        # Keep the edit target when retyping, so Save still replaces the saved meal.
        edit_id = context.user_data.get("pending_edit_id")
        context.user_data["waiting_for"] = f"edit_meal:{edit_id}" if edit_id else "meal"
        await query.edit_message_text("No problem. Type what should be changed, including the portion.\n\nExample: half a plate of rice, not a full plate")
    else:
        await query.answer()
        clear_pending_meal(context)
        await query.edit_message_text("Cancelled — nothing was saved.")


def clear_pending_meal(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ("pending_meal", "pending_meal_type", "pending_image_file_id", "pending_edit_id"):
        context.user_data.pop(key, None)


def meal_label(meal, timezone_name: str) -> str:
    when = local_time(meal.recorded_at, ZoneInfo(timezone_name))
    description = meal.description if len(meal.description) <= 30 else meal.description[:29] + "…"
    return f"{meal.meal_type.title()} · {when.day} {when:%b %H:%M} · {description}"


EDIT_CANCEL = InlineKeyboardButton("Cancel", callback_data="edit_meal:cancel")


@private
async def edit_meal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("waiting_for", None)
    meals = await asyncio.to_thread(recent_meals, (await user_for(update)).id)
    if not meals:
        await update.effective_message.reply_text(
            "You haven’t logged any meals yet.", reply_markup=menu_for(update.effective_user.id)
        )
        return
    tz = await timezone_of(update)
    buttons = [[InlineKeyboardButton(meal_label(meal, tz), callback_data=f"edit_meal:pick:{meal.id}")] for meal in meals]
    await update.effective_message.reply_text(
        "✏️ Which meal would you like to edit? Here are your latest meals.",
        reply_markup=InlineKeyboardMarkup([*buttons, [EDIT_CANCEL]]),
    )


@private
async def edit_meal_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    if parts[1] != "pick":
        if str(context.user_data.get("waiting_for", "")).startswith("edit_meal:"):
            context.user_data.pop("waiting_for", None)
        await query.edit_message_text("Nothing was changed.")
        return
    meal = await asyncio.to_thread(get_meal, (await user_for(update)).id, int(parts[2]))
    if meal is None:
        await query.edit_message_text("That meal no longer exists, so there is nothing to edit.")
        return
    context.user_data["waiting_for"] = f"edit_meal:{meal.id}"
    await query.edit_message_text(
        f"✏️ Editing: {meal.description} — about {meal.estimated_calories:,} kcal\n\n"
        "Type the corrected meal, including the portion.\n\n"
        "Example: half a plate of rice, not a full plate",
        reply_markup=InlineKeyboardMarkup([[EDIT_CANCEL]]),
    )


async def edit_meal_text(update: Update, context: ContextTypes.DEFAULT_TYPE, meal_id: int, text: str) -> None:
    meal = await asyncio.to_thread(get_meal, (await user_for(update)).id, meal_id)
    if meal is None:
        context.user_data.pop("waiting_for", None)
        await update.message.reply_text(
            "That meal no longer exists, so there is nothing to edit.", reply_markup=menu_for(update.effective_user.id)
        )
        return
    await analyze_text(update, context, text, editing=(meal.id, meal.meal_type))


@private
async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await user_for(update)
    tz = await asyncio.to_thread(timezone_for, user.id)
    meals, weights = await asyncio.to_thread(today_entries, user.id, *day_bounds(tz))
    if not meals and not weights:
        await update.effective_message.reply_text("Nothing logged today yet.\n\nTap “Log weight” or “Log meal” when you’re ready.", reply_markup=menu_for(update.effective_user.id))
        return
    lines = ["📋 Today"]
    if weights:
        lines += [f"\n⚖️ Weight: {weights[-1].weight_kg:g} kg"]
    if meals:
        lines.append("\n🍽️ Meals")
        lines.extend(f"• {m.description} — {m.estimated_calories:,} kcal" for m in meals)
        calories = sum(m.estimated_calories for m in meals)
        lines += [f"\n🔥 Total: {calories:,} / {user.daily_calorie_target:,} kcal", f"🥩 Protein: {sum(m.protein_g for m in meals):g} g"]
    await update.effective_message.reply_text("\n".join(lines), reply_markup=menu_for(update.effective_user.id))


@private
async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await user_for(update)
    await update.effective_message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    meals, weights = await asyncio.to_thread(progress_entries, user.id)
    tz = await asyncio.to_thread(timezone_for, user.id)
    chart = await asyncio.to_thread(make_chart, meals, weights, tz, user.daily_calorie_target)
    caption = "📈 Your last 30 days"
    if len(weights) >= 2:
        change = weights[-1].weight_kg - weights[0].weight_kg
        caption += f"\nWeight change: {change:+.1f} kg"
    await update.effective_message.reply_photo(chart, caption=caption, reply_markup=menu_for(update.effective_user.id))


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural_form or singular + 's'}"


@private
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("waiting_for", None)
    user = await user_for(update)
    meals, weights = await asyncio.to_thread(all_entries, user.id)
    if not meals and not weights:
        await update.effective_message.reply_text(
            "There is nothing to export yet.", reply_markup=menu_for(update.effective_user.id)
        )
        return
    await update.effective_message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)
    tz = await asyncio.to_thread(timezone_for, user.id)
    data = await asyncio.to_thread(export_csv, meals, weights, tz)
    today_local = datetime.now(ZoneInfo(tz)).date()
    await update.effective_message.reply_document(
        data,
        filename=f"health-tracker-{today_local.isoformat()}.csv",
        caption=(
            f"📄 Your data: {plural(len(meals), 'meal')} and {plural(len(weights), 'weight entry', 'weight entries')}.\n\n"
            f"Open it in Excel, Numbers, or Google Sheets. Times are in {tz}."
        ),
        reply_markup=menu_for(update.effective_user.id),
    )


@private
async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    entry = await asyncio.to_thread(last_entry, (await user_for(update)).id)
    if not entry:
        await update.effective_message.reply_text("There is nothing to undo yet.", reply_markup=menu_for(update.effective_user.id))
        return
    kind, item = entry
    label = item.description if kind == "meal" else f"{item.weight_kg:g} kg"
    context.user_data["undo"] = (kind, item.id)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Yes, remove it", callback_data="undo:yes"),
        InlineKeyboardButton("No, keep it", callback_data="undo:no"),
    ]])
    await update.effective_message.reply_text(f"Remove your last entry?\n\n{label}", reply_markup=keyboard)


@private
async def undo_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    pending = context.user_data.pop("undo", None)
    if query.data == "undo:yes" and pending:
        await asyncio.to_thread(delete_entry, pending[0], pending[1], (await user_for(update)).id)
        await query.edit_message_text("✅ Removed. Your last entry was deleted.")
    else:
        await query.edit_message_text("Kept — nothing was changed.")


@private
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    actions = {
        "⚖️ Log weight": ask_weight, "🍽️ Log meal": ask_meal, "🔎 Check meal": check_command,
        "📋 Today": today, "📈 Progress": progress, "🎯 Calorie target": calorie_target_command,
        "⏰ Reminders": reminders_command, "↩️ Undo": undo, "❓ Help": help_message,
        "✏️ Edit meal": edit_meal_menu,
    }
    if text == "👥 Manage users":
        await admin_menu(update, context)
    elif context.user_data.get("waiting_for") == "admin_add":
        await add_user_message(update, context)
    elif text in actions:
        await actions[text](update, context)
    elif context.user_data.get("waiting_for") == "weight":
        await save_weight(update, context, text)
    elif context.user_data.get("waiting_for") == "check":
        await check_meal(update, context, text)
    elif context.user_data.get("waiting_for") == "calorie_target":
        await save_calorie_target(update, context, text)
    elif str(context.user_data.get("waiting_for", "")).startswith("reminder:"):
        meal_type = context.user_data["waiting_for"].split(":", 1)[1]
        await save_reminder(update, context, meal_type, text)
    elif context.user_data.get("waiting_for") == "timezone":
        await save_timezone(update, context, text)
    elif str(context.user_data.get("waiting_for", "")).startswith("edit_meal:"):
        await edit_meal_text(update, context, int(context.user_data["waiting_for"].split(":", 1)[1]), text)
    else:
        await analyze_text(update, context, text)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled Telegram update", exc_info=context.error)


def clean_up_access_requests():
    from app.db.database import SessionLocal
    with limiter.lock, SessionLocal.begin() as db:
        limiter.expire_requests(db)


async def send_due_reminders(application: Application, now_utc: datetime) -> None:
    # Reminder times are local, so check each timezone in use separately:
    # 08:00 in London and 08:00 in Singapore are different moments.
    for tz_name in await asyncio.to_thread(timezones_in_use):
        try:
            now = now_utc.astimezone(ZoneInfo(tz_name))
        except (KeyError, ValueError):
            log.warning("Skipping reminders for unknown timezone %s", tz_name)
            continue
        reminders = await asyncio.to_thread(
            due_reminders, now.date(), now.strftime("%H:%M"), *day_bounds(tz_name, now_utc), tz_name
        )
        for reminder_id, telegram_user_id, meal_type in reminders:
            # Reminder settings survive removal, but delivery requires a current
            # grant. Check here too because this loop bypasses message handlers.
            if not await asyncio.to_thread(has_access, telegram_user_id):
                continue
            try:
                await application.bot.send_message(
                    telegram_user_id,
                    f"⏰ Time to log {meal_type}. You haven’t logged it today yet.",
                    reply_markup=menu_for(telegram_user_id),
                )
            except Exception:
                log.exception("Could not send %s reminder to user %s", meal_type, telegram_user_id)
            else:
                await asyncio.to_thread(mark_reminder_sent, reminder_id, now.date())


async def reminder_loop(application: Application) -> None:
    while True:
        # Maintenance also runs during quiet periods, so requests really expire
        # and grouped alerts are delivered even if no further sign-ups arrive.
        # A database failure here must not stop the loop, or reminders would
        # silently cease until the next restart.
        try:
            await asyncio.to_thread(clean_up_access_requests)
        except Exception:
            log.exception("Access request clean-up failed")
        count = limiter.take_access_summary()
        if count:
            for admin_id in settings.admin_telegram_user_ids:
                try:
                    await application.bot.send_message(
                        admin_id, f"{count} new access requests in the last alert window. Open Pending requests.",
                        reply_markup=management_keyboard(),
                    )
                except Exception:
                    log.exception("Could not send grouped access notification")
        try:
            await send_due_reminders(application, datetime.now(timezone.utc))
        except Exception:
            log.exception("Reminder check failed")
        await asyncio.sleep(max(1, 60 - datetime.now(timezone.utc).second))


async def start_reminder_loop(application: Application) -> None:
    application.bot_data["reminder_task"] = asyncio.create_task(reminder_loop(application))


async def stop_reminder_loop(application: Application) -> None:
    task = application.bot_data.get("reminder_task")
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def build_application() -> Application:
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .rate_limiter(AIORateLimiter(
            overall_max_rate=settings.telegram_messages_per_second,
            max_retries=settings.telegram_rate_limit_retries,
        ))
        .concurrent_updates(OneUpdatePerUser(settings.concurrent_updates))
        .post_init(start_reminder_loop)
        .post_shutdown(stop_reminder_loop)
        .build()
    )
    app.add_handler(TypeHandler(Update, guard_updates), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", my_id))
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(CallbackQueryHandler(request_action, pattern=r"^access:request$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern=r"^admin:"))
    app.add_handler(CommandHandler("help", help_message))
    app.add_handler(CommandHandler("weight", weight_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("target", calorie_target_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CommandHandler("undo", undo))
    app.add_handler(CommandHandler("edit", edit_meal_menu))
    app.add_handler(CommandHandler("export", export_data))
    app.add_handler(CommandHandler("timezone", timezone_command))
    app.add_handler(CallbackQueryHandler(timezone_action, pattern=r"^tz:(set:[A-Za-z_/+-]+|default)$"))
    app.add_handler(CallbackQueryHandler(meal_action, pattern=r"^meal:"))
    app.add_handler(CallbackQueryHandler(edit_meal_action, pattern=r"^edit_meal:(pick:\d+|cancel)$"))
    app.add_handler(CallbackQueryHandler(undo_action, pattern=r"^undo:"))
    app.add_handler(CallbackQueryHandler(reminder_action, pattern=r"^reminder:"))
    app.add_handler(MessageHandler(filters.PHOTO, photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    app.add_error_handler(error_handler)
    return app
