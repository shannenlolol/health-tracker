"""Progress chart layout: readable date labels and an unobstructed goal line."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from app.bot import bot
from app.models import Meal, Weight
from app.services import tracker
from app.services.progress import build_chart

END = datetime(2026, 10, 13, 4, tzinfo=timezone.utc)  # Ranges below cross the 1 October boundary.


def entries(days, kcal=1500):
    meals = [SimpleNamespace(recorded_at=END - timedelta(days=d), estimated_calories=kcal) for d in range(days)]
    weights = [SimpleNamespace(recorded_at=END - timedelta(days=d), weight_kg=70 + d * 0.05) for d in range(0, days, 2)]
    return meals, weights


def drawn(days, kcal=1500, target=2000):
    fig = build_chart(*entries(days, kcal), 'Asia/Singapore', target)
    FigureCanvasAgg(fig).draw()
    return fig.axes


@pytest.mark.parametrize('days', [1, 3, 10, 30])
def test_date_labels_are_unique_and_evenly_spaced(days):
    for axis in drawn(days):
        labels = [label.get_text() for label in axis.get_xticklabels() if label.get_text()]
        assert len(labels) == len(set(labels)), labels  # No repeated dates (hourly ticks).
        assert 1 <= len(labels) <= 7, labels
        ticks = axis.get_xticks()
        gaps = {round(b - a, 6) for a, b in zip(ticks, ticks[1:], strict=False)}
        assert len(gaps) <= 1, labels  # Even spacing: no "29 Sep" right before "01 Oct".


@pytest.mark.parametrize('kcal', [1500, 2400])
def test_goal_is_named_in_title_without_a_legend(kcal):
    _, calorie_axis = drawn(30, kcal, target=1800)
    assert '1,800 kcal goal' in calorie_axis.get_title(loc='left')
    assert calorie_axis.get_legend() is None


def test_empty_chart_still_renders():
    _, calorie_axis = drawn(0)
    assert '2,000 kcal goal' in calorie_axis.get_title(loc='left')


@pytest.mark.parametrize('days', [120, 400, 1100])
def test_long_ranges_label_months_without_crowding(days):
    for axis in drawn(days):
        labels = [label.get_text() for label in axis.get_xticklabels() if label.get_text()]
        assert len(labels) == len(set(labels)), labels
        assert 1 <= len(labels) <= 7, labels
        assert all(label[-4:].isdigit() for label in labels), labels  # "Mar 2026", so years are clear.


def test_titles_name_the_chosen_period():
    fig = build_chart(*entries(7), 'Asia/Singapore', 2000, 'last 7 days')
    weight_axis, calorie_axis = fig.axes
    assert weight_axis.get_title(loc='left') == 'Weight — last 7 days'
    assert calorie_axis.get_title(loc='left').startswith('Daily calories — last 7 days')


# --- Range choice ----------------------------------------------------------------

@pytest.fixture
def anyio_backend():
    return 'asyncio'


def store(sessions, days_ago):
    user = tracker.get_user(1, 'Ann')
    with sessions() as db:
        for d in days_ago:
            when = datetime.now(timezone.utc) - timedelta(days=d)
            db.add(Meal(user_id=user.id, description='Rice', meal_type='lunch', estimated_calories=500,
                        protein_g=10, carbs_g=80, fat_g=5, recorded_at=when))
            db.add(Weight(user_id=user.id, weight_kg=70 - d / 100, recorded_at=when))
        db.commit()
    return user


@pytest.mark.parametrize(('days', 'expected'), [(7, 2), (30, 3), (None, 4)])
def test_progress_entries_follow_the_range(sessions, days, expected):
    user = store(sessions, [1, 5, 20, 400])
    meals, weights = tracker.progress_entries(user.id, days)
    assert len(meals) == len(weights) == expected
    assert [m.recorded_at for m in meals] == sorted(m.recorded_at for m in meals)


def fake_update(data=None):
    message = SimpleNamespace(reply_text=AsyncMock(), reply_photo=AsyncMock(), delete=AsyncMock(),
                              chat=SimpleNamespace(send_action=AsyncMock(), type='private'))
    query = SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock(), message=message) if data else None
    return SimpleNamespace(effective_user=SimpleNamespace(id=1, first_name='Ann', full_name='Ann', username=None),
                           effective_chat=SimpleNamespace(type='private'), effective_message=message,
                           message=None if data else message, callback_query=query)


@pytest.mark.anyio
async def test_progress_asks_for_a_range_first(sessions, monkeypatch):
    monkeypatch.setattr(bot, 'allowed', lambda update: True)
    update = fake_update()
    await bot.progress(update, SimpleNamespace(user_data={}))
    update.message.reply_photo.assert_not_awaited()
    markup = update.message.reply_text.await_args.kwargs['reply_markup']
    assert [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row] == [
        ('7 days', 'progress:7'), ('30 days', 'progress:30'), ('All time', 'progress:all'),
    ]


@pytest.mark.anyio
async def test_choosing_all_time_sends_every_entry(sessions, monkeypatch):
    monkeypatch.setattr(bot, 'allowed', lambda update: True)
    store(sessions, [1, 400])
    charted = {}
    monkeypatch.setattr(bot, 'make_chart', lambda meals, weights, tz, target, period: charted.update(
        meals=len(meals), period=period) or b'png')
    update = fake_update('progress:all')
    await bot.progress_action(update, SimpleNamespace(user_data={}))
    assert charted == {'meals': 2, 'period': 'all time'}
    caption = update.effective_message.reply_photo.await_args.kwargs['caption']
    assert caption.startswith('📈 All time\nWeight change: ')
    update.callback_query.message.delete.assert_awaited_once()  # The question is replaced by the chart.
