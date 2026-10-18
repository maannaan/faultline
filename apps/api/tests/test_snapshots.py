"""As-of snapshots against the seeded Atlas graph."""

from helpers import AUTH_A, AUTH_B

EARLY = "2026-10-15T12:00:00Z"
MID = "2026-10-16T10:30:00Z"
LATE = "2026-10-16T13:00:00Z"
ENTITY = "project-atlas"


def _snapshot(
    client,
    when,
    *,
    mode="known",
    exclude=None,
    key="snap-key",
    predicate=None,
    auth=None,
):
    body = {
        "as_of_time": when,
        "time_mode": mode,
        "entity_ids": [ENTITY],
        "exclude_source_ids": exclude or [],
        "idempotency_key": key,
    }
    if predicate:
        body["predicate"] = predicate
    return client.post("/v1/snapshots", headers=auth or AUTH_A, json=body)


def _by_id(payload):
    return {item["assertion_id"]: item for item in payload["included"]}


def test_early_known_snapshot_has_only_region_a(client, seeded):
    response = _snapshot(client, EARLY, key="early")
    assert response.status_code == 201, response.text
    included = _by_id(response.json())
    assert set(included) == {"assert-region-a"}
    assert included["assert-region-a"]["status"] == "current"
    assert included["assert-region-a"]["value"] == "region-a"
    current = client.get("/v1/assertions/assert-region-a", headers=AUTH_A)
    assert current.json()["status"] == "superseded"


def test_late_known_snapshot_supersedes_and_disputes(client, seeded):
    response = _snapshot(client, LATE, key="late")
    assert response.status_code == 201, response.text
    included = _by_id(response.json())
    assert included["assert-region-a"]["status"] == "superseded"
    assert included["assert-region-b"]["status"] == "current"
    assert included["assert-region-b"]["supersedes_ids"] == ["assert-region-a"]
    assert included["assert-oncall-priya"]["status"] == "disputed"
    assert included["assert-oncall-jordan"]["status"] == "disputed"
    assert "assert-oncall-jordan" in included["assert-oncall-priya"]["conflicts_with_ids"]


def test_midpoint_supersedes_region_only(client, seeded):
    response = _snapshot(client, MID, key="mid")
    assert response.status_code == 201, response.text
    included = _by_id(response.json())
    assert set(included) == {"assert-region-a", "assert-region-b"}
    assert included["assert-region-b"]["status"] == "current"
    assert included["assert-region-a"]["status"] == "superseded"


def test_valid_mode_drops_unknown_intervals(client, seeded):
    response = _snapshot(client, LATE, mode="valid", key="valid-late")
    assert response.status_code == 201, response.text
    body = response.json()
    included = _by_id(body)
    assert set(included) == {"assert-region-a", "assert-region-b"}
    assert set(body["validity_unknown_ids"]) == {"assert-oncall-priya", "assert-oncall-jordan"}
    timeline = client.get("/v1/timeline", headers=AUTH_A, params={"entity_id": ENTITY})
    oncall = [
        item
        for item in timeline.json()["items"]
        if item["assertion_id"] in body["validity_unknown_ids"]
    ]
    assert oncall
    assert all(item["valid_from"] is None for item in oncall)


def test_excluding_change_source_restores_region_a(client, seeded):
    response = _snapshot(
        client,
        LATE,
        exclude=["source-change-002"],
        key="exclude-change",
    )
    assert response.status_code == 201, response.text
    included = _by_id(response.json())
    assert "assert-region-b" not in included
    assert included["assert-region-a"]["status"] == "current"


def test_snapshot_idempotency_returns_original(client, seeded):
    first = _snapshot(client, EARLY, key="same-snap")
    second = _snapshot(client, LATE, key="same-snap")
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["snapshot_id"] == second.json()["snapshot_id"]
    assert second.json()["as_of_time"] == EARLY


def test_unknown_entity_and_source_write_nothing(client, seeded):
    missing_entity = client.post(
        "/v1/snapshots",
        headers=AUTH_A,
        json={
            "as_of_time": EARLY,
            "time_mode": "known",
            "entity_ids": ["missing-entity"],
            "idempotency_key": "missing-entity",
        },
    )
    assert missing_entity.status_code == 400
    missing_source = _snapshot(client, LATE, exclude=["source-missing"], key="missing-source")
    assert missing_source.status_code == 400
    assert "region-a" not in missing_entity.text
    assert "region-b" not in missing_source.text


def test_tenant_cannot_read_other_snapshot_or_evidence(client, seeded):
    created = _snapshot(client, LATE, key="tenant-snap")
    snapshot_id = created.json()["snapshot_id"]
    denied_snapshot = client.get(f"/v1/snapshots/{snapshot_id}", headers=AUTH_B)
    denied_evidence = client.get("/v1/assertions/assert-region-b/evidence", headers=AUTH_B)
    assert denied_snapshot.status_code == 404
    assert denied_evidence.status_code == 404
    for body in (denied_snapshot.text, denied_evidence.text):
        assert "region-a" not in body
        assert "region-b" not in body
        assert "Priya" not in body
        assert "Jordan" not in body


def test_evidence_path_returns_graph_ids(client, seeded):
    response = client.get("/v1/assertions/assert-region-b/evidence", headers=AUTH_A)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assertion_id"] == "assert-region-b"
    assert body["source_id"] == "source-change-002"
    assert body["event_id"] == "evt-assert-region-b"
    assert body["session_id"] == "session-atlas-seed"
    assert body["entity_id"] == ENTITY
    assert body["status"] == "current"
    assert body["supersedes_ids"] == ["assert-region-a"]


def test_second_connection_reads_snapshot(client, seeded, settings):
    created = _snapshot(client, EARLY, key="reconnect-snap")
    snapshot_id = created.json()["snapshot_id"]
    from faultline.graph.client import GraphStore
    from faultline.graph.repository import load_snapshot

    other = GraphStore(settings)
    loaded = load_snapshot(other.graph_for_tenant("tenant-synthetic"), snapshot_id)
    assert loaded is not None
    ids = {row["assertion_id"] for row in loaded["rows"] if row.get("assertion_id")}
    assert ids == {"assert-region-a"}
