"use client";

import { Bot, Gauge, GitCommitHorizontal, Sigma } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import type { BenchmarkResults, LlmResult, ScaleResult, SuiteResult } from "@/lib/types";

const SCENARIOS: Array<[string, string]> = [
  ["stable", "Stable fact"],
  ["correction", "Correction"],
  ["chain", "Two corrections"],
  ["conflict", "Conflict"],
  ["unreviewed_noise", "Unreviewed noise"],
];

const ERROR_LABELS: Record<string, string> = {
  missed_conflict: "picked a side in a conflict",
  untrusted_value: "trusted an unreviewed note",
  future_value: "answered with a value learned later",
  answered_too_early: "answered before anything was known",
  missed_answer: "said unknown when the answer was known",
  wrong_abstain: "said unknown instead of disputed",
  stale_value: "gave a corrected value",
  false_conflict: "reported a conflict that wasn't there",
  invented_value: "invented a value",
  invalid_output: "invalid output",
};

const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

export function BenchmarkResultsPanels() {
  const [data, setData] = useState<BenchmarkResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/faultline/v1/benchmarks/results", { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body?.error?.message || "Results unavailable");
        setData(body as BenchmarkResults);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Results unavailable"));
  }, []);

  if (error) return <p className="text-sm text-disputed">{error}</p>;
  if (!data) return <p className="text-sm text-dim">Loading saved benchmark results…</p>;
  return (
    <div className="space-y-8">
      {data.suite ? <Suite suite={data.suite} /> : null}
      {data.llm.map((run) => (
        <Llm key={run.model} run={run} />
      ))}
      {data.scale ? <Scale scale={data.scale} /> : null}
    </div>
  );
}

function SectionTitle({ icon, title, note }: { icon: React.ReactNode; title: string; note: string }) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      {icon}
      <h2 className="text-sm font-medium">{title}</h2>
      <span className="text-xs text-dim">{note}</span>
    </div>
  );
}

