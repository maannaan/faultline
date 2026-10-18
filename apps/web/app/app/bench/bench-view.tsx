"use client";

import { CircleCheck, CircleX, FlaskConical, ListChecks, RotateCcw, Scissors } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorBanner, PageHeader, StatusPill } from "@/components/ui";
import type { AblationReport, BenchClaim, MemoryTestReport } from "@/lib/types";
import { GITHUB_URL } from "@/components/app-nav";

type Props = {
  apiError: string | null;
};

/* From docs/benchmark.json (make bench): three synthetic questions on the seeded graph. */
const BASELINE = [
  { method: "No memory", correct: 0, stale: 0, conflicts: 0 },
  { method: "Flat summary · latest line wins", correct: 1, stale: 1, conflicts: 0 },
  { method: "Faultline", correct: 3, stale: 0, conflicts: 1 },
] as const;

export function BenchView({ apiError }: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<AblationReport | null>(null);

  async function onRun() {
    setPending(true);
    setError(null);
    setReport(null);
    try {
      const response = await fetch("/api/faultline/v1/benchmarks/ablation", { method: "POST" });
      const body = (await response.json()) as AblationReport & { error?: { message?: string } };
      if (!response.ok) {
        throw new Error(body.error?.message || "The Faultline API is not reachable.");
      }
      setReport(body);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The ablation could not be run.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="faultline test"
        title="The edge is the answer"
        description="Delete one FalkorDB relationship, ask the late rollout question, then put the relationship back. If the answer didn't change, the graph wasn't doing the work."
        actions={
          <button type="button" onClick={onRun} disabled={pending || Boolean(apiError)} className="btn btn-primary">
            <Scissors className="size-4" />
            {pending ? "Cutting edges…" : "Run ablation"}
          </button>
        }
      />
      {apiError ? <ErrorBanner>{apiError}</ErrorBanner> : null}
      {error ? <ErrorBanner title="Ablation failed">{error}</ErrorBanner> : null}

      {!report && !apiError ? (
        <EmptyState>
          {pending ? "Deleting and restoring edges on the seeded Project Atlas graph…" : "No ablation yet. Run it against the seeded Project Atlas graph."}
        </EmptyState>
      ) : null}

      {report ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Stage index={0} title="Intact graph" edge={null} claim={report.intact} />
          <Stage index={1} title="Delete SUPPORTED_BY" edge="(assert-region-b)-[:SUPPORTED_BY]->(source-change-002)" claim={report.support_deleted} />
          <Stage index={2} title="Delete SUPERSEDES" edge="(assert-region-b)-[:SUPERSEDES]->(assert-region-a)" claim={report.supersedes_deleted} />
        </div>
      ) : null}
      {report?.restored ? (
        <motion.p
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.1 }}
          className="flex items-center gap-2 rounded-xl border border-ok/30 bg-ok/[0.06] p-4 text-sm"
        >
          <CircleCheck className="size-4 text-ok" />
          <span>Both edges restored. A late cutoff treats region-b as current again.</span>
        </motion.p>
      ) : null}

      {apiError ? null : <MemoryTests />}

      <section>
        <div className="mb-4 flex items-center gap-2">
          <FlaskConical className="size-4 text-fault" />
          <h2 className="text-sm font-medium">Baseline comparison</h2>
          <span className="text-xs text-dim">3 synthetic questions · deterministic answerer</span>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {BASELINE.map((row) => {
            const hero = row.method === "Faultline";
            return (
              <div key={row.method} className={`panel panel-pad ${hero ? "border-fault/40 bg-fault/[0.04]" : ""}`}>
                <p className="text-sm text-muted">{row.method}</p>
                <p className="mt-3 text-4xl font-semibold tracking-tight">
                  {row.correct}
                  <span className="text-xl text-dim">/3</span>
                </p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                  <motion.div
                    className={`h-full ${hero ? "bg-fault" : "bg-white/30"}`}
                    initial={{ width: 0 }}
                    whileInView={{ width: `${(row.correct / 3) * 100}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8 }}
                  />
                </div>
                <dl className="mono mt-4 flex gap-6 text-[11px]">
                  <div>
                    <dt className="text-dim">stale answers</dt>
                    <dd className={row.stale ? "text-disputed" : "text-ink"}>{row.stale}</dd>
                  </div>
                  <div>
                    <dt className="text-dim">conflicts surfaced</dt>
                    <dd className="text-ink">{row.conflicts}/1</dd>
                  </div>
                </dl>
              </div>
            );
          })}
        </div>
        <p className="mt-3 text-xs text-dim">
          Small synthetic sample. It shows the mechanism, not a general advantage over other memory systems.
        </p>
      </section>
    </div>
  );
}

function MemoryTests() {
  const [report, setReport] = useState<MemoryTestReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [runKey, setRunKey] = useState(0);

  const run = useCallback(async () => {
    setPending(true);
    setError(null);
    try {
      const response = await fetch("/api/faultline/v1/benchmarks/memory-tests", { cache: "no-store" });
      const body = (await response.json()) as MemoryTestReport & { error?: { message?: string } };
      if (!response.ok) throw new Error(body.error?.message || "Memory tests could not run.");
      setReport(body);
      setRunKey((key) => key + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Memory tests could not run.");
    } finally {
      setPending(false);
    }
  }, []);

  useEffect(() => {
    run();
  }, [run]);

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 sm:px-5">
        <ListChecks className="size-4 text-fault" />
        <h2 className="text-sm font-medium">Memory regression tests</h2>
        <span className="mono text-[11px] text-dim">memory-tests.yaml</span>
        {report ? (
          <span className={`pill ${report.failed ? "pill-disputed" : "pill-current"}`}>
            {report.passed} passed{report.failed ? ` · ${report.failed} failed` : ""}
          </span>
        ) : null}
        <div className="ml-auto flex items-center gap-2">
          <a href={`${GITHUB_URL}/actions`} className="text-xs text-dim hover:text-ink">
            runs in CI on every push →
          </a>
          <button type="button" onClick={run} disabled={pending} className="btn btn-ghost !px-2.5 !py-1.5 text-xs">
            <RotateCcw className="size-3.5" /> {pending ? "Running…" : "Re-run"}
          </button>
        </div>
      </div>
      {error ? <p className="px-5 py-4 text-sm text-disputed">{error}</p> : null}
      {report ? (
        <ul key={runKey} className="divide-y divide-line">
          {report.cases.map((item, index) => (
            <motion.li
              key={item.name}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: index * 0.08 }}
              className="grid gap-2 px-4 py-3 sm:grid-cols-[22px_1fr_auto] sm:items-center sm:px-5"
            >
              {item.passed ? <CircleCheck className="size-4 text-ok" /> : <CircleX className="size-4 text-disputed" />}
              <div className="min-w-0">
                <p className="mono text-[13px] text-ink">{item.name}</p>
                <p className="text-xs text-dim">
                  {item.description} <span className="mono">· {item.predicate} @ {item.as_of} {item.time_mode}</span>
                </p>
                {item.message ? <p className="mono mt-1 text-[11px] text-disputed">{item.message}</p> : null}
              </div>
              <div className="flex items-center gap-2">
                <StatusPill status={item.actual_status} />
                <span className="mono text-xs text-muted">{item.actual_value ?? "—"}</span>
              </div>
            </motion.li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function Stage({
  index,
  title,
  edge,
  claim,
}: {
  index: number;
  title: string;
  edge: string | null;
  claim: BenchClaim;
}) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.35, duration: 0.4 }}
      className={`panel panel-pad ${edge ? "border-disputed/25" : "border-ok/25"}`}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">{title}</h2>
        <span className="mono text-[10px] text-dim">step {index + 1}</span>
      </div>
      {edge ? (
        <div className="mono mt-3 rounded-md border border-disputed/25 bg-disputed/[0.05] px-2.5 py-2 text-[10.5px] leading-5 break-all text-disputed">
          <motion.span
            initial={{ textDecorationColor: "transparent" }}
            animate={{ textDecorationColor: "#fb7185" }}
            transition={{ delay: index * 0.35 + 0.3 }}
            className="line-through"
          >
            {edge}
          </motion.span>
        </div>
      ) : (
        <div className="mono mt-3 rounded-md border border-ok/25 bg-ok/[0.05] px-2.5 py-2 text-[10.5px] text-ok">all edges present</div>
      )}
      <div className="mt-4 flex items-center gap-2">
        <StatusPill status={claim.status} />
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight">{claim.value ?? <span className="text-muted">No value chosen</span>}</p>
      <p className="mono mt-1 text-[11px] break-all text-dim">{claim.evidence_ids.join(", ") || "no evidence"}</p>
      <ul className="mt-4 space-y-1.5 border-t border-line pt-3">
        {claim.included.map((item) => (
          <li key={item.assertion_id} className="flex items-center justify-between gap-2 text-xs">
            <span className="mono truncate text-muted">
              {item.assertion_id} · {item.value}
            </span>
            <StatusPill status={item.status} />
          </li>
        ))}
      </ul>
    </motion.article>
  );
}
