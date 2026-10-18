"""Saved benchmark results, written by bench.report and bench.llm_eval and served read-only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).resolve().parents[3] / "benchmarks"


def load_results() -> dict[str, Any]:
    def read(path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    llm = [data for path in sorted(RESULTS_DIR.glob("llm-*.json")) if (data := read(path))]
    return {
        "suite": read(RESULTS_DIR / "suite.json"),
        "scale": read(RESULTS_DIR / "scale.json"),
        "llm": llm,
    }
