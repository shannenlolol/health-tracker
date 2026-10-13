from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.config import settings
from app.db.database import SessionLocal
from app.models import Meal, MealReminder, User, Weight
from app.models.entities import UserTimezone
from app.services.meal_analyzer import MealEstimate


def get_user(telegram_user_id: int, name: str) -> User:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
        if not user:
            user = User(telegram_user_id=telegram_user_id, name=name, daily_calorie_target=settings.daily_calorie_target)
            db.add(user)
            db.commit()
        return user


def update_calorie_target(user_id: int, daily_calorie_target: int) -> User:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            raise ValueError("User not found")
        user.daily_calorie_target = daily_calorie_target
        db.commit()
        return user


def reminder_settings(user_id: int) -> dict[str, str | None]:
    settings_by_meal = {"breakfast": None, "lunch": None, "dinner": None}
    with SessionLocal() as db:
        reminders = db.scalars(select(MealReminder).where(MealReminder.user_id == user_id))
        for reminder in reminders:
            settings_by_meal[reminder.meal_type] = reminder.reminder_time
    return settings_by_meal


def set_reminder(user_id: int, meal_type: str, reminder_time: str | None) -> None:
    with SessionLocal() as db:
        reminder = db.scalar(
            select(MealReminder).where(
                MealReminder.user_id == user_id,
                MealReminder.meal_type == meal_type,
            )
        )
        if reminder is None:
            reminder = MealReminder(user_id=user_id, meal_type=meal_type)
            db.add(reminder)
        reminder.reminder_time = reminder_time
        reminder.last_sent_on = None
        db.commit()


def timezone_for(user_id: int) -> str:
    with SessionLocal() as db:
        row = db.get(UserTimezone, user_id)
        return row.timezone if row else settings.timezone


def set_timezone(user_id: int, timezone_name: str | None) -> None:
    """Store a user's timezone; None returns them to the bot-wide default."""
    with SessionLocal() as db:
        row = db.get(UserTimezone, user_id)
        if timezone_name is None or timezone_name == settings.timezone:
            if row:
                db.delete(row)
        elif row:
            row.timezone = timezone_name
        else:
            db.add(UserTimezone(user_id=user_id, timezone=timezone_name))
        db.commit()


def timezones_in_use() -> set[str]:
    with SessionLocal() as db:
        return {settings.timezone, *db.scalars(select(UserTimezone.timezone).distinct())}


def due_reminders(local_date: date, local_time: str, start_utc: datetime, end_utc: datetime,
                  timezone_name: str | None = None) -> list[tuple[int, int, str]]:
    """Find reminders for this local minute that still need a meal log.

    Only users in `timezone_name` (default: the bot-wide timezone) are checked,
    because the date, time and day bounds are local to that timezone.

    The query uses UTC bounds because meal timestamps are stored in UTC.
    Suppressed reminders are marked handled here; delivered reminders are marked
    only after Telegram accepts them, so failed sends aren't recorded as sent.
    """
    due: list[tuple[int, int, str]] = []
    # One query for all reminders: join the owner's Telegram ID and check for a
    # matching meal with a correlated EXISTS, instead of two queries per reminder.
    already_logged = (
        select(Meal.id).where(
            Meal.user_id == MealReminder.user_id,
            Meal.meal_type == MealReminder.meal_type,
            Meal.recorded_at >= start_utc,
            Meal.recorded_at < end_utc,
        ).exists()
    )
    with SessionLocal() as db:
        rows = db.execute(
            select(MealReminder, User.telegram_user_id, already_logged)
            .join(User, User.id == MealReminder.user_id)
            .outerjoin(UserTimezone, UserTimezone.user_id == MealReminder.user_id)
            .where(
                func.coalesce(UserTimezone.timezone, settings.timezone) == (timezone_name or settings.timezone),
                MealReminder.reminder_time == local_time,
                (MealReminder.last_sent_on.is_(None) | (MealReminder.last_sent_on != local_date)),
            )
        )
        for reminder, telegram_user_id, logged in rows:
            if logged:
                reminder.last_sent_on = local_date
            else:
                due.append((reminder.id, telegram_user_id, reminder.meal_type))
        db.commit()
    return due


def mark_reminder_sent(reminder_id: int, sent_on: date) -> None:
    with SessionLocal() as db:
        reminder = db.get(MealReminder, reminder_id)
        if reminder is not None:
            reminder.last_sent_on = sent_on
            db.commit()


