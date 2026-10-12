"""Offline abuse-protection tests; never connect to the configured NAS database."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['TELEGRAM_BOT_TOKEN'] = '123:test'
os.environ['OPENAI_API_KEY'] = 'test-key'
os.environ['ADMIN_TELEGRAM_USER_IDS'] = '999'
os.environ['ALLOWED_TELEGRAM_USER_IDS'] = ''
os.environ['ALLOWED_TELEGRAM_USER_ID'] = ''
os.environ['MPLCONFIGDIR'] = '/tmp/health-tracker-test-matplotlib'
os.environ['XDG_CACHE_HOME'] = '/tmp/health-tracker-test-cache'

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from telegram.ext import AIORateLimiter, ApplicationHandlerStop

from app.config import Settings, positive_setting
from app.db.database import Base
from app.models.entities import AccessAttempt, AccessRequest, AccessRequestTiming, UsageCounter
from app.services import access
from app.services.rate_limit import LimitExceeded, RateLimiter
from app.bot import access_handlers, bot


class Clock:
    def __init__(self):
        self.seconds = 0
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)

    def advance(self, seconds):
        self.seconds += seconds
        self.now += timedelta(seconds=seconds)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.clock = Clock()
        self.config = Settings()
        self.limiter = self.new_limiter()
        self.addCleanup(self.engine.dispose)

    def new_limiter(self):
        return RateLimiter(self.config, self.sessions, lambda: self.clock.seconds, lambda: self.clock.now)

    def configure(self, **kwargs):
        self.config = replace(self.config, **kwargs)
        self.limiter.config = self.config

    def call(self, uid=1, kind='text', content='rice'):
        self.limiter.begin_ai(uid, kind, content)
        self.limiter.finish_ai(uid)

    def total(self):
        with self.sessions() as db:
            return db.scalar(select(func.sum(UsageCounter.count)).where(UsageCounter.kind == 'ai')) or 0


class QuotaTests(Fixture):
    def test_text_and_photo_minutes_are_separate_and_expire(self):
        for kind, limit in [('text', 5), ('photo', 3)]:
            for _ in range(limit):
                self.call(kind=kind)
            with self.assertRaisesRegex(LimitExceeded, 'minute'):
                self.call(kind=kind)
        self.clock.advance(60)
        self.call()
        self.call(kind='photo')
        self.assertEqual(self.total(), 10)

    def test_daily_quotas_survive_restart_and_reset_at_local_midnight(self):
        self.configure(ai_text_per_day=2, ai_photo_per_day=1)
        self.call()
        self.call()
        self.call(kind='photo')
        self.limiter = self.new_limiter()
        for kind in ['text', 'photo']:
            with self.assertRaisesRegex(LimitExceeded, 'midnight'):
                self.call(kind=kind)
        # 16:00 UTC is midnight in Singapore, not midnight UTC.
        self.clock.advance(4 * 3600)
        self.call()
        self.call(kind='photo')
        self.assertEqual(self.total(), 2)

    def test_global_limit_includes_admins_and_alert_claim_survives_restart(self):
        self.configure(ai_global_per_day=2, ai_text_per_day=1)
        self.call(uid=999)
        self.call(uid=999)
        with self.assertRaisesRegex(LimitExceeded, 'paused'):
            self.call(uid=2)
        self.assertTrue(self.limiter.claim_global_alert())
        self.limiter = self.new_limiter()
        self.assertFalse(self.limiter.claim_global_alert())
        with self.assertRaisesRegex(LimitExceeded, 'paused'):
            self.call(uid=999)
        self.clock.advance(86400)
        self.call(uid=999)
        self.assertFalse(self.limiter.claim_global_alert())

    def test_input_caps_reject_before_charging_even_for_admin(self):
        for uid in [1, 999]:
            for kind, length in [('text', 301), ('photo', 201)]:
                with self.assertRaisesRegex(LimitExceeded, 'characters'):
                    self.call(uid=uid, kind=kind, content='x' * length)
        self.assertEqual(self.total(), 0)
        self.call(content='x' * 300)
        self.call(kind='photo', content='x' * 200)

    def test_per_user_and_global_active_limits_release(self):
        self.limiter.begin_ai(1, 'text', 'rice')
        with self.assertRaisesRegex(LimitExceeded, 'last meal'):
            self.limiter.begin_ai(1, 'photo', '')
        self.limiter.begin_ai(2, 'text', 'rice')
        self.limiter.begin_ai(3, 'text', 'rice')
        with self.assertRaisesRegex(LimitExceeded, 'busy'):
            self.limiter.begin_ai(999, 'text', 'rice')
        self.limiter.finish_ai(2)
        self.limiter.begin_ai(999, 'text', 'rice')
        self.assertEqual(self.total(), 4)

    def test_concurrent_workers_cannot_overspend(self):
        self.configure(ai_global_per_day=3)
        def attempt(uid):
            try:
                self.call(uid=uid)
                return True
            except LimitExceeded:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(1, 30)))
        self.assertEqual(sum(results), 3)
        self.assertEqual(self.total(), 3)

    def test_database_failure_leaves_no_active_slot(self):
        with patch.object(self.limiter, 'sessions') as sessions:
            sessions.begin.side_effect = RuntimeError('offline')
            with self.assertRaises(RuntimeError):
                self.call()
        self.assertEqual(self.limiter.active, set())
        self.assertEqual(self.total(), 0)


class FloodTests(Fixture):
    def test_flood_warns_once_then_silences_and_recovers(self):
        for _ in range(20):
            self.assertEqual(self.limiter.message(1), 'allow')
        self.assertEqual(self.limiter.message(1), 'warn')
        self.assertEqual(self.limiter.message(1), 'drop')
        self.clock.advance(59)
        self.assertEqual(self.limiter.message(1), 'drop')
        self.clock.advance(1)
        self.assertEqual(self.limiter.message(1), 'allow')
        for _ in range(30):
            self.assertEqual(self.limiter.message(999), 'allow')

    def test_access_reply_throttle_and_approval_clear(self):
        self.assertTrue(self.limiter.access_reply(1))
        self.assertTrue(self.limiter.access_silenced(1))
        self.assertFalse(self.limiter.access_reply(1))
        self.clock.advance(600)
        self.assertTrue(self.limiter.access_reply(1))
        self.limiter.clear_access_silence(1)
        self.assertFalse(self.limiter.access_silenced(1))

    def test_memory_limits_fail_closed_and_expire(self):
        for uid in range(10000):
            self.limiter.access_reply(uid)
        self.assertFalse(self.limiter.access_reply(10001))
        self.assertEqual(len(self.limiter.windows), 10000)
        self.assertFalse(self.limiter.access_silenced(10001))
        self.clock.advance(600)
        self.assertTrue(self.limiter.access_reply(10001))
        self.assertEqual(len(self.limiter.windows), 1)

    def test_grouped_alerts_flush_once_without_new_requests(self):
        self.assertEqual([self.limiter.access_alert() for _ in range(7)], [True] * 5 + [False] * 2)
        self.assertEqual(self.limiter.take_access_summary(), 0)
        self.clock.advance(600)
        self.assertEqual(self.limiter.take_access_summary(), 7)
        self.assertEqual(self.limiter.take_access_summary(), 0)
        self.assertTrue(self.limiter.access_alert())


class AccessTests(Fixture):
    def setUp(self):
        super().setUp()
        for target, value in [('SessionLocal', self.sessions), ('settings', self.config), ('limiter', self.limiter)]:
            p = patch.object(access, target, value)
            p.start()
            self.addCleanup(p.stop)

    def request(self, uid=1):
        return access.request_access(uid, 'Person', None)

    def test_rejection_keeps_rolling_limit_and_cooldown_across_restart(self):
        for index in range(3):
            request = self.request()
            self.assertIsNotNone(request)
            self.assertIsNone(self.request())  # Duplicate consumes no admission.
            access.decide_request(request.token, False)
            with self.assertRaisesRegex(LimitExceeded, 'few minutes'):
                self.request()
            self.clock.advance(300)
        with patch.object(access, 'limiter', self.new_limiter()):
            with self.assertRaisesRegex(LimitExceeded, 'tomorrow'):
                self.request()
        self.clock.advance(86400)
        self.assertIsNotNone(self.request())
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AccessAttempt)), 1)

    def test_global_hourly_limit(self):
        for uid in range(1, 11):
            self.assertIsNotNone(self.request(uid))
        with self.assertRaisesRegex(LimitExceeded, 'Not accepting'):
            self.request(11)
        self.clock.advance(3600)
        self.assertIsNotNone(self.request(11))

    def test_pending_capacity(self):
        self.configure(access_pending_limit=2)
        self.request(1)
        second = self.request(2)
        with self.assertRaisesRegex(LimitExceeded, 'Not accepting'):
            self.request(3)
        access.decide_request(second.token, False)
        self.assertIsNotNone(self.request(3))

    def test_expired_request_cannot_be_approved_and_replaced_button_is_stale(self):
        old = self.request()
        self.clock.advance(14 * 86400)
        self.assertIsNone(access.decide_request(old.token, True))
        self.assertFalse(access.has_access(1))
        new = self.request()
        self.assertNotEqual(old.token, new.token)
        self.assertIsNone(access.decide_request(old.token, True))
        self.assertIsNotNone(access.decide_request(new.token, True))
        self.assertTrue(access.has_access(1))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AccessRequestTiming)), 0)

    def test_existing_request_receives_grace_period_once(self):
        with self.sessions.begin() as db:
            db.add(AccessRequest(token='legacy', telegram_user_id=1, name='Existing'))
        access.initialize_access()
        self.clock.advance(13 * 86400)
        access.initialize_access()
        self.assertIsNotNone(access.pending_request(1))
        self.clock.advance(86400)
        self.assertIsNone(access.pending_request(1))


def fake_update(uid=1, text='rice'):
    message = SimpleNamespace(
        text=text, caption='', reply_text=AsyncMock(), chat=SimpleNamespace(send_action=AsyncMock()),
        photo=[],
    )
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=uid), effective_chat=SimpleNamespace(type='private'),
        effective_message=message, message=message, callback_query=None,
    )


class HandlerTests(Fixture, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        for module in [bot, access_handlers]:
            for target, value in [('limiter', self.limiter), ('settings', self.config)]:
                p = patch.object(module, target, value)
                p.start()
                self.addCleanup(p.stop)
        self.context = SimpleNamespace(user_data={}, bot=SimpleNamespace(send_message=AsyncMock()))

    async def test_both_text_paths_share_quota_and_handle_failure(self):
        self.configure(ai_text_per_day=1)
        with patch.object(bot, 'MealAnalyzer') as analyser:
            analyser.return_value.from_text = AsyncMock(side_effect=RuntimeError('test failure'))
            with self.assertLogs(bot.log, level='ERROR'):
                await bot.analyze_text(fake_update(), self.context, 'rice')
            await bot.check_meal(fake_update(), self.context, 'rice')
            self.assertEqual(analyser.return_value.from_text.await_count, 1)
        self.assertEqual(self.limiter.active, set())
        self.assertEqual(self.total(), 1)

    async def test_cancelled_analysis_releases_slot(self):
        entered = asyncio.Event()
        @bot.ai_guard('text')
        async def slow(update, context, text):
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(slow(fake_update(), self.context, 'rice'))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.limiter.active, set())

    async def test_photo_uses_middle_size_and_rejects_long_caption_before_download(self):
        update = fake_update()
        sizes = [SimpleNamespace(file_id=str(i), get_file=AsyncMock()) for i in range(3)]
        sizes[1].get_file.return_value.download_as_bytearray = AsyncMock(return_value=b'image')
        update.message.photo = sizes
        update.message.reply_text.return_value = SimpleNamespace(delete=AsyncMock(), edit_text=AsyncMock())
        with patch.object(bot, 'allowed', return_value=True), patch.object(bot, 'MealAnalyzer') as analyser, patch.object(bot, 'show_estimate', new_callable=AsyncMock):
            analyser.return_value.from_image = AsyncMock()
            await bot.photo(update, self.context)
            self.assertEqual(self.context.user_data['pending_image_file_id'], '1')
            sizes[1].get_file.assert_awaited_once()
            sizes[2].get_file.assert_not_awaited()
            update.message.caption = 'x' * 201
            await bot.photo(update, self.context)
            analyser.return_value.from_image.assert_awaited_once()

    async def test_unauthorised_prompt_is_silent_without_repeated_database_lookup(self):
        update = fake_update()
        with patch.object(bot, 'allowed', return_value=False) as allowed, patch.object(access, 'pending_request', return_value=None):
            await bot.start(update, self.context)
            await bot.start(update, self.context)
            self.assertEqual(allowed.call_count, 1)
            update.message.reply_text.assert_awaited_once()

    async def test_ingress_flood_covers_all_dispatch_and_warns_once(self):
        update = fake_update()
        for _ in range(20):
            await bot.guard_updates(update, self.context)
        for _ in range(3):
            with self.assertRaises(ApplicationHandlerStop):
                await bot.guard_updates(update, self.context)
        update.message.reply_text.assert_awaited_once()

    async def test_global_alert_sent_once_per_admin(self):
        self.configure(ai_global_per_day=1)
        @bot.ai_guard('text')
        async def estimate(update, context, text):
            return None
        await estimate(fake_update(), self.context, 'rice')
        await estimate(fake_update(2), self.context, 'rice')
        self.context.bot.send_message.assert_awaited_once()

    async def test_explicit_controls_are_usable_after_prompt_but_repeats_are_silent(self):
        update = fake_update()
        update.effective_user.full_name = 'Person'
        update.effective_user.username = None
        update.callback_query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
        request = SimpleNamespace(telegram_user_id=1, name='Person', username=None, token='token')
        self.limiter.access_reply(1)
        with patch.object(access, 'has_access', return_value=False) as has_access, patch.object(access, 'pending_request', return_value=None), patch.object(access, 'request_access', return_value=request) as request_access:
            await access_handlers.request_action(update, self.context)
            await access_handlers.request_action(update, self.context)
            request_access.assert_called_once()
            has_access.assert_called_once()
        await access_handlers.my_id(update, self.context)
        await access_handlers.my_id(update, self.context)
        update.message.reply_text.assert_awaited_once()

    async def test_rejected_admin_controls_do_not_repeat_replies_or_silence_tracking(self):
        update = fake_update()
        self.assertFalse(await access_handlers.require_admin(update))
        self.assertFalse(await access_handlers.require_admin(update))
        update.message.reply_text.assert_awaited_once()
        self.assertFalse(self.limiter.access_silenced(1))

    async def test_build_registers_send_limiter_and_ingress(self):
        app = bot.build_application()
        self.assertIsInstance(app.bot.rate_limiter, AIORateLimiter)
        self.assertEqual(app.handlers[-1][0].callback, bot.guard_updates)


class ReviewFixTests(Fixture):
    def test_cooldown_converts_non_utc_database_times(self):
        # Postgres in a non-UTC session returns 13:00+08:00 for 05:00 UTC; it is
        # long past the cooldown, not eight hours in the future.
        latest = (self.clock.now - timedelta(hours=7)).astimezone(timezone(timedelta(hours=8)))
        db = SimpleNamespace(scalar=lambda _: next(results), add=lambda _: None)
        results = iter([0, latest, 0, 0])
        self.limiter.record_request(db, 1)

    def test_reminder_loop_survives_clean_up_failure(self):
        app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
        with patch.object(bot, 'clean_up_access_requests', side_effect=RuntimeError('database down')), \
                patch.object(bot, 'due_reminders', return_value=[]) as due, \
                patch.object(bot.asyncio, 'sleep', AsyncMock(side_effect=asyncio.CancelledError)), \
                self.assertLogs(bot.log, 'ERROR'):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(bot.reminder_loop(app))
        due.assert_called_once()


class SettingsTests(unittest.TestCase):
    def test_zero_and_negative_limits_rejected(self):
        for value in ['0', '-1', 'invalid']:
            with patch.dict(os.environ, {'TEST_LIMIT': value}):
                with self.assertRaises(ValueError):
                    positive_setting('TEST_LIMIT', 1)


if __name__ == '__main__':
    unittest.main()
