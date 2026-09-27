import asyncio
from collections.abc import AsyncIterator

import asyncpg
import httpx
import pytest

from app.config import settings
from app.db import init_schema
from app.main import app

TEST_DB_URL = settings.TEST_DATABASE_URL


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Inicializa el esquema ledger_test una vez al arrancar los tests."""

    async def _init():
        pool = await asyncpg.create_pool(dsn=TEST_DB_URL, min_size=1, max_size=5)
        await init_schema(pool)
        await pool.close()

    asyncio.run(_init())


@pytest.fixture
async def db_pool() -> AsyncIterator[asyncpg.Pool]:
    """Proporciona un pool de conexiones para el test y limpia tablas antes y después."""
    pool = await asyncpg.create_pool(dsn=TEST_DB_URL, min_size=1, max_size=15)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE postings, transactions, accounts RESTART IDENTITY CASCADE;")
    yield pool
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE postings, transactions, accounts RESTART IDENTITY CASCADE;")
    await pool.close()


@pytest.fixture
async def client(db_pool: asyncpg.Pool) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente HTTP asíncrono configurado con la base de datos de test."""

    async def get_test_conn() -> AsyncIterator[asyncpg.Connection]:
        async with db_pool.acquire() as conn:
            yield conn

    from app.routes.accounts import get_db_conn as acc_conn
    from app.routes.reports import get_db_conn as rep_conn
    from app.routes.transactions import get_db_conn as tx_conn

    app.dependency_overrides[acc_conn] = get_test_conn
    app.dependency_overrides[tx_conn] = get_test_conn
    app.dependency_overrides[rep_conn] = get_test_conn

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
