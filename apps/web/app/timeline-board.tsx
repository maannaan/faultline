"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
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
      router.refresh();
    } catch {
      setFormError("The Faultline API is not reachable.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 lg:grid-cols-[280px_1fr] lg:px-6">
      <aside className="space-y-4">
        <header>
          <p className="mono text-xs tracking-[0.16em] text-[var(--fault)]">TRACK 02</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Faultline</h1>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Source-backed memory. Status on this screen is the state now. Cutoff status is computed beside it.
          </p>
        </header>
        <EntityPicker entities={entities} selectedEntity={selectedEntity} />
        <CutoffForm
          entityId={selectedEntity}
          pending={cutoffPending}
          onResult={setSnapshot}
          onError={setCutoffError}
          onPending={setCutoffPending}
        />
        {cutoffError ? <p className="text-xs leading-5 text-[var(--fault)]">{cutoffError}</p> : null}
        <form onSubmit={onSubmit} className="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4">
          <h2 className="text-sm font-semibold">Ingest a note</h2>
          <label className="mt-3 block text-xs text-[var(--muted)]" htmlFor="note-text">
            Note
          </label>
          <textarea
            id="note-text"
            name="text"
            required
            rows={5}
            placeholder="entity=Project Atlas; type=Project; predicate=deploy_region; value=region-c; confidence=0.9"
            className="mono mt-1 w-full rounded-lg border border-[var(--line)] bg-white p-2 text-xs leading-5"
          />
          <label className="mt-3 block text-xs text-[var(--muted)]" htmlFor="trust-tier">
            Trust
          </label>
          <select
            id="trust-tier"
            name="trust_tier"
            className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
            defaultValue="reviewed"
          >
            <option value="reviewed">reviewed</option>
            <option value="unreviewed">unreviewed</option>
          </select>
          <label className="mt-3 block text-xs text-[var(--muted)]" htmlFor="observed-at">
            Observed at
          </label>
          <input
            id="observed-at"
            name="observed_at"
            type="datetime-local"
            required
            defaultValue={localInputValue(new Date())}
            className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={pending}
            className="mt-4 w-full rounded-lg bg-[var(--ink)] px-3 py-2 text-sm font-medium text-[var(--paper)] disabled:opacity-60"
          >
            {pending ? "Recording…" : "Record note"}
          </button>
          {notice ? <p className="mt-3 text-xs leading-5 text-[var(--current)]">{notice}</p> : null}
          {formError ? <p className="mt-3 text-xs leading-5 text-[var(--fault)]">{formError}</p> : null}
        </form>
      </aside>
      <section className="min-w-0">
        {apiError ? (
          <div className="rounded-xl border border-[var(--fault)] bg-[#fff4ef] p-4 text-sm">
            <p className="font-semibold">API down</p>
            <p className="mt-1 text-[var(--muted)]">{apiError} Start it with <span className="mono">make api</span>.</p>
          </div>
        ) : null}
        {!apiError && entities.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--line)] bg-[var(--card)] p-6 text-sm text-[var(--muted)]">
            No entities yet. Record a note or run <span className="mono">make seed</span> to load Project Atlas.
          </div>
        ) : null}
        {timeline ? (
          <div className="overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--card)]">
            <div className="flex items-baseline justify-between border-b border-[var(--line)] px-4 py-3">
              <h2 className="text-sm font-semibold">Timeline</h2>
              <p className="mono text-xs text-[var(--muted)]">{timeline.policy_version}</p>
            </div>
            {timeline.items.length === 0 ? (
              <p className="px-4 py-6 text-sm text-[var(--muted)]">This entity has no assertions.</p>
            ) : (
              <ul>
                {timeline.items.map((item) => (
                  <li key={item.assertion_id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(item.assertion_id)}
                      className={`grid w-full gap-2 border-b border-[var(--line)] px-4 py-3 text-left last:border-b-0 md:grid-cols-[170px_1fr_auto] ${
                        selectedId === item.assertion_id ? "bg-[#fff7f2]" : "bg-transparent"
                      }`}
                    >
                      <span className="mono text-xs text-[var(--muted)]">{item.observed_at}</span>
                      <span>
                        <span className="mono text-xs text-[var(--muted)]">{item.predicate}</span>
                        <span className="mt-1 block font-medium">{item.value}</span>
                        <span className="mono mt-1 block text-xs text-[var(--muted)]">{item.source_id}</span>
                      </span>
                      <span className="flex flex-col items-start gap-1">
                        <span className={`h-fit rounded-full px-2 py-1 text-xs font-medium status-${item.status}`}>
                          now {item.status}
                        </span>
                        <CutoffPill item={item} snapshot={snapshot} />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
        {selected ? <Inspector item={selected} entityId={timeline?.entity_id ?? selectedEntity} /> : null}
      </section>
    </div>
  );
}

function EntityPicker({ entities, selectedEntity }: { entities: Entity[]; selectedEntity: string }) {
  if (entities.length === 0) {
    return null;
  }
  return (
    <form className="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4" action="/" method="get">
      <label className="text-xs text-[var(--muted)]" htmlFor="entity">
        Entity
      </label>
      <select
        id="entity"
        name="entity"
        defaultValue={selectedEntity}
        className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
        onChange={(event) => {
          window.location.href = `/?entity=${encodeURIComponent(event.target.value)}`;
        }}
      >
        {entities.map((entity) => (
          <option key={entity.entity_id} value={entity.entity_id}>
            {entity.canonical_name}
          </option>
        ))}
      </select>
    </form>
  );
}

function Inspector({ item, entityId }: { item: TimelineItem; entityId: string }) {
  const rows = [
    ["Assertion", item.assertion_id],
    ["Source", item.source_id ?? "—"],
    ["Event", item.event_id ?? "—"],
    ["Entity", entityId],
    ["Valid from", item.valid_from ?? "unknown"],
    ["Valid to", item.valid_to ?? "unknown"],
    ["Supersedes", item.supersedes_ids.join(", ") || "—"],
    ["Conflicts", item.conflicts_with_ids.join(", ") || "—"],
  ];
  return (
    <div className="mt-4 rounded-xl border border-[var(--line)] bg-[var(--card)] p-4">
      <h2 className="text-sm font-semibold">Evidence</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">{item.resolution_reason}</p>
      <dl className="mt-3 grid gap-2">
        {rows.map(([label, value]) => (
          <div key={label} className="grid grid-cols-[110px_1fr] gap-2 text-sm">
            <dt className="text-[var(--muted)]">{label}</dt>
            <dd className="mono break-all">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function CutoffForm({
  entityId,
  pending,
  onResult,
  onError,
  onPending,
}: {
  entityId: string;
  pending: boolean;
  onResult: (snapshot: SnapshotResult) => void;
  onError: (message: string | null) => void;
  onPending: (pending: boolean) => void;
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
    <form onSubmit={onSubmit} className="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4">
      <h2 className="text-sm font-semibold">As of</h2>
      <label className="mt-3 block text-xs text-[var(--muted)]" htmlFor="as-of">
        Cutoff
      </label>
      <input
        id="as-of"
        name="as_of"
        type="datetime-local"
        required
        defaultValue={localInputValue(new Date("2026-10-15T12:00:00Z"))}
        className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
      />
      <label className="mt-3 block text-xs text-[var(--muted)]" htmlFor="time-mode">
        Time mode
      </label>
      <select
        id="time-mode"
        name="time_mode"
        defaultValue="known"
        className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
      >
        <option value="known">known</option>
        <option value="valid">valid</option>
      </select>
      <button
        type="submit"
        disabled={pending || !entityId}
        className="mt-4 w-full rounded-lg bg-[var(--ink)] px-3 py-2 text-sm font-medium text-[var(--paper)] disabled:opacity-60"
      >
        {pending ? "Loading cutoff…" : "Show cutoff"}
      </button>
    </form>
  );
}

function CutoffPill({ item, snapshot }: { item: TimelineItem; snapshot: SnapshotResult | null }) {
  if (!snapshot) {
    return null;
  }
  const included = snapshot.included.find((row) => row.assertion_id === item.assertion_id);
  if (included) {
    return (
      <span className={`h-fit rounded-full px-2 py-1 text-xs font-medium status-${included.status}`}>
        at cutoff {included.status}
      </span>
    );
  }
  if (snapshot.validity_unknown_ids.includes(item.assertion_id)) {
    return <span className="text-xs text-[var(--unverified)]">interval was not supplied</span>;
  }
  return <span className="text-xs text-[var(--muted)]">not yet known</span>;
}

function localInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