function Suite({ suite }: { suite: SuiteResult }) {
  const methods = [...suite.methods].sort((a, b) => b.accuracy - a.accuracy);
  return (
    <section>
      <SectionTitle
        icon={<Sigma className="size-4 text-fault" />}
        title="Generated benchmark"
        note={`${suite.questions.toLocaleString()} questions · ${suite.timelines} timelines · seed ${suite.meta.seed} · no LLM`}
      />
      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-dim">
              <th className="px-4 py-3 font-normal">Method</th>
              <th className="px-4 py-3 font-normal">Accuracy</th>
              {SCENARIOS.map(([key, label]) => (
                <th key={key} className="px-3 py-3 text-right font-normal">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {methods.map((method, index) => {
              const hero = method.method === "faultline";
              const topError = Object.entries(method.errors).sort((a, b) => b[1] - a[1])[0];
              return (
                <tr key={method.method} className={hero ? "bg-fault/[0.05]" : ""}>
                  <td className="px-4 py-3">
                    <p className={hero ? "font-medium text-ink" : "text-muted"}>{method.label}</p>
                    <p className="mono text-[11px] text-dim">
                      {topError ? `mostly: ${ERROR_LABELS[topError[0]] ?? topError[0]} (${topError[1]})` : "no errors"}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span className="mono w-14 text-ink">{pct(method.accuracy)}</span>
                      <div className="h-1.5 w-28 overflow-hidden rounded-full bg-white/[0.06]">
                        <motion.div
                          className={`h-full ${hero ? "bg-fault" : "bg-white/30"}`}
                          initial={{ width: 0 }}
                          whileInView={{ width: pct(method.accuracy) }}
                          viewport={{ once: true }}
                          transition={{ duration: 0.8, delay: index * 0.05 }}
                        />
                      </div>
                    </div>
                  </td>
                  {SCENARIOS.map(([key]) => {
                    const cell = method.by_scenario[key];
                    const ratio = cell && cell.questions ? cell.correct / cell.questions : 0;
                    const tone = ratio === 1 ? "text-ok" : ratio >= 0.6 ? "text-unverified" : "text-disputed";
                    return (
                      <td key={key} className={`mono px-3 py-3 text-right text-xs ${tone}`}>
                        {cell ? pct(ratio) : "—"}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs leading-5 text-dim">
        Every method reads the same assertion rows from FalkorDB. Baselines ignore the edges; Faultline uses
        SUPERSEDES / CONFLICTS_WITH and the policy. Ground truth comes from each generated story, and questions are
        asked before, between and after its notes. Ties are real: a log that keeps only reviewed notes handles plain
        corrections just as well. Generated {suite.meta.generated_at.slice(0, 10)}.
      </p>
    </section>
  );
}

function Llm({ run }: { run: LlmResult }) {
  const raw = run.conditions.raw_notes;
  const fl = run.conditions.faultline_evidence;
  const rows: Array<[string, typeof raw, boolean]> = [
    ["Same model + raw notes", raw, false],
    ["Same model + Faultline evidence", fl, true],
  ];
  return (
    <section>
      <SectionTitle
        icon={<Bot className="size-4 text-fault" />}
        title="LLM in the loop"
        note={`${run.model} · ${run.sample} questions · temperature 0 · measured ${run.meta.generated_at.slice(0, 10)}`}
      />
      <div className="grid gap-4 md:grid-cols-2">
        {rows.map(([label, cond, hero]) => (
          <div key={label} className={`panel panel-pad ${hero ? "border-fault/40 bg-fault/[0.04]" : ""}`}>
            <p className="text-sm text-muted">{label}</p>
            <p className="mt-3 text-4xl font-semibold tracking-tight">
              {cond.correct}
              <span className="text-xl text-dim">/{cond.questions}</span>
            </p>
            <ul className="mono mt-4 space-y-1 text-[11px] text-dim">
              {Object.entries(cond.errors).length === 0 ? <li className="text-ok">no errors</li> : null}
              {Object.entries(cond.errors).map(([kind, count]) => (
                <li key={kind}>
                  <span className="text-disputed">{count}×</span> {ERROR_LABELS[kind] ?? kind}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-dim">
        Both conditions get the same rules and question; only the memory context differs. Raw prompts and replies for
        the first questions are saved in the result file.
      </p>
    </section>
  );
}

function Scale({ scale }: { scale: ScaleResult }) {
  const maxCandidates = Math.max(...scale.bisect.map((row) => row.linear_worst_case), 1);
  return (
    <section className="grid gap-6 lg:grid-cols-2">
      <div>
        <SectionTitle icon={<Gauge className="size-4 text-fault" />} title="Scale on FalkorDB" note={scale.meta.machine.split("-")[0]} />
        <div className="panel overflow-x-auto">
          <table className="w-full min-w-[420px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-dim">
                <th className="px-4 py-3 font-normal">Entities</th>
                <th className="px-3 py-3 text-right font-normal">Nodes / edges</th>
                <th className="px-3 py-3 text-right font-normal">Writes/s</th>
                <th className="px-3 py-3 text-right font-normal">As-of p50 / p95</th>
                <th className="px-3 py-3 text-right font-normal">Full scan p50</th>
              </tr>
            </thead>
            <tbody className="mono divide-y divide-line text-xs">
              {scale.sizes.map((row) => (
                <tr key={row.entities}>
                  <td className="px-4 py-3 text-ink">{row.entities.toLocaleString()}</td>
                  <td className="px-3 py-3 text-right text-muted">
                    {row.graph.nodes.toLocaleString()} / {row.graph.edges.toLocaleString()}
                  </td>
                  <td className="px-3 py-3 text-right text-muted">{row.writes_per_second}</td>
                  <td className="px-3 py-3 text-right text-ok">
                    {row.as_of_read_ms.p50} / {row.as_of_read_ms.p95} ms
                  </td>
                  <td className="px-3 py-3 text-right text-dim">{row.full_scan_read_ms.p50} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs leading-5 text-dim">
          As-of reads match one entity through its index. &ldquo;Full scan&rdquo; is the earlier read path that fetched
          every entity; this benchmark is why it was replaced.
        </p>
      </div>
      <div>
        <SectionTitle
          icon={<GitCommitHorizontal className="size-4 text-fault" />}
          title="Bisect efficiency"
          note="probes to find a hidden correction"
        />
        <div className="panel panel-pad space-y-4">
          {scale.bisect.map((row) => (
            <div key={row.history_length}>
              <div className="mb-1.5 flex justify-between text-xs">
                <span className="text-muted">{row.history_length} recorded notes</span>
                <span className="mono text-dim">
                  <span className="text-fault">{row.bisect_probes}</span> vs {row.linear_worst_case} worst case
                  {row.found_culprit ? " · culprit found" : " · missed"}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full bg-white/15" style={{ width: `${(row.linear_worst_case / maxCandidates) * 100}%` }}>
                  <motion.div
                    className="h-full bg-fault"
                    initial={{ width: 0 }}
                    whileInView={{ width: `${(row.bisect_probes / row.linear_worst_case) * 100}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8 }}
                  />
                </div>
              </div>
            </div>
          ))}
          <p className="text-xs leading-5 text-dim">
            Each history hides one reviewed correction among unreviewed notes. Bisect binary-searches the observed
            moments with read-only as-of queries.
          </p>
        </div>
      </div>
    </section>
  );
}
