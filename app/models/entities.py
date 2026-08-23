from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    daily_calorie_target: Mapped[int] = mapped_column(Integer, default=2000)
    weights: Mapped[list["Weight"]] = relationship(cascade="all, delete-orphan")
    meals: Mapped[list["Meal"]] = relationship(cascade="all, delete-orphan")
    reminders: Mapped[list["MealReminder"]] = relationship(cascade="all, delete-orphan")


class Weight(Base):
    __tablename__ = "weights"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    weight_kg: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    description: Mapped[str] = mapped_column(String(500))
    meal_type: Mapped[str] = mapped_column(String(30), default="meal")
    estimated_calories: Mapped[int] = mapped_column(Integer)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    image_file_id: Mapped[str | None] = mapped_column(String(250), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MealReminder(Base):
    __tablename__ = "meal_reminders"
    __table_args__ = (UniqueConstraint("user_id", "meal_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    meal_type: Mapped[str] = mapped_column(String(30))
    reminder_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    last_sent_on: Mapped[date | None] = mapped_column(Date, nullable=True)
