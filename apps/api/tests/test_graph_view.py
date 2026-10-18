"""The evidence graph view matches snapshot status at a cutoff."""

from helpers import AUTH_A, AUTH_B

EARLY = "2026-10-15T12:00:00Z"
LATE = "2026-10-16T13:00:00Z"


def _graph(client, **params):
    response = client.get(
        "/v1/graph",
        headers=AUTH_A,
        params={"entity_id": "project-atlas", **params},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    nodes = {node["id"]: node for node in body["nodes"]}
    edges = {(edge["type"], edge["source"], edge["target"]): edge for edge in body["edges"]}
    return body, nodes, edges


def test_early_cutoff_hides_the_correction(client, seeded):
    body, nodes, edges = _graph(client, as_of=EARLY)
    assert nodes["assert-region-a"]["visible"] is True
    assert nodes["assert-region-a"]["status"] == "current"
    assert nodes["assert-region-b"]["visible"] is False
    assert nodes["assert-region-b"]["status"] is None
    assert nodes["source-change-002"]["visible"] is False
    supersedes = edges[("SUPERSEDES", "assert-region-b", "assert-region-a")]
    assert supersedes["visible"] is False
    assert body["moments"] == sorted(body["moments"])


def test_late_cutoff_shows_supersession_and_dispute(client, seeded):
    _, nodes, edges = _graph(client, as_of=LATE)
    assert nodes["assert-region-b"]["status"] == "current"
    assert nodes["assert-region-a"]["status"] == "superseded"
    assert nodes["assert-oncall-priya"]["status"] == "disputed"
    assert nodes["assert-oncall-jordan"]["status"] == "disputed"
    assert edges[("SUPERSEDES", "assert-region-b", "assert-region-a")]["visible"] is True
    conflict = [key for key in edges if key[0] == "CONFLICTS_WITH"]
    assert len(conflict) == 1
    assert edges[("SUPPORTED_BY", "assert-region-b", "source-change-002")]["visible"] is True
    assert nodes["evt-assert-region-b"]["kind"] == "event"


def test_excluding_a_source_greys_it_and_restores_region_a(client, seeded):
    _, nodes, _ = _graph(client, as_of=LATE, exclude_source_ids="source-change-002")
    assert nodes["source-change-002"]["excluded"] is True
    assert nodes["assert-region-b"]["visible"] is False
    assert nodes["assert-region-a"]["status"] == "current"


def test_other_tenant_cannot_read_the_graph(client, seeded):
    response = client.get(
        "/v1/graph",
        headers=AUTH_B,
        params={"entity_id": "project-atlas"},
    )
    assert response.status_code == 404
    assert "region" not in response.text
