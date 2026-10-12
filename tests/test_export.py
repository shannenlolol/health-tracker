"""Personal data export: CSV content, spreadsheet safety and the /export command."""
import csv
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot import bot
from app.models import Meal, Weight
from app.services import tracker
from app.services.export import export_csv
from app.services.meal_analyzer import MealEstimate


def meal(description='Chicken rice', at=datetime(2026, 10, 12, 4, tzinfo=timezone.utc), meal_type='lunch'):
    return Meal(description=description, meal_type=meal_type, estimated_calories=600,
                protein_g=30, carbs_g=70.5, fat_g=20, recorded_at=at)


def read(output):
    raw = output.getvalue()
    assert raw.startswith(b'\xef\xbb\xbf')  # UTF-8 byte-order mark for Excel.
    return list(csv.reader(StringIO(raw.decode('utf-8-sig'))))


def test_rows_are_merged_in_local_time_order():
    weight = Weight(weight_kg=60.2, recorded_at=datetime(2026, 10, 12, 0, 30, tzinfo=timezone.utc))
    # Naive values are how SQLite returns stored UTC times.
    dinner = meal('Laksa', datetime(2026, 10, 12, 11), 'dinner')
    rows = read(export_csv([meal(), dinner], [weight], 'Asia/Singapore'))
    assert rows[0][:2] == ['Type', 'Date and time']
    assert rows[1:] == [
        ['Weight', '2026-10-12 08:30', '', '', '', '', '', '', '60.2'],
        ['Meal', '2026-10-12 12:00', 'Lunch', 'Chicken rice', '600', '30', '70.5', '20', ''],
        ['Meal', '2026-10-12 19:00', 'Dinner', 'Laksa', '600', '30', '70.5', '20', ''],
    ]


@pytest.mark.parametrize('description', ['=HYPERLINK("http://x")', '+1', '-2 eggs', '@SUM(A1)'])
def test_formula_like_descriptions_stay_text(description):
    rows = read(export_csv([meal(description)], [], 'Asia/Singapore'))
    assert rows[1][3] == "'" + description


def test_commas_quotes_and_non_ascii_survive():
    description = 'Nasi lemak, "extra" sambal — 椰浆饭'
    rows = read(export_csv([meal(description)], [], 'Asia/Singapore'))
    assert rows[1][3] == description


def test_all_entries_returns_only_own_data(sessions):
    ann, ben = tracker.get_user(1, 'Ann'), tracker.get_user(2, 'Ben')
    estimate = MealEstimate(description='Toast', estimated_calories=200, protein_g=5, carbs_g=30, fat_g=5)
    tracker.add_meal(ann.id, estimate, 'breakfast')
    tracker.add_meal(ben.id, estimate, 'breakfast')
    tracker.add_weight(ann.id, 60)
    meals, weights = tracker.all_entries(ann.id)
    assert (len(meals), len(weights)) == (1, 1)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def export_update(uid=1):
    message = SimpleNamespace(reply_text=AsyncMock(), reply_document=AsyncMock(),
                              chat=SimpleNamespace(send_action=AsyncMock()))
    return SimpleNamespace(effective_user=SimpleNamespace(id=uid, first_name='Ann'),
                           effective_chat=SimpleNamespace(type='private'), effective_message=message, message=message)


@pytest.mark.anyio
async def test_export_command_sends_file(sessions, monkeypatch):
    monkeypatch.setattr(bot, 'allowed', lambda update: True)
    user = tracker.get_user(1, 'Ann')
    tracker.add_weight(user.id, 60)
    update = export_update()
    await bot.export_data(update, SimpleNamespace(user_data={'waiting_for': 'weight'}))
    document = update.effective_message.reply_document.await_args
    assert document.kwargs['filename'].startswith('health-tracker-')
    assert '0 meals and 1 weight entry.' in document.kwargs['caption']
    assert read(document.args[0])[1][0] == 'Weight'


@pytest.mark.anyio
async def test_export_with_no_data(sessions, monkeypatch):
    monkeypatch.setattr(bot, 'allowed', lambda update: True)
    update = export_update()
    await bot.export_data(update, SimpleNamespace(user_data={}))
    update.effective_message.reply_document.assert_not_awaited()
    assert 'nothing to export' in update.effective_message.reply_text.await_args.args[0]
