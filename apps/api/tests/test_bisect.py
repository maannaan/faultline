"""Memory bisect names the event that flipped an answer."""

from helpers import AUTH_A, AUTH_B

EARLY = "2026-10-15T12:00:00Z"
LATE = "2026-10-16T13:00:00Z"


def _bisect(client, predicate, good=EARLY, bad=LATE, headers=AUTH_A):
    return client.post(
        "/v1/bisect",
        headers=headers,
        json={
            "entity_id": "project-atlas",
            "predicate": predicate,
            "good_as_of": good,
            "bad_as_of": bad,
        },
    )


def test_bisect_finds_the_region_correction(client, seeded):
    response = _bisect(client, "deploy_region")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["flipped"] is True
    assert body["good"]["value"] == "region-a"
    assert body["bad"]["value"] == "region-b"
    assert body["first_bad_as_of"] == "2026-10-16T10:00:00Z"
    assert body["culprit_assertion_ids"] == ["assert-region-b"]
    assert body["culprit_source_ids"] == ["source-change-002"]
    assert body["culprit_event_ids"] == ["evt-assert-region-b"]
    assert "SUPERSEDES" in body["explanation"]
    assert body["probes"][-1]["verdict"] == "bad"


def test_bisect_finds_when_oncall_became_disputed(client, seeded):
    body = _bisect(client, "oncall_owner").json()
    assert body["flipped"] is True
    assert body["bad"]["status"] == "disputed"
    assert body["first_bad_as_of"] == "2026-10-16T12:00:00Z"
    assert body["culprit_assertion_ids"] == ["assert-oncall-jordan"]
    assert body["candidates"] == 2
    assert "CONFLICTS_WITH" in body["explanation"]


def test_bisect_reports_no_flip(client, seeded):
    body = _bisect(client, "deploy_region", good="2026-10-16T11:00:00Z").json()
    assert body["flipped"] is False
    assert body["probes"] == []


def test_bisect_validates_range_and_tenant(client, seeded):
    assert _bisect(client, "deploy_region", good=LATE, bad=EARLY).status_code == 400
    assert _bisect(client, "deploy_region", headers=AUTH_B).status_code == 404
