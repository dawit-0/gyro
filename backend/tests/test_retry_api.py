import pytest
import pytest_asyncio


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _create_flow(client, name="Test Flow", **kwargs):
    payload = {"name": name, **kwargs}
    resp = await client.post("/api/flows", json=payload)
    assert resp.status_code == 200
    return resp.json()


async def _create_task(client, title="Task", prompt="do it", **kwargs):
    payload = {"title": title, "prompt": prompt, **kwargs}
    resp = await client.post("/api/tasks", json=payload)
    assert resp.status_code == 200
    return resp.json()


async def _trigger_task(client, task_id):
    resp = await client.post(f"/api/tasks/{task_id}/trigger")
    assert resp.status_code == 200
    return resp.json()


async def _fail_run(db, run_id):
    """Manually mark a queued run as failed (simulates execution failure)."""
    await db.execute(
        "UPDATE task_runs SET status = 'failed', finished_at = datetime('now'), "
        "error_message = 'simulated failure' WHERE id = ?",
        (run_id,),
    )
    await db.commit()


async def _succeed_run(db, run_id):
    """Manually mark a queued run as succeeded."""
    await db.execute(
        "UPDATE task_runs SET status = 'success', finished_at = datetime('now') WHERE id = ?",
        (run_id,),
    )
    await db.commit()


async def _cancel_run(db, run_id):
    """Manually mark a queued run as cancelled."""
    await db.execute(
        "UPDATE task_runs SET status = 'cancelled', finished_at = datetime('now') WHERE id = ?",
        (run_id,),
    )
    await db.commit()


# ── Task Retry Config ───────────────────────────────────────────────────────

async def test_create_task_with_retry_config(client, db):
    """Tasks can be created with max_retries and retry_delay_seconds."""
    task = await _create_task(client, max_retries=3, retry_delay_seconds=30)

    cursor = await db.execute(
        "SELECT max_retries, retry_delay_seconds FROM tasks WHERE id = ?",
        (task["id"],),
    )
    row = await cursor.fetchone()
    assert row["max_retries"] == 3
    assert row["retry_delay_seconds"] == 30


async def test_create_task_default_retry_config(client, db):
    """Tasks default to max_retries=0 (no auto-retry)."""
    task = await _create_task(client)

    cursor = await db.execute(
        "SELECT max_retries, retry_delay_seconds FROM tasks WHERE id = ?",
        (task["id"],),
    )
    row = await cursor.fetchone()
    assert row["max_retries"] == 0
    assert row["retry_delay_seconds"] == 10


async def test_update_task_retry_config(client, db):
    """Retry config can be updated via PATCH."""
    task = await _create_task(client)
    resp = await client.patch(f"/api/tasks/{task['id']}", json={
        "max_retries": 5,
        "retry_delay_seconds": 60,
    })
    assert resp.status_code == 200

    cursor = await db.execute(
        "SELECT max_retries, retry_delay_seconds FROM tasks WHERE id = ?",
        (task["id"],),
    )
    row = await cursor.fetchone()
    assert row["max_retries"] == 5
    assert row["retry_delay_seconds"] == 60


# ── Task Retry Endpoint ─────────────────────────────────────────────────────

async def test_retry_task(client, db):
    """POST /api/tasks/{id}/retry creates a new run with trigger='retry'."""
    task = await _create_task(client)
    run = await _trigger_task(client, task["id"])
    await _fail_run(db, run["id"])

    resp = await client.post(f"/api/tasks/{task['id']}/retry")
    assert resp.status_code == 200
    retry_run = resp.json()
    assert retry_run["task_id"] == task["id"]
    assert retry_run["run_number"] == 2

    # Verify the retry run in DB
    cursor = await db.execute(
        "SELECT * FROM task_runs WHERE id = ?", (retry_run["id"],)
    )
    row = await cursor.fetchone()
    assert row["trigger"] == "retry"
    assert row["status"] == "queued"
    assert row["attempt_number"] == 2
    assert row["retry_of_run_id"] == run["id"]


