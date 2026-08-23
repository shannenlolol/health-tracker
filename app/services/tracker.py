from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.config import settings
from app.db.database import SessionLocal
from app.models import Meal, User, Weight
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


def add_weight(user_id: int, kg: float) -> Weight:
    with SessionLocal() as db:
        entry = Weight(user_id=user_id, weight_kg=kg)
        db.add(entry)
        db.commit()
        return entry


def add_meal(user_id: int, estimate: MealEstimate, image_file_id: str | None = None) -> Meal:
    with SessionLocal() as db:
        meal = Meal(user_id=user_id, image_file_id=image_file_id, **estimate.model_dump())
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
