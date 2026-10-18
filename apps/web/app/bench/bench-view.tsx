"use client";

import { useState } from "react";
import type { AblationReport, BenchClaim } from "@/lib/types";

type Props = {
  apiError: string | null;
};

export function BenchView({ apiError }: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<AblationReport | null>(null);

  async function onRun() {
    setPending(true);
    setError(null);
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
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 lg:px-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mono text-xs tracking-[0.16em] text-[var(--fault)]">BENCH</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">The edge is the answer</h1>
          <p className="mt-2 max-w-2xl text-sm text-[var(--muted)]">
            Delete one FalkorDB relationship, ask the late rollout question, then put the relationship back.
          </p>
        </div>
        <button
          type="button"
          onClick={onRun}
          disabled={pending || Boolean(apiError)}
          className="rounded-lg bg-[var(--ink)] px-3 py-2 text-sm font-medium text-[var(--paper)] disabled:opacity-60"
        >
          {pending ? "Measuring…" : "Run ablation"}
        </button>
      </header>
      {apiError ? <p className="text-sm text-[var(--fault)]">{apiError}</p> : null}
      {error ? <p className="text-sm text-[var(--fault)]">{error}</p> : null}
      {!report && !apiError ? (
        <p className="rounded-xl border border-dashed border-[var(--line)] bg-[var(--card)] p-6 text-sm text-[var(--muted)]">
          No ablation yet. Run it against the seeded Project Atlas graph.
        </p>
      ) : null}
      {report ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <ClaimCard title="Intact graph" claim={report.intact} />
          <ClaimCard title="SUPPORTED_BY removed" claim={report.support_deleted} />
          <ClaimCard title="SUPERSEDES removed" claim={report.supersedes_deleted} />
        </div>
      ) : null}
      {report?.restored ? (
        <p className="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4 text-sm">
          <span className="rounded-full px-2 py-1 text-xs font-medium status-current">restored</span>
          <span className="ml-2">Both edges are back. A later cutoff still treats region-b as current.</span>
        </p>
      ) : null}
    </div>
  );
}

function ClaimCard({ title, claim }: { title: string; claim: BenchClaim }) {
  return (
    <article className="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4">
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className={`mt-3 inline-block rounded-full px-2 py-1 text-xs font-medium status-${claim.status === "supported" ? "current" : claim.status === "insufficient" ? "unverified" : "disputed"}`}>
        {claim.status}
      </p>
      <p className="mt-3 text-sm font-medium">{claim.value ?? "No value chosen."}</p>
      <p className="mono mt-2 text-xs break-all text-[var(--muted)]">
        {claim.evidence_ids.join(", ") || "no evidence"}
      </p>
      <ul className="mt-3 space-y-1 text-xs">
        {claim.included.map((item) => (
          <li key={item.assertion_id} className="mono">
            {item.assertion_id} {item.value} {item.status}
          </li>
        ))}
      </ul>
    </article>
  );
}
