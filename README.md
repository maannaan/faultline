# Faultline

Faultline is a memory debugger for AI agents. When an answer changes, it shows the snapshot the agent had, the sources behind each fact, and the unresolved conflicts a later agent still has to see.

This is [Graph Hacks](https://www.wemakedevs.org/hackathons/falkordb) Track 02, Agent Memory and Coordination. The graph stores events, assertions, supersession, conflicts, snapshots, replays, and handoffs. The demo data is the synthetic Project Atlas rollout. There is no public deployment. Run it locally.

An AI coding assistant implemented the code. The author owns the architecture, the memory policy, and the verification.

## Graph

One FalkorDB graph per tenant. `tenant-synthetic` is stored as `tenant_tenant_synthetic`. The server derives the name from the bearer token. Request bodies cannot select a tenant or an assertion status.

Labels: `Tenant`, `User`, `Agent`, `Session`, `MemoryEvent`, `Entity`, `Source`, `Assertion`, `Snapshot`, `ReplayRun`, `AnswerClaim`, `Task`, `Handoff`, `SchemaMeta`.

Relationships:

- `(Assertion)-[:ABOUT]->(Entity)`
- `(Assertion)-[:SUPPORTED_BY]->(Source)`
- `(Assertion)-[:SUPERSEDES]->(Assertion)` from the newer correction to the older assertion
- `(Assertion)-[:CONFLICTS_WITH]->(Assertion)` once, read in either direction
- `(MemoryEvent)-[:CREATED_ASSERTION]->(Assertion)`, `(MemoryEvent)-[:OBSERVED_SOURCE]->(Source)`, `(MemoryEvent)-[:MENTIONS_ENTITY]->(Entity)`
- `(Session)-[:CONTAINS_EVENT]->(MemoryEvent)`, `(Agent)-[:RECORDED]->(MemoryEvent)`, `(User)-[:STARTED_SESSION]->(Session)`
- `(Tenant)-[:HAS_USER]->(User)` and `(Tenant)-[:HAS_AGENT]->(Agent)`
- `(Snapshot)-[:INCLUDES_ASSERTION]->(Assertion)` with `status_at_snapshot` on the edge
- `(ReplayRun)-[:USED_SNAPSHOT]->(Snapshot)` and `(AnswerClaim)-[:SUPPORTED_BY_ASSERTION]->(Assertion)`
- `(Agent)-[:OWNS_TASK]->(Task)`, `(Task)-[:HAS_HANDOFF]->(Handoff)`, `(Handoff)-[:ASSIGNED_TO]->(Agent)`
- `(Handoff)-[:USED_SNAPSHOT]->(Snapshot)`, `(Handoff)-[:REFERENCES_MEMORY]->(Assertion|Source)`, `(Handoff)-[:INCLUDES_CONFLICT]->(Assertion)`

## Observed time and valid time

`observed_at` is when Faultline recorded the evidence. `valid_from` and `valid_to` are stored only when the source supplied them. The `status` property on an assertion is the status now. A snapshot stores a separate status on `INCLUDES_ASSERTION` and does not rewrite the node.

- `time_mode=known` includes an assertion when `observed_at` is at or before the cutoff.
- `time_mode=valid` also requires a supplied interval that covers the cutoff. A missing `valid_from` is listed in `validity_unknown_ids` and is not invented.

An edge counts at a cutoff only when the other assertion was also observed by that time. For Project Atlas after `make reset` and `make seed`:

- `2026-10-15T12:00:00Z` known: `assert-region-a` is current. `region-b` is not included.
- `2026-10-16T13:00:00Z` known: `region-b` is current, `region-a` is superseded, and Priya and Jordan are disputed.
- The same late time with `time_mode=valid` keeps the region assertions and lists both on-call assertions as validity unknown.
- Excluding `source-change-002` removes `region-b` from that snapshot and makes `region-a` current inside it. That filter does not delete the edge.

## Cypher

As-of retrieval requires the source edge. Values stay in parameters. The relationship lists use pattern comprehensions so one assertion's supersession edges are not mixed into another row:

```cypher
MATCH (a:Assertion)-[:ABOUT]->(e:Entity)
WHERE a.observed_at <= $as_of
MATCH (a)-[:SUPPORTED_BY]->(s:Source)
RETURN a.id, a.predicate, a.value, s.id, s.trust_tier,
       [(a)-[:SUPERSEDES]->(older) | older.id] AS supersedes_ids,
       [(newer)-[:SUPERSEDES]->(a) | newer.id] AS superseded_by_ids,
       [(a)-[:CONFLICTS_WITH]-(other) | other.id] AS conflict_ids
```

The ablation command deletes one relationship and recreates it:

```cypher
MATCH (a:Assertion {id: $from_id})-[r:SUPPORTED_BY]->(b:Source {id: $to_id})
DELETE r
```

```cypher
MATCH (a:Assertion {id: $from_id}), (b:Assertion {id: $to_id})
MERGE (a)-[:SUPERSEDES]->(b)
```

Handoff context is the latest `(Task)-[:HAS_HANDOFF]->(Handoff)` plus `(Handoff)-[:INCLUDES_CONFLICT]->(Assertion)` for every disputed member of the snapshot. The client cannot omit those conflict ids.

## Quick start

Requirements: Docker, Python 3.12, [uv](https://docs.astral.sh/uv/), and Node.js.

```bash
cp .env.example .env
# Set FALKORDB_PASSWORD. Do not commit .env or an API key.
make up
make test
make seed
make bench
make api
make web
```

- API: http://127.0.0.1:8000/docs
- Timeline: http://127.0.0.1:3010
- Replay Lab: http://127.0.0.1:3010/replay
- Handoff: http://127.0.0.1:3010/handoff
- Bench: http://127.0.0.1:3010/bench
- FalkorDB Browser: http://127.0.0.1:3000

The graph port and the browser are bound to `127.0.0.1` only. FalkorDB is pinned to image digest `sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6`. The web app uses port 3010 so it stays off that browser. `make up` starts FalkorDB. Day-to-day API work uses `make api` on the host. Copy `apps/web/.env.example` to `apps/web/.env.local` if you start Next.js without `make`.

| Variable | Purpose |
| --- | --- |
| `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_PASSWORD` | Graph connection |
| `AUTH_KEYS` | `key:tenant` pairs. Local keys: `dev-key:tenant-synthetic`, `other-key:tenant-other` |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | Live extraction and answer phrasing. Groq: base `https://api.groq.com/openai/v1`, model `openai/gpt-oss-20b`. An empty key uses the scripted extractor and the deterministic answerer |
| `POLICY_VERSION` | `memory-policy-v1` |
| `SCHEMA_VERSION` | `1` |
| `MAX_NOTE_CHARS` | Reject longer notes and source text |
| `APP_ENV` | `reset` and `make bench` run only when this is `development` |

`make seed` loads Project Atlas through the write path: `region-a` superseded by `region-b`, and on-call owners Priya and Jordan disputed. No task is seeded.

`make reset` deletes only `tenant-synthetic` and `tenant-other`.

Restart check:

```bash
make seed
docker compose restart falkordb
make api
```

Open the timeline. `region-b` is still current, `region-a` is still superseded, and both owners are still disputed.

Replay answers one predicate from one snapshot. A disputed predicate returns no chosen value. `GET /v1/replays/{id}/diff?baseline_replay_id=` reports added and removed assertion ids, status changes, and a `SUPERSEDES` explanation when that edge is why the status changed.

Handoff transitions that are implemented: `queued` to `handed_off`, `handed_off` to `claimed` by the recipient only, and `claimed` to `completed` when the handoff is not stale. `blocked` and `failed` are named and unused. Version checks are the concurrency control. This is one API process, not a distributed transaction.

The server copies every disputed assertion in the snapshot onto the handoff. `stale` is derived on read and on complete. It is true when `expires_at` is already past, or when a later `current` or `disputed` assertion on a referenced predicate was observed after the snapshot cutoff. A stale complete returns 409 `snapshot_stale` and does not store the result.

```bash
curl -s -X POST http://127.0.0.1:8000/v1/snapshots \
  -H "Authorization: Bearer dev-key" -H "Content-Type: application/json" \
  -d '{"as_of_time":"2026-10-16T13:00:00Z","time_mode":"known","entity_ids":["project-atlas"],"idempotency_key":"atlas-late"}'

curl -s -X POST http://127.0.0.1:8000/v1/tasks \
  -H "Authorization: Bearer dev-key" -H "Content-Type: application/json" \
  -d '{"objective":"Prepare the Atlas rollout checklist","owner_agent_id":"agent-planner","acceptance_criteria":["Use the accepted deploy region","Surface unresolved memory conflicts before proceeding"],"idempotency_key":"atlas-task"}'

curl -s -X POST http://127.0.0.1:8000/v1/tasks/TASK_ID/handoff \
  -H "Authorization: Bearer dev-key" -H "Content-Type: application/json" \
  -d '{"to_agent_id":"agent-release","snapshot_id":"SNAPSHOT_ID","memory_refs":["assert-region-b","source-change-002"],"expected_version":1,"idempotency_key":"atlas-handoff","open_questions":["Who is on call?"],"expires_at":"2026-10-20T00:00:00Z"}'
```

The handoff cites `assert-region-b` and `source-change-002`, and it still stores both on-call assertions. The recording script is `docs/demo-script.md`.

## Benchmark

`make bench` scores three questions on the seeded graph and writes `docs/benchmark.json`. It uses the deterministic answerer. It does not call Groq. The count below is the seeded graph before those writes: 26 nodes, 49 edges, 4 assertions, on `macOS-26.6.2-x86_64-i386-64bit`. Token counts are `len(prompt) / 4`, not a model tokenizer. Sample size is 3. These scores do not show a general advantage over other memory systems.

| Method | Correct | Evidence coverage | Stale answers | Conflicts surfaced |
| --- | --- | --- | --- | --- |
| No memory | 0/3 | 0 | 0 | 0 |
| Flat summary, latest line wins | 1/3 | 0 | 1 | 0 |
| Faultline | 3/3 | 1 | 0 | 1 |

The early region question is the stale one: the flat summary answers `region-b` before that correction was observed. Faultline answers `region-a` and cites `assert-region-a`. At the late cutoff Faultline answers `region-b` and cites `assert-region-b`. On-call stays disputed, with both owners cited. The flat summary picks Jordan.

`POST /v1/benchmarks/ablation` deletes `(assert-region-b)-[:SUPPORTED_BY]->(source-change-002)`, asks the late region question, and restores the edge. The answer is no longer `region-b`. It then deletes `(assert-region-b)-[:SUPERSEDES]->(assert-region-a)`. Both assertions stay `current`, and the claim is `insufficient` with no chosen value. Both edges are put back. The Bench page is http://127.0.0.1:3010/bench.

## Isolation and limits

Another tenant's read of a timeline, snapshot, replay, task, or ablation returns 404. The body does not include assertion values, owner names, or the objective. If FalkorDB is stopped, the API returns `graph_unavailable` with HTTP 503 and does not invent an answer.

Only `deploy_region` and `oncall_owner` are accepted. A reviewed `correction_of` writes `SUPERSEDES`. Two reviewed sources with different values and no correction write `CONFLICTS_WITH` and stay disputed. An unreviewed source stays unverified and cannot be the supported answer. The model may propose a fact or phrase a sentence. It cannot set status, tenant, or current.

The scripted extractor, used when `OPENAI_API_KEY` is empty, reads lines like:

```text
entity=Project Atlas; type=Project; predicate=deploy_region; value=region-c; confidence=0.9
```

Policy ablation, retraction, a second policy version, `blocked`, and `failed` are not built. There is no public deployment. The recorded demo video is not in this repository. Record it from `docs/demo-script.md`.

## Tests

`make test` runs pytest against the Compose database. The suite covers health, the seeded timeline, idempotency, supersession, equal-trust conflict, unreviewed and missing sources, tenant denial, fake ingest, snapshots, replays, handoff conflict carry-forward, version conflicts, stale completion, edge ablation, the three-question baseline, a second FalkorDB connection, and a faked graph outage.
