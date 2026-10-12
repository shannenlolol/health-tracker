"""Single-process throttles with durable quotas and injectable clocks.

The bot runs in one container. The lock serialises reservations made by worker
threads; running multiple bot processes would require database-level locking.
"""
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import RLock
from time import monotonic
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select

from app.config import settings
from app.db.database import SessionLocal
from app.models.entities import AccessAttempt, AccessRequest, AccessRequestTiming, UsageCounter


class LimitExceeded(Exception):
    pass


class RateLimiter:
    def __init__(self, config=settings, sessions=SessionLocal, clock=monotonic,
                 utcnow=lambda: datetime.now(timezone.utc)):
        self.config = config
        self.sessions = sessions
        self.clock = clock
        self.utcnow = utcnow
        self.lock = RLock()
        self.windows = {}
        self.next_sweep = 0
        self.blocked = {}
        self.active = set()
        self.alert_started = None
        self.alert_count = 0

    def _window(self, key, limit, seconds, consume=True):
        now = self.clock()
        # Expired keys are removed, and new identities fail closed at capacity
        # rather than evicting active limits during a many-account flood.
        if now >= self.next_sweep:
            self.windows = {key: entry for key, entry in self.windows.items() if entry[0] > now}
            self.next_sweep = now + 1
        entry = self.windows.get(key)
        if entry is None and len(self.windows) >= 10000:
            return False
        events = entry[1] if entry else deque()
        while events and events[0] <= now - seconds:
            events.popleft()
        if len(events) >= limit:
            return False
        if consume:
            events.append(now)
            self.windows[key] = (now + seconds, events)
        return True

    def message(self, uid):
        """Return allow, warn once, or silently drop during the block."""
        if uid in self.config.admin_telegram_user_ids:
            return "allow"
        with self.lock:
            now = self.clock()
            self.blocked = {key: end for key, end in self.blocked.items() if end > now}
            if uid in self.blocked:
                return "drop"
            if self._window(("message", uid), self.config.message_limit, self.config.message_window_seconds):
                return "allow"
            if len(self.blocked) >= 10000:
                return "drop"
            self.blocked[uid] = now + self.config.message_block_seconds
            return "warn"

    def access_reply(self, uid):
        with self.lock:
            return self._window(("access_reply", uid), 1, self.config.access_reply_seconds)

    def control_reply(self, uid, kind):
        # Explicit sign-up and /myid controls each get one reply per window so
        # they remain usable immediately after the initial access prompt.
        if uid in self.config.admin_telegram_user_ids:
            return True
        with self.lock:
            return self._window((kind, uid), 1, self.config.access_reply_seconds)

    def access_silenced(self, uid):
        with self.lock:
            entry = self.windows.get(("access_reply", uid))
            return bool(entry and entry[0] > self.clock())

    def clear_access_silence(self, uid):
        with self.lock:
            for kind in ("access_reply", "request_reply", "myid_reply"):
                self.windows.pop((kind, uid), None)

    def begin_ai(self, uid, kind, content):
        cfg = self.config
        maximum = cfg.meal_caption_max_chars if kind == "photo" else cfg.meal_text_max_chars
        if len(content) > maximum:
            raise LimitExceeded(f"Please keep it to {maximum} characters or fewer, e.g. 'chicken rice, less rice'.")
        with self.lock:
            if uid in self.active:
                raise LimitExceeded("Still working on your last meal…")
            if len(self.active) >= cfg.ai_max_concurrent:
                raise LimitExceeded("Meal estimates are busy. Please try again in a moment.")
            admin = uid in cfg.admin_telegram_user_ids
            minute_limit = getattr(cfg, f"ai_{kind}_per_minute")
            daily_limit = getattr(cfg, f"ai_{kind}_per_day")
            if not admin and not self._window((kind, uid), minute_limit, 60, consume=False):
                raise LimitExceeded("Too many meal estimates this minute. Please try again shortly.")
            day = self.utcnow().astimezone(ZoneInfo(cfg.timezone)).date()
            with self.sessions.begin() as db:
                # Keep only current quota state, not a permanent usage history.
                db.execute(delete(UsageCounter).where(UsageCounter.day < day))
                total = db.get(UsageCounter, (0, day, "ai"))
                if total and total.count >= cfg.ai_global_per_day:
                    raise LimitExceeded("Meal estimates are paused until tomorrow.")
                user = db.get(UsageCounter, (uid, day, kind))
                if not admin and user and user.count >= daily_limit:
                    raise LimitExceeded(
                        f"You've used today's {daily_limit} {kind} meal estimates. "
                        f"It resets at midnight ({cfg.timezone})."
                    )
                for counter, counter_uid, counter_kind in [(total, 0, "ai"), (user, uid, kind)]:
                    if counter:
                        counter.count += 1
                    else:
                        db.add(UsageCounter(telegram_user_id=counter_uid, day=day, kind=counter_kind, count=1))
            # Charge attempted calls, including failures: a failed response may
            # still have incurred provider cost. Rejected requests cost no quota.
            if not admin:
                self._window((kind, uid), minute_limit, 60)
            self.active.add(uid)

    def finish_ai(self, uid):
        with self.lock:
            self.active.discard(uid)

    def claim_global_alert(self):
        """Persist the claim before delivery, preventing restart notification spam."""
        with self.lock, self.sessions.begin() as db:
            day = self.utcnow().astimezone(ZoneInfo(self.config.timezone)).date()
            total = db.get(UsageCounter, (0, day, "ai"))
            if not total or total.count < self.config.ai_global_per_day:
                return False
            if db.get(UsageCounter, (0, day, "ai_alert")):
                return False
            db.add(UsageCounter(telegram_user_id=0, day=day, kind="ai_alert", count=1))
            return True

    def expire_requests(self, db):
        now = self.utcnow()
        # Existing pending requests receive a full grace period on upgrade.
        missing = db.scalars(select(AccessRequest.token).where(
            ~AccessRequest.token.in_(select(AccessRequestTiming.token))))
        for token in missing:
            db.add(AccessRequestTiming(token=token, created_at=now))
        db.flush()
        expired = select(AccessRequestTiming.token).where(
            AccessRequestTiming.created_at <= now - timedelta(days=self.config.access_expiry_days))
        db.execute(delete(AccessRequest).where(AccessRequest.token.in_(expired)))
        db.execute(delete(AccessRequestTiming).where(
            ~AccessRequestTiming.token.in_(select(AccessRequest.token))))
        db.execute(delete(AccessAttempt).where(AccessAttempt.created_at <= now - timedelta(days=1)))

    def record_request(self, db, uid):
        """Check and record admission within the caller's request transaction."""
        now = self.utcnow()
        attempts = select(AccessAttempt).where(AccessAttempt.telegram_user_id == uid)
        recent = db.scalar(select(func.count()).select_from(attempts.subquery()))
        latest = db.scalar(select(func.max(AccessAttempt.created_at)).where(AccessAttempt.telegram_user_id == uid))
        # SQLite returns naive UTC; Postgres returns aware times in the session
        # time zone, which must be converted rather than relabelled.
        if latest:
            latest = latest.astimezone(timezone.utc) if latest.tzinfo else latest.replace(tzinfo=timezone.utc)
        if latest and latest > now - timedelta(seconds=self.config.access_request_cooldown_seconds):
            raise LimitExceeded("Please wait a few minutes between requests, then send /start to try again.")
        if recent >= self.config.access_requests_per_day:
            raise LimitExceeded("You've reached the access request limit. Please try again tomorrow.")
        hourly = db.scalar(select(func.count()).select_from(AccessAttempt).where(
            AccessAttempt.created_at > now - timedelta(hours=1)))
        pending = db.scalar(select(func.count()).select_from(AccessRequest))
        if hourly >= self.config.access_requests_per_hour or pending >= self.config.access_pending_limit:
            raise LimitExceeded("Not accepting new requests right now. Please try again later.")
        db.add(AccessAttempt(telegram_user_id=uid, created_at=now))

    def access_alert(self):
        """Send the first few immediately; summarise the rest when the window ends."""
        with self.lock:
            if self.alert_started is None:
                self.alert_started = self.clock()
            self.alert_count += 1
            return self.alert_count <= self.config.admin_alert_limit

    def take_access_summary(self):
        with self.lock:
            if self.alert_started is None or self.clock() < self.alert_started + self.config.admin_alert_window_seconds:
                return 0
            count = self.alert_count if self.alert_count > self.config.admin_alert_limit else 0
            self.alert_started = None
            self.alert_count = 0
            return count


limiter = RateLimiter()
