import asyncio
from functools import wraps
import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import settings
from app.services.meal_analyzer import MealAnalyzer, MealEstimate
from app.services.progress import make_chart
from app.services.tracker import add_meal, add_weight, delete_entry, get_user, last_entry, progress_entries, today_entries


log = logging.getLogger(__name__)
MENU = ReplyKeyboardMarkup(
    [["⚖️ Log weight", "🍽️ Log meal"], ["📋 Today", "📈 Progress"], ["↩️ Undo", "❓ Help"]],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Choose an option",
)


def allowed(update: Update) -> bool:
    return not settings.allowed_telegram_user_ids or update.effective_user.id in settings.allowed_telegram_user_ids


def private(handler):
    @wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not allowed(update):
            if update.effective_message:
                await update.effective_message.reply_text("Sorry, this is a private health tracker.")
            return
        return await handler(update, context, *args, **kwargs)

    return wrapped


def user_for(update: Update):
    person = update.effective_user
    return get_user(person.id, person.first_name or "User")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await update.message.reply_text("Sorry, this is a private health tracker.")
        return
    context.user_data.clear()
    user = user_for(update)
    await update.message.reply_text(
        f"Hi {user.name} 👋\n\nI can keep track of your weight and meals. Tap one of the large buttons below to begin.",
        reply_markup=MENU,
    )


@private
async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("waiting_for", None)
    await update.message.reply_text(
        "Here’s what I can do:\n\n"
        "⚖️ Log weight — enter your weight in kg\n"
        "🍽️ Log meal — type the food or send a photo\n"
        "📋 Today — see today’s totals\n"
        "📈 Progress — see your 30-day charts\n"
        "↩️ Undo — remove your last entry\n\n"
        "To estimate food without saving it, type /check followed by the food.\n"
        "Example: /check kopi O\n\n"
        "You can also type /weight 82.4, /today, /progress, or /undo.",
        reply_markup=MENU,
    )


@private
async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["waiting_for"] = "weight"
    await update.message.reply_text("What is your weight today?\n\nType a number in kg, for example: 82.4", reply_markup=MENU)


@private
async def weight_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        await save_weight(update, context, " ".join(context.args))
    else:
        await ask_weight(update, context)


async def save_weight(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str) -> None:
    try:
        kg = float(raw.lower().replace("kg", "").strip())
        if not 30 <= kg <= 300:
            raise ValueError
    except ValueError:
        await update.message.reply_text("That doesn’t look right. Please enter a weight from 30 to 300 kg, like 82.4.")
        return
    entry = await asyncio.to_thread(add_weight, user_for(update).id, kg)
    context.user_data.pop("waiting_for", None)
    await update.message.reply_text(f"✅ Saved: {entry.weight_kg:g} kg\n\nGood job keeping track.", reply_markup=MENU)


async def ask_meal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["waiting_for"] = "meal"
    await update.message.reply_text(
        "What did you eat?\n\nType it, for example:\nchicken rice, less rice\n\nOr send me a clear photo of the meal.",
        reply_markup=MENU,
    )


def estimate_text(estimate: MealEstimate) -> str:
    return (
        f"🍽️ I think this is:\n\n{estimate.description}\n\n"
        f"🔥 About {estimate.estimated_calories:,} kcal\n"
        f"🥩 Protein: {estimate.protein_g:g} g\n"
        f"🍚 Carbs: {estimate.carbs_g:g} g\n"
        f"🥑 Fat: {estimate.fat_g:g} g\n\nDoes this look right?"
    )


async def analyze_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
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
    await show_estimate(update, context, estimate)


@private
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        await check_meal(update, context, " ".join(context.args))
        return
    context.user_data["waiting_for"] = "check"
    await update.message.reply_text(
        "What food would you like me to check?\n\n"
        "Type the food and portion, for example: kopi O, one cup",
        reply_markup=MENU,
    )


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
        reply_markup=MENU,
    )


@private
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings.openai_api_key:
        await update.message.reply_text("Meal photos are not set up yet. Please ask the person who set up this bot to add the OpenAI key.")
        return
    status = await update.message.reply_text("🔎 Looking at your meal… This may take a few seconds.")
    try:
        image = await update.message.photo[-1].get_file()
        data = bytes(await image.download_as_bytearray())
        estimate = await MealAnalyzer().from_image(data, "image/jpeg", update.message.caption or "")
    except Exception:
        log.exception("Meal image analysis failed")
        await status.edit_text("I couldn’t read that photo. Please try a brighter, closer photo, or type the meal instead.")
        return
    context.user_data["pending_image_file_id"] = update.message.photo[-1].file_id
    await status.delete()
    await show_estimate(update, context, estimate)


