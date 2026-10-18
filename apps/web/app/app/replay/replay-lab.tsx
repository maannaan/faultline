"use client";

import { ArrowRight, Minus, Plus } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { EvidenceGraph } from "@/components/evidence-graph";
import { EmptyState, ErrorBanner, PageHeader, Panel, StatusPill, formatTime, localInputValue } from "@/components/ui";
import type { Entity, ReplayDiff, ReplayResult, SnapshotResult } from "@/lib/types";

type Props = {
  entities: Entity[];
  apiError: string | null;
};

const EARLY = "2026-10-15T12:00:00Z";
const LATE = "2026-10-16T13:00:00Z";

type RunInfo = { entityId: string; candidateAt: string; baselineAt: string; exclude: boolean };

export function ReplayLab({ entities, apiError }: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [baseline, setBaseline] = useState<ReplayResult | null>(null);
  const [candidate, setCandidate] = useState<ReplayResult | null>(null);
  const [diff, setDiff] = useState<ReplayDiff | null>(null);
  const [run, setRun] = useState<RunInfo | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const entityId = String(data.get("entity_id") || "");
    const predicate = String(data.get("predicate") || "deploy_region");
    const question = String(data.get("question") || "");
    const baselineAt = new Date(String(data.get("baseline_at") || "")).toISOString();
    const candidateAt = new Date(String(data.get("candidate_at") || "")).toISOString();
    const exclude = data.get("exclude_change") === "on";
    setPending(true);
    setError(null);
    try {
      const baselineSnapshot = await createSnapshot(entityId, baselineAt, false);
      const candidateSnapshot = await createSnapshot(entityId, candidateAt, exclude);
      const baselineReplay = await createReplay(question, predicate, baselineSnapshot.snapshot_id);
      const candidateReplay = await createReplay(question, predicate, candidateSnapshot.snapshot_id);
      const compared = await fetchDiff(candidateReplay.replay_id, baselineReplay.replay_id);
      setBaseline(baselineReplay);
      setCandidate(candidateReplay);
      setDiff(compared);
      setRun({ entityId, candidateAt, baselineAt, exclude });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The replay could not be run.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="faultline diff"
        title="Replay Lab"
        description="Ask the same question against two memory snapshots. The evidence diff is computed from graph ids, not from answer wording."
      />
      {apiError ? <ErrorBanner>{apiError}</ErrorBanner> : null}
      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <Panel title="Replay setup">
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="label" htmlFor="entity">
                Entity
              </label>
              <select id="entity" name="entity_id" className="field" defaultValue={entities[0]?.entity_id ?? ""}>
                {entities.map((entity) => (
                  <option key={entity.entity_id} value={entity.entity_id}>
                    {entity.canonical_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="question">
                Question
              </label>
              <textarea
                id="question"
                name="question"
                required
                rows={2}
                defaultValue="Which deployment region should the rollout use?"
                className="field"
              />
            </div>
            <div>
              <label className="label" htmlFor="predicate">
                Predicate
              </label>
              <select id="predicate" name="predicate" defaultValue="deploy_region" className="field mono">
                <option value="deploy_region">deploy_region</option>
                <option value="oncall_owner">oncall_owner</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <TimeField id="baseline-at" name="baseline_at" label="Baseline" iso={EARLY} />
              <TimeField id="candidate-at" name="candidate_at" label="Candidate" iso={LATE} />
            </div>
            <label
              className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-line bg-black/30 p-3 text-sm"
              htmlFor="exclude-change"
            >
              <input id="exclude-change" name="exclude_change" type="checkbox" className="mt-0.5 accent-[#f59e0b]" />
              <span>
                <span className="text-ink">Counterfactual</span>
                <span className="mt-0.5 block text-xs leading-5 text-muted">
                  Exclude <span className="mono">source-change-002</span> from the candidate snapshot. A filter, not a delete.
                </span>
              </span>
            </label>
            <button
              type="submit"
              disabled={pending || Boolean(apiError) || entities.length === 0}
              className="btn btn-primary w-full"
            >
              {pending ? "Replaying…" : "Run replay"} <ArrowRight className="size-4" />
            </button>
            {error ? <p className="text-xs leading-5 text-disputed">{error}</p> : null}
          </form>
        </Panel>
        <section className="min-w-0 space-y-6">
          {entities.length === 0 && !apiError ? (
            <EmptyState>
              No entities yet. Run <span className="mono text-ink">make seed</span> before a replay.
            </EmptyState>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2">
            <ClaimCard title="Baseline" at={run?.baselineAt} replay={baseline} />
            <ClaimCard title="Candidate" at={run?.candidateAt} replay={candidate} accent />
          </div>
          <AnimatePresence>{diff ? <DiffCard key={diff.candidate_replay_id} diff={diff} /> : null}</AnimatePresence>
          {run ? (
            <EvidenceGraph
              key={`${run.candidateAt}-${run.exclude}`}
              entityId={run.entityId}
              mode="fixed"
              asOf={run.candidateAt}
              excludeSourceIds={run.exclude ? ["source-change-002"] : []}
              highlightIds={candidate?.claims[0]?.evidence_ids ?? []}
              title="Candidate snapshot graph"
              height={440}
            />
          ) : null}
        </section>
      </div>
    </div>
  );
}

function TimeField({ id, name, label, iso }: { id: string; name: string; label: string; iso: string }) {
  return (
    <div>
      <label className="label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        name={name}
        type="datetime-local"
        required
        defaultValue={localInputValue(new Date(iso))}
        className="field !px-2 !text-xs"
      />
    </div>
  );
}

function ClaimCard({
  title,
  at,
  replay,
  accent = false,
}: {
  title: string;
  at?: string;
  replay: ReplayResult | null;
  accent?: boolean;
}) {
  const claim = replay?.claims[0];
  return (
    <div className={`panel panel-pad ${accent && claim ? "border-fault/30" : ""}`}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">{title}</h2>
        <span className="mono text-[11px] text-dim">{at ? formatTime(at) : "—"}</span>
      </div>
      {!claim ? <p className="mt-3 text-sm text-dim">No replay yet.</p> : null}
      <AnimatePresence mode="wait">
        {claim ? (
          <motion.div
            key={replay?.replay_id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-3 space-y-2.5"
          >
            <StatusPill status={claim.status === "disputed" ? "disputed" : claim.status} />
            <p className="text-2xl font-semibold tracking-tight">{claim.value ?? <span className="text-muted">No value chosen</span>}</p>
            <p className="text-sm leading-6 text-muted">{claim.wording}</p>
            <div className="flex flex-wrap gap-1.5">
              {claim.evidence_ids.length ? (
                claim.evidence_ids.map((id) => (
                  <span key={id} className="pill pill-neutral mono">
                    {id}
                  </span>
                ))
              ) : (
                <span className="pill pill-neutral">no evidence</span>
              )}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function DiffCard({ diff }: { diff: ReplayDiff }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="panel overflow-hidden"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3 sm:px-5">
        <h2 className="text-sm font-medium">Evidence diff</h2>
        <span className="mono text-[11px] text-fault">{diff.answer_change}</span>
      </div>
      <div className="panel-pad space-y-4">
        <p className="text-sm leading-6 text-ink">{diff.explanation}</p>
        <div className="mono space-y-1 rounded-lg border border-line bg-black/40 p-3 text-[12px] leading-6">
          {diff.added.map((id) => (
            <motion.p key={`a-${id}`} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-2 text-ok">
              <Plus className="size-3" /> {id}
            </motion.p>
          ))}
          {diff.removed.map((id) => (
            <motion.p key={`r-${id}`} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-2 text-disputed">
              <Minus className="size-3" /> {id}
            </motion.p>
          ))}
          {diff.status_changed.map((item) => (
            <p key={`s-${item.assertion_id}`} className="text-fault">
              ~ {item.assertion_id} {item.from_status} → {item.to_status}
            </p>
          ))}
          {diff.unchanged.map((id) => (
            <p key={`u-${id}`} className="text-dim">
              &nbsp;&nbsp;{id}
            </p>
          ))}
          {!diff.added.length && !diff.removed.length && !diff.status_changed.length && !diff.unchanged.length ? (
            <p className="text-dim">No evidence on either side.</p>
          ) : null}
        </div>
        {diff.added_source_ids.length || diff.removed_source_ids.length ? (
          <p className="text-xs text-muted">
            Sources added: <span className="mono text-ink">{diff.added_source_ids.join(", ") || "—"}</span> · removed:{" "}
            <span className="mono text-ink">{diff.removed_source_ids.join(", ") || "—"}</span>
          </p>
        ) : null}
      </div>
    </motion.div>
  );
}

async function createSnapshot(entityId: string, asOf: string, excludeChange: boolean): Promise<SnapshotResult> {
  const exclude = excludeChange ? ["source-change-002"] : [];
  const response = await fetch("/api/faultline/v1/snapshots", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      as_of_time: asOf,
      time_mode: "known",
      entity_ids: [entityId],
      exclude_source_ids: exclude,
      idempotency_key: `ui-replay-snap:${entityId}:${asOf}:${exclude.join(",")}`,
    }),
  });
  return readJson<SnapshotResult>(response);
}

async function createReplay(question: string, predicate: string, snapshotId: string): Promise<ReplayResult> {
  const response = await fetch("/api/faultline/v1/replays", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      predicate,
      snapshot_id: snapshotId,
      idempotency_key: `ui-replay:${snapshotId}:${predicate}:${question}`,
    }),
  });
  return readJson<ReplayResult>(response);
}

async function fetchDiff(candidateId: string, baselineId: string): Promise<ReplayDiff> {
  const response = await fetch(
    `/api/faultline/v1/replays/${encodeURIComponent(candidateId)}/diff?baseline_replay_id=${encodeURIComponent(baselineId)}`,
  );
  return readJson<ReplayDiff>(response);
}

async function readJson<T>(response: Response): Promise<T> {
  const body = (await response.json()) as T & { error?: { message?: string } };
  if (!response.ok) {
    throw new Error(body.error?.message || "The Faultline API is not reachable.");
  }
  return body;
}
