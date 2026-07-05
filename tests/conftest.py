import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.main import app

# Use /tmp so we never collide with the source tree
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:////tmp/test_scheduler.db",
)

_engine = None


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    global _engine
    kwargs = {}
    if "sqlite" in TEST_DB_URL:
        kwargs["connect_args"] = {"check_same_thread": False}
        # Remove stale DB so schema is always fresh
        db_path = TEST_DB_URL.replace("sqlite+aiosqlite:///", "")
        if os.path.exists(db_path):
            os.remove(db_path)
    _engine = create_async_engine(TEST_DB_URL, **kwargs)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture
def test_session_factory():
    return async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
