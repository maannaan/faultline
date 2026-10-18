"""Write the ablation and baseline report. Does not call a model."""

from __future__ import annotations

import json
import platform

from faultline.bench.ablation import run_ablation
from faultline.bench.baseline import run_baseline
from faultline.config import REPO_ROOT, get_settings
from faultline.graph import repository as repo
from faultline.graph.client import GraphStore


def main() -> None:
    settings = get_settings()
    store = GraphStore(settings)
    seeded_size = repo.graph_size(store.graph_for_tenant("tenant-synthetic"))
    report = run_baseline(settings, store)
    ablation = run_ablation(settings, store, "tenant-synthetic")
    report["graph"] = seeded_size
    report["hardware"] = platform.platform()
    report["ablation"] = ablation.model_dump()
    path = REPO_ROOT / "docs" / "benchmark.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
