import pytest
import pytest_asyncio


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _create_task(client, title="Test Task", prompt="Do the thing", **kwargs):
    payload = {"title": title, "prompt": prompt, **kwargs}
    resp = await client.post("/api/tasks", json=payload)
    assert resp.status_code == 200
    return resp.json()


async def _create_flow(client, name="Flow"):
    resp = await client.post("/api/flows", json={"name": name})
    assert resp.status_code == 200
    return resp.json()


# ── CRUD ─────────────────────────────────────────────────────────────────────

async def test_create_task(client, db):
    data = await _create_task(client, title="My Task", prompt="hello")
    assert data["title"] == "My Task"
    assert data["prompt"] == "hello"
    assert data["status"] == "active"
    assert data["id"]

    # Verify row exists in DB
    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (data["id"],))
    row = await cursor.fetchone()
    assert row is not None
    assert row["title"] == "My Task"
    assert row["prompt"] == "hello"
    assert row["status"] == "active"


async def test_get_task(client):
    task = await _create_task(client)
    resp = await client.get(f"/api/tasks/{task['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == task["id"]
    assert resp.json()["latest_run"] is None


async def test_get_task_not_found(client):
    resp = await client.get("/api/tasks/nonexistent-id")
    assert resp.status_code == 404


async def test_list_tasks(client):
    await _create_task(client, title="A")
    await _create_task(client, title="B")
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_tasks_filter_by_status(client):
    task = await _create_task(client, title="Paused")
    await client.patch(f"/api/tasks/{task['id']}", json={"status": "paused"})

    await _create_task(client, title="Active")

    resp = await client.get("/api/tasks", params={"status": "active"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "Active"


async def test_list_tasks_filter_by_flow(client):
    flow = await _create_flow(client)
    await _create_task(client, title="In flow", flow_id=flow["id"])
    await _create_task(client, title="No flow")

    resp = await client.get("/api/tasks", params={"flow_id": flow["id"]})
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "In flow"


async def test_update_task(client, db):
    task = await _create_task(client)
    resp = await client.patch(f"/api/tasks/{task['id']}", json={
        "title": "Updated",
        "priority": 5,
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"
    assert resp.json()["priority"] == 5

    # Verify update persisted in DB
    cursor = await db.execute("SELECT title, priority FROM tasks WHERE id = ?", (task["id"],))
    row = await cursor.fetchone()
    assert row["title"] == "Updated"
    assert row["priority"] == 5


async def test_update_task_status(client):
    task = await _create_task(client)
    resp = await client.patch(f"/api/tasks/{task['id']}", json={"status": "paused"})
    assert resp.json()["status"] == "paused"


async def test_delete_task(client, db):
    task = await _create_task(client)
    resp = await client.delete(f"/api/tasks/{task['id']}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp = await client.get(f"/api/tasks/{task['id']}")
    assert resp.status_code == 404

    # Verify row is gone from DB
    cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE id = ?", (task["id"],))
    assert (await cursor.fetchone())[0] == 0


# ── Trigger & Runs ───────────────────────────────────────────────────────────

async def test_trigger_task(client, db):
    task = await _create_task(client)
    resp = await client.post(f"/api/tasks/{task['id']}/trigger")
    assert resp.status_code == 200
    run = resp.json()
    assert run["task_id"] == task["id"]
    assert run["run_number"] == 1
    assert run["status"] == "queued"
    assert run["trigger"] == "manual"

    # Verify task_runs row exists in DB
    cursor = await db.execute("SELECT * FROM task_runs WHERE id = ?", (run["id"],))
    row = await cursor.fetchone()
    assert row is not None
    assert row["task_id"] == task["id"]
    assert row["run_number"] == 1
    assert row["status"] == "queued"


async def test_trigger_task_increments_run_number(client):
    task = await _create_task(client)
    await client.post(f"/api/tasks/{task['id']}/trigger")
    resp = await client.post(f"/api/tasks/{task['id']}/trigger")
    assert resp.json()["run_number"] == 2


async def test_trigger_nonexistent_task(client):
    resp = await client.post("/api/tasks/bad-id/trigger")
    assert resp.status_code == 404


async def test_list_task_runs(client):
    task = await _create_task(client)
    await client.post(f"/api/tasks/{task['id']}/trigger")
    await client.post(f"/api/tasks/{task['id']}/trigger")
    resp = await client.get(f"/api/tasks/{task['id']}/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_task_with_latest_run(client):
    task = await _create_task(client)
    await client.post(f"/api/tasks/{task['id']}/trigger")
    resp = await client.get(f"/api/tasks/{task['id']}")
    assert resp.json()["latest_run"] is not None
    assert resp.json()["latest_run"]["run_number"] == 1


# ── Dependencies ─────────────────────────────────────────────────────────────

async def test_create_task_with_dependency(client):
    upstream = await _create_task(client, title="Upstream")
    downstream = await _create_task(client, title="Downstream", depends_on=[upstream["id"]])

    resp = await client.get(f"/api/tasks/{downstream['id']}/dependencies")
    assert upstream["id"] in resp.json()["depends_on"]


async def test_add_dependency(client, db):
    a = await _create_task(client, title="A")
    b = await _create_task(client, title="B")
    resp = await client.post(f"/api/tasks/{b['id']}/dependencies", json={
        "depends_on": [a["id"]],
    })
    assert resp.status_code == 200

    resp = await client.get(f"/api/tasks/{b['id']}/dependencies")
    assert a["id"] in resp.json()["depends_on"]

    # Verify dependency row in DB
    cursor = await db.execute(
        "SELECT * FROM task_dependencies WHERE task_id = ? AND depends_on_task_id = ?",
        (b["id"], a["id"]),
    )
    assert await cursor.fetchone() is not None


async def test_remove_dependency(client):
    a = await _create_task(client, title="A")
    b = await _create_task(client, title="B", depends_on=[a["id"]])
    resp = await client.delete(f"/api/tasks/{b['id']}/dependencies/{a['id']}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/tasks/{b['id']}/dependencies")
    assert resp.json()["depends_on"] == []


async def test_circular_dependency_rejected(client):
    a = await _create_task(client, title="A")
    b = await _create_task(client, title="B", depends_on=[a["id"]])

    # Try to make A depend on B → circular
    resp = await client.post(f"/api/tasks/{a['id']}/dependencies", json={
        "depends_on": [b["id"]],
    })
    assert resp.status_code == 400
    assert "circular" in resp.json()["error"]


async def test_self_dependency_rejected(client):
    a = await _create_task(client, title="A")
    resp = await client.post(f"/api/tasks/{a['id']}/dependencies", json={
        "depends_on": [a["id"]],
    })
    assert resp.status_code == 400


async def test_dependency_on_nonexistent_task(client):
    a = await _create_task(client, title="A")
    resp = await client.post(f"/api/tasks/{a['id']}/dependencies", json={
        "depends_on": ["nonexistent"],
    })
    assert resp.status_code == 404


# ── DAG ──────────────────────────────────────────────────────────────────────

async def test_dag_endpoint(client):
    a = await _create_task(client, title="A")
    b = await _create_task(client, title="B", depends_on=[a["id"]])

    resp = await client.get("/api/tasks/dag")
    assert resp.status_code == 200
    dag = resp.json()
    assert len(dag["nodes"]) == 2
    assert len(dag["edges"]) == 1
    assert dag["edges"][0]["source"] == a["id"]
    assert dag["edges"][0]["target"] == b["id"]


async def test_dag_filtered_by_flow(client):
    flow = await _create_flow(client)
    await _create_task(client, title="In flow", flow_id=flow["id"])
    await _create_task(client, title="Outside flow")

    resp = await client.get("/api/tasks/dag", params={"flow_id": flow["id"]})
    dag = resp.json()
    assert len(dag["nodes"]) == 1
    assert dag["nodes"][0]["title"] == "In flow"


# ── Schedule ─────────────────────────────────────────────────────────────────

async def test_create_task_with_schedule(client):
    task = await _create_task(client, schedule="*/5 * * * *")
    assert task["schedule"] == "*/5 * * * *"
    assert task["next_run_at"] is not None


# ── Delete cascades ──────────────────────────────────────────────────────────

async def test_delete_task_removes_runs_and_deps(client, db):
    a = await _create_task(client, title="A")
    b = await _create_task(client, title="B", depends_on=[a["id"]])
    await client.post(f"/api/tasks/{a['id']}/trigger")

    resp = await client.delete(f"/api/tasks/{a['id']}")
    assert resp.status_code == 200

    # Verify task row gone from DB
    cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE id = ?", (a["id"],))
    assert (await cursor.fetchone())[0] == 0

    # Verify task_runs rows gone from DB
    cursor = await db.execute("SELECT COUNT(*) FROM task_runs WHERE task_id = ?", (a["id"],))
    assert (await cursor.fetchone())[0] == 0

    # Verify dependency rows gone from DB
    cursor = await db.execute(
        "SELECT COUNT(*) FROM task_dependencies WHERE task_id = ? OR depends_on_task_id = ?",
        (a["id"], a["id"]),
    )
    assert (await cursor.fetchone())[0] == 0
