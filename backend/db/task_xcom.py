import aiosqlite


async def insert(db: aiosqlite.Connection, task_run_id: str, task_id: str,
                 key: str, value: str) -> None:
    await db.execute(
        """INSERT OR REPLACE INTO task_xcom (task_run_id, task_id, key, value)
           VALUES (?, ?, ?, ?)""",
        (task_run_id, task_id, key, value),
    )


async def get_latest_for_task(db: aiosqlite.Connection, task_id: str,
                               key: str = "return_value") -> aiosqlite.Row | None:
    cursor = await db.execute(
        """SELECT x.* FROM task_xcom x
           JOIN task_runs tr ON tr.id = x.task_run_id
           WHERE x.task_id = ? AND x.key = ?
           ORDER BY tr.run_number DESC LIMIT 1""",
        (task_id, key),
    )
    return await cursor.fetchone()


async def get_all_for_run(db: aiosqlite.Connection, task_run_id: str) -> list[dict]:
    cursor = await db.execute(
        "SELECT * FROM task_xcom WHERE task_run_id = ? ORDER BY key",
        (task_run_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def delete_by_task(db: aiosqlite.Connection, task_id: str) -> None:
    await db.execute("DELETE FROM task_xcom WHERE task_id = ?", (task_id,))


async def delete_by_flow(db: aiosqlite.Connection, flow_id: str) -> None:
    await db.execute(
        """DELETE FROM task_xcom
           WHERE task_id IN (SELECT id FROM tasks WHERE flow_id = ?)""",
        (flow_id,),
    )