def add_weight(user_id: int, kg: float) -> Weight:
    with SessionLocal() as db:
        entry = Weight(user_id=user_id, weight_kg=kg)
        db.add(entry)
        db.commit()
        return entry


def log_weight(user_id: int, kg: float, start_utc: datetime, end_utc: datetime) -> tuple[Weight, float | None]:
    """Save the day's weight, replacing the latest one already logged between the two times.

    Keeping one weight per day lets a typo be fixed by logging again. Returns the
    entry and the weight it replaced, or None if it is the day's first.
    """
    with SessionLocal() as db:
        entry = db.scalar(
            select(Weight)
            .where(Weight.user_id == user_id, Weight.recorded_at >= start_utc, Weight.recorded_at < end_utc)
            .order_by(Weight.recorded_at.desc())
            .limit(1)
        )
        previous = entry.weight_kg if entry else None
        if entry is None:
            entry = Weight(user_id=user_id, weight_kg=kg)
            db.add(entry)
        else:
            entry.weight_kg = kg
            entry.recorded_at = datetime.now(timezone.utc)
        db.commit()
        return entry, previous


def add_meal(user_id: int, estimate: MealEstimate, meal_type: str, image_file_id: str | None = None) -> Meal:
    with SessionLocal() as db:
        meal = Meal(user_id=user_id, meal_type=meal_type, image_file_id=image_file_id, **estimate.model_dump())
        db.add(meal)
        db.commit()
        return meal


def recent_meals(user_id: int, limit: int = 5) -> list[Meal]:
    with SessionLocal() as db:
        return list(db.scalars(select(Meal).where(Meal.user_id == user_id).order_by(Meal.recorded_at.desc()).limit(limit)))


def get_meal(user_id: int, meal_id: int) -> Meal | None:
    """Return the meal only if it belongs to this user; button data can't be trusted."""
    with SessionLocal() as db:
        return db.scalar(select(Meal).where(Meal.id == meal_id, Meal.user_id == user_id))


def update_meal(user_id: int, meal_id: int, estimate: MealEstimate, meal_type: str) -> Meal | None:
    """Replace a saved meal's estimate, keeping its original time and photo.

    Returns None if the meal was deleted while being edited.
    """
    with SessionLocal() as db:
        meal = db.scalar(select(Meal).where(Meal.id == meal_id, Meal.user_id == user_id))
        if meal is None:
            return None
        for field, value in estimate.model_dump().items():
            setattr(meal, field, value)
        meal.meal_type = meal_type
        db.commit()
        return meal


def today_entries(user_id: int, start_utc: datetime, end_utc: datetime) -> tuple[list[Meal], list[Weight]]:
    with SessionLocal() as db:
        meals = list(db.scalars(select(Meal).where(Meal.user_id == user_id, Meal.recorded_at >= start_utc, Meal.recorded_at < end_utc).order_by(Meal.recorded_at)))
        weights = list(db.scalars(select(Weight).where(Weight.user_id == user_id, Weight.recorded_at >= start_utc, Weight.recorded_at < end_utc).order_by(Weight.recorded_at)))
        return meals, weights


def progress_entries(user_id: int, days: int | None = 30) -> tuple[list[Meal], list[Weight]]:
    """Entries from the last `days` days, or every entry when `days` is None."""
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    def entries(model):
        query = select(model).where(model.user_id == user_id).order_by(model.recorded_at)
        return query.where(model.recorded_at >= since) if since else query

    with SessionLocal() as db:
        return list(db.scalars(entries(Meal))), list(db.scalars(entries(Weight)))


def all_entries(user_id: int) -> tuple[list[Meal], list[Weight]]:
    with SessionLocal() as db:
        meals = list(db.scalars(select(Meal).where(Meal.user_id == user_id).order_by(Meal.recorded_at)))
        weights = list(db.scalars(select(Weight).where(Weight.user_id == user_id).order_by(Weight.recorded_at)))
        return meals, weights


def delete_entry(kind: str, entry_id: int, user_id: int) -> bool:
    """Delete one of the user's own entries; False if it was already gone or belongs to someone else."""
    model = Meal if kind == "meal" else Weight
    with SessionLocal() as db:
        deleted = db.execute(delete(model).where(model.id == entry_id, model.user_id == user_id)).rowcount
        db.commit()
        return bool(deleted)
