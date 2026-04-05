import json
from typing import Optional

import aiosqlite

DEFAULTS = {
    "default_work_dir": "",
    "max_concurrent_runs": 5,
    "theme": "dark",
}


async def get_all(db: aiosqlite.Connection) -> dict:
    cursor = await db.execute("SELECT key, value FROM settings")
    rows = await cursor.fetchall()
    result = dict(DEFAULTS)
    for row in rows:
        key = row["key"]
        raw = row["value"]
        # Cast to correct type based on defaults
        default = DEFAULTS.get(key)
        if isinstance(default, int):
            try:
                raw = int(raw)
            except (ValueError, TypeError):
                raw = default
        result[key] = raw
    return result


async def get(db: aiosqlite.Connection, key: str) -> Optional[str]:
    cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cursor.fetchone()
    if row:
        return row["value"]
    return DEFAULTS.get(key)


async def put(db: aiosqlite.Connection, key: str, value) -> None:
    await db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    await db.commit()


async def put_many(db: aiosqlite.Connection, data: dict) -> dict:
    for key, value in data.items():
        if key in DEFAULTS:
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
    await db.commit()
    return await get_all(db)
