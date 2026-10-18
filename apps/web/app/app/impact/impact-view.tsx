"use client";

import { Radar, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorBanner, PageHeader, Panel, StatusPill, formatTime } from "@/components/ui";
import type { ImpactReport, TimelineItem } from "@/lib/types";

const EARLY = "2026-10-15T12:00:00Z";

export function ImpactView({ items, apiError }: { items: TimelineItem[]; apiError: string | null }) {
  const initial = items.find((item) => item.status === "superseded")?.assertion_id ?? items[0]?.assertion_id ?? "";
  const [assertionId, setAssertionId] = useState(initial);
  const [report, setReport] = useState<ImpactReport | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runKey, setRunKey] = useState(0);

  const load = useCallback(async (id: string) => {
    if (!id) return;
    setError(null);
    try {
      const response = await fetch(`/api/faultline/v1/assertions/${encodeURIComponent(id)}/impact`, { cache: "no-store" });
      const body = (await response.json()) as ImpactReport & { error?: { message?: string } };
      if (!response.ok) throw new Error(body.error?.message || "Impact could not be loaded.");
      setReport(body);
      setRunKey((key) => key + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Impact could not be loaded.");
    }
  }, []);

  useEffect(() => {
    load(assertionId);
  }, [assertionId, load]);

  async function simulate() {
    setPending(true);
    setError(null);
    try {
      const stamp = Date.now();
      const snapshot = await post<{ snapshot_id: string }>("/v1/snapshots", {
        as_of_time: EARLY,
        time_mode: "known",
        entity_ids: ["project-atlas"],
        idempotency_key: `impact-demo-snap:${EARLY}`,
      });
      await post("/v1/replays", {
        question: "Which deployment region should the rollout use?",
        predicate: "deploy_region",
        snapshot_id: snapshot.snapshot_id,
        idempotency_key: `impact-demo-replay:${snapshot.snapshot_id}`,
      });
      const task = await post<{ task_id: string; version: number }>("/v1/tasks", {
        objective: "Prepare the Atlas rollout checklist (planned on 15 Oct)",
        owner_agent_id: "agent-planner",
        acceptance_criteria: ["Use the accepted deploy region"],
        idempotency_key: `impact-demo-task:${stamp}`,
      });
      await post(`/v1/tasks/${task.task_id}/handoff`, {
        to_agent_id: "agent-release",
        snapshot_id: snapshot.snapshot_id,
        memory_refs: ["assert-region-a", "source-design-001"],
        expected_version: task.version,
        idempotency_key: `impact-demo-handoff:${stamp}`,
        open_questions: [],
        expires_at: "2026-10-30T00:00:00Z",
      });
      await load(assertionId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Simulation failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="faultline impact"
        title="Correction blast radius"
        description="When a fact is superseded or disputed, what already relied on it? Faultline walks the graph backwards from the assertion to every snapshot, replay answer and handoff, and flags the ones that saw a different status than it has now."
        actions={
          <button type="button" onClick={simulate} disabled={pending || Boolean(apiError)} className="btn btn-fault">
            <Sparkles className="size-4" />
            {pending ? "Recording…" : "Simulate an agent that acted on 15 Oct"}
          </button>
        }
      />
      {apiError ? <ErrorBanner>{apiError}</ErrorBanner> : null}
      {error ? <ErrorBanner title="Impact failed">{error}</ErrorBanner> : null}

      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <button
            key={item.assertion_id}
            type="button"
            onClick={() => setAssertionId(item.assertion_id)}
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition ${
              assertionId === item.assertion_id ? "border-fault/50 bg-fault/[0.06]" : "border-line bg-panel/60 hover:bg-white/[0.03]"
            }`}
          >
            <span className="mono text-[11px] text-dim">{item.predicate}</span>
            <span className="font-medium">{item.value}</span>
            <StatusPill status={item.status} />
          </button>
        ))}
      </div>

      {report ? (
        <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
          <Ripple key={runKey} report={report} />
          <div className="min-w-0 space-y-4">
            <div className={`rounded-xl border p-4 ${report.outdated_count ? "border-disputed/30 bg-disputed/[0.05]" : "border-line bg-panel/70"}`}>
              <div className="flex items-center gap-2">
                <Radar className={`size-4 ${report.outdated_count ? "text-disputed" : "text-dim"}`} />
                <p className="text-sm font-medium">
                  {report.outdated_count} item{report.outdated_count === 1 ? "" : "s"} need review
                </p>
              </div>
              <p className="mt-1.5 text-sm leading-6 text-muted">{report.summary}</p>
              {report.assertion.superseded_by.length ? (
                <p className="mono mt-2 text-xs text-fault">replaced by {report.assertion.superseded_by.join(", ")} via SUPERSEDES</p>
              ) : null}
              {report.assertion.conflicts_with.length ? (
                <p className="mono mt-2 text-xs text-disputed">conflicts with {report.assertion.conflicts_with.join(", ")}</p>
              ) : null}
            </div>
            <ImpactList
              title="Replay answers that cited it"
              empty="No replay answer cited this assertion."
              rows={report.replays.map((item) => ({
                key: item.replay_id,
                main: item.claim_value ? `answered "${item.claim_value}"` : `answer ${item.claim_status}`,
                sub: `${item.replay_id} · snapshot as of ${formatTime(item.as_of)}`,
                then: item.status_then,
                outdated: item.outdated,
              }))}
            />
            <ImpactList
              title="Handoffs built on a snapshot that included it"
              empty="No handoff used a snapshot with this assertion."
              rows={report.handoffs.map((item) => ({
                key: item.handoff_id,
                main: item.objective,
                sub: `${item.task_status} · ${item.referenced ? "cited as memory" : item.carried_as_conflict ? "carried as conflict" : "in snapshot"} · as of ${formatTime(item.as_of)}`,
                then: item.status_then,
                outdated: item.outdated,
              }))}
            />
            <ImpactList
              title="Snapshots that included it"
              empty="No snapshot included this assertion."
              rows={report.snapshots.map((item) => ({
                key: item.snapshot_id,
                main: `as of ${formatTime(item.as_of)}`,
                sub: `${item.snapshot_id} · ${item.replay_count} replay(s), ${item.handoff_count} handoff(s)`,
                then: item.status_then,
                outdated: item.outdated,
              }))}
            />
          </div>
        </div>
      ) : !apiError ? (
        <EmptyState>Loading impact…</EmptyState>
      ) : null}
    </div>
  );
}

function Ripple({ report }: { report: ImpactReport }) {
  const nodes = [
    ...report.snapshots.map((item) => ({ id: item.snapshot_id, kind: "snapshot", outdated: item.outdated })),
    ...report.replays.map((item) => ({ id: item.replay_id, kind: "replay", outdated: item.outdated })),
    ...report.handoffs.map((item) => ({ id: item.handoff_id, kind: "handoff", outdated: item.outdated })),
  ].slice(0, 18);
  const ring = { snapshot: 78, replay: 122, handoff: 160 } as const;
  const tone = statusColor(report.assertion.status_now);
  return (
    <Panel title="Ripple" aside={<span className="mono">{nodes.length} dependents</span>}>
      <svg viewBox="-190 -190 380 380" className="mx-auto block w-full max-w-[380px]" role="img" aria-label="Dependents of the assertion">
        {[78, 122, 160].map((radius, index) => (
          <motion.circle
            key={radius}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.07)"
            strokeDasharray="3 5"
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1 + index * 0.15, duration: 0.5 }}
          />
        ))}
        <motion.circle
          r={30}
          fill="none"
          stroke={tone}
          initial={{ scale: 1, opacity: 0.6 }}
          animate={{ scale: 6, opacity: 0 }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeOut" }}
        />
        {(["snapshot", "replay", "handoff"] as const).map((kind) => {
          const group = nodes.filter((node) => node.kind === kind);
          return group.map((node, index) => {
            const angle = (index / Math.max(group.length, 1)) * Math.PI * 2 - Math.PI / 2 + (kind === "replay" ? 0.5 : kind === "handoff" ? 1 : 0);
            const x = Math.cos(angle) * ring[kind];
            const y = Math.sin(angle) * ring[kind];
            const color = node.outdated ? "#fb7185" : "#71717a";
            return (
              <motion.g key={node.id} initial={{ opacity: 0, scale: 0.4 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.5 + index * 0.08 + ring[kind] / 400 }}>
                <line x1={0} y1={0} x2={x} y2={y} stroke={color} strokeOpacity={0.35} strokeDasharray={node.outdated ? "4 4" : undefined} />
                <circle cx={x} cy={y} r={kind === "handoff" ? 11 : 9} fill="#0e0e11" stroke={color} strokeWidth={1.5} />
                <text x={x} y={y + 3} textAnchor="middle" fontSize="8" fill={color} className="mono">
                  {kind === "snapshot" ? "S" : kind === "replay" ? "R" : "H"}
                </text>
              </motion.g>
            );
          });
        })}
        <circle r={30} fill="#121216" stroke={tone} strokeWidth={2} />
        <text y={-2} textAnchor="middle" fontSize="11" fill="#f4f4f5">
          {report.assertion.value}
        </text>
        <text y={12} textAnchor="middle" fontSize="8" fill={tone}>
          {report.assertion.status_now}
        </text>
      </svg>
      <div className="mono mt-2 flex justify-center gap-4 text-[10px] text-dim">
        <span>S snapshot</span>
        <span>R replay</span>
        <span>H handoff</span>
        <span className="text-disputed">red = saw a different status</span>
      </div>
    </Panel>
  );
}

function ImpactList({
  title,
  empty,
  rows,
}: {
  title: string;
  empty: string;
  rows: Array<{ key: string; main: string; sub: string; then: string; outdated: boolean }>;
}) {
  return (
    <Panel title={title} aside={<span className="mono">{rows.length}</span>}>
      {rows.length === 0 ? (
        <p className="text-sm text-dim">{empty}</p>
      ) : (
        <ul className="-my-1 divide-y divide-line">
          {rows.map((row, index) => (
            <motion.li
              key={row.key}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              className="flex items-center gap-3 py-2.5"
            >
              <span className={`size-2 shrink-0 rounded-full ${row.outdated ? "bg-disputed" : "bg-white/20"}`} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{row.main}</p>
                <p className="mono truncate text-[11px] text-dim">{row.sub}</p>
              </div>
              <StatusPill status={row.then} prefix="saw" />
              {row.outdated ? <span className="pill pill-disputed">outdated</span> : null}
            </motion.li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function statusColor(status: string): string {
  return status === "current" ? "#34d399" : status === "disputed" ? "#fb7185" : status === "superseded" ? "#8b8b94" : "#facc15";
}

async function post<T = unknown>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api/faultline${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = (await response.json()) as T & { error?: { message?: string } };
  if (!response.ok) throw new Error(json.error?.message || "Request failed.");
  return json;
}
