"""Offline tests for per-user update ordering and thread-safe chart rendering."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', '123:test')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/health-tracker-test-matplotlib')

from app.bot import bot
from app.bot.update_processor import BUSY_TEXT, OneUpdatePerUser
from app.services.progress import make_chart


def message_update(uid):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=uid), callback_query=None,
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )


class OneUpdatePerUserTests(unittest.TestCase):
    def test_busy_user_is_rejected_with_one_notice_then_accepted_again(self):
        async def scenario():
            processor = OneUpdatePerUser(8)
            release = asyncio.Event()
            handled = []

            async def handler(name, wait=False):
                if wait:
                    await release.wait()
                handled.append(name)

            first = asyncio.create_task(processor.process_update(message_update(1), handler('first', wait=True)))
            await asyncio.sleep(0)
            second, third = message_update(1), message_update(1)
            await processor.process_update(second, handler('second'))
            await processor.process_update(third, handler('third'))
            # Another user is not blocked by user 1's slow update.
            await processor.process_update(message_update(2), handler('other user'))
            release.set()
            await first
            await processor.process_update(message_update(1), handler('after'))
            return handled, second, third

        with self.assertNoLogs('asyncio', 'WARNING'):
            handled, second, third = asyncio.run(scenario())
        self.assertEqual(handled, ['other user', 'first', 'after'])
        second.effective_message.reply_text.assert_awaited_once_with(BUSY_TEXT)
        third.effective_message.reply_text.assert_not_awaited()

    def test_updates_rejected_at_the_same_time_get_one_notice(self):
        async def slow_reply(*args):
            await asyncio.sleep(0.01)

        async def scenario():
            processor = OneUpdatePerUser(8)
            processor.busy.add(1)
            # A double tap arrives in one batch, so both rejections run concurrently.
            updates = [message_update(1) for _ in range(2)]
            for update in updates:
                update.effective_message.reply_text.side_effect = slow_reply

            async def handler():
                raise AssertionError('handler must not run')
            await asyncio.gather(*(processor.process_update(u, handler()) for u in updates))
            return updates

        first, second = asyncio.run(scenario())
        first.effective_message.reply_text.assert_awaited_once_with(BUSY_TEXT)
        second.effective_message.reply_text.assert_not_awaited()

    def test_rejected_button_taps_are_always_answered(self):
        async def scenario():
            processor = OneUpdatePerUser(8)
            processor.busy.add(1)
            taps = [SimpleNamespace(effective_user=SimpleNamespace(id=1),
                                    callback_query=SimpleNamespace(answer=AsyncMock())) for _ in range(2)]
            for tap in taps:
                async def handler():
                    raise AssertionError('handler must not run')
                await processor.process_update(tap, handler())
            return taps

        first, second = asyncio.run(scenario())
        first.callback_query.answer.assert_awaited_once_with(BUSY_TEXT)
        second.callback_query.answer.assert_awaited_once_with(None)

    def test_build_application_uses_processor(self):
        app = bot.build_application()
        self.assertIsInstance(app.update_processor, OneUpdatePerUser)
        self.assertEqual(app.update_processor.max_concurrent_updates, bot.settings.concurrent_updates)


class OffLoopTests(unittest.TestCase):
    def test_user_lookup_runs_in_worker_thread(self):
        threads = []
        update = SimpleNamespace(effective_user=SimpleNamespace(id=1, first_name='Ann'))
        with patch.object(bot, 'get_user', side_effect=lambda *_: threads.append(threading.current_thread())):
            asyncio.run(bot.user_for(update))
        self.assertIsNot(threads[0], threading.main_thread())

    def test_charts_render_concurrently(self):
        meal = SimpleNamespace(recorded_at=datetime(2026, 10, 12, 4, tzinfo=timezone.utc), estimated_calories=500)
        weight = SimpleNamespace(recorded_at=datetime(2026, 10, 12, 4, tzinfo=timezone.utc), weight_kg=60.0)
        with ThreadPoolExecutor(4) as pool:
            charts = list(pool.map(lambda _: make_chart([meal], [weight], 'Asia/Singapore', 2000), range(8)))
        for chart in charts:
            self.assertEqual(chart.read(8), b'\x89PNG\r\n\x1a\n')


if __name__ == '__main__':
    unittest.main()
