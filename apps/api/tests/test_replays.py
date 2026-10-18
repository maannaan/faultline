"""Replay answers and evidence diffs."""

from fastapi.testclient import TestClient
from helpers import AUTH_A, AUTH_B

from faultline.errors import FaultlineError
from faultline.llm.fake import FakeExtractor
from faultline.main import create_app
from faultline.memory.temporal import SnapshotMember
from faultline.replay.answer import CLAIM_SUPPORTED, AnswerClaimDraft

EARLY = "2026-10-15T12:00:00Z"
LATE = "2026-10-16T13:00:00Z"
QUESTION = "Which deployment region should the rollout use?"


def _snapshot(client, when, *, key, exclude=None):
    response = client.post(
        "/v1/snapshots",
        headers=AUTH_A,
        json={
            "as_of_time": when,
            "time_mode": "known",
            "entity_ids": ["project-atlas"],
            "exclude_source_ids": exclude or [],
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["snapshot_id"]


def _replay(client, snapshot_id, *, predicate, key, question=QUESTION, auth=None):
    return client.post(
        "/v1/replays",
        headers=auth or AUTH_A,
        json={
            "question": question,
            "predicate": predicate,
            "snapshot_id": snapshot_id,
            "idempotency_key": key,
        },
    )


def test_region_replays_cite_the_cutoff_assertion(client, seeded):
    early = _snapshot(client, EARLY, key="replay-early-snap")
    late = _snapshot(client, LATE, key="replay-late-snap")
    before = _replay(client, early, predicate="deploy_region", key="replay-early")
    after = _replay(client, late, predicate="deploy_region", key="replay-late")
    assert before.status_code == 201, before.text
    assert after.status_code == 201, after.text
    before_claim = before.json()["claims"][0]
    after_claim = after.json()["claims"][0]
    assert before_claim["status"] == "supported"
    assert before_claim["value"] == "region-a"
    assert before_claim["evidence_ids"] == ["assert-region-a"]
    assert after_claim["value"] == "region-b"
    assert after_claim["evidence_ids"] == ["assert-region-b"]
    diff = client.get(
        f"/v1/replays/{after.json()['replay_id']}/diff",
        headers=AUTH_A,
        params={"baseline_replay_id": before.json()["replay_id"]},
    )
    assert diff.status_code == 200, diff.text
    body = diff.json()
    assert "assert-region-b" in body["added"]
    assert "source-change-002" in body["added_source_ids"]
    changed = {item["assertion_id"]: item for item in body["status_changed"]}
    assert changed["assert-region-a"]["from_status"] == "current"
    assert changed["assert-region-a"]["to_status"] == "superseded"
    assert "SUPERSEDES" in body["explanation"]
    assert "assert-region-a" in body["explanation"]
    assert body["answer_change"] == "evidence_changed"


def test_oncall_replay_abstains(client, seeded):
    late = _snapshot(client, LATE, key="oncall-snap")
    response = _replay(client, late, predicate="oncall_owner", key="oncall-replay")
    assert response.status_code == 201, response.text
    claim = response.json()["claims"][0]
    assert claim["status"] == "disputed"
    assert claim["value"] is None
    assert set(claim["evidence_ids"]) == {"assert-oncall-priya", "assert-oncall-jordan"}


def test_source_exclusion_replay_restores_region_a(client, seeded):
    late = _snapshot(client, LATE, key="ablate-base-snap")
    excluded = _snapshot(
        client,
        LATE,
        key="ablate-snap",
        exclude=["source-change-002"],
    )
    current = _replay(client, late, predicate="deploy_region", key="ablate-base-replay")
    counterfactual = _replay(
        client,
        excluded,
        predicate="deploy_region",
        key="ablate-replay",
    )
    diff = client.get(
        f"/v1/replays/{counterfactual.json()['replay_id']}/diff",
        headers=AUTH_A,
        params={"baseline_replay_id": current.json()["replay_id"]},
    )
    assert diff.status_code == 200, diff.text
    body = diff.json()
    assert "assert-region-b" in body["removed"]
    changed = {item["assertion_id"]: item for item in body["status_changed"]}
    assert changed["assert-region-a"]["from_status"] == "superseded"
    assert changed["assert-region-a"]["to_status"] == "current"


def test_unverified_claim_is_not_supported(client, seeded):
    source = client.post(
        "/v1/sources",
        headers=AUTH_A,
        json={
            "source_type": "synthetic_doc",
            "trust_tier": "unreviewed",
            "observed_at": "2026-10-16T12:30:00Z",
            "title": "Rumor",
            "text": "Someone heard region-c.",
        },
    )
    assert source.status_code == 201, source.text
    created = client.post(
        "/v1/assertions",
        headers=AUTH_A,
        json={
            "entity_id": "project-atlas",
            "predicate": "deploy_region",
            "value": "region-c",
            "source_id": source.json()["source_id"],
            "observed_at": "2026-10-16T12:30:00Z",
            "confidence": 0.4,
            "idempotency_key": "unverified-region-c",
        },
    )
    assert created.status_code == 201, created.text
    unverified_id = created.json()["assertion_id"]
    snapshot = client.post(
        "/v1/snapshots",
        headers=AUTH_A,
        json={
            "as_of_time": LATE,
            "time_mode": "known",
            "entity_ids": ["project-atlas"],
            "predicate": "deploy_region",
            "idempotency_key": "unverified-snap",
        },
    )
    included = {item["assertion_id"]: item for item in snapshot.json()["included"]}
    assert included[unverified_id]["status"] == "unverified"
    replay = _replay(
        client,
        snapshot.json()["snapshot_id"],
        predicate="deploy_region",
        key="unverified-replay",
    )
    claim = replay.json()["claims"][0]
    assert claim["status"] == "supported"
    assert claim["evidence_ids"] == ["assert-region-b"]
    assert unverified_id not in claim["evidence_ids"]


def test_replay_idempotency_returns_original(client, seeded):
    snapshot_id = _snapshot(client, EARLY, key="idem-replay-snap")
    first = _replay(client, snapshot_id, predicate="deploy_region", key="same-replay")
    second = _replay(client, snapshot_id, predicate="oncall_owner", key="same-replay")
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["replay_id"] == second.json()["replay_id"]
    assert second.json()["claims"][0]["predicate"] == "deploy_region"


def test_tenant_cannot_replay_other_snapshot(client, seeded):
    snapshot_id = _snapshot(client, EARLY, key="tenant-replay-snap")
    denied = _replay(
        client,
        snapshot_id,
        predicate="deploy_region",
        key="tenant-replay",
        auth=AUTH_B,
    )
    assert denied.status_code == 404
    assert "region-a" not in denied.text
    assert "region-b" not in denied.text


class _OutsideAnswerer:
    model_version = "test-outside"

    def answer(self, question: str, predicate: str, members: list[SnapshotMember]):
        del question, members
        return [
            AnswerClaimDraft(
                predicate=predicate,
                value="region-z",
                status=CLAIM_SUPPORTED,
                evidence_ids=("assert-not-in-snapshot",),
                wording="Invented.",
            )
        ]


def test_citation_outside_snapshot_is_rejected(settings, store, seeded):
    application = create_app(settings, store, FakeExtractor(), _OutsideAnswerer())
    with TestClient(application) as test_client:
        snapshot = test_client.post(
            "/v1/snapshots",
            headers=AUTH_A,
            json={
                "as_of_time": EARLY,
                "time_mode": "known",
                "entity_ids": ["project-atlas"],
                "idempotency_key": "cite-snap",
            },
        )
        assert snapshot.status_code == 201, snapshot.text
        replay = test_client.post(
            "/v1/replays",
            headers=AUTH_A,
            json={
                "question": QUESTION,
                "predicate": "deploy_region",
                "snapshot_id": snapshot.json()["snapshot_id"],
                "idempotency_key": "cite-replay",
            },
        )
    assert replay.status_code == 201, replay.text
    body = replay.json()
    assert body["citation_rejected"] is True
    assert body["claims"][0]["status"] == "insufficient"
    assert body["claims"][0]["evidence_ids"] == []
    assert "region-z" not in replay.text
    assert "assert-not-in-snapshot" not in replay.text


class _WordingAnswerer:
    model_version = "test-wording"

    def __init__(self) -> None:
        self.calls = 0

    def answer(self, question: str, predicate: str, members: list[SnapshotMember]):
        del question
        self.calls += 1
        evidence = tuple(
            member.assertion_id
            for member in members
            if member.predicate == predicate and member.status == "current"
        )
        value = next(member.value for member in members if member.assertion_id == evidence[0])
        return [
            AnswerClaimDraft(
                predicate=predicate,
                value=value,
                status=CLAIM_SUPPORTED,
                evidence_ids=evidence,
                wording=f"phrase-{self.calls}",
            )
        ]


def test_same_evidence_and_different_wording_is_not_a_memory_change(settings, store, seeded):
    answerer = _WordingAnswerer()
    application = create_app(settings, store, FakeExtractor(), answerer)
    with TestClient(application) as test_client:
        snapshot = test_client.post(
            "/v1/snapshots",
            headers=AUTH_A,
            json={
                "as_of_time": EARLY,
                "time_mode": "known",
                "entity_ids": ["project-atlas"],
                "idempotency_key": "wording-snap",
            },
        )
        first = test_client.post(
            "/v1/replays",
            headers=AUTH_A,
            json={
                "question": QUESTION,
                "predicate": "deploy_region",
                "snapshot_id": snapshot.json()["snapshot_id"],
                "idempotency_key": "wording-1",
            },
        )
        second = test_client.post(
            "/v1/replays",
            headers=AUTH_A,
            json={
                "question": QUESTION,
                "predicate": "deploy_region",
                "snapshot_id": snapshot.json()["snapshot_id"],
                "idempotency_key": "wording-2",
            },
        )
        diff = test_client.get(
            f"/v1/replays/{second.json()['replay_id']}/diff",
            headers=AUTH_A,
            params={"baseline_replay_id": first.json()["replay_id"]},
        )
    assert diff.status_code == 200, diff.text
    body = diff.json()
    assert body["added"] == []
    assert body["removed"] == []
    assert body["status_changed"] == []
    assert body["answer_change"] == "wording_only"


class _DownStore:
    def graph_for_tenant(self, tenant_id: str):
        del tenant_id
        raise FaultlineError("graph_unavailable", "FalkorDB is unavailable", 503)


def test_snapshot_reports_graph_down_without_a_claim(settings):
    application = create_app(settings, _DownStore(), FakeExtractor())
    with TestClient(application) as test_client:
        response = test_client.post(
            "/v1/snapshots",
            headers=AUTH_A,
            json={
                "as_of_time": EARLY,
                "time_mode": "known",
                "entity_ids": ["project-atlas"],
                "idempotency_key": "down",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "graph_unavailable"
    assert "region-a" not in response.text
