from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update

from app.core.db import get_engine, get_sessionmaker
from app.main import app
from app.models.base import Base
from app.models.comment import Comment
from app.models.event import Event
from app.models.job import Job
from app.models.post import Post
from app.models.user import User


@pytest.fixture(scope="session", autouse=True)
async def _schema() -> AsyncGenerator[None, None]:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncGenerator[None, None]:
    yield
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # posts.solution_comment_id -> comments and comments.post_id -> posts
        # form a cycle; null out the back-reference before deleting either.
        await session.execute(update(Post).values(solution_comment_id=None))
        await session.execute(delete(Job))
        await session.execute(delete(Event))
        await session.execute(delete(Comment))
        await session.execute(delete(Post))
        await session.execute(delete(User))
        await session.commit()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
