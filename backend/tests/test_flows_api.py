import pytest
import pytest_asyncio


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _create_flow(client, name="Test Flow", **kwargs):
    payload = {"name": name, **kwargs}
    resp = await client.post("/api/flows", json=payload)
    assert resp.status_code == 200
    return resp.json()


# ── Tests ────────────────────────────────────────────────────────────────────

async def test_create_flow(client):
    data = await _create_flow(client, name="My Flow", description="A test flow")
    assert data["name"] == "My Flow"
    assert data["description"] == "A test flow"
    assert data["archived"] == 0
    assert data["id"]


async def test_list_flows(client):
    await _create_flow(client, name="Flow A")
    await _create_flow(client, name="Flow B")
    resp = await client.get("/api/flows")
    assert resp.status_code == 200
    flows = resp.json()
    assert len(flows) == 2


async def test_list_flows_excludes_archived(client):
    flow = await _create_flow(client, name="Archived Flow")
    await client.delete(f"/api/flows/{flow['id']}")
    resp = await client.get("/api/flows")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


async def test_get_flow(client):
    flow = await _create_flow(client)
    resp = await client.get(f"/api/flows/{flow['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == flow["id"]


async def test_update_flow(client):
    flow = await _create_flow(client, name="Original")
    resp = await client.patch(f"/api/flows/{flow['id']}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


async def test_archive_flow(client):
    flow = await _create_flow(client)
    resp = await client.delete(f"/api/flows/{flow['id']}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_create_flow_with_schedule(client):
    data = await _create_flow(client, name="Scheduled", schedule="0 9 * * *")
    assert data["schedule"] == "0 9 * * *"
    assert data["next_run_at"] is not None


async def test_trigger_flow(client):
    """Triggering a flow should queue runs for its root tasks."""
    flow = await _create_flow(client)
    # Create two root tasks in this flow
    for title in ("Root A", "Root B"):
        await client.post("/api/tasks", json={
            "title": title,
            "prompt": "do something",
            "flow_id": flow["id"],
        })

    resp = await client.post(f"/api/flows/{flow['id']}/trigger")
    assert resp.status_code == 200
    body = resp.json()
    assert body["triggered"] == 2
    assert len(body["runs"]) == 2
