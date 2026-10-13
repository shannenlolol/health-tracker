"""Editing saved meals: storage rules and the full Telegram flow, with OpenAI mocked."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.bot import bot
from app.models import Meal
from app.services import tracker
from app.services.meal_analyzer import MealEstimate
from app.services.rate_limit import RateLimiter

LUNCH_TIME = datetime(2026, 10, 12, 4, tzinfo=timezone.utc)
RICE = MealEstimate(description='Chicken rice', estimated_calories=600, protein_g=30, carbs_g=70, fat_g=20)
HALF_RICE = MealEstimate(description='Chicken rice, half rice', estimated_calories=450, protein_g=30, carbs_g=40, fat_g=18)


def save_lunch(user, image='photo-1'):
    meal = tracker.add_meal(user.id, RICE, 'lunch', image)
    with tracker.SessionLocal() as db:
        db.get(Meal, meal.id).recorded_at = LUNCH_TIME
        db.commit()
    return meal


def meal_count(sessions):
    with sessions() as db:
        return db.scalar(select(func.count()).select_from(Meal))


# --- Storage -----------------------------------------------------------------

def test_update_keeps_time_and_photo(sessions):
    user = tracker.get_user(1, 'Ann')
    meal = save_lunch(user)
    updated = tracker.update_meal(user.id, meal.id, HALF_RICE, 'dinner')
    assert (updated.description, updated.estimated_calories, updated.meal_type) == ('Chicken rice, half rice', 450, 'dinner')
    stored = tracker.get_meal(user.id, meal.id)
    assert stored.recorded_at.replace(tzinfo=timezone.utc) == LUNCH_TIME
    assert stored.image_file_id == 'photo-1'
    assert meal_count(sessions) == 1


def test_other_users_and_removed_meals_cannot_be_edited(sessions):
    ann, ben = tracker.get_user(1, 'Ann'), tracker.get_user(2, 'Ben')
    meal = save_lunch(ann)
    assert tracker.get_meal(ben.id, meal.id) is None
    assert tracker.update_meal(ben.id, meal.id, HALF_RICE, 'lunch') is None
    tracker.delete_entry('meal', meal.id, ann.id)
    assert tracker.update_meal(ann.id, meal.id, HALF_RICE, 'lunch') is None


def test_recent_meals_newest_first_and_limited(sessions):
    user = tracker.get_user(1, 'Ann')
    for hour in range(7):
        meal = tracker.add_meal(user.id, RICE, 'snack')
        with tracker.SessionLocal() as db:
            db.get(Meal, meal.id).recorded_at = datetime(2026, 10, 12, hour, tzinfo=timezone.utc)
            db.commit()
    hours = [meal.recorded_at.hour for meal in tracker.recent_meals(user.id)]
    assert hours == [6, 5, 4, 3, 2]


# --- Telegram flow -------------------------------------------------------------

class Chat:
    """Collects what the bot sends so tests can follow its buttons."""

    def __init__(self, uid=1):
        self.uid = uid
        self.context = SimpleNamespace(user_data={}, args=[])
        self.sent = []

    def _record(self, text=None, reply_markup=None, **_):
        self.sent.append((text, reply_markup))
        return SimpleNamespace(delete=AsyncMock(), edit_text=AsyncMock())

    def message(self, text):
        msg = SimpleNamespace(text=text, caption=None, reply_text=AsyncMock(side_effect=self._record),
                              chat=SimpleNamespace(send_action=AsyncMock(), type='private'))
        return SimpleNamespace(effective_user=SimpleNamespace(id=self.uid, first_name='Ann', full_name='Ann', username=None),
                               effective_chat=SimpleNamespace(type='private'), effective_message=msg,
                               message=msg, callback_query=None)

    def tap(self, data):
        query = SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock(side_effect=self._record),
                                edit_message_reply_markup=AsyncMock())
        update = self.message(None)
        update.message, update.callback_query = None, query
        return update

    def buttons(self):
        markup = self.sent[-1][1]
        return [button.callback_data for row in markup.inline_keyboard for button in row]

    def last_text(self):
        return self.sent[-1][0]


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def chat(sessions, monkeypatch):
    monkeypatch.setattr(bot, 'allowed', lambda update: True)
    monkeypatch.setattr(bot, 'limiter', RateLimiter(sessions=sessions))
    analyser = SimpleNamespace(from_text=AsyncMock(return_value=HALF_RICE))
    monkeypatch.setattr(bot, 'MealAnalyzer', lambda: analyser)
    return Chat()


async def start_edit(chat, meal):
    await bot.text_message(chat.message('✏️ Edit meal'), chat.context)
    assert f'edit_meal:pick:{meal.id}' in chat.buttons()
    await bot.edit_meal_action(chat.tap(f'edit_meal:pick:{meal.id}'), chat.context)
    assert chat.context.user_data['waiting_for'] == f'edit_meal:{meal.id}'


@pytest.mark.anyio
async def test_edit_replaces_meal_and_keeps_its_type(chat, sessions):
    meal = save_lunch(tracker.get_user(1, 'Ann'))
    await start_edit(chat, meal)
    await bot.text_message(chat.message('chicken rice, half rice'), chat.context)
    assert chat.last_text().startswith('✏️ Editing a saved meal')
    assert chat.context.user_data['pending_meal_type'] == 'lunch'  # Preselected, so Save works straight away.

    await bot.meal_action(chat.tap('meal:save'), chat.context)
    assert chat.last_text().startswith('✅ Lunch updated')
    assert chat.buttons() == [f'edit_meal:pick:{meal.id}']
    assert meal_count(sessions) == 1
    assert tracker.get_meal(1, meal.id).estimated_calories == 450
    assert 'pending_edit_id' not in chat.context.user_data


@pytest.mark.anyio
async def test_editing_an_older_meal_totals_that_day(chat, sessions):
    user = tracker.get_user(1, 'Ann')
    meal = save_lunch(user)
    tracker.add_meal(user.id, RICE, 'dinner')  # Logged now, so it belongs to a later day.
    await start_edit(chat, meal)
    await bot.text_message(chat.message('chicken rice, half rice'), chat.context)
    await bot.meal_action(chat.tap('meal:save'), chat.context)
    # Only the edited lunch counts towards its own day, not today's dinner.
    assert '📋 Mon 12 Oct: 450 / ' in chat.last_text()


@pytest.mark.anyio
async def test_change_during_edit_still_replaces(chat, sessions):
    meal = save_lunch(tracker.get_user(1, 'Ann'))
    await start_edit(chat, meal)
    await bot.text_message(chat.message('chicken rice'), chat.context)
    await bot.meal_action(chat.tap('meal:edit'), chat.context)
    await bot.text_message(chat.message('chicken rice, half rice'), chat.context)
    await bot.meal_action(chat.tap('meal:save'), chat.context)
    assert meal_count(sessions) == 1
    assert tracker.get_meal(1, meal.id).estimated_calories == 450


@pytest.mark.anyio
async def test_starting_another_flow_abandons_the_edit(chat, sessions):
    meal = save_lunch(tracker.get_user(1, 'Ann'))
    await start_edit(chat, meal)
    # The edit estimate is on screen but never saved; the user logs something else instead.
    await bot.text_message(chat.message('chicken rice, half rice'), chat.context)
    assert chat.context.user_data['pending_edit_id'] == meal.id
    await bot.text_message(chat.message('🍽️ Log meal'), chat.context)
    await bot.text_message(chat.message('kaya toast'), chat.context)
    assert not chat.last_text().startswith('✏️')
    await bot.meal_action(chat.tap('meal:type:breakfast'), chat.context)
    await bot.meal_action(chat.tap('meal:save'), chat.context)
    assert meal_count(sessions) == 2
    assert tracker.get_meal(1, meal.id).estimated_calories == 600  # The original is untouched.


@pytest.mark.anyio
async def test_cancel_and_stale_buttons(chat, sessions):
    meal = save_lunch(tracker.get_user(1, 'Ann'))
    await start_edit(chat, meal)
    await bot.edit_meal_action(chat.tap('edit_meal:cancel'), chat.context)
    assert 'waiting_for' not in chat.context.user_data

    other = save_lunch(tracker.get_user(2, 'Ben'))
    await bot.edit_meal_action(chat.tap(f'edit_meal:pick:{other.id}'), chat.context)
    assert 'no longer exists' in chat.last_text()
    assert 'waiting_for' not in chat.context.user_data


@pytest.mark.anyio
async def test_meal_removed_mid_edit_is_not_recreated(chat, sessions):
    meal = save_lunch(tracker.get_user(1, 'Ann'))
    await start_edit(chat, meal)
    await bot.text_message(chat.message('chicken rice, half rice'), chat.context)
    tracker.delete_entry('meal', meal.id, tracker.get_user(1, 'Ann').id)
    await bot.meal_action(chat.tap('meal:save'), chat.context)
    assert 'removed' in chat.last_text()
    assert meal_count(sessions) == 0


@pytest.mark.anyio
async def test_no_meals_yet(chat):
    await bot.edit_meal_menu(chat.message('/edit'), chat.context)
    assert 'haven’t logged any meals' in chat.last_text()
