from datetime import date, datetime, timezone

from sqlalchemy import event, select

from app.models import Meal, MealReminder, Weight
from app.services import tracker

# Singapore (UTC+8) day of 12 Oct 2026, expressed in UTC as the bot stores it.
DAY = date(2026, 10, 12)
START = datetime(2026, 10, 11, 16, tzinfo=timezone.utc)
END = datetime(2026, 10, 12, 16, tzinfo=timezone.utc)


def add_meal(db, user, meal_type='lunch', at=datetime(2026, 10, 12, 4, tzinfo=timezone.utc)):
    db.add(Meal(user_id=user.id, description='Chicken rice', meal_type=meal_type, estimated_calories=600,
                protein_g=30, carbs_g=70, fat_g=20, recorded_at=at))
    db.commit()


def test_day_boundaries_include_start_and_exclude_end(sessions):
    user = tracker.get_user(1, 'Ann')
    with sessions() as db:
        add_meal(db, user, at=datetime(2026, 10, 11, 15, 59, tzinfo=timezone.utc))  # 23:59 the day before
        add_meal(db, user, at=START)                                                 # 00:00 local
        add_meal(db, user, at=datetime(2026, 10, 12, 15, 59, tzinfo=timezone.utc))  # 23:59 local
        add_meal(db, user, at=END)                                                   # 00:00 next day
    meals, weights = tracker.today_entries(user.id, START, END)
    assert len(meals) == 2
    assert weights == []


def test_get_user_creates_once(sessions):
    first = tracker.get_user(1, 'Ann')
    assert tracker.get_user(1, 'Someone else').id == first.id


def test_due_reminders_sent_once_and_only_when_meal_missing(sessions):
    ann, ben = tracker.get_user(1, 'Ann'), tracker.get_user(2, 'Ben')
    tracker.set_reminder(ann.id, 'breakfast', '08:00')
    tracker.set_reminder(ben.id, 'breakfast', '08:00')
    tracker.set_reminder(ann.id, 'lunch', '12:00')
    with sessions() as db:
        add_meal(db, ben, meal_type='breakfast')

    due = tracker.due_reminders(DAY, '08:00', START, END)
    assert [(telegram_id, meal) for _, telegram_id, meal in due] == [(1, 'breakfast')]
    # Ben already logged breakfast, so his reminder is marked handled without sending.
    with sessions() as db:
        ben_reminder = db.scalar(select(MealReminder).where(MealReminder.user_id == ben.id))
        assert ben_reminder.last_sent_on == DAY

    tracker.mark_reminder_sent(due[0][0], DAY)
    assert tracker.due_reminders(DAY, '08:00', START, END) == []
    assert tracker.due_reminders(DAY, '08:01', START, END) == []


def test_due_reminders_query_count_does_not_grow_with_reminders(sessions):
    engine = sessions.kw['bind']
    selects = []

    def count_select(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith('SELECT'):
            selects.append(statement)

    def selects_for(user_count):
        for uid in range(user_count):
            user = tracker.get_user(100 + uid + user_count * 1000, 'User')
            tracker.set_reminder(user.id, 'breakfast', f'07:{user_count:02d}')
        selects.clear()
        due = tracker.due_reminders(DAY, f'07:{user_count:02d}', START, END)
        assert len(due) == user_count
        return len(selects)

    event.listen(engine, 'before_cursor_execute', count_select)
    try:
        assert selects_for(1) == selects_for(10) == 1
    finally:
        event.remove(engine, 'before_cursor_execute', count_select)


def test_unsent_reminder_is_retried_and_reset_by_new_time(sessions):
    ann = tracker.get_user(1, 'Ann')
    tracker.set_reminder(ann.id, 'dinner', '19:00')
    # Not marked sent (e.g. Telegram failed), so the same minute finds it again.
    assert len(tracker.due_reminders(DAY, '19:00', START, END)) == 1
    reminder_id = tracker.due_reminders(DAY, '19:00', START, END)[0][0]
    tracker.mark_reminder_sent(reminder_id, DAY)
    tracker.set_reminder(ann.id, 'dinner', '19:30')
    assert len(tracker.due_reminders(DAY, '19:30', START, END)) == 1


def test_undo_removes_latest_entry_of_own_user_only(sessions):
    ann, ben = tracker.get_user(1, 'Ann'), tracker.get_user(2, 'Ben')
    with sessions() as db:
        add_meal(db, ann, at=datetime(2026, 10, 12, 4, tzinfo=timezone.utc))
        db.add(Weight(user_id=ann.id, weight_kg=60, recorded_at=datetime(2026, 10, 12, 5, tzinfo=timezone.utc)))
        db.commit()

    kind, entry = tracker.last_entry(ann.id)
    assert kind == 'weight'
    tracker.delete_entry(kind, entry.id, ben.id)  # Another user's ID must not delete it.
    assert tracker.last_entry(ann.id)[0] == 'weight'

    tracker.delete_entry(kind, entry.id, ann.id)
    assert tracker.last_entry(ann.id)[0] == 'meal'
    tracker.delete_entry('meal', tracker.last_entry(ann.id)[1].id, ann.id)
    assert tracker.last_entry(ann.id) is None
