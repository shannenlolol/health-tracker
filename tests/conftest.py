"""Shared pytest setup. Runs before any app module reads its settings."""
import os

# Assign rather than setdefault: a developer's shell or .env must never point
# the tests at the real NAS database or a real bot/OpenAI account.
os.environ.update({
    'DATABASE_URL': 'sqlite://',
    'TELEGRAM_BOT_TOKEN': '123:test',
    'OPENAI_API_KEY': 'test-key',
    'ADMIN_TELEGRAM_USER_IDS': '999',
    'ALLOWED_TELEGRAM_USER_IDS': '',
    'ALLOWED_TELEGRAM_USER_ID': '',
    'MPLCONFIGDIR': '/tmp/health-tracker-test-matplotlib',
    'XDG_CACHE_HOME': '/tmp/health-tracker-test-cache',
})

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.services import access, tracker
from app.services.rate_limit import RateLimiter


@pytest.fixture
def sessions(monkeypatch):
    """A fresh in-memory database wired into the tracker and access services."""
    # StaticPool keeps one connection, so every session sees the same in-memory database.
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(tracker, 'SessionLocal', factory)
    monkeypatch.setattr(access, 'SessionLocal', factory)
    monkeypatch.setattr(access, 'limiter', RateLimiter(sessions=factory))
    yield factory
    engine.dispose()
