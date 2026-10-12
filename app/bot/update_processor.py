"""Process different users' updates concurrently, but one at a time per user."""
import logging
from typing import Any, Awaitable

from telegram import Update
from telegram.ext import BaseUpdateProcessor

log = logging.getLogger(__name__)
BUSY_TEXT = "Still working on your last request… Please wait for my reply."


class OneUpdatePerUser(BaseUpdateProcessor):
    """Reject a user's new updates while their previous one is still running.

    Handlers keep multi-step state in user_data, so two updates from one user
    running at once could, for example, save the same meal twice. Rejecting
    rather than queueing also stops a burst of photos turning into a burst of
    paid estimates once the first one finishes.
    """

    def __init__(self, max_concurrent_updates: int):
        super().__init__(max_concurrent_updates)
        self.busy: set[int] = set()
        # Users already told they are busy, so a burst gets one notice only.
        self.notified: set[int] = set()

    async def do_process_update(self, update: object, coroutine: Awaitable[Any]) -> None:
        user = getattr(update, "effective_user", None)
        if user is None:
            await coroutine
            return
        if user.id in self.busy:
            # Close the unscheduled handler coroutine to avoid a "never awaited" warning.
            coroutine.close()
            await self.reject(update, user.id)
            return
        self.busy.add(user.id)
        try:
            await coroutine
        finally:
            self.busy.discard(user.id)
            self.notified.discard(user.id)

    async def reject(self, update: Update, uid: int) -> None:
        try:
            if update.callback_query:
                # Always answer button taps so Telegram stops showing a spinner.
                await update.callback_query.answer(BUSY_TEXT if uid not in self.notified else None)
            elif update.effective_message and uid not in self.notified:
                await update.effective_message.reply_text(BUSY_TEXT)
            self.notified.add(uid)
        except Exception:
            log.exception("Could not send busy notice to user %s", uid)

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass
