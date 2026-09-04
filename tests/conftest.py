"""Pytest fixtures and test database configuration."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.session import Base
from aiogram import Bot
from aiogram.types import ChatInviteLink


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine):
    session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_bot():
    bot = AsyncMock(spec=Bot)
    # Mock create_chat_invite_link
    invite_mock = MagicMock(spec=ChatInviteLink)
    invite_mock.invite_link = "https://t.me/+MockTestInviteLink123"
    bot.create_chat_invite_link.return_value = invite_mock
    bot.ban_chat_member.return_value = True
    bot.unban_chat_member.return_value = True
    bot.restrict_chat_member.return_value = True
    bot.send_message.return_value = AsyncMock()
    return bot
