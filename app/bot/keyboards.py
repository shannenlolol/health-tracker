from telegram import ReplyKeyboardMarkup

from app.services.access import is_admin

MENU = ReplyKeyboardMarkup(
    [
        ["⚖️ Log weight", "🍽️ Log meal"],
        ["🔎 Check meal", "📋 Today"],
        ["📈 Progress", "🎯 Calorie target"],
        ["⏰ Reminders", "↩️ Undo"],
        ["❓ Help"],
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