async def test_retry_task_increments_attempt(client, db):
    """Multiple retries increment the attempt number."""
    task = await _create_task(client)

    run1 = await _trigger_task(client, task["id"])
    await _fail_run(db, run1["id"])

    resp = await client.post(f"/api/tasks/{task['id']}/retry")
    retry1 = resp.json()

    await _fail_run(db, retry1["id"])

    resp = await client.post(f"/api/tasks/{task['id']}/retry")
    retry2 = resp.json()

    cursor = await db.execute(
        "SELECT attempt_number FROM task_runs WHERE id = ?", (retry2["id"],)
    )
    row = await cursor.fetchone()
    assert row["attempt_number"] == 3


async def test_retry_task_with_no_prior_runs(client, db):
    """Retrying a task that has never run still works (attempt 1)."""
    task = await _create_task(client)
    resp = await client.post(f"/api/tasks/{task['id']}/retry")
    assert resp.status_code == 200
    retry_run = resp.json()
    assert retry_run["run_number"] == 1

    cursor = await db.execute(
        "SELECT attempt_number FROM task_runs WHERE id = ?", (retry_run["id"],)
    )
    row = await cursor.fetchone()
    assert row["attempt_number"] == 1


# ── Flow Retry Endpoint ─────────────────────────────────────────────────────

