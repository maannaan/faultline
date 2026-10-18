"""Every case in memory-tests.yaml holds against the seeded graph, and a broken
graph makes the suite fail instead of passing silently."""

from helpers import AUTH_A

from faultline.bench.memory_tests import load_cases, run_cases
from faultline.graph.seed import TENANT_ID


def test_memory_yaml_cases_pass(client, seeded):
    response = client.get("/v1/benchmarks/memory-tests", headers=AUTH_A)
    assert response.status_code == 200, response.text
    body = response.json()
    failed = [case for case in body["cases"] if not case["passed"]]
    assert failed == [], failed
    assert body["passed"] == len(load_cases()["cases"]) >= 6


def test_memory_yaml_catches_a_regression(store, seeded):
    spec = load_cases()
    spec["cases"][1]["expect"]["value"] = "region-a"
    report = run_cases(store.graph_for_tenant(TENANT_ID), spec)
    assert report.failed == 1
    assert report.cases[1].message.startswith("value region-b != region-a")
