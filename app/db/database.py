from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    from app.models.entities import AccessMigration, AccessRequest, AllowedUser, Meal, MealReminder, User, Weight  # noqa: F401

    # Access control uses new tables, leaving existing health-table columns and
    # rows intact. create_all creates missing tables; it isn't a schema migrator.
    Base.metadata.create_all(engine)

    from app.services.access import initialize_access

    initialize_access()
