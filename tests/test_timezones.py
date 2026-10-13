"""Per-user timezones: lookup, local days, storage, reminders and the /timezone command."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot import bot
from app.config import settings
from app.services import tracker
from app.services.timezones import day_bounds, resolve_timezone

DEFAULT = settings.timezone  # Asia/Singapore unless TIMEZONE is set


@pytest.mark.parametrize('text, expected', [
    ('London', 'Europe/London'), ('  new   york ', 'America/New_York'), ('asia/tokyo', 'Asia/Tokyo'),
    ('Singapore', 'Asia/Singapore'), ('Kolkata', 'Asia/Kolkata'), ('buenos aires', 'America/Argentina/Buenos_Aires'),
    ('UTC', 'UTC'), ('Atlantis', None), ('', None),
])
def test_resolve_timezone(text, expected):
    assert resolve_timezone(text) == expected


def test_day_bounds_singapore():
    start, end = day_bounds('Asia/Singapore', datetime(2026, 10, 12, 20, tzinfo=timezone.utc))  # 04:00 on the 13th
    assert (start, end) == (datetime(2026, 10, 12, 16, tzinfo=timezone.utc), datetime(2026, 10, 13, 16, tzinfo=timezone.utc))


def test_day_bounds_on_daylight_saving_day_is_23_hours():
    # UK clocks go forward on 29 March 2026, so that local day is only 23 hours long.
    start, end = day_bounds('Europe/London', datetime(2026, 3, 29, 12, tzinfo=timezone.utc))
    assert start == datetime(2026, 3, 29, 0, tzinfo=timezone.utc)
    assert end - start == timedelta(hours=23)


def test_timezone_storage_and_default(sessions):
    ann = tracker.get_user(1, 'Ann')
    assert tracker.timezone_for(ann.id) == DEFAULT
    tracker.set_timezone(ann.id, 'Europe/London')
    tracker.set_timezone(ann.id, 'Asia/Tokyo')  # Updates the existing row.
    assert tracker.timezone_for(ann.id) == 'Asia/Tokyo'
    assert tracker.timezones_in_use() == {DEFAULT, 'Asia/Tokyo'}
    tracker.set_timezone(ann.id, DEFAULT)  # Choosing the default removes the row.
    assert tracker.timezones_in_use() == {DEFAULT}
    tracker.set_timezone(ann.id, 'Asia/Tokyo')
    tracker.set_timezone(ann.id, None)
    assert tracker.timezone_for(ann.id) == DEFAULT


def test_due_reminders_only_for_the_given_timezone(sessions):
    ann, ben = tracker.get_user(1, 'Ann'), tracker.get_user(2, 'Ben')
    tracker.set_timezone(ben.id, 'Europe/London')
    for user in (ann, ben):
        tracker.set_reminder(user.id, 'breakfast', '08:00')
    bounds = (datetime(2026, 10, 11, 16, tzinfo=timezone.utc), datetime(2026, 10, 12, 16, tzinfo=timezone.utc))
    day = datetime(2026, 10, 12).date()
    assert [due[1] for due in tracker.due_reminders(day, '08:00', *bounds)] == [1]
    assert [due[1] for due in tracker.due_reminders(day, '08:00', *bounds, 'Europe/London')] == [2]


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_reminders_arrive_at_each_users_local_time(sessions, monkeypatch):
    monkeypatch.setattr(bot, 'has_access', lambda uid: True)
    ann, ben = tracker.get_user(1, 'Ann'), tracker.get_user(2, 'Ben')
    tracker.set_timezone(ben.id, 'Europe/London')
    for user in (ann, ben):
        tracker.set_reminder(user.id, 'breakfast', '08:00')
    application = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    def recipients():
        return [call.args[0] for call in application.bot.send_message.await_args_list]

    await bot.send_due_reminders(application, datetime(2026, 10, 12, 0, tzinfo=timezone.utc))  # 08:00 Singapore
    assert recipients() == [1]
    await bot.send_due_reminders(application, datetime(2026, 10, 12, 7, tzinfo=timezone.utc))  # 08:00 London (BST)
    assert recipients() == [1, 2]
    await bot.send_due_reminders(application, datetime(2026, 10, 12, 7, tzinfo=timezone.utc))  # Not sent twice.
    assert recipients() == [1, 2]


def command_update(text=None, data=None):
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    query = SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock()) if data else None
    return SimpleNamespace(effective_user=SimpleNamespace(id=1, first_name='Ann'), effective_chat=SimpleNamespace(type='private'),
                           effective_message=message, message=None if data else message, callback_query=query)


@pytest.mark.anyio
async def test_timezone_command_typed_and_buttons(sessions, monkeypatch):
    monkeypatch.setattr(bot, 'allowed', lambda update: True)
    context = SimpleNamespace(user_data={}, args=[])
    await bot.timezone_command(command_update('/timezone'), context)
    assert context.user_data['waiting_for'] == 'timezone'

    update = command_update('Atlantis')
    await bot.text_message(update, context)
    assert 'don’t recognise' in update.message.reply_text.await_args.args[0]
    assert context.user_data['waiting_for'] == 'timezone'  # Still waiting for a valid place.

    update = command_update('london')
    await bot.text_message(update, context)
    assert 'Europe/London' in update.message.reply_text.await_args.args[0]
    assert tracker.timezone_for(tracker.get_user(1, 'Ann').id) == 'Europe/London'
    assert 'waiting_for' not in context.user_data

    await bot.timezone_action(command_update(data='tz:set:Asia/Tokyo'), context)
    assert tracker.timezone_for(1) == 'Asia/Tokyo'
    await bot.timezone_action(command_update(data='tz:default'), context)
    assert tracker.timezone_for(1) == DEFAULT


@pytest.mark.anyio
async def test_forged_timezone_button_is_not_stored(sessions, monkeypatch):
    monkeypatch.setattr(bot, 'allowed', lambda update: True)
    await bot.timezone_action(command_update(data='tz:set:Europe/Paris'), SimpleNamespace(user_data={}))
    assert tracker.timezones_in_use() == {DEFAULT}
