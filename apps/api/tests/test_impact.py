"""Impact finds what relied on an assertion and flags what saw a different status."""

from helpers import AUTH_A, AUTH_B

EARLY = "2026-10-15T12:00:00Z"
LATE = "2026-10-16T13:00:00Z"


def _snapshot(client, as_of, key):
    response = client.post(
        "/v1/snapshots",
        headers=AUTH_A,
        json={
            "as_of_time": as_of,
            "time_mode": "known",
            "entity_ids": ["project-atlas"],
            "idempotency_key": key,
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["snapshot_id"]


def _replay(client, snapshot_id, key):
    response = client.post(
        "/v1/replays",
        headers=AUTH_A,
        json={
            "question": "Which region?",
            "predicate": "deploy_region",
            "snapshot_id": snapshot_id,
            "idempotency_key": key,
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["replay_id"]


def test_impact_flags_early_replay_and_handoff(client, seeded):
    early = _snapshot(client, EARLY, "impact-early")
    late = _snapshot(client, LATE, "impact-late")
    early_replay = _replay(client, early, "impact-early-replay")
    _replay(client, late, "impact-late-replay")
    task = client.post(
        "/v1/tasks",
        headers=AUTH_A,
        json={
            "objective": "Ship Atlas",
            "owner_agent_id": "agent-planner",
            "acceptance_criteria": ["Use the deploy region"],
            "idempotency_key": "impact-task",
        },
    ).json()
    handoff = client.post(
        f"/v1/tasks/{task['task_id']}/handoff",
        headers=AUTH_A,
        json={
            "to_agent_id": "agent-release",
            "snapshot_id": early,
            "memory_refs": ["assert-region-a"],
            "expected_version": task["version"],
            "idempotency_key": "impact-handoff",
            "open_questions": [],
            "expires_at": "2026-10-20T00:00:00Z",
        },
    )
    assert handoff.status_code in (200, 201), handoff.text

    response = client.get("/v1/assertions/assert-region-a/impact", headers=AUTH_A)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assertion"]["status_now"] == "superseded"
    assert body["assertion"]["superseded_by"] == ["assert-region-b"]
    snapshots = {item["snapshot_id"]: item for item in body["snapshots"]}
    assert snapshots[early]["status_then"] == "current"
    assert snapshots[early]["outdated"] is True
    assert snapshots[late]["outdated"] is False
    assert [item["replay_id"] for item in body["replays"]] == [early_replay]
    assert body["replays"][0]["outdated"] is True
    assert body["replays"][0]["claim_value"] == "region-a"
    assert len(body["handoffs"]) == 1
    assert body["handoffs"][0]["referenced"] is True
    assert body["handoffs"][0]["outdated"] is True
    assert body["outdated_count"] == 3


def test_impact_with_nothing_recorded(client, seeded):
    body = client.get("/v1/assertions/assert-region-b/impact", headers=AUTH_A).json()
    assert body["snapshots"] == [] and body["replays"] == [] and body["handoffs"] == []
    assert "Nothing recorded" in body["summary"]


def test_impact_is_tenant_scoped(client, seeded):
    response = client.get("/v1/assertions/assert-region-a/impact", headers=AUTH_B)
    assert response.status_code == 404
    assert "region-a" not in response.text.replace("assert-region-a", "")
