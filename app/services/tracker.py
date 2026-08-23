from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.config import settings
from app.db.database import SessionLocal
from app.models import Meal, MealReminder, User, Weight
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


def due_reminders(local_date: date, local_time: str, start_utc: datetime, end_utc: datetime) -> list[tuple[int, int, str]]:
    due: list[tuple[int, int, str]] = []
    with SessionLocal() as db:
        reminders = db.scalars(
            select(MealReminder).where(
                MealReminder.reminder_time == local_time,
                (MealReminder.last_sent_on.is_(None) | (MealReminder.last_sent_on != local_date)),
            )
        )
        for reminder in reminders:
            already_logged = db.scalar(
                select(Meal.id).where(
                    Meal.user_id == reminder.user_id,
                    Meal.meal_type == reminder.meal_type,
                    Meal.recorded_at >= start_utc,
                    Meal.recorded_at < end_utc,
                ).limit(1)
            )
            if already_logged is None:
                telegram_user_id = db.scalar(select(User.telegram_user_id).where(User.id == reminder.user_id))
                if telegram_user_id is not None:
                    due.append((reminder.id, telegram_user_id, reminder.meal_type))
            else:
                reminder.last_sent_on = local_date
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


def add_meal(user_id: int, estimate: MealEstimate, meal_type: str, image_file_id: str | None = None) -> Meal:
    with SessionLocal() as db:
        meal = Meal(user_id=user_id, meal_type=meal_type, image_file_id=image_file_id, **estimate.model_dump())
        db.add(meal)
        db.commit()
        return meal


def today_entries(user_id: int, start_utc: datetime, end_utc: datetime) -> tuple[list[Meal], list[Weight]]:
    with SessionLocal() as db:
        meals = list(db.scalars(select(Meal).where(Meal.user_id == user_id, Meal.recorded_at >= start_utc, Meal.recorded_at < end_utc).order_by(Meal.recorded_at)))
        weights = list(db.scalars(select(Weight).where(Weight.user_id == user_id, Weight.recorded_at >= start_utc, Weight.recorded_at < end_utc).order_by(Weight.recorded_at)))
        return meals, weights


def progress_entries(user_id: int, days: int = 30) -> tuple[list[Meal], list[Weight]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with SessionLocal() as db:
        meals = list(db.scalars(select(Meal).where(Meal.user_id == user_id, Meal.recorded_at >= since).order_by(Meal.recorded_at)))
        weights = list(db.scalars(select(Weight).where(Weight.user_id == user_id, Weight.recorded_at >= since).order_by(Weight.recorded_at)))
        return meals, weights


def last_entry(user_id: int) -> tuple[str, Meal | Weight] | None:
    with SessionLocal() as db:
        meal = db.scalar(select(Meal).where(Meal.user_id == user_id).order_by(Meal.recorded_at.desc()).limit(1))
        weight = db.scalar(select(Weight).where(Weight.user_id == user_id).order_by(Weight.recorded_at.desc()).limit(1))
        if not meal and not weight:
            return None
        if meal and (not weight or meal.recorded_at >= weight.recorded_at):
            return "meal", meal
        return "weight", weight


def delete_entry(kind: str, entry_id: int, user_id: int) -> None:
    model = Meal if kind == "meal" else Weight
    with SessionLocal() as db:
        db.execute(delete(model).where(model.id == entry_id, model.user_id == user_id))
        db.commit()
