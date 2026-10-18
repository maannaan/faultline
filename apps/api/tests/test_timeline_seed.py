"""Atlas seed is visible from a Cypher-backed timeline."""

from helpers import AUTH_A


def test_seeded_timeline_shows_supersession_and_conflict(client, seeded):
    response = client.get(
        "/v1/timeline",
        headers=AUTH_A,
        params={"entity_id": "project-atlas"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["policy_version"] == "memory-policy-v1"
    by_id = {item["assertion_id"]: item for item in body["items"]}
    region_a = by_id["assert-region-a"]
    region_b = by_id["assert-region-b"]
    priya = by_id["assert-oncall-priya"]
    jordan = by_id["assert-oncall-jordan"]
    assert region_a["status"] == "superseded"
    assert region_a["source_id"] == "source-design-001"
    assert region_a["event_id"] == "evt-assert-region-a"
    assert region_a["valid_from"] == "2026-10-15T09:00:00Z"
    assert region_b["status"] == "current"
    assert region_b["source_id"] == "source-change-002"
    assert region_b["event_id"] == "evt-assert-region-b"
    assert "assert-region-a" in region_b["supersedes_ids"]
    assert priya["status"] == "disputed"
    assert jordan["status"] == "disputed"
    assert "assert-oncall-jordan" in priya["conflicts_with_ids"]
    assert "assert-oncall-priya" in jordan["conflicts_with_ids"]
    assert [item["observed_at"] for item in body["items"]] == sorted(
        item["observed_at"] for item in body["items"]
    )
