"""The three-question baseline stays deterministic and does not call a model."""

from faultline.bench.baseline import run_baseline


def test_baseline_counts(settings, seeded):
    report = run_baseline(settings, seeded)
    methods = {item["method"]: item for item in report["methods"]}
    faultline = methods["faultline"]
    flat = methods["flat_summary"]
    empty = methods["no_memory"]
    assert report["sample_size"] == 3
    assert faultline["correct"] == 3
    assert faultline["stale_answers"] == 0
    assert faultline["conflict_detections"] == 1
    assert faultline["evidence_coverage"] == 1
    assert empty["evidence_coverage"] == 0
    assert empty["correct"] == 0
    flat_rows = {row["question_id"]: row for row in flat["rows"]}
    assert flat_rows["early-region"]["stale"] is True
    assert flat_rows["early-region"]["value"] == "region-b"
    assert flat_rows["late-oncall"]["correct"] is False
    assert flat_rows["late-oncall"]["value"] == "Jordan"
    assert flat["conflict_detections"] == 0
    assert "do not show a general advantage" in report["limitations"]
