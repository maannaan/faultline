"""Policy v1 against the real graph."""

from helpers import AUTH_A

OBSERVED = "2026-10-15T09:00:00Z"
LATER = "2026-10-16T10:00:00Z"


def _source(client, *, title, text, trust="reviewed", observed_at=OBSERVED):
    response = client.post(
        "/v1/sources",
        headers=AUTH_A,
        json={
            "source_type": "synthetic_doc",
            "trust_tier": trust,
            "observed_at": observed_at,
            "title": title,
            "text": text,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["source_id"]


def _assertion(client, **overrides):
    body = {
        "entity_name": "Project Atlas",
        "entity_type": "Project",
        "predicate": "deploy_region",
        "value": "region-a",
        "source_id": overrides.get("source_id"),
        "observed_at": OBSERVED,
        "confidence": 0.9,
        "idempotency_key": "k-default",
    }
    body.update(overrides)
    return client.post("/v1/assertions", headers=AUTH_A, json=body)


def _entity_id(payload):
    return payload["evidence_path"][2]


def test_idempotency_key_returns_original_assertion(client):
    source_id = _source(client, title="Design", text="region a")
    first = _assertion(client, source_id=source_id, idempotency_key="same-key")
    second = _assertion(
        client,
        source_id=source_id,
        idempotency_key="same-key",
        value="region-z",
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["assertion_id"] == second.json()["assertion_id"]
    timeline = client.get(
        "/v1/timeline",
        headers=AUTH_A,
        params={"entity_id": _entity_id(first.json())},
    )
    assert timeline.status_code == 200
    assert len(timeline.json()["items"]) == 1
    assert timeline.json()["items"][0]["value"] == "region-a"


def test_semantic_duplicate_reuses_assertion(client):
    source_id = _source(client, title="Design", text="region a")
    first = _assertion(client, source_id=source_id, idempotency_key="sem-1")
    second = _assertion(client, source_id=source_id, idempotency_key="sem-2")
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["assertion_id"] == second.json()["assertion_id"]


def test_reviewed_correction_supersedes(client):
    design = _source(client, title="Design", text="region a")
    change = _source(client, title="Change", text="region b", observed_at=LATER)
    original = _assertion(
        client,
        source_id=design,
        idempotency_key="region-a",
        valid_from=OBSERVED,
    )
    corrected = _assertion(
        client,
        source_id=change,
        value="region-b",
        observed_at=LATER,
        idempotency_key="region-b",
        correction_of=original.json()["assertion_id"],
        valid_from=LATER,
    )
    assert corrected.status_code == 201
    body = corrected.json()
    assert body["status"] == "current"
    assert body["resolution"] == "supersedes_prior_assertion"
    assert original.json()["assertion_id"] in body["superseded_ids"]
    timeline = client.get(
        "/v1/timeline",
        headers=AUTH_A,
        params={"entity_id": _entity_id(body)},
    ).json()
    by_value = {item["value"]: item for item in timeline["items"]}
    assert by_value["region-a"]["status"] == "superseded"
    assert by_value["region-b"]["status"] == "current"
    assert by_value["region-a"]["valid_from"] == "2026-10-15T09:00:00Z"
    assert "valid_to" in by_value["region-a"]


def test_equal_trust_conflict_disputes_both(client):
    priya = _source(client, title="Runbook", text="Priya")
    jordan = _source(client, title="Note", text="Jordan", observed_at=LATER)
    first = _assertion(
        client,
        source_id=priya,
        predicate="oncall_owner",
        value="Priya",
        idempotency_key="priya",
    )
    second = _assertion(
        client,
        source_id=jordan,
        predicate="oncall_owner",
        value="Jordan",
        observed_at=LATER,
        idempotency_key="jordan",
    )
    assert second.status_code == 201
    assert second.json()["status"] == "disputed"
    assert second.json()["resolution"] == "unresolved_equal_trust"
    timeline = client.get(
        "/v1/timeline",
        headers=AUTH_A,
        params={"entity_id": _entity_id(first.json())},
    ).json()
    by_value = {item["value"]: item for item in timeline["items"]}
    assert by_value["Priya"]["status"] == "disputed"
    assert by_value["Jordan"]["status"] == "disputed"
    assert by_value["Priya"]["assertion_id"] in by_value["Jordan"]["conflicts_with_ids"]
    assert by_value["Jordan"]["assertion_id"] in by_value["Priya"]["conflicts_with_ids"]


def test_unreviewed_source_cannot_become_current(client):
    reviewed = _source(client, title="Design", text="region a")
    unreviewed = _source(client, title="Rumor", text="region c", trust="unreviewed")
    current = _assertion(client, source_id=reviewed, idempotency_key="current")
    rumor = _assertion(
        client,
        source_id=unreviewed,
        value="region-c",
        idempotency_key="rumor",
    )
    assert rumor.status_code == 201
    assert rumor.json()["status"] == "unverified"
    timeline = client.get(
        "/v1/timeline",
        headers=AUTH_A,
        params={"entity_id": _entity_id(current.json())},
    ).json()
    by_value = {item["value"]: item for item in timeline["items"]}
    assert by_value["region-a"]["status"] == "current"
    assert by_value["region-c"]["status"] == "unverified"


def test_unknown_source_writes_nothing(client):
    response = _assertion(client, source_id="missing-source", idempotency_key="no-source")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    entities = client.get("/v1/entities", headers=AUTH_A)
    assert entities.json()["entities"] == []


def test_unknown_predicate_is_rejected(client):
    source_id = _source(client, title="Design", text="color")
    response = _assertion(
        client,
        source_id=source_id,
        predicate="favorite_color",
        value="blue",
        idempotency_key="color",
    )
    assert response.status_code == 400
    assert "allow-listed" in response.json()["error"]["message"]


def test_naive_timestamp_is_rejected(client):
    response = client.post(
        "/v1/sources",
        headers=AUTH_A,
        json={
            "source_type": "synthetic_doc",
            "trust_tier": "reviewed",
            "observed_at": "2026-10-15T09:00:00",
            "title": "Naive",
            "text": "no zone",
        },
    )
    assert response.status_code == 400
    assert "timezone" in response.json()["error"]["message"]


def test_client_cannot_choose_tenant_or_status(client):
    source_id = _source(client, title="Design", text="region a")
    rejected = client.post(
        "/v1/assertions",
        headers=AUTH_A,
        json={
            "entity_name": "Project Atlas",
            "entity_type": "Project",
            "predicate": "deploy_region",
            "value": "region-a",
            "source_id": source_id,
            "observed_at": OBSERVED,
            "confidence": 0.5,
            "idempotency_key": "injected",
            "tenant_id": "tenant-other",
            "status": "current",
        },
    )
    assert rejected.status_code == 400
    created = _assertion(client, source_id=source_id, idempotency_key="kept")
    assert created.status_code == 201
    others = client.get("/v1/entities", headers={"Authorization": "Bearer other-key"})
    assert others.json()["entities"] == []
