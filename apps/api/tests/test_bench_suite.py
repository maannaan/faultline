"""The generated benchmark: Faultline answers every question, and each baseline fails
only in the way its design predicts. Uses its own tenant graph."""

from faultline.bench.generate import build_timelines, reset_bench_graph, write_timelines
from faultline.bench.suite import score
from faultline.memory.service import MemoryService

TENANT = "tenant-bench-ci"


def test_generated_benchmark(settings, store):
    reset_bench_graph(store, TENANT)
    timelines = build_timelines(20, seed=11)
    write_timelines(MemoryService(settings, store), timelines, TENANT)
    report = score(store.graph_for_tenant(TENANT), timelines)
    methods = {method["method"]: method for method in report["methods"]}
    reset_bench_graph(store, TENANT)

    assert report["questions"] > 50
    assert methods["faultline"]["correct"] == report["questions"], methods["faultline"]["errors"]
    # The strongest baseline only ever misses conflicts: it has no notion of disagreement.
    assert set(methods["log_latest_reviewed"]["errors"]) <= {"missed_conflict"}
    # A plain log also trusts unreviewed notes.
    assert set(methods["log_latest"]["errors"]) <= {"missed_conflict", "untrusted_value"}
    # A key-value store answers past questions with values learned later.
    assert methods["kv_current"]["errors"].get("future_value", 0) > 0
