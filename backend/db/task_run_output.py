import aiosqlite


async def insert(db: aiosqlite.Connection, task_run_id: str, seq: int,
                  output_type: str, content: str) -> None:
    await db.execute(
        "INSERT INTO task_run_output (task_run_id, seq, type, content) VALUES (?, ?, ?, ?)",
        (task_run_id, seq, output_type, content),
    )


async def list_by_run(db: aiosqlite.Connection, run_id: str) -> list[dict]:
    cursor = await db.execute(
        "SELECT * FROM task_run_output WHERE task_run_id = ? ORDER BY seq ASC",
        (run_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def delete_by_task(db: aiosqlite.Connection, task_id: str) -> None:
    await db.execute(
        "DELETE FROM task_run_output WHERE task_run_id IN (SELECT id FROM task_runs WHERE task_id = ?)",
        (task_id,),
    )


async def delete_by_flow(db: aiosqlite.Connection, flow_id: str) -> None:
    await db.execute(
        """DELETE FROM task_run_output
           WHERE task_run_id IN (
               SELECT tr.id FROM task_runs tr
               JOIN tasks t ON t.id = tr.task_id
               WHERE t.flow_id = ?
           )""",
        (flow_id,),
    )
