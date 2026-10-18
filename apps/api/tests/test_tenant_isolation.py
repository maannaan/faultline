"""Tenant B cannot read Tenant A's memory."""

from helpers import AUTH_A, AUTH_B

FORBIDDEN = ("region-a", "region-b", "Priya", "Jordan", "assert-region-a")


def test_other_tenant_cannot_read_timeline_or_assertion(client, seeded):
    timeline = client.get(
        "/v1/timeline",
        headers=AUTH_B,
        params={"entity_id": "project-atlas", "tenant_id": "tenant-synthetic"},
    )
    assert timeline.status_code == 404
    timeline_text = timeline.text
    for secret in FORBIDDEN:
        assert secret not in timeline_text

    assertion = client.get("/v1/assertions/assert-region-b", headers=AUTH_B)
    assert assertion.status_code == 404
    assertion_text = assertion.text
    for secret in FORBIDDEN:
        assert secret not in assertion_text

    own = client.get(
        "/v1/timeline",
        headers=AUTH_A,
        params={"entity_id": "project-atlas"},
    )
    assert own.status_code == 200
    assert own.json()["items"][0]["value"] == "region-a"


def test_missing_token_is_rejected(client):
    response = client.get("/v1/entities")
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Bearer token is required"
