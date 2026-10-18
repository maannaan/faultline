"""Deleting a real edge changes the Atlas answer, then the edge comes back."""

from helpers import AUTH_A, AUTH_B

from faultline.constants import REL_SUPERSEDES, REL_SUPPORTED_BY
from faultline.graph.repository import relationship_exists


def test_support_edge_drops_region_b_and_supersedes_abstains(client, seeded):
    response = client.post("/v1/benchmarks/ablation", headers=AUTH_A)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["restored"] is True
    assert body["intact"]["value"] == "region-b"
    assert "assert-region-b" in body["intact"]["evidence_ids"]

    support = body["support_deleted"]
    assert support["value"] != "region-b"
    assert "assert-region-b" not in support["evidence_ids"]
    assert "assert-region-b" not in {item["assertion_id"] for item in support["included"]}

    removed = body["supersedes_deleted"]
    assert removed["status"] == "insufficient"
    assert removed["value"] is None
    included = {item["assertion_id"]: item["status"] for item in removed["included"]}
    assert included["assert-region-a"] == "current"
    assert included["assert-region-b"] == "current"

    graph = seeded.graph_for_tenant("tenant-synthetic")
    assert relationship_exists(graph, REL_SUPPORTED_BY, "assert-region-b", "source-change-002")
    assert relationship_exists(graph, REL_SUPERSEDES, "assert-region-b", "assert-region-a")
    snapshot = client.post(
        "/v1/snapshots",
        headers=AUTH_A,
        json={
            "as_of_time": "2026-10-16T13:00:00Z",
            "time_mode": "known",
            "entity_ids": ["project-atlas"],
            "predicate": "deploy_region",
            "idempotency_key": "after-ablation-late",
        },
    )
    assert snapshot.status_code == 201, snapshot.text
    statuses = {item["assertion_id"]: item["status"] for item in snapshot.json()["included"]}
    assert statuses["assert-region-b"] == "current"
    assert statuses["assert-region-a"] == "superseded"


def test_other_tenant_cannot_run_ablation(client, seeded):
    denied = client.post("/v1/benchmarks/ablation", headers=AUTH_B)
    assert denied.status_code == 404
    assert "region-b" not in denied.text
    assert "Priya" not in denied.text
    assert "Jordan" not in denied.text
    graph = seeded.graph_for_tenant("tenant-synthetic")
    assert relationship_exists(graph, REL_SUPPORTED_BY, "assert-region-b", "source-change-002")
    assert relationship_exists(graph, REL_SUPERSEDES, "assert-region-b", "assert-region-a")
