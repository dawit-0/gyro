import aiosqlite


async def delete_by_task(db: aiosqlite.Connection, task_id: str) -> None:
    await db.execute("DELETE FROM questions WHERE task_id = ?", (task_id,))


async def delete_by_flow(db: aiosqlite.Connection, flow_id: str) -> None:
    await db.execute(
        """DELETE FROM questions
           WHERE task_id IN (SELECT id FROM tasks WHERE flow_id = ?)""",
        (flow_id,),
    )
