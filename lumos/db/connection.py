from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import json
from pathlib import Path

import asyncpg

from lumos.config import settings


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


class Database:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool has not been connected")
        return self._pool

    async def connect(self) -> None:
        if self._pool is not None:
            return

        self._pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=settings.database_min_pool_size,
            max_size=settings.database_max_pool_size,
            init=_init_connection,
        )

    async def close(self) -> None:
        if self._pool is None:
            return

        await self._pool.close()
        self._pool = None

    async def init_schema(self) -> None:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            await conn.execute(schema_sql)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        async with self.pool.acquire() as conn:
            yield conn


db = Database()
