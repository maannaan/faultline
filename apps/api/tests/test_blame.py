"""Blame follows an answer back to source, event, session and agent."""

from helpers import AUTH_A, AUTH_B
from test_impact import _replay, _snapshot

LATE = "2026-10-16T13:00:00Z"


def test_blame_traces_region_answer_to_the_agent(client, seeded):
    replay_id = _replay(client, _snapshot(client, LATE, "blame-late"), "blame-late-replay")
    response = client.get(f"/v1/replays/{replay_id}/blame", headers=AUTH_A)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["as_of"] == LATE
    [claim] = body["claims"]
    assert claim["value"] == "region-b"
    [hop] = claim["chain"]
    assert hop["assertion_id"] == "assert-region-b"
    assert hop["status_then"] == "current"
    assert hop["source_id"] == "source-change-002"
    assert hop["trust_tier"] == "reviewed"
    assert hop["event_id"] == "evt-assert-region-b"
    assert hop["session_id"] == "session-atlas-seed"
    assert hop["agent_id"]

    listed = client.get("/v1/replays", headers=AUTH_A).json()["replays"]
    assert listed[0]["replay_id"] == replay_id
    assert listed[0]["claim_value"] == "region-b"


def test_blame_of_disputed_answer_lists_both_sources(client, seeded):
    snapshot_id = _snapshot(client, LATE, "blame-oncall")
    response = client.post(
        "/v1/replays",
        headers=AUTH_A,
        json={
            "question": "Who is on call?",
            "predicate": "oncall_owner",
            "snapshot_id": snapshot_id,
            "idempotency_key": "blame-oncall-replay",
        },
    )
    body = client.get(f"/v1/replays/{response.json()['replay_id']}/blame", headers=AUTH_A).json()
    [claim] = body["claims"]
    assert claim["status"] == "disputed"
    assert claim["value"] is None
    sources = {hop["source_id"] for hop in claim["chain"]}
    assert sources == {"source-runbook-003", "source-slack-004"}


def test_blame_is_tenant_scoped(client, seeded):
    replay_id = _replay(client, _snapshot(client, LATE, "blame-tenant"), "blame-tenant-replay")
    assert client.get(f"/v1/replays/{replay_id}/blame", headers=AUTH_B).status_code == 404
