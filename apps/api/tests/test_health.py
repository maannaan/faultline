"""Health checks."""

from fastapi.testclient import TestClient

from faultline.errors import FaultlineError
from faultline.llm.fake import FakeExtractor
from faultline.main import create_app


def test_ready_against_live_graph(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-correlation-id"]


def test_health_does_not_require_auth(client):
    assert client.get("/health").status_code == 200


class _DownStore:
    def ping(self) -> None:
        raise FaultlineError("graph_unavailable", "FalkorDB is unavailable", 503)


def test_ready_reports_graph_down(settings):
    application = create_app(settings, _DownStore(), FakeExtractor())
    with TestClient(application) as test_client:
        response = test_client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "graph_unavailable"
    assert "unavailable" in body["error"]["message"].lower()
