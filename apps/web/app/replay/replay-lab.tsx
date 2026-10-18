"use client";

import { useState } from "react";
import type { Entity, ReplayDiff, ReplayResult, SnapshotResult } from "@/lib/types";

type Props = {
  entities: Entity[];
  apiError: string | null;
};

const EARLY = "2026-10-15T12:00:00Z";
const LATE = "2026-10-16T13:00:00Z";

export function ReplayLab({ entities, apiError }: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [baseline, setBaseline] = useState<ReplayResult | null>(null);
  const [candidate, setCandidate] = useState<ReplayResult | null>(null);
  const [diff, setDiff] = useState<ReplayDiff | null>(null);

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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The replay could not be run.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 lg:grid-cols-[320px_1fr] lg:px-6">
      <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-[var(--line)] bg-[var(--card)] p-4">
        <header>
          <p className="mono text-xs tracking-[0.16em] text-[var(--fault)]">REPLAY LAB</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Same question, two cutoffs</h1>
        </header>
        {apiError ? <p className="text-sm text-[var(--fault)]">{apiError}</p> : null}
        <label className="block text-xs text-[var(--muted)]" htmlFor="entity">
          Entity
        </label>
        <select
          id="entity"
          name="entity_id"
          className="w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
          defaultValue={entities[0]?.entity_id ?? ""}
        >
          {entities.map((entity) => (
            <option key={entity.entity_id} value={entity.entity_id}>
              {entity.canonical_name}
            </option>
          ))}
        </select>
        <label className="block text-xs text-[var(--muted)]" htmlFor="question">
          Question
        </label>
        <textarea
          id="question"
          name="question"
          required
          rows={3}
          defaultValue="Which deployment region should the rollout use?"
          className="w-full rounded-lg border border-[var(--line)] bg-white p-2 text-sm"
        />
        <label className="block text-xs text-[var(--muted)]" htmlFor="predicate">
          Predicate
        </label>
        <select
          id="predicate"
          name="predicate"
          defaultValue="deploy_region"
          className="w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
        >
          <option value="deploy_region">deploy_region</option>
          <option value="oncall_owner">oncall_owner</option>
        </select>
        <TimeField id="baseline-at" name="baseline_at" label="Baseline cutoff" iso={EARLY} />
        <TimeField id="candidate-at" name="candidate_at" label="Candidate cutoff" iso={LATE} />
        <label className="flex items-start gap-2 text-sm" htmlFor="exclude-change">
          <input id="exclude-change" name="exclude_change" type="checkbox" className="mt-1" />
          Exclude source-change-002 from the candidate snapshot
        </label>
        <button
          type="submit"
          disabled={pending || Boolean(apiError) || entities.length === 0}
          className="w-full rounded-lg bg-[var(--ink)] px-3 py-2 text-sm font-medium text-[var(--paper)] disabled:opacity-60"
        >
          {pending ? "Replaying…" : "Run replay"}
        </button>
        {error ? <p className="text-xs leading-5 text-[var(--fault)]">{error}</p> : null}
      </form>
      <section className="space-y-4">
        {entities.length === 0 && !apiError ? (
          <p className="rounded-xl border border-dashed border-[var(--line)] bg-[var(--card)] p-6 text-sm text-[var(--muted)]">
            No entities yet. Run <span className="mono">make seed</span> before a replay.
          </p>
        ) : null}
        <div className="grid gap-4 md:grid-cols-2">
          <ClaimCard title="Baseline" replay={baseline} />
          <ClaimCard title="Candidate" replay={candidate} />
        </div>
        {diff ? <DiffCard diff={diff} /> : null}
      </section>
    </div>
  );
}

function TimeField({ id, name, label, iso }: { id: string; name: string; label: string; iso: string }) {
  return (
    <div>
      <label className="block text-xs text-[var(--muted)]" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        name={name}
        type="datetime-local"
        required
        defaultValue={localInputValue(new Date(iso))}
        className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
      />
    </div>
  );
}

function ClaimCard({ title, replay }: { title: string; replay: ReplayResult | null }) {
  const claim = replay?.claims[0];
  return (
    <div className="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4">
      <h2 className="text-sm font-semibold">{title}</h2>
      {!claim ? <p className="mt-2 text-sm text-[var(--muted)]">No replay yet.</p> : null}
      {claim ? (
        <div className="mt-3 space-y-2 text-sm">
          <p className={`inline-block rounded-full px-2 py-1 text-xs font-medium status-${claim.status === "supported" ? "current" : claim.status === "disputed" ? "disputed" : "unverified"}`}>
            {claim.status === "disputed" ? "abstained" : claim.status}
          </p>
          <p className="font-medium">{claim.value ?? "No value chosen."}</p>
          <p className="text-[var(--muted)]">{claim.wording}</p>
          <p className="mono text-xs break-all">{claim.evidence_ids.join(", ") || "no evidence"}</p>
        </div>
      ) : null}
    </div>
  );
}

function DiffCard({ diff }: { diff: ReplayDiff }) {
  return (
    <div className="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4">
      <h2 className="text-sm font-semibold">Evidence diff</h2>
      <p className="mono mt-1 text-xs text-[var(--muted)]">{diff.answer_change}</p>
      <p className="mt-3 text-sm leading-6">{diff.explanation}</p>
      <dl className="mt-3 grid gap-2 text-sm">
        <DiffRow label="Added" value={diff.added.join(", ")} />
        <DiffRow label="Removed" value={diff.removed.join(", ")} />
        <DiffRow label="Unchanged" value={diff.unchanged.join(", ")} />
        <DiffRow
          label="Status changed"
          value={diff.status_changed
            .map((item) => `${item.assertion_id} ${item.from_status} → ${item.to_status}`)
            .join("; ")}
        />
        <DiffRow label="Sources added" value={diff.added_source_ids.join(", ")} />
      </dl>
    </div>
  );
}

function DiffRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[130px_1fr] gap-2">
      <dt className="text-[var(--muted)]">{label}</dt>
      <dd className="mono break-all">{value || "—"}</dd>
    </div>
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

function localInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
