"use client";

import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { EvidenceGraph } from "@/components/evidence-graph";
import {
  EmptyState,
  ErrorBanner,
  KeyValue,
  PageHeader,
  Panel,
  StatusPill,
  formatTime,
  localInputValue,
} from "@/components/ui";
import type { Entity, NoteResult, SnapshotResult, Timeline, TimelineItem } from "@/lib/types";

type Props = {
  entities: Entity[];
  timeline: Timeline | null;
  selectedEntity: string;
  apiError: string | null;
};

export function TimelineBoard({ entities, timeline, selectedEntity, apiError }: Props) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(timeline?.items[0]?.assertion_id ?? null);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotResult | null>(null);
  const [cutoffError, setCutoffError] = useState<string | null>(null);
  const [cutoffPending, setCutoffPending] = useState(false);
  const [graphKey, setGraphKey] = useState(0);

  const selected = useMemo(
    () => timeline?.items.find((item) => item.assertion_id === selectedId) ?? null,
    [timeline, selectedId],
  );

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const observedLocal = String(data.get("observed_at") || "");
    const observedAt = observedLocal ? new Date(observedLocal).toISOString() : new Date().toISOString();
    setPending(true);
    setFormError(null);
    setNotice(null);
    try {
      const response = await fetch("/api/faultline/v1/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: String(data.get("text") || ""),
          trust_tier: String(data.get("trust_tier") || "reviewed"),
          observed_at: observedAt,
          session_id: "session-system",
          agent_id: "agent-system",
        }),
      });
      const body = (await response.json()) as NoteResult & {
        error?: { message?: string };
      };
      if (!response.ok) {
        setFormError(body.error?.message || "The note could not be recorded.");
        return;
      }
      const count = body.assertions?.length ?? 0;
      const failed = body.extraction_status === "failed";
      setNotice(
        failed
          ? `Source ${body.source_id} was kept. Extraction did not produce assertions.`
          : `Recorded ${body.source_id} with ${count} assertion${count === 1 ? "" : "s"}.`,
      );
      form.reset();
      setGraphKey((key) => key + 1);
      router.refresh();
    } catch {
      setFormError("The Faultline API is not reachable.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="faultline checkout"
        title="Memory Time Machine"
        description={
          <>
            Scrub through what the agent could know. Every node is a FalkorDB record; status at each cutoff is recomputed
            from the edges visible at that moment, never rewritten in place.
          </>
        }
        actions={entities.length > 0 ? <EntityPicker entities={entities} selectedEntity={selectedEntity} /> : null}
      />

      {apiError ? (
        <ErrorBanner>
          {apiError} No timeline is shown rather than a guessed one.
        </ErrorBanner>
      ) : null}
      {!apiError && entities.length === 0 ? (
        <EmptyState>
          No entities yet. Record a note below or run <span className="mono text-ink">make seed</span> to load Project Atlas.
        </EmptyState>
      ) : null}

      {selectedEntity && !apiError ? (
        <EvidenceGraph key={`${selectedEntity}-${graphKey}`} entityId={selectedEntity} highlightIds={selectedId ? [selectedId] : []} />
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <div className="min-w-0 space-y-6">
          {timeline ? (
            <Panel title="Assertions" aside={<span className="mono">{timeline.policy_version}</span>} className="overflow-hidden">
              {timeline.items.length === 0 ? (
                <p className="text-sm text-muted">This entity has no assertions.</p>
              ) : (
                <ul className="-mx-4 -my-4 divide-y divide-line sm:-mx-5 sm:-my-5">
                  {timeline.items.map((item, index) => (
                    <motion.li
                      key={item.assertion_id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.04 }}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedId(item.assertion_id)}
                        className={`grid w-full gap-2 px-4 py-3.5 text-left transition sm:grid-cols-[150px_1fr_auto] sm:px-5 ${
                          selectedId === item.assertion_id ? "bg-fault/[0.06]" : "hover:bg-white/[0.02]"
                        }`}
                      >
                        <span className="mono text-xs text-dim">{formatTime(item.observed_at)}</span>
                        <span className="min-w-0">
                          <span className="mono text-[11px] text-dim">{item.predicate}</span>
                          <span
                            className={`mt-0.5 block font-medium ${item.status === "superseded" ? "text-muted line-through decoration-white/25" : ""}`}
                          >
                            {item.value}
                          </span>
                          <span className="mono mt-0.5 block truncate text-[11px] text-dim">{item.source_id}</span>
                        </span>
                        <span className="flex flex-wrap items-start gap-1.5 sm:flex-col sm:items-end">
                          <StatusPill status={item.status} prefix="now" />
                          <CutoffPill item={item} snapshot={snapshot} />
                        </span>
                      </button>
                    </motion.li>
                  ))}
                </ul>
              )}
            </Panel>
          ) : null}
          {selected ? <Inspector item={selected} entityId={timeline?.entity_id ?? selectedEntity} /> : null}
        </div>

        <div className="space-y-6">
          <CutoffForm
            entityId={selectedEntity}
            pending={cutoffPending}
            onResult={setSnapshot}
            onError={setCutoffError}
            onPending={setCutoffPending}
            error={cutoffError}
            snapshot={snapshot}
          />
          <Panel title="Ingest a note">
            <form onSubmit={onSubmit} className="space-y-3">
              <div>
                <label className="label" htmlFor="note-text">
                  Note
                </label>
                <textarea
                  id="note-text"
                  name="text"
                  required
                  rows={4}
                  placeholder="entity=Project Atlas; type=Project; predicate=deploy_region; value=region-c; confidence=0.9"
                  className="field mono !text-xs leading-5"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label" htmlFor="trust-tier">
                    Trust
                  </label>
                  <select id="trust-tier" name="trust_tier" className="field" defaultValue="reviewed">
                    <option value="reviewed">reviewed</option>
                    <option value="unreviewed">unreviewed</option>
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="observed-at">
                    Observed at
                  </label>
                  <input
                    id="observed-at"
                    name="observed_at"
                    type="datetime-local"
                    required
                    defaultValue={localInputValue(new Date())}
                    className="field !px-2 !text-xs"
                  />
                </div>
              </div>
              <button type="submit" disabled={pending} className="btn btn-primary w-full">
                {pending ? "Recording…" : "Record note"}
              </button>
              {notice ? <p className="text-xs leading-5 text-ok">{notice}</p> : null}
              {formError ? <p className="text-xs leading-5 text-disputed">{formError}</p> : null}
              <p className="text-[11px] leading-4 text-dim">
                The model may propose a fact. Only the deterministic policy sets current, superseded or disputed.
              </p>
            </form>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function EntityPicker({ entities, selectedEntity }: { entities: Entity[]; selectedEntity: string }) {
  return (
    <div className="flex items-center gap-2">
      <label className="label !mt-0" htmlFor="entity">
        Entity
      </label>
      <select
        id="entity"
        name="entity"
        defaultValue={selectedEntity}
        className="field !mt-0 !w-auto"
        onChange={(event) => {
          window.location.href = `/app/timeline?entity=${encodeURIComponent(event.target.value)}`;
        }}
      >
        {entities.map((entity) => (
          <option key={entity.entity_id} value={entity.entity_id}>
            {entity.canonical_name}
          </option>
        ))}
      </select>
    </div>
  );
}

function Inspector({ item, entityId }: { item: TimelineItem; entityId: string }) {
  return (
    <Panel title="Evidence" aside={<StatusPill status={item.status} prefix="now" />}>
      <p className="mb-4 text-sm leading-6 text-muted">{item.resolution_reason}</p>
      <KeyValue
        rows={[
          ["Assertion", item.assertion_id],
          ["Source", item.source_id ?? "—"],
          ["Event", item.event_id ?? "—"],
          ["Entity", entityId],
          ["Valid from", item.valid_from ?? "unknown"],
          ["Valid to", item.valid_to ?? "unknown"],
          ["Supersedes", item.supersedes_ids.join(", ") || "—"],
          ["Conflicts", item.conflicts_with_ids.join(", ") || "—"],
        ]}
      />
    </Panel>
  );
}

function CutoffForm({
  entityId,
  pending,
  onResult,
  onError,
  onPending,
  error,
  snapshot,
}: {
  entityId: string;
  pending: boolean;
  onResult: (snapshot: SnapshotResult) => void;
  onError: (message: string | null) => void;
  onPending: (pending: boolean) => void;
  error: string | null;
  snapshot: SnapshotResult | null;
}) {
  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const observedLocal = String(data.get("as_of") || "");
    const asOf = new Date(observedLocal).toISOString();
    const timeMode = String(data.get("time_mode") || "known");
    onPending(true);
    onError(null);
    try {
      const response = await fetch("/api/faultline/v1/snapshots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          as_of_time: asOf,
          time_mode: timeMode,
          entity_ids: [entityId],
          idempotency_key: `ui-snap:${entityId}:${timeMode}:${asOf}`,
        }),
      });
      const body = (await response.json()) as SnapshotResult & { error?: { message?: string } };
      if (!response.ok) {
        onError(body.error?.message || "The cutoff could not be loaded.");
        return;
      }
      onResult(body);
    } catch {
      onError("The Faultline API is not reachable.");
    } finally {
      onPending(false);
    }
  }

  return (
    <Panel title="Record a snapshot" aside={snapshot ? <span className="mono">{snapshot.snapshot_id.slice(0, 14)}…</span> : null}>
      <form onSubmit={onSubmit} className="space-y-3">
        <div className="grid grid-cols-[1fr_auto] gap-3">
          <div>
            <label className="label" htmlFor="as-of">
              Cutoff
            </label>
            <input
              id="as-of"
              name="as_of"
              type="datetime-local"
              required
              defaultValue={localInputValue(new Date("2026-10-15T12:00:00Z"))}
              className="field !px-2 !text-xs"
            />
          </div>
          <div>
            <label className="label" htmlFor="time-mode">
              Mode
            </label>
            <select id="time-mode" name="time_mode" defaultValue="known" className="field">
              <option value="known">known</option>
              <option value="valid">valid</option>
            </select>
          </div>
        </div>
        <button type="submit" disabled={pending || !entityId} className="btn btn-ghost w-full">
          {pending ? "Writing snapshot…" : "Show cutoff beside each assertion"}
        </button>
        {error ? <p className="text-xs leading-5 text-disputed">{error}</p> : null}
        <p className="text-[11px] leading-4 text-dim">
          <span className="mono text-muted">known</span> uses observed time. <span className="mono text-muted">valid</span> also needs a
          supplied validity interval and never invents one.
        </p>
      </form>
    </Panel>
  );
}

function CutoffPill({ item, snapshot }: { item: TimelineItem; snapshot: SnapshotResult | null }) {
  if (!snapshot) {
    return null;
  }
  const included = snapshot.included.find((row) => row.assertion_id === item.assertion_id);
  if (included) {
    return <StatusPill status={included.status} prefix="cutoff" />;
  }
  if (snapshot.validity_unknown_ids.includes(item.assertion_id)) {
    return <span className="pill pill-unverified">interval not supplied</span>;
  }
  return <span className="pill pill-neutral">not yet known</span>;
}
