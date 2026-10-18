# Faultline: git for agent memory

[![ci-deploy](https://github.com/maannaan/faultline/actions/workflows/deploy.yml/badge.svg)](https://github.com/maannaan/faultline/actions/workflows/deploy.yml)

**Live demo: https://faultline.mannnan.com** · Demo video: _link added after recording_ · [Graph Hacks](https://www.wemakedevs.org/hackathons/falkordb) **Track 02: Agent Memory and Coordination**

Developers have `git blame`, `git diff`, `git bisect` and CI tests for code. Faultline gives them the same for what their AI agents remember.

Every fact an agent learns is stored in FalkorDB as an assertion. Each assertion is linked to its source, the time it was observed, and the edges that later corrected or contradicted it. Nothing is overwritten. That makes changed answers debuggable:

| Verb | What it answers | Where |
| --- | --- | --- |
| `checkout` | What could the agent know at 15 Oct 12:00? | [Time Machine](https://faultline.mannnan.com/app/timeline): Evidence Graph with a time scrubber |
| `diff` | Same question, two snapshots. Which evidence changed, and which edge caused it? | [Replay Lab](https://faultline.mannnan.com/app/replay) |
| `blame` | Where did this answer come from? Claim → assertion → source → event → session → agent | [Blame](https://faultline.mannnan.com/app/blame) |
| `bisect` | Right yesterday, different today. Which recorded event flipped it? | [Bisect](https://faultline.mannnan.com/app/bisect) |
| `impact` | A fact was corrected. Which replays and handoffs relied on the old version? | [Impact](https://faultline.mannnan.com/app/impact) |
| `handoff` | Pass a task to another agent without dropping the open dispute | [Handoff](https://faultline.mannnan.com/app/handoff) |
| `test` | Memory regression tests in CI: at time X, question Y must answer Z | [Bench](https://faultline.mannnan.com/app/bench) + `memory-tests.yaml` |

The demo data is the synthetic **Project Atlas** rollout:
- A design note says the deploy region is `region-a`.
- A reviewed change record corrects it to `region-b`.
- Two equally trusted sources disagree on who is on call (Priya or Jordan).

Faultline answers `region-a` before the correction and `region-b` after it. It refuses to pick an on-call owner, and it carries that dispute into the next agent's handoff.

## Track 02 coverage

| Track focus | How Faultline does it |
| --- | --- |
| Episodic memory | `MemoryEvent` nodes in a `Session`, recorded by an `Agent`, each with `observed_at` |
| Semantic memory | `Assertion` nodes about an `Entity`, `SUPPORTED_BY` a `Source`. Corrections are `SUPERSEDES` edges and disagreements are `CONFLICTS_WITH` edges, never overwrites |
| Procedural memory | `memory-policy-v1`: deterministic rules decide current / superseded / disputed / unverified. Tasks carry acceptance criteria. The model can propose facts but cannot set status |
| Persistent history | Everything lives in FalkorDB with AOF persistence. Restart the graph and the timeline, snapshots and handoffs are still there. Old assertions are kept and marked superseded |
| Shared state and handoffs | `Task -HAS_HANDOFF-> Handoff -USED_SNAPSHOT-> Snapshot`. The server copies every disputed assertion onto the handoff (`INCLUDES_CONFLICT`), so a client cannot drop it. Stale snapshots block completion with `409 snapshot_stale` |
| Reads and writes under load | Every write is idempotent (`idempotency_key`), and task transitions use optimistic `expected_version` checks. Reads are bounded as-of queries. Limit: one API process; the version check and the write are separate queries (see Limits) |
| Separate memory per tenant | One FalkorDB graph per tenant (`tenant_tenant_synthetic`). The graph name comes from the bearer token, never from the request body. Cross-tenant reads return 404 without values |

## Architecture

```
Browser ── Next.js 15 (landing + /app) ──► /api/faultline proxy (holds the API key server-side)
                                              │
                                              ▼
                              FastAPI (memory writer, snapshots, replay,
                              bisect, impact, blame, handoffs, policy)
                                              │  Cypher, parameters only
                                              ▼
                              FalkorDB: one graph per tenant
```

- **Backend** (`apps/api`): FastAPI, Pydantic and the `falkordb` client. The policy is deterministic. The LLM adapter is optional: with an empty key, a scripted extractor and a deterministic answerer are used.
- **Frontend** (`apps/web`): Next.js 15, React 19, Tailwind 4, React Flow for the Evidence Graph, and Motion for animation.
- **Deploy**: one AWS EC2 host running `docker-compose.prod.yml` (FalkorDB, API, web and Caddy with automatic HTTPS). Only ports 80 and 443 are open.
- **CI/CD** (`.github/workflows/deploy.yml`): on every push to `main`, the pipeline runs these steps in order:
  1. ruff
  2. pytest against a real FalkorDB service container
  3. memory regression tests
  4. `tsc` and `next build`
  5. deploy: assumes an AWS role through **GitHub OIDC** and runs the deploy through **SSM Run Command**
  6. HTTPS smoke check of the landing page and graph readiness

  No secrets are stored in GitHub and there is no SSH.

## Graph model

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
- `(ReplayRun)-[:USED_SNAPSHOT]->(Snapshot)`, `(ReplayRun)-[:PRODUCED_ANSWER]->(AnswerClaim)`, `(AnswerClaim)-[:SUPPORTED_BY_ASSERTION]->(Assertion)`
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

## Cypher that does the work

All values are passed as parameters. The relationship lists use pattern comprehensions, so one assertion's edges are not mixed into another row.

**As-of retrieval** (`checkout`, `diff`, `bisect`, the Evidence Graph). The source edge is required:

```cypher
MATCH (a:Assertion)-[:ABOUT]->(e:Entity)
WHERE a.observed_at <= $as_of
MATCH (a)-[:SUPPORTED_BY]->(s:Source)
RETURN a.id, a.predicate, a.value, s.id, s.trust_tier,
       [(a)-[:SUPERSEDES]->(older) | older.id] AS supersedes_ids,
       [(newer)-[:SUPERSEDES]->(a) | newer.id] AS superseded_by_ids,
       [(a)-[:CONFLICTS_WITH]-(other) | other.id] AS conflict_ids
```

**Bisect** runs that query at each probe cutoff. It binary-searches the distinct `observed_at` values between the good and bad cutoffs, and stops at the first moment whose answer matches the bad one. Nothing is written. Like `git bisect`, it assumes a single flip in the range.

**Blame** follows one answer back to the agent:

```cypher
MATCH (r:ReplayRun {id: $id})-[:PRODUCED_ANSWER]->(c:AnswerClaim)
MATCH (r)-[:USED_SNAPSHOT]->(s:Snapshot)
OPTIONAL MATCH (c)-[:SUPPORTED_BY_ASSERTION]->(a:Assertion)
OPTIONAL MATCH (s)-[inc:INCLUDES_ASSERTION]->(a)
OPTIONAL MATCH (a)-[:SUPPORTED_BY]->(src:Source)
OPTIONAL MATCH (ev:MemoryEvent {id: a.origin_event_id})
OPTIONAL MATCH (se:Session)-[:CONTAINS_EVENT]->(ev)
OPTIONAL MATCH (ag:Agent)-[:RECORDED]->(ev)
RETURN c.value, a.id, inc.status_at_snapshot, src.id, src.trust_tier, ev.id, se.id, ag.id
```

**Impact** walks backwards from a corrected assertion. A dependent is outdated when the status it saw differs from the status now:

```cypher
MATCH (r:ReplayRun)-[:PRODUCED_ANSWER]->(c:AnswerClaim)
      -[:SUPPORTED_BY_ASSERTION]->(a:Assertion {id: $id})
MATCH (r)-[:USED_SNAPSHOT]->(s:Snapshot)-[inc:INCLUDES_ASSERTION]->(a)
RETURN r.id, c.value, inc.status_at_snapshot AS status_then, a.status AS status_now

MATCH (t:Task)-[:HAS_HANDOFF]->(h:Handoff)-[:USED_SNAPSHOT]->(s:Snapshot)
      -[inc:INCLUDES_ASSERTION]->(a:Assertion {id: $id})
RETURN h.id, t.objective, inc.status_at_snapshot,
       size([(h)-[:REFERENCES_MEMORY]->(a) | a]) AS direct_refs
```

**Ablation** deletes one relationship, asks the question again, then recreates it:

```cypher
MATCH (a:Assertion {id: $from_id})-[r:SUPPORTED_BY]->(b:Source {id: $to_id})
DELETE r
```

```cypher
MATCH (a:Assertion {id: $from_id}), (b:Assertion {id: $to_id})
MERGE (a)-[:SUPERSEDES]->(b)
```

The handoff context is the latest `(Task)-[:HAS_HANDOFF]->(Handoff)`, plus `(Handoff)-[:INCLUDES_CONFLICT]->(Assertion)` for every disputed member of the snapshot. The client cannot omit those conflict ids.

## API

All `/v1` routes need `Authorization: Bearer <key>`, and the key selects the tenant. Interactive docs are at `/docs` when the API runs locally.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/notes`, `/v1/events`, `/v1/sources`, `/v1/assertions` | Write path. The policy decides status |
| GET | `/v1/entities`, `/v1/timeline`, `/v1/assertions/{id}`, `/v1/assertions/{id}/evidence` | Read memory and provenance |
| GET | `/v1/graph?entity_id=&as_of=&time_mode=&exclude_source_ids=` | Evidence subgraph with status at a cutoff |
| POST/GET | `/v1/snapshots`, `/v1/snapshots/{id}` | Record an as-of snapshot |
| POST/GET | `/v1/replays`, `/v1/replays`, `/v1/replays/{id}/diff` | Replay a question, list replays, evidence diff |
| GET | `/v1/replays/{id}/blame` | Blame chain for each answer claim |
| POST | `/v1/bisect` | First recorded moment the answer took its later value |
| GET | `/v1/assertions/{id}/impact` | Snapshots, replays and handoffs that relied on it, and which are outdated |
| POST/GET | `/v1/tasks`, `/v1/tasks/{id}`, `.../handoff`, `.../accept`, `.../complete`, `.../revalidate` | Versioned coordination |
| GET | `/v1/benchmarks/memory-tests` | Run `memory-tests.yaml` against the tenant graph |
| POST | `/v1/benchmarks/ablation` | Delete and restore two edges, report the answers |

## Quick start (local)

Requirements: Docker, Python 3.12, [uv](https://docs.astral.sh/uv/), and Node.js 22.

```bash
cp .env.example .env
# Set FALKORDB_PASSWORD. Do not commit .env or an API key.
make up        # FalkorDB (and the API container)
make test      # 66 tests against the real graph
make seed      # load Project Atlas
make memtest   # memory regression tests
make bench     # baseline comparison -> docs/benchmark.json
make api       # API on 127.0.0.1:8000
make web       # web on 127.0.0.1:3010
```

- Landing: http://127.0.0.1:3010
- App: http://127.0.0.1:3010/app/timeline
- API docs: http://127.0.0.1:8000/docs
- FalkorDB Browser: http://127.0.0.1:3000

The graph port and the browser are bound to `127.0.0.1` only. FalkorDB is pinned to image digest `sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6`. Copy `apps/web/.env.example` to `apps/web/.env.local` if you start Next.js without `make`.

| Variable | Purpose |
| --- | --- |
| `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_PASSWORD` | Graph connection. `FALKORDB_USERNAME` and `FALKORDB_SSL=true` support a hosted FalkorDB such as FalkorDB Cloud |
| `AUTH_KEYS` | `key:tenant` pairs. Local keys: `dev-key:tenant-synthetic`, `other-key:tenant-other` |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | Optional live extraction and answer phrasing (any OpenAI-compatible endpoint, for example Groq `openai/gpt-oss-20b`). An empty key uses the scripted extractor and the deterministic answerer |
| `POLICY_VERSION` | `memory-policy-v1` |
| `SCHEMA_VERSION` | `1` |
| `MAX_NOTE_CHARS` | Reject longer notes and source text |
| `APP_ENV` | `reset`, `make bench` and the ablation endpoint run only when this is `development` |

The scripted extractor, used when `OPENAI_API_KEY` is empty, reads lines like:

```text
entity=Project Atlas; type=Project; predicate=deploy_region; value=region-c; confidence=0.9
```

To check persistence, run `make seed`, then `docker compose restart falkordb`, then `make api`. `region-b` is still current, `region-a` is still superseded, and both owners are still disputed.

### Production

`docker-compose.prod.yml` runs FalkorDB (the `local-graph` profile), the API, the standalone Next.js server and Caddy. `deploy/deploy.sh` creates the server `.env` with random secrets on first run, starts the stack, and seeds idempotently. The GitHub workflow uses three repository variables: the deploy role ARN, the instance id and the site host. It stores no secrets.

## Memory regression tests

`memory-tests.yaml` states what memory must answer:

```yaml
- name: late-oncall-stays-disputed
  predicate: oncall_owner
  as_of: "2026-10-16T13:00:00Z"
  expect: {status: disputed, value: null, cites: [assert-oncall-jordan, assert-oncall-priya]}
```

There are six cases: early region, late region, the disputed on-call pair, the `source-change-002` counterfactual, empty memory before the first note, and valid-time without intervals. They run in pytest, in a separate CI step that writes a table to the job summary, through `make memtest`, and live on the Bench page. A test edits one expectation to prove that a regression fails the suite.

## Benchmark

`make bench` scores three questions on the seeded graph and writes `docs/benchmark.json`. It uses the deterministic answerer and does not call an LLM.

The setup:
- The graph is seeded with 26 nodes, 49 edges and 4 assertions.
- Token counts are `len(prompt) / 4`, not a model tokenizer.
- The sample size is 3.

These scores show the mechanism, not a general advantage over other memory systems.

| Method | Correct | Evidence coverage | Stale answers | Conflicts surfaced |
| --- | --- | --- | --- | --- |
| No memory | 0/3 | 0 | 0 | 0 |
| Flat summary, latest line wins | 1/3 | 0 | 1 | 0 |
| Faultline | 3/3 | 1 | 0 | 1 |

The early region question is the stale one: the flat summary answers `region-b` before that correction was observed. Faultline answers `region-a` and cites `assert-region-a`. At the late cutoff, Faultline answers `region-b` and cites `assert-region-b`. On-call stays disputed with both owners cited, while the flat summary picks Jordan.

`POST /v1/benchmarks/ablation` runs two experiments on the late region question and restores both edges afterwards:
- **Delete `(assert-region-b)-[:SUPPORTED_BY]->(source-change-002)`:** the answer is no longer `region-b`.
- **Delete `(assert-region-b)-[:SUPERSEDES]->(assert-region-a)`:** both assertions stay `current`, and the claim is `insufficient` with no chosen value.

## Isolation and limits

Another tenant's read of a timeline, graph, snapshot, replay, blame, impact, task or ablation returns 404. The body does not include assertion values, owner names or the objective. If FalkorDB is stopped, the API returns `graph_unavailable` with HTTP 503 and does not invent an answer.

Policy rules:
- Only `deploy_region` and `oncall_owner` are accepted.
- A reviewed `correction_of` writes `SUPERSEDES`.
- Two reviewed sources with different values and no correction write `CONFLICTS_WITH`, and both stay disputed.
- An unreviewed source stays unverified and cannot be the supported answer.
- The model may propose a fact or phrase a sentence. It cannot set status, tenant, or current.

Handoff states:
- **Implemented:** `queued` to `handed_off`; `handed_off` to `claimed` (by the recipient only); and `claimed` to `completed` when the handoff is not stale.
- **Staleness:** `stale` is derived on read and on complete. It is true when `expires_at` has passed, or when a later `current` or `disputed` assertion on a referenced predicate was observed after the snapshot cutoff.

Known limits:
- Task version checks and the following write are separate queries in one API process, so this is not a distributed transaction.
- Policy ablation, retraction, a second policy version, and the `blocked` and `failed` handoff states are not built.
- Bisect assumes a single flip in its range.

The live demo runs with `APP_ENV=development` so the ablation button works. That button deletes and restores two edges in the synthetic graph. Reset is not exposed over HTTP.

## Tests

`make test` runs 66 pytest cases against FalkorDB. They cover:
- health, the seeded timeline and idempotency
- supersession, equal-trust conflict, and unreviewed or missing sources
- tenant denial and fake ingest
- snapshots, replays and the Evidence Graph view
- bisect, impact, blame and the memory YAML suite
- handoff conflict carry-forward, version conflicts and stale completion
- edge ablation and the three-question baseline
- a second FalkorDB connection and a faked graph outage

## AI assistance

An AI coding assistant (Claude Code) wrote most of the code, the deploy pipeline and this README under the author's direction. The author owns the architecture, the memory policy, the scope decisions and the verification. Every claim above is backed by a test, the live demo, or a stated limit.
