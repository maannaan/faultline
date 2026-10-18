"""Run the generated benchmark, scale and bisect efficiency; write apps/api/benchmarks/*.json.

Usage: python -m faultline.bench.report [--entities 200] [--sizes 50,250,1000] [--seed 42]
Writes only to the separate bench tenant graph, never to the demo tenant.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from faultline.bench.generate import (
    BENCH_TENANT,
    build_timelines,
    reset_bench_graph,
    write_timelines,
)
from faultline.bench.results import RESULTS_DIR
from faultline.bench.scale import run_bisect_efficiency, run_scale
from faultline.bench.suite import score
from faultline.config import get_settings
from faultline.graph.client import GraphStore
from faultline.memory.service import MemoryService


def meta(seed: int) -> dict:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip()
    except OSError:
        commit = ""
    return {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": seed,
        "machine": platform.platform(),
        "python": platform.python_version(),
        "commit": commit,
        "llm_calls": 0,
    }


def write(name: str, payload: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entities", type=int, default=200)
    parser.add_argument("--sizes", default="50,250,1000")
    parser.add_argument("--lengths", default="8,32,128,512")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    settings = get_settings()
    store = GraphStore(settings)
    service = MemoryService(settings, store)

    reset_bench_graph(store)
    timelines = build_timelines(args.entities, args.seed)
    write_timelines(service, timelines)
    suite = score(store.graph_for_tenant(BENCH_TENANT), timelines)
    write("suite.json", {"meta": meta(args.seed), "entities": args.entities, **suite})
    for method in suite["methods"]:
        print(f"  {method['method']:<22} {method['correct']}/{method['questions']}")

    sizes = [int(size) for size in args.sizes.split(",") if size]
    lengths = [int(length) for length in args.lengths.split(",") if length]
    scale = run_scale(service, store, sizes, args.seed)
    bisect = run_bisect_efficiency(service, store, lengths, args.seed)
    write("scale.json", {"meta": meta(args.seed), "sizes": scale, "bisect": bisect})
    reset_bench_graph(store)


if __name__ == "__main__":
    main()