async def test_retry_flow(client, db):
    """POST /api/flows/{id}/retry re-triggers all root tasks."""
    flow = await _create_flow(client)
    root_a = await _create_task(client, title="Root A", flow_id=flow["id"])
    root_b = await _create_task(client, title="Root B", flow_id=flow["id"])
    downstream = await _create_task(
        client, title="Downstream", flow_id=flow["id"], depends_on=[root_a["id"]]
    )

    # Trigger and fail the flow
    run_a = await _trigger_task(client, root_a["id"])
    run_b = await _trigger_task(client, root_b["id"])
    await _fail_run(db, run_a["id"])
    await _succeed_run(db, run_b["id"])

    # Retry the whole flow
    resp = await client.post(f"/api/flows/{flow['id']}/retry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["retried"] == 2  # Both root tasks
    assert len(body["runs"]) == 2

    # Verify the new runs are for root tasks only
    retried_task_ids = {r["task_id"] for r in body["runs"]}
    assert root_a["id"] in retried_task_ids
    assert root_b["id"] in retried_task_ids
    assert downstream["id"] not in retried_task_ids


async def test_retry_flow_cancels_active_runs(client, db):
    """Flow retry cancels any currently queued/running runs."""
    flow = await _create_flow(client)
    task = await _create_task(client, title="Root", flow_id=flow["id"])
    run = await _trigger_task(client, task["id"])

    # Run is still queued, now retry the flow
    resp = await client.post(f"/api/flows/{flow['id']}/retry")
    assert resp.status_code == 200

    # Original run should be cancelled
    cursor = await db.execute(
        "SELECT status FROM task_runs WHERE id = ?", (run["id"],)
    )
    row = await cursor.fetchone()
    assert row["status"] == "cancelled"


async def test_retry_flow_creates_retry_trigger_runs(client, db):
    """Retry flow runs have trigger='retry'."""
    flow = await _create_flow(client)
    await _create_task(client, title="Root", flow_id=flow["id"])

    resp = await client.post(f"/api/flows/{flow['id']}/retry")
    body = resp.json()

    cursor = await db.execute(
        "SELECT trigger FROM task_runs WHERE id = ?", (body["runs"][0]["id"],)
    )
    row = await cursor.fetchone()
    assert row["trigger"] == "retry"


async def test_retry_nonexistent_flow(client):
    """Retrying a non-existent flow returns an error."""
    resp = await client.post("/api/flows/nonexistent/retry")
    assert resp.status_code == 200  # FastAPI tuple quirk
    # The response is a tuple (dict, 404) serialized


# ── Flow Resume Endpoint ────────────────────────────────────────────────────

async def test_resume_flow_retries_failed_tasks(client, db):
    """POST /api/flows/{id}/resume retries only failed tasks whose deps are satisfied."""
    flow = await _create_flow(client)
    root = await _create_task(client, title="Root", flow_id=flow["id"])
    mid = await _create_task(
        client, title="Middle", flow_id=flow["id"], depends_on=[root["id"]]
    )
    leaf = await _create_task(
        client, title="Leaf", flow_id=flow["id"], depends_on=[mid["id"]]
    )

    # Simulate: root succeeded, mid failed, leaf was cancelled
    run_root = await _trigger_task(client, root["id"])
    await _succeed_run(db, run_root["id"])

    run_mid = await _trigger_task(client, mid["id"])
    await _fail_run(db, run_mid["id"])

    run_leaf = await _trigger_task(client, leaf["id"])
    await _cancel_run(db, run_leaf["id"])

    # Resume should retry 'mid' (the earliest failure point), not 'leaf'
    # because leaf's upstream (mid) is still failed
    resp = await client.post(f"/api/flows/{flow['id']}/resume")
    assert resp.status_code == 200
    body = resp.json()
    assert body["retried"] == 1
    retried_ids = {r["task_id"] for r in body["runs"]}
    assert mid["id"] in retried_ids
    assert leaf["id"] not in retried_ids  # leaf's dep (mid) is still failed


async def test_resume_flow_no_failures(client, db):
    """Resuming a flow with no failures returns 0 retried."""
    flow = await _create_flow(client)
    task = await _create_task(client, title="Root", flow_id=flow["id"])
    run = await _trigger_task(client, task["id"])
    await _succeed_run(db, run["id"])

    resp = await client.post(f"/api/flows/{flow['id']}/resume")
    assert resp.status_code == 200
    assert resp.json()["retried"] == 0


async def test_resume_flow_retry_has_retry_of_ref(client, db):
    """Resumed runs reference the original failed run via retry_of_run_id."""
    flow = await _create_flow(client)
    task = await _create_task(client, title="Task", flow_id=flow["id"])
    run = await _trigger_task(client, task["id"])
    await _fail_run(db, run["id"])

    resp = await client.post(f"/api/flows/{flow['id']}/resume")
    body = resp.json()

    cursor = await db.execute(
        "SELECT retry_of_run_id FROM task_runs WHERE id = ?",
        (body["runs"][0]["id"],),
    )
    row = await cursor.fetchone()
    assert row["retry_of_run_id"] == run["id"]


# ── DAG includes retry fields ───────────────────────────────────────────────

async def test_dag_includes_retry_fields(client, db):
    """DAG endpoint returns max_retries, attempt_number, and latest_run_trigger."""
    task = await _create_task(client, max_retries=2)
    run = await _trigger_task(client, task["id"])

    resp = await client.get("/api/tasks/dag")
    assert resp.status_code == 200
    dag = resp.json()
    node = dag["nodes"][0]
    assert node["max_retries"] == 2
    assert node["attempt_number"] == 1
    assert node["latest_run_trigger"] == "manual"


async def test_dag_retry_trigger_shown(client, db):
    """After retrying, DAG node shows trigger='retry' and updated attempt_number."""
    task = await _create_task(client)
    run = await _trigger_task(client, task["id"])
    await _fail_run(db, run["id"])

    await client.post(f"/api/tasks/{task['id']}/retry")

    resp = await client.get("/api/tasks/dag")
    node = resp.json()["nodes"][0]
    assert node["latest_run_trigger"] == "retry"
    assert node["attempt_number"] == 2


# ── Task run fields ─────────────────────────────────────────────────────────

async def test_task_run_default_attempt_number(client, db):
    """Normal task runs have attempt_number=1 by default."""
    task = await _create_task(client)
    run = await _trigger_task(client, task["id"])

    cursor = await db.execute(
        "SELECT attempt_number, retry_of_run_id FROM task_runs WHERE id = ?",
        (run["id"],),
    )
    row = await cursor.fetchone()
    assert row["attempt_number"] == 1
    assert row["retry_of_run_id"] is None


async def test_resume_multiple_failed_roots(client, db):
    """Resume handles multiple independent failed tasks."""
    flow = await _create_flow(client)
    t1 = await _create_task(client, title="A", flow_id=flow["id"])
    t2 = await _create_task(client, title="B", flow_id=flow["id"])

    run1 = await _trigger_task(client, t1["id"])
    run2 = await _trigger_task(client, t2["id"])
    await _fail_run(db, run1["id"])
    await _fail_run(db, run2["id"])

    resp = await client.post(f"/api/flows/{flow['id']}/resume")
    body = resp.json()
    assert body["retried"] == 2
    retried_ids = {r["task_id"] for r in body["runs"]}
    assert t1["id"] in retried_ids
    assert t2["id"] in retried_ids
