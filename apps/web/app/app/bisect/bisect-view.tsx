"use client";

import { Crosshair, GitBranch } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { EvidenceGraph } from "@/components/evidence-graph";
import { EmptyState, ErrorBanner, KeyValue, PageHeader, Panel, StatusPill, formatTime, localInputValue } from "@/components/ui";
import type { BisectProbe, BisectResult, Entity } from "@/lib/types";

const EARLY = "2026-10-15T12:00:00Z";
const LATE = "2026-10-16T13:00:00Z";

export function BisectView({ entities, apiError }: { entities: Entity[]; apiError: string | null }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BisectResult | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const response = await fetch("/api/faultline/v1/bisect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_id: String(data.get("entity_id") || ""),
          predicate: String(data.get("predicate") || "deploy_region"),
          good_as_of: new Date(String(data.get("good") || "")).toISOString(),
          bad_as_of: new Date(String(data.get("bad") || "")).toISOString(),
        }),
      });
      const body = (await response.json()) as BisectResult & { error?: { message?: string } };
      if (!response.ok) throw new Error(body.error?.message || "Bisect failed.");
      setResult(body);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Bisect failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="faultline bisect"
        title="Memory bisect"
        description="The answer was right at one time and different later. Bisect binary-searches the recorded memory between them and names the event and source that flipped it. Every probe is an as-of query against FalkorDB; nothing is written."
      />
      {apiError ? <ErrorBanner>{apiError}</ErrorBanner> : null}
      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <Panel title="Range">
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
              <label className="label" htmlFor="predicate">
                Question
              </label>
              <select id="predicate" name="predicate" className="field mono" defaultValue="deploy_region">
                <option value="deploy_region">deploy_region</option>
                <option value="oncall_owner">oncall_owner</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label" htmlFor="good">
                  <span className="text-ok">good</span> at
                </label>
                <input id="good" name="good" type="datetime-local" required defaultValue={localInputValue(new Date(EARLY))} className="field !px-2 !text-xs" />
              </div>
              <div>
                <label className="label" htmlFor="bad">
                  <span className="text-disputed">bad</span> at
                </label>
                <input id="bad" name="bad" type="datetime-local" required defaultValue={localInputValue(new Date(LATE))} className="field !px-2 !text-xs" />
              </div>
            </div>
            <button type="submit" disabled={pending || Boolean(apiError) || entities.length === 0} className="btn btn-primary w-full">
              <GitBranch className="size-4" /> {pending ? "Bisecting…" : "Run bisect"}
            </button>
            {error ? <p className="text-xs leading-5 text-disputed">{error}</p> : null}
            <p className="text-[11px] leading-4 text-dim">
              Like <span className="mono text-muted">git bisect</span>, it assumes the answer flips once in the range.
            </p>
          </form>
        </Panel>

        <section className="min-w-0 space-y-6">
          {!result && !apiError ? (
            <EmptyState>
              Run bisect with the defaults: deploy_region was <span className="mono text-ink">region-a</span> on 15 Oct and{" "}
              <span className="mono text-ink">region-b</span> on 16 Oct. Which recorded event changed it?
            </EmptyState>
          ) : null}
          <AnimatePresence>{result ? <BisectReport key={`${result.predicate}-${result.good.as_of}-${result.bad.as_of}`} result={result} /> : null}</AnimatePresence>
          {result?.flipped && result.first_bad_as_of ? (
            <EvidenceGraph
              key={result.first_bad_as_of + result.predicate}
              entityId={result.entity_id}
              mode="fixed"
              asOf={result.first_bad_as_of}
              highlightIds={[...result.culprit_assertion_ids, ...result.culprit_source_ids, ...result.culprit_event_ids]}
              title="Memory at the first bad moment"
              height={420}
            />
          ) : null}
        </section>
      </div>
    </div>
  );
}

function BisectReport({ result }: { result: BisectResult }) {
  const lines: Array<{ probe: BisectProbe; label: string }> = [
    { probe: result.good, label: "good" },
    ...result.probes.map((probe, index) => ({ probe, label: `probe ${index + 1}` })),
    { probe: result.bad, label: "bad" },
  ];
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-6">
      <Panel
        title="Bisect log"
        aside={
          <span className="mono">
            {result.probes.length} probe{result.probes.length === 1 ? "" : "s"} · {result.candidates} candidate moment
            {result.candidates === 1 ? "" : "s"}
          </span>
        }
      >
        <ol className="mono space-y-1.5 text-[12px]">
          {lines.map(({ probe, label }, index) => (
            <motion.li
              key={`${label}-${probe.as_of}`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.35 }}
              className="grid grid-cols-[72px_150px_1fr] items-center gap-3 rounded-md px-2 py-1.5 hover:bg-white/[0.02] sm:grid-cols-[80px_170px_1fr_auto]"
            >
              <span className={probe.verdict === "bad" ? "text-disputed" : "text-ok"}>{label}</span>
              <span className="text-dim">{formatTime(probe.as_of)}</span>
              <span className="truncate text-ink">
                {probe.value ?? <span className="text-muted">no value</span>}
                <span className="ml-2 text-dim">{probe.evidence_ids.join(", ")}</span>
              </span>
              <span className="hidden sm:block">
                <StatusPill status={probe.status} />
              </span>
            </motion.li>
          ))}
        </ol>
      </Panel>

      {result.flipped ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: lines.length * 0.35 }}
          className="relative overflow-hidden rounded-xl border border-fault/40 bg-fault/[0.05] p-5"
        >
          <div className="flex items-center gap-2 text-fault">
            <Crosshair className="size-4" />
            <p className="eyebrow">First bad moment · {formatTime(result.first_bad_as_of)}</p>
          </div>
          <p className="mt-3 text-lg font-medium leading-7">{result.explanation}</p>
          <div className="mt-4">
            <KeyValue
              rows={[
                ["Culprit", result.culprit_assertion_ids.join(", ") || "—"],
                ["Source", result.culprit_source_ids.join(", ") || "—"],
                ["Event", result.culprit_event_ids.join(", ") || "—"],
                ["Answer", `${result.good.value ?? result.good.status} → ${result.bad.value ?? result.bad.status}`],
              ]}
            />
          </div>
        </motion.div>
      ) : (
        <EmptyState>{result.explanation}</EmptyState>
      )}
    </motion.div>
  );
}