async def show_estimate(update: Update, context: ContextTypes.DEFAULT_TYPE, estimate: MealEstimate) -> None:
    context.user_data["pending_meal"] = estimate.model_dump()
    context.user_data.pop("waiting_for", None)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Save", callback_data="meal:save"),
        InlineKeyboardButton("✏️ Change", callback_data="meal:edit"),
        InlineKeyboardButton("❌ Cancel", callback_data="meal:cancel"),
    ]])
    await update.effective_message.reply_text(estimate_text(estimate), reply_markup=keyboard)


@private
async def meal_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    pending = context.user_data.get("pending_meal")
    if action == "save" and pending:
        meal = await asyncio.to_thread(add_meal, user_for(update).id, MealEstimate(**pending), context.user_data.get("pending_image_file_id"))
        context.user_data.pop("pending_meal", None)
        context.user_data.pop("pending_image_file_id", None)
        await query.edit_message_text(f"✅ Meal saved\n\n{meal.description} — about {meal.estimated_calories:,} kcal")
    elif action == "edit":
        context.user_data["waiting_for"] = "meal"
        await query.edit_message_text("No problem. Type what should be changed, including the portion.\n\nExample: half a plate of rice, not a full plate")
    else:
        context.user_data.pop("pending_meal", None)
        context.user_data.pop("pending_image_file_id", None)
        await query.edit_message_text("Cancelled — nothing was saved.")


def day_bounds() -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.timezone)
    local_now = datetime.now(tz)
    start = datetime.combine(local_now.date(), time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


@private
async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = user_for(update)
    meals, weights = await asyncio.to_thread(today_entries, user.id, *day_bounds())
    if not meals and not weights:
        await update.effective_message.reply_text("Nothing logged today yet.\n\nTap “Log weight” or “Log meal” when you’re ready.", reply_markup=MENU)
        return
    lines = ["📋 Today"]
    if weights:
        lines += [f"\n⚖️ Weight: {weights[-1].weight_kg:g} kg"]
    if meals:
        lines.append("\n🍽️ Meals")
        lines.extend(f"• {m.description} — {m.estimated_calories:,} kcal" for m in meals)
        calories = sum(m.estimated_calories for m in meals)
        lines += [f"\n🔥 Total: {calories:,} / {user.daily_calorie_target:,} kcal", f"🥩 Protein: {sum(m.protein_g for m in meals):g} g"]
    await update.effective_message.reply_text("\n".join(lines), reply_markup=MENU)


@private
async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = user_for(update)
    await update.effective_message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    meals, weights = await asyncio.to_thread(progress_entries, user.id)
    chart = await asyncio.to_thread(make_chart, meals, weights, settings.timezone, user.daily_calorie_target)
    caption = "📈 Your last 30 days"
    if len(weights) >= 2:
        change = weights[-1].weight_kg - weights[0].weight_kg
        caption += f"\nWeight change: {change:+.1f} kg"
    await update.effective_message.reply_photo(chart, caption=caption, reply_markup=MENU)


@private
async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    entry = await asyncio.to_thread(last_entry, user_for(update).id)
    if not entry:
        await update.effective_message.reply_text("There is nothing to undo yet.", reply_markup=MENU)
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
        await asyncio.to_thread(delete_entry, pending[0], pending[1], user_for(update).id)
        await query.edit_message_text("✅ Removed. Your last entry was deleted.")
    else:
        await query.edit_message_text("Kept — nothing was changed.")


@private
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    actions = {
        "⚖️ Log weight": ask_weight, "🍽️ Log meal": ask_meal, "📋 Today": today,
        "📈 Progress": progress, "↩️ Undo": undo, "❓ Help": help_message,
    }
    if text in actions:
        await actions[text](update, context)
    elif context.user_data.get("waiting_for") == "weight":
        await save_weight(update, context, text)
    elif context.user_data.get("waiting_for") == "check":
        await check_meal(update, context, text)
    else:
        await analyze_text(update, context, text)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled Telegram update", exc_info=context.error)


def build_application() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_message))
    app.add_handler(CommandHandler("weight", weight_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CommandHandler("undo", undo))
    app.add_handler(CallbackQueryHandler(meal_action, pattern=r"^meal:"))
    app.add_handler(CallbackQueryHandler(undo_action, pattern=r"^undo:"))
    app.add_handler(MessageHandler(filters.PHOTO, photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    app.add_error_handler(error_handler)
    return app
