"""Note ingest uses the fake extractor and still runs policy."""

from helpers import AUTH_A, AUTH_B

NOTE = (
    "entity=Project Atlas; type=Project; predicate=deploy_region; "
    "value=region-c; confidence=0.91"
)


def test_fake_ingest_persists_policy_outcome(client):
    response = client.post(
        "/v1/notes",
        headers=AUTH_A,
        json={
            "text": NOTE,
            "trust_tier": "reviewed",
            "observed_at": "2026-10-17T09:00:00Z",
            "session_id": "session-system",
            "agent_id": "agent-system",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["extraction_status"] == "completed"
    assert body["source_id"]
    assert len(body["assertions"]) == 1
    assert body["assertions"][0]["status"] == "current"
    assert body["assertions"][0]["evidence_path"][1] == body["source_id"]
    timeline = client.get(
        "/v1/timeline",
        headers=AUTH_A,
        params={"entity_id": body["assertions"][0]["evidence_path"][2]},
    )
    assert timeline.json()["items"][0]["value"] == "region-c"


def test_extraction_failure_keeps_the_source(client, store):
    class Boom:
        def extract(self, text: str):
            raise RuntimeError("model down")

    from fastapi.testclient import TestClient

    from faultline.main import create_app

    application = create_app(client.app.state.settings, store, Boom())
    with TestClient(application) as broken:
        response = broken.post(
            "/v1/notes",
            headers=AUTH_A,
            json={
                "text": "Project Atlas might move regions.",
                "trust_tier": "reviewed",
                "observed_at": "2026-10-17T09:00:00Z",
                "session_id": "session-system",
                "agent_id": "agent-system",
            },
        )
    assert response.status_code == 201
    body = response.json()
    assert body["extraction_status"] == "failed"
    assert body["assertions"] == []
    from faultline.graph.names import graph_name_for_tenant
    from faultline.graph.repository import find_source

    graph = store.graph_for_tenant("tenant-synthetic")
    assert graph.name if hasattr(graph, "name") else graph_name_for_tenant("tenant-synthetic")
    stored = find_source(graph, body["source_id"])
    assert stored is not None
    assert stored["trust_tier"] == "reviewed"
    entities = client.get("/v1/entities", headers=AUTH_A)
    assert entities.json()["entities"] == []
    assert client.get("/v1/entities", headers=AUTH_B).json()["entities"] == []
