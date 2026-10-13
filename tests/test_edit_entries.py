"""Editing saved meals and weights: storage rules and the full Telegram flow, with OpenAI mocked."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.bot import bot
from app.models import Meal, Weight
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


def save_weight(user, kg=62.4, hour=1):
    entry = tracker.add_weight(user.id, kg)
    with tracker.SessionLocal() as db:
        db.get(Weight, entry.id).recorded_at = datetime(2026, 10, 12, hour, tzinfo=timezone.utc)
        db.commit()
    return entry


def test_recent_entries_mix_meals_and_weights_newest_first(sessions):
    user = tracker.get_user(1, 'Ann')
    for hour in range(0, 10, 2):
        meal = tracker.add_meal(user.id, RICE, 'snack')
        with tracker.SessionLocal() as db:
            db.get(Meal, meal.id).recorded_at = datetime(2026, 10, 12, hour, tzinfo=timezone.utc)
            db.commit()
        save_weight(user, hour=hour + 1)
    save_weight(tracker.get_user(2, 'Ben'), hour=23)  # Someone else's entry never appears.
    entries = tracker.recent_entries(user.id, limit=4)
    assert [(kind, entry.recorded_at.hour) for kind, entry in entries] == [
        ('weight', 9), ('meal', 8), ('weight', 7), ('meal', 6),
    ]


def test_weights_can_be_corrected_and_deleted_by_their_owner_only(sessions):
    ann, ben = tracker.get_user(1, 'Ann'), tracker.get_user(2, 'Ben')
    entry = save_weight(ann, 64.2)
    assert tracker.get_weight(ben.id, entry.id) is None
    assert tracker.update_weight(ben.id, entry.id, 50) is None
    assert tracker.update_weight(ann.id, entry.id, 62.4).weight_kg == 62.4
    assert tracker.get_weight(ann.id, entry.id).recorded_at.hour == 1  # The original time is kept.
    assert tracker.delete_entry('weight', entry.id, ben.id) is False
    assert tracker.delete_entry('weight', entry.id, ann.id) is True
    assert tracker.delete_entry('weight', entry.id, ann.id) is False
    assert tracker.update_weight(ann.id, entry.id, 62.4) is None


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
    await bot.text_message(chat.message('✏️ Edit entries'), chat.context)
    assert f'edit_meal:pick:{meal.id}' in chat.buttons()
    await bot.edit_entry_action(chat.tap(f'edit_meal:pick:{meal.id}'), chat.context)
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
    await bot.edit_entry_action(chat.tap('edit_meal:cancel'), chat.context)
    assert 'waiting_for' not in chat.context.user_data

    other = save_lunch(tracker.get_user(2, 'Ben'))
    await bot.edit_entry_action(chat.tap(f'edit_meal:pick:{other.id}'), chat.context)
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
async def test_nothing_logged_yet(chat):
    await bot.edit_entries_menu(chat.message('/edit'), chat.context)
    assert 'haven’t logged any meals or weights' in chat.last_text()


@pytest.mark.anyio
async def test_menu_lists_weights_alongside_meals(chat, sessions):
    ann = tracker.get_user(1, 'Ann')
    meal, weight = save_lunch(ann), save_weight(ann, hour=6)
    await bot.text_message(chat.message('✏️ Edit entries'), chat.context)
    assert chat.buttons() == [f'edit_weight:pick:{weight.id}', f'edit_meal:pick:{meal.id}', 'edit_meal:cancel']


@pytest.mark.anyio
async def test_correct_a_weight(chat, sessions):
    weight = save_weight(tracker.get_user(1, 'Ann'), 64.2)
    await bot.edit_entry_action(chat.tap(f'edit_weight:pick:{weight.id}'), chat.context)
    assert chat.context.user_data['waiting_for'] == f'edit_weight:{weight.id}'
    assert chat.buttons() == [f'edit_weight:delete:{weight.id}', 'edit_meal:cancel']

    await bot.text_message(chat.message('abc'), chat.context)  # Invalid input keeps waiting.
    assert 'doesn’t look right' in chat.last_text()
    await bot.text_message(chat.message('62.4'), chat.context)
    assert chat.last_text() == '✅ Weight updated: 62.4 kg (was 64.2 kg)'
    assert 'waiting_for' not in chat.context.user_data
    assert tracker.get_weight(1, weight.id).weight_kg == 62.4


@pytest.mark.anyio
@pytest.mark.parametrize('kind', ['meal', 'weight'])
async def test_delete_asks_first_then_removes(chat, sessions, kind):
    ann = tracker.get_user(1, 'Ann')
    entry = save_lunch(ann) if kind == 'meal' else save_weight(ann)
    await bot.edit_entry_action(chat.tap(f'edit_{kind}:pick:{entry.id}'), chat.context)
    await bot.edit_entry_action(chat.tap(f'edit_{kind}:delete:{entry.id}'), chat.context)
    assert chat.last_text().startswith('🗑️ Delete this entry?')
    assert chat.buttons() == [f'edit_{kind}:confirm:{entry.id}', 'edit_meal:cancel']
    assert 'waiting_for' not in chat.context.user_data  # Typing now must not edit the entry.

    await bot.edit_entry_action(chat.tap(f'edit_{kind}:confirm:{entry.id}'), chat.context)
    assert chat.last_text().startswith('🗑️ Deleted:')
    assert bot.ENTRY_GETTERS[kind](ann.id, entry.id) is None

    # A second tap on the old confirm button finds nothing to delete.
    await bot.edit_entry_action(chat.tap(f'edit_{kind}:confirm:{entry.id}'), chat.context)
    assert 'no longer exists' in chat.last_text()


@pytest.mark.anyio
async def test_keeping_an_entry_changes_nothing(chat, sessions):
    meal = save_lunch(tracker.get_user(1, 'Ann'))
    await bot.edit_entry_action(chat.tap(f'edit_meal:delete:{meal.id}'), chat.context)
    await bot.edit_entry_action(chat.tap('edit_meal:cancel'), chat.context)
    assert chat.last_text() == 'Nothing was changed.'
    assert meal_count(sessions) == 1


@pytest.mark.anyio
@pytest.mark.parametrize('button', ['✏️ Edit meal', '↩️ Undo'])
async def test_old_menu_buttons_open_edit_entries_not_the_ai(chat, sessions, button):
    save_lunch(tracker.get_user(1, 'Ann'))
    await bot.text_message(chat.message(button), chat.context)
    assert chat.last_text().startswith('✏️ Which entry')
    bot.MealAnalyzer().from_text.assert_not_awaited()


def test_menu_has_download_instead_of_undo():
    from app.bot.keyboards import MENU
    labels = [str(button.text) for row in MENU.keyboard for button in row]
    assert '📥 Download' in labels and '✏️ Edit entries' in labels
    assert '↩️ Undo' not in labels and '✏️ Edit meal' not in labels
