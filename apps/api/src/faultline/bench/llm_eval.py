"""LLM-in-the-loop benchmark: the same model answers from raw notes or from Faultline evidence.

Both conditions get the same rules and the same question. Only the memory context
differs: a chronological note log versus Faultline's as-of evidence with statuses.
Needs OPENAI_API_KEY (any OpenAI-compatible host, e.g. Groq). Never runs in CI.

Usage: python -m faultline.bench.llm_eval [--sample 48] [--model openai/gpt-oss-20b] [--rpm 25]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import defaultdict
from typing import Any

from openai import APIError, RateLimitError

from faultline.bench.generate import (
    BENCH_TENANT,
    DISPUTED,
    INSUFFICIENT,
    SCENARIOS,
    SUPPORTED,
    Question,
    Timeline,
    build_timelines,
    reset_bench_graph,
    write_timelines,
)
from faultline.bench.report import meta, write
from faultline.bench.suite import FAR, _error_kind
from faultline.config import get_settings
from faultline.graph import repository as repo
from faultline.graph.client import GraphStore
from faultline.llm.client import openai_client
from faultline.memory.service import MemoryService
from faultline.replay.bisect import answer_at

PROMPT_VERSION = "llm-eval-v1"
SYSTEM_PROMPT = """You answer questions about what an AI agent's memory said at a given time.
Use only the memory provided. Rules:
- Only notes from reviewed sources count. Ignore unreviewed notes.
- A note that says it corrects an earlier note replaces that earlier note.
- If reviewed notes give different values and none corrects the other, the answer is DISPUTED.
- If nothing usable is known at that time, the answer is UNKNOWN.
Reply with JSON only: {"answer": "<value>" or "DISPUTED" or "UNKNOWN", "evidence_ids": ["..."]}"""


def raw_context(line: Timeline, question: Question) -> str:
    notes = [note for note in line.notes if _iso(note.observed_at) <= question.as_of]
    if not notes:
        return "(no notes)"
    out = []
    for note in notes:
        text = f"{line.entity_name} {line.predicate} is {note.value}."
        if note.correction_of:
            text += f" This corrects note {note.correction_of}."
        out.append(
            f"[{note.assertion_id}] {_iso(note.observed_at)} source={note.trust_tier}: {text}"
        )
    return "\n".join(out)


def faultline_context(graph: Any, question: Question) -> str:
    members, _claim = answer_at(
        graph, entity_id=question.entity_id, predicate=question.predicate, as_of=question.as_of
    )
    members = [member for member in members if member.predicate == question.predicate]
    if not members:
        return "(no evidence)"
    return "\n".join(
        f"[{m.assertion_id}] {m.predicate}={m.value} status={m.status} "
        f"observed={m.observed_at} reason: {m.reason}"
        for m in members
    )


def ask(client, model: str, question: Question, context: str, name: str) -> dict[str, Any]:
    user = (
        f"Memory as of {question.as_of}:\n{context}\n\n"
        f"Question: As of {question.as_of}, what is the {question.predicate} of {name}?"
    )
    for attempt in range(5):
        try:
            started = time.perf_counter()
            completion = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
            )
            latency = (time.perf_counter() - started) * 1000
            text = completion.choices[0].message.content or ""
            usage = completion.usage
            return {
                "text": text,
                "latency_ms": latency,
                "prompt": user,
                "tokens": (usage.total_tokens if usage else 0),
            }
        except RateLimitError:
            time.sleep(10 * (attempt + 1))
        except APIError as exc:
            return {
                "text": "",
                "error": exc.__class__.__name__,
                "latency_ms": 0.0,
                "prompt": user,
                "tokens": 0,
            }
    return {"text": "", "error": "rate_limited", "latency_ms": 0.0, "prompt": user, "tokens": 0}


def parse(text: str) -> tuple[str, str | None, list[str]] | None:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    answer = str(data.get("answer", "")).strip()
    cited = [str(item) for item in data.get("evidence_ids") or []]
    if not answer:
        return None
    if answer.upper() == "DISPUTED":
        return DISPUTED, None, cited
    if answer.upper() == "UNKNOWN":
        return INSUFFICIENT, None, cited
    return SUPPORTED, answer, cited


def stratified(timelines: list[Timeline], size: int, seed: int) -> list[tuple[Timeline, Question]]:
    rng = random.Random(seed)
    buckets: dict[str, list[tuple[Timeline, Question]]] = defaultdict(list)
    for line in timelines:
        for question in line.questions:
            buckets[line.scenario].append((line, question))
    per = max(1, size // len(SCENARIOS))
    picked: list[tuple[Timeline, Question]] = []
    for scenario in SCENARIOS:
        pool = buckets[scenario]
        picked.extend(rng.sample(pool, min(per, len(pool))))
    return picked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entities", type=int, default=200)
    parser.add_argument("--sample", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default="")
    parser.add_argument("--rpm", type=int, default=25)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        print(
            "OPENAI_API_KEY is empty. Set it in the repo-root .env (see README).", file=sys.stderr
        )
        return 1
    model = args.model or settings.openai_model
    client = openai_client(settings)
    store = GraphStore(settings)
    reset_bench_graph(store)
    timelines = build_timelines(args.entities, args.seed)
    write_timelines(MemoryService(settings, store), timelines)
    graph = store.graph_for_tenant(BENCH_TENANT)
    rows = repo.observed_assertions(graph, FAR)
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_key[(str(row["entity_id"]), str(row["predicate"]))].append(row)

    sample = stratified(timelines, args.sample, args.seed)
    gap = 60.0 / max(1, args.rpm)
    conditions = {
        "raw_notes": lambda line, q: raw_context(line, q),
        "faultline_evidence": lambda line, q: faultline_context(graph, q),
    }
    results = {}
    for condition, build in conditions.items():
        rows_out = []
        for index, (line, question) in enumerate(sample):
            context = build(line, question)
            reply = ask(client, model, question, context, line.entity_name)
            time.sleep(gap)
            parsed = parse(reply["text"])
            context_values = {n.value for n in line.notes}
            if parsed is None:
                status, value, cited, kind = "invalid", None, [], "invalid_output"
            else:
                status, value, cited = parsed
                correct = status == question.expected_status and value == question.expected_value
                kind = None if correct else _error_kind(question, status, value, by_key)
                if value is not None and value not in context_values:
                    kind = "invented_value"
            rows_out.append(
                {
                    "question_id": question.question_id,
                    "scenario": question.scenario,
                    "as_of": question.as_of,
                    "expected": [question.expected_status, question.expected_value],
                    "answer": [status, value],
                    "cited": cited,
                    "correct": kind is None,
                    "error": kind,
                    "latency_ms": round(reply["latency_ms"], 1),
                    "tokens": reply["tokens"],
                    **({"prompt": reply["prompt"], "reply": reply["text"]} if index < 3 else {}),
                }
            )
            print(
                f"{condition:<20} {index + 1:>3}/{len(sample)} {question.scenario:<17} "
                f"{'ok ' if kind is None else kind}"
            )
        results[condition] = _summary(rows_out)
        results[condition]["rows"] = rows_out
    reset_bench_graph(store)
    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
    write(
        f"llm-{slug}.json",
        {
            "meta": {**meta(args.seed), "llm_calls": 2 * len(sample)},
            "model": model,
            "base_url": settings.openai_base_url,
            "prompt_version": PROMPT_VERSION,
            "temperature": 0,
            "sample": len(sample),
            "system_prompt": SYSTEM_PROMPT,
            "conditions": results,
        },
    )
    for condition, summary in results.items():
        print(f"{condition:<20} {summary['correct']}/{summary['questions']} {summary['errors']}")
    return 0


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: dict[str, int] = defaultdict(int)
    by_scenario: dict[str, list[int]] = {s: [0, 0] for s in SCENARIOS}
    for row in rows:
        by_scenario[row["scenario"]][1] += 1
        if row["correct"]:
            by_scenario[row["scenario"]][0] += 1
        else:
            errors[row["error"]] += 1
    correct = sum(1 for row in rows if row["correct"])
    latencies = sorted(row["latency_ms"] for row in rows if row["latency_ms"])
    return {
        "correct": correct,
        "questions": len(rows),
        "accuracy": round(correct / len(rows), 4) if rows else 0.0,
        "errors": dict(sorted(errors.items())),
        "by_scenario": {s: {"correct": c, "questions": t} for s, (c, t) in by_scenario.items()},
        "latency_ms_p50": latencies[len(latencies) // 2] if latencies else 0.0,
        "tokens_total": sum(row["tokens"] for row in rows),
    }


def _iso(value) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
