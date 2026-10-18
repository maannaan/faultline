"""Task handoffs carry snapshot conflicts the client cannot omit."""

from helpers import AUTH_A, AUTH_B

LATE = "2026-10-16T13:00:00Z"
EARLY = "2026-10-15T12:00:00Z"
FUTURE = "2026-10-20T00:00:00Z"
PAST = "2026-10-16T00:00:00Z"
OBJECTIVE = "Prepare the Atlas rollout checklist"


def _snapshot(client, when, key):
    response = client.post(
        "/v1/snapshots",
        headers=AUTH_A,
        json={
            "as_of_time": when,
            "time_mode": "known",
            "entity_ids": ["project-atlas"],
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["snapshot_id"]


def _task(client, key="task-1"):
    response = client.post(
        "/v1/tasks",
        headers=AUTH_A,
        json={
            "objective": OBJECTIVE,
            "owner_agent_id": "agent-planner",
            "acceptance_criteria": [
                "Use the accepted deploy region",
                "Surface unresolved memory conflicts before proceeding",
            ],
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["version"] == 1
    assert body["owner_agent_id"] == "agent-planner"
    return body["task_id"]


def _handoff(client, task_id, snapshot_id, *, key, refs, expires=FUTURE, version=1, auth=None):
    return client.post(
        f"/v1/tasks/{task_id}/handoff",
        headers=auth or AUTH_A,
        json={
            "to_agent_id": "agent-release",
            "snapshot_id": snapshot_id,
            "memory_refs": refs,
            "expected_version": version,
            "idempotency_key": key,
            "open_questions": ["Confirm the deployment window"],
            "expires_at": expires,
        },
    )


def test_handoff_keeps_conflicts_the_client_omits(client, seeded):
    snapshot_id = _snapshot(client, LATE, "handoff-late")
    task_id = _task(client)
    response = _handoff(
        client,
        task_id,
        snapshot_id,
        key="handoff-1",
        refs=["assert-region-b", "source-change-002"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "handed_off"
    assert body["version"] == 2
    handoff = body["handoff"]
    assert handoff["snapshot_id"] == snapshot_id
    assert set(handoff["memory_refs"]) == {"assert-region-b", "source-change-002"}
    conflicts = {item["assertion_id"]: item for item in handoff["unresolved_conflicts"]}
    assert set(conflicts) == {"assert-oncall-priya", "assert-oncall-jordan"}
    assert conflicts["assert-oncall-priya"]["value"] == "Priya"
    assert conflicts["assert-oncall-jordan"]["value"] == "Jordan"
    assert handoff["stale"] is False


def test_assertion_outside_snapshot_writes_nothing(client, seeded):
    snapshot_id = _snapshot(client, LATE, "outside-snap")
    task_id = _task(client, key="outside-task")
    response = _handoff(
        client,
        task_id,
        snapshot_id,
        key="outside-handoff",
        refs=["assert-region-b", "assert-not-in-snapshot"],
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "reference_not_in_snapshot"
    task = client.get(f"/v1/tasks/{task_id}", headers=AUTH_A)
    assert task.json()["status"] == "queued"
    assert task.json()["version"] == 1
    assert task.json()["handoff"] is None


def test_handoff_idempotency_does_not_bump_version(client, seeded):
    snapshot_id = _snapshot(client, LATE, "idem-snap")
    task_id = _task(client, key="idem-task")
    first = _handoff(client, task_id, snapshot_id, key="same-handoff", refs=["assert-region-b"])
    second = _handoff(
        client,
        task_id,
        snapshot_id,
        key="same-handoff",
        refs=["source-design-001"],
        version=2,
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["handoff"]["handoff_id"] == second.json()["handoff"]["handoff_id"]
    assert second.json()["version"] == 2
    assert "assert-region-b" in second.json()["handoff"]["memory_refs"]


def test_wrong_version_leaves_the_task_unchanged(client, seeded):
    snapshot_id = _snapshot(client, LATE, "version-snap")
    task_id = _task(client, key="version-task")
    response = _handoff(
        client,
        task_id,
        snapshot_id,
        key="version-handoff",
        refs=["assert-region-b"],
        version=9,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"
    task = client.get(f"/v1/tasks/{task_id}", headers=AUTH_A)
    assert task.json()["version"] == 1
    assert task.json()["status"] == "queued"


def test_accept_moves_owner_and_sender_cannot_accept(client, seeded):
    snapshot_id = _snapshot(client, LATE, "accept-snap")
    task_id = _task(client, key="accept-task")
    created = _handoff(client, task_id, snapshot_id, key="accept-handoff", refs=["assert-region-b"])
    assert created.status_code == 201
    sender = client.post(
        f"/v1/tasks/{task_id}/accept",
        headers=AUTH_A,
        json={"agent_id": "agent-planner", "expected_version": 2},
    )
    assert sender.status_code == 400
    unchanged = client.get(f"/v1/tasks/{task_id}", headers=AUTH_A)
    assert unchanged.json()["owner_agent_id"] == "agent-planner"
    accepted = client.post(
        f"/v1/tasks/{task_id}/accept",
        headers=AUTH_A,
        json={"agent_id": "agent-release", "expected_version": 2},
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "claimed"
    assert body["version"] == 3
    assert body["owner_agent_id"] == "agent-release"


def test_complete_stores_result_and_expired_handoff_blocks(client, seeded):
    snapshot_id = _snapshot(client, LATE, "complete-snap")
    fresh_id = _task(client, key="complete-task")
    _handoff(client, fresh_id, snapshot_id, key="complete-handoff", refs=["assert-region-b"])
    client.post(
        f"/v1/tasks/{fresh_id}/accept",
        headers=AUTH_A,
        json={"agent_id": "agent-release", "expected_version": 2},
    )
    completed = client.post(
        f"/v1/tasks/{fresh_id}/complete",
        headers=AUTH_A,
        json={
            "expected_version": 3,
            "result": "Checklist uses region-b",
            "evidence_refs": ["assert-region-b"],
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["handoff"]["result"] == "Checklist uses region-b"

    expired_task = _task(client, key="expired-task")
    _handoff(
        client,
        expired_task,
        snapshot_id,
        key="expired-handoff",
        refs=["assert-region-b"],
        expires=PAST,
    )
    client.post(
        f"/v1/tasks/{expired_task}/accept",
        headers=AUTH_A,
        json={"agent_id": "agent-release", "expected_version": 2},
    )
    blocked = client.post(
        f"/v1/tasks/{expired_task}/complete",
        headers=AUTH_A,
        json={
            "expected_version": 3,
            "result": "Should not land",
            "evidence_refs": ["assert-region-b"],
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "snapshot_stale"
    current = client.get(f"/v1/tasks/{expired_task}", headers=AUTH_A)
    assert current.json()["status"] == "claimed"
    assert current.json()["handoff"]["result"] is None


def test_revalidate_clears_expiry_with_a_future_timestamp(client, seeded):
    snapshot_id = _snapshot(client, LATE, "revalidate-snap")
    refreshed = _snapshot(client, LATE, "revalidate-snap-2")
    task_id = _task(client, key="revalidate-task")
    _handoff(
        client,
        task_id,
        snapshot_id,
        key="revalidate-handoff",
        refs=["assert-region-b"],
        expires=PAST,
    )
    response = client.post(
        f"/v1/tasks/{task_id}/revalidate",
        headers=AUTH_A,
        json={
            "expected_version": 2,
            "snapshot_id": refreshed,
            "expires_at": FUTURE,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == 3
    assert body["status"] == "handed_off"
    assert body["handoff"]["snapshot_id"] == refreshed
    assert body["handoff"]["stale"] is False
    assert {item["assertion_id"] for item in body["handoff"]["unresolved_conflicts"]} == {
        "assert-oncall-priya",
        "assert-oncall-jordan",
    }


def test_newer_assertion_makes_an_early_handoff_stale(client, seeded):
    snapshot_id = _snapshot(client, EARLY, "early-handoff-snap")
    task_id = _task(client, key="early-handoff-task")
    created = _handoff(
        client,
        task_id,
        snapshot_id,
        key="early-handoff",
        refs=["assert-region-a"],
    )
    assert created.status_code == 201, created.text
    assert created.json()["handoff"]["stale"] is True
    client.post(
        f"/v1/tasks/{task_id}/accept",
        headers=AUTH_A,
        json={"agent_id": "agent-release", "expected_version": 2},
    )
    blocked = client.post(
        f"/v1/tasks/{task_id}/complete",
        headers=AUTH_A,
        json={
            "expected_version": 3,
            "result": "Would use region-a",
            "evidence_refs": ["assert-region-a"],
        },
    )
    assert blocked.status_code == 409
    assert client.get(f"/v1/tasks/{task_id}", headers=AUTH_A).json()["status"] == "claimed"


def test_tenant_cannot_read_or_accept_another_task(client, seeded):
    snapshot_id = _snapshot(client, LATE, "tenant-snap")
    task_id = _task(client, key="tenant-task")
    _handoff(client, task_id, snapshot_id, key="tenant-handoff", refs=["assert-region-b"])
    denied_read = client.get(f"/v1/tasks/{task_id}", headers=AUTH_B)
    denied_accept = client.post(
        f"/v1/tasks/{task_id}/accept",
        headers=AUTH_B,
        json={"agent_id": "agent-release", "expected_version": 2},
    )
    denied_complete = client.post(
        f"/v1/tasks/{task_id}/complete",
        headers=AUTH_B,
        json={
            "expected_version": 2,
            "result": "nope",
            "evidence_refs": ["assert-region-b"],
        },
    )
    for response in (denied_read, denied_accept, denied_complete):
        assert response.status_code == 404
        assert OBJECTIVE not in response.text
        assert "region-b" not in response.text
        assert "Priya" not in response.text
        assert "Jordan" not in response.text


def test_second_connection_reads_handoff(client, seeded, settings):
    snapshot_id = _snapshot(client, LATE, "reconnect-snap")
    task_id = _task(client, key="reconnect-task")
    created = _handoff(
        client,
        task_id,
        snapshot_id,
        key="reconnect-handoff",
        refs=["assert-region-b"],
    )
    handoff_id = created.json()["handoff"]["handoff_id"]
    from faultline.graph.client import GraphStore
    from faultline.graph.repository import load_task

    other = GraphStore(settings)
    loaded = load_task(other.graph_for_tenant("tenant-synthetic"), task_id)
    assert loaded is not None
    assert loaded["handoff_id"] == handoff_id
    assert "assert-oncall-priya" in {row["assertion_id"] for row in loaded["conflicts"]}
