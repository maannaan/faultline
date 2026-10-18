"use client";

import { Bot, ChevronRight, Diamond, FileText, MessageSquareQuote, MessagesSquare, Zap } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorBanner, PageHeader, Panel, StatusPill, formatTime } from "@/components/ui";
import type { BlameHop, BlameReport, ReplaySummary } from "@/lib/types";

const PRESETS = [
  { label: "Region · 15 Oct", predicate: "deploy_region", asOf: "2026-10-15T12:00:00Z", question: "Which deployment region should the rollout use?" },
  { label: "Region · 16 Oct", predicate: "deploy_region", asOf: "2026-10-16T13:00:00Z", question: "Which deployment region should the rollout use?" },
  { label: "On-call · 16 Oct", predicate: "oncall_owner", asOf: "2026-10-16T13:00:00Z", question: "Who is on call for the rollout?" },
] as const;

export function BlameView() {
  const [replays, setReplays] = useState<ReplaySummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [report, setReport] = useState<BlameReport | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const body = await get<{ replays: ReplaySummary[] }>("/v1/replays?limit=20");
      setReplays(body.replays);
      return body.replays;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Replays could not be loaded.");
      return [];
    }
  }, []);

  useEffect(() => {
    refresh().then((list) => {
      if (list[0]) setSelected(list[0].replay_id);
    });
  }, [refresh]);

  useEffect(() => {
    if (!selected) return;
    setReport(null);
    get<BlameReport>(`/v1/replays/${encodeURIComponent(selected)}/blame`)
      .then(setReport)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Blame failed."));
  }, [selected]);

  async function runPreset(preset: (typeof PRESETS)[number]) {
    setPending(true);
    setError(null);
    try {
      const snapshot = await post<{ snapshot_id: string }>("/v1/snapshots", {
        as_of_time: preset.asOf,
        time_mode: "known",
        entity_ids: ["project-atlas"],
        idempotency_key: `blame-snap:${preset.asOf}`,
      });
      const replay = await post<{ replay_id: string }>("/v1/replays", {
        question: preset.question,
        predicate: preset.predicate,
        snapshot_id: snapshot.snapshot_id,
        idempotency_key: `blame-replay:${snapshot.snapshot_id}:${preset.predicate}`,
      });
      await refresh();
      setSelected(replay.replay_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The replay could not be created.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="faultline blame"
        title="Blame an answer"
        description="Pick a recorded replay. Each claim is followed edge by edge back to the assertion, the source and its trust tier, the memory event, the session and the agent that recorded it."
        actions={PRESETS.map((preset) => (
          <button key={preset.label} type="button" disabled={pending} onClick={() => runPreset(preset)} className="btn btn-ghost !py-1.5 text-xs">
            Ask: {preset.label}
          </button>
        ))}
      />
      {error ? <ErrorBanner title="Blame failed">{error}</ErrorBanner> : null}
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <Panel title="Recorded replays" aside={<span className="mono">{replays.length}</span>}>
          {replays.length === 0 ? (
            <p className="text-sm leading-6 text-dim">No replays yet. Use one of the Ask buttons above, or run the Replay Lab.</p>
          ) : (
            <ul className="-mx-2 space-y-1">
              {replays.map((item) => (
                <li key={item.replay_id}>
                  <button
                    type="button"
                    onClick={() => setSelected(item.replay_id)}
                    className={`w-full rounded-lg px-2.5 py-2 text-left transition ${
                      selected === item.replay_id ? "bg-fault/[0.08]" : "hover:bg-white/[0.03]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="mono text-[11px] text-dim">{item.predicate}</span>
                      <StatusPill status={item.claim_status} />
                    </div>
                    <p className="mt-1 truncate text-sm">{item.claim_value ?? "no value chosen"}</p>
                    <p className="mono mt-0.5 text-[10px] text-dim">as of {formatTime(item.as_of)}</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <section className="min-w-0 space-y-4">
          {!report && replays.length === 0 ? <EmptyState>Create a replay to blame it.</EmptyState> : null}
          <AnimatePresence mode="wait">
            {report ? (
              <motion.div key={report.replay_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-4">
                <div className="panel panel-pad">
                  <p className="mono text-[11px] text-dim">
                    {report.replay_id} · snapshot as of {formatTime(report.as_of)} · {report.model_version} / {report.prompt_version}
                  </p>
                  <p className="mt-2 text-sm text-muted">{report.question}</p>
                </div>
                {report.claims.map((claim) => (
                  <div key={claim.claim_id} className="panel overflow-hidden">
                    <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 sm:px-5">
                      <StatusPill status={claim.status} />
                      <p className="text-xl font-semibold tracking-tight">{claim.value ?? <span className="text-muted">No value chosen</span>}</p>
                      <p className="text-sm text-dim">{claim.wording}</p>
                    </div>
                    <div className="panel-pad space-y-4">
                      {claim.chain.length === 0 ? (
                        <p className="text-sm text-dim">This claim cites no assertion, so there is nothing to blame.</p>
                      ) : (
                        claim.chain.map((hop, index) => <Chain key={hop.assertion_id} hop={hop} index={index} />)
                      )}
                    </div>
                  </div>
                ))}
              </motion.div>
            ) : null}
          </AnimatePresence>
        </section>
      </div>
    </div>
  );
}

function Chain({ hop, index }: { hop: BlameHop; index: number }) {
  const steps = [
    { icon: Diamond, label: "Assertion", value: `${hop.predicate} = ${hop.value}`, sub: hop.assertion_id, pill: hop.status_then },
    { icon: FileText, label: "Source", value: hop.source_title ?? hop.source_id ?? "—", sub: `${hop.source_id ?? ""} · ${hop.trust_tier ?? "?"}` },
    { icon: Zap, label: "MemoryEvent", value: hop.event_id ?? "—", sub: formatTime(hop.observed_at) },
    { icon: MessagesSquare, label: "Session", value: hop.session_id ?? "—", sub: "CONTAINS_EVENT" },
    { icon: Bot, label: "Agent", value: hop.agent_id ?? "—", sub: "RECORDED" },
  ];
  return (
    <div className="rounded-lg border border-line bg-black/20 p-3">
      <div className="flex flex-col gap-2 xl:flex-row xl:items-stretch">
        {steps.map((step, stepIndex) => (
          <motion.div
            key={step.label}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.2 + stepIndex * 0.12 }}
            className="flex min-w-0 flex-1 items-center gap-2"
          >
            <div className="min-w-0 flex-1 rounded-lg border border-line bg-panel px-3 py-2">
              <div className="flex items-center gap-1.5 text-[10px] tracking-wide text-dim uppercase">
                <step.icon className="size-3 text-fault" /> {step.label}
              </div>
              <p className="mt-1 truncate text-[13px] font-medium">{step.value}</p>
              <div className="mt-0.5 flex items-center gap-1.5">
                <p className="mono truncate text-[10px] text-dim">{step.sub}</p>
                {step.pill ? <StatusPill status={step.pill} prefix="saw" /> : null}
              </div>
            </div>
            {stepIndex < steps.length - 1 ? <ChevronRight className="hidden size-4 shrink-0 text-dim xl:block" /> : null}
          </motion.div>
        ))}
      </div>
      {hop.excerpt ? (
        <p className="mt-3 flex gap-2 text-xs leading-5 text-muted">
          <MessageSquareQuote className="mt-0.5 size-3.5 shrink-0 text-dim" />
          <span>&ldquo;{hop.excerpt}&rdquo;</span>
        </p>
      ) : null}
      {hop.status_then && hop.status_then !== hop.status_now ? (
        <p className="mono mt-2 text-[11px] text-fault">
          status then {hop.status_then} → now {hop.status_now}
        </p>
      ) : null}
    </div>
  );
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`/api/faultline${path}`, { cache: "no-store" });
  const body = (await response.json()) as T & { error?: { message?: string } };
  if (!response.ok) throw new Error(body.error?.message || "Request failed.");
  return body;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api/faultline${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = (await response.json()) as T & { error?: { message?: string } };
  if (!response.ok) throw new Error(json.error?.message || "Request failed.");
  return json;
}
