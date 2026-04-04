import aiosqlite


async def get_edges_for_nodes(db: aiosqlite.Connection,
                               node_ids: set[str]) -> list[dict]:
    placeholders = ",".join("?" for _ in node_ids)
    cursor = await db.execute(
        f"SELECT task_id, depends_on_task_id FROM task_dependencies WHERE task_id IN ({placeholders})",
        list(node_ids),
    )
    return [{"source": r["depends_on_task_id"], "target": r["task_id"]}
            for r in await cursor.fetchall()]


async def get_upstream(db: aiosqlite.Connection, task_id: str) -> list[str]:
    cursor = await db.execute(
        "SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?", (task_id,)
    )
    return [r["depends_on_task_id"] for r in await cursor.fetchall()]


async def get_downstream(db: aiosqlite.Connection, task_id: str) -> list[dict]:
    cursor = await db.execute(
        "SELECT DISTINCT task_id FROM task_dependencies WHERE depends_on_task_id = ?",
        (task_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def insert(db: aiosqlite.Connection, task_id: str,
                  depends_on_task_id: str) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?, ?)",
        (task_id, depends_on_task_id),
    )


async def delete_for_task(db: aiosqlite.Connection, task_id: str) -> None:
    await db.execute(
        "DELETE FROM task_dependencies WHERE task_id = ? OR depends_on_task_id = ?",
        (task_id, task_id),
    )


async def delete_one(db: aiosqlite.Connection, task_id: str,
                      depends_on_task_id: str) -> None:
    await db.execute(
        "DELETE FROM task_dependencies WHERE task_id = ? AND depends_on_task_id = ?",
        (task_id, depends_on_task_id),
    )


async def delete_by_flow(db: aiosqlite.Connection, flow_id: str) -> None:
    await db.execute(
        """DELETE FROM task_dependencies
           WHERE task_id IN (SELECT id FROM tasks WHERE flow_id = ?)
           OR depends_on_task_id IN (SELECT id FROM tasks WHERE flow_id = ?)""",
        (flow_id, flow_id),
    )


async def get_unmet_upstream(db: aiosqlite.Connection, task_id: str) -> list[dict]:
    """Get upstream deps that don't have a successful latest run."""
    cursor = await db.execute(
        """SELECT td.depends_on_task_id FROM task_dependencies td
           WHERE td.task_id = ?
           AND NOT EXISTS (
               SELECT 1 FROM task_runs tr
               WHERE tr.task_id = td.depends_on_task_id
               AND tr.status = 'success'
               AND tr.run_number = (
                   SELECT MAX(run_number) FROM task_runs WHERE task_id = td.depends_on_task_id
               )
           )""",
        (task_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_queued_downstream(db: aiosqlite.Connection, task_id: str) -> list[dict]:
    """Get queued runs for tasks that depend on the given task."""
    cursor = await db.execute(
        """SELECT DISTINCT tr.id, tr.task_id FROM task_runs tr
           JOIN task_dependencies td ON td.task_id = tr.task_id
           WHERE td.depends_on_task_id = ? AND tr.status = 'queued'""",
        (task_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]
