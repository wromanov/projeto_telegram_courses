from __future__ import annotations

import asyncio
import sqlite3

import aiosqlite


def test_asyncio_local_coroutine_returns_sentinel() -> None:
    async def operation() -> str:
        return "s0-asyncio-sentinel"

    assert asyncio.run(operation()) == "s0-asyncio-sentinel"


def test_sqlite3_in_memory_round_trip() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE probe (value TEXT NOT NULL)")
        connection.execute("INSERT INTO probe VALUES (?)", ("s0-sqlite-sentinel",))
        row = connection.execute("SELECT value FROM probe").fetchone()
        assert row == ("s0-sqlite-sentinel",)
    finally:
        connection.close()


def test_aiosqlite_in_memory_round_trip() -> None:
    async def operation() -> tuple[str]:
        async with aiosqlite.connect(":memory:") as connection:
            await connection.execute("CREATE TABLE probe (value TEXT NOT NULL)")
            await connection.execute(
                "INSERT INTO probe VALUES (?)", ("s0-aiosqlite-sentinel",)
            )
            async with connection.execute("SELECT value FROM probe") as cursor:
                row = await cursor.fetchone()
            return row

    assert asyncio.run(operation()) == ("s0-aiosqlite-sentinel",)
