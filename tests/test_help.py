"""The Help message must list every user command, one per line."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import CommandHandler

from app.bot import bot

# Admin tools are reached through the Manage users button, not listed for everyone.
NOT_LISTED = {'admin', 'myid'}


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_help_lists_every_user_command_on_its_own_line(monkeypatch):
    monkeypatch.setattr(bot, 'allowed', lambda update: True)
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), effective_chat=SimpleNamespace(type='private'),
                             message=message, effective_message=message)
    await bot.help_message(update, SimpleNamespace(user_data={}))
    text = message.reply_text.await_args.args[0]

    registered = {
        command
        for handler in bot.build_application().handlers[0]
        if isinstance(handler, CommandHandler)
        for command in handler.commands
    }
    listed = {line.split(' ', 1)[0][1:] for line in text.splitlines() if line.startswith('/')}
    assert listed == registered - NOT_LISTED
