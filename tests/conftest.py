import json
import os
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv


pytest_plugins = ("pytest_asyncio.plugin",)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "lumos" / "db" / "schema.sql"
load_dotenv(ROOT / ".env")


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.getenv("LUMOS_TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "Set LUMOS_TEST_DATABASE_URL to run DB-backed tests. "
            "Create a project-root .env file or export the variable in your shell.",
            pytrace=False,
        )
    return url


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


@pytest_asyncio.fixture
async def conn(test_database_url: str):
    connection = await asyncpg.connect(test_database_url)
    await _init_connection(connection)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    await connection.execute(schema_sql)
    await connection.execute(
        """
        TRUNCATE budget_state, rate_limit_state, audit_events, capabilities, sessions, auth_nonces, agent_keys, agents
        RESTART IDENTITY CASCADE
        """
    )
    try:
        yield connection
    finally:
        await connection.close()
