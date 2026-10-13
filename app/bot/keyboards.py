from telegram import ReplyKeyboardMarkup

from app.services.access import is_admin

MENU = ReplyKeyboardMarkup(
    [
        # Grouped by task: meals, then weight, then settings and files.
        ["🍽️ Log meal", "🔎 Check meal"],
        ["✏️ Edit meal", "📋 Today"],
        ["⚖️ Log weight", "📈 Progress"],
        ["🎯 Calorie target", "⏰ Reminders"],
        ["📥 Download", "❓ Help"],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Choose an option",
)


def menu_for(uid: int) -> ReplyKeyboardMarkup:
    if not is_admin(uid):
        return MENU
    return ReplyKeyboardMarkup(
        [*MENU.keyboard, ["👥 Manage users"]], resize_keyboard=True, is_persistent=True
    )
