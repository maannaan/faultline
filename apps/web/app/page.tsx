import {
  ArrowRight,
  ChartColumn,
  Clock,
  GitBranch,
  GitCompareArrows,
  GitPullRequestArrow,
  Radar,
  Search,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { HeroGraph } from "@/components/hero-graph";
import { GITHUB_URL } from "@/components/app-nav";
import { GithubMark, Logo } from "@/components/logo";
import { Reveal } from "@/components/reveal";
import { TerminalDemo } from "@/components/terminal-demo";

const VERBS = [
  {
    verb: "checkout",
    title: "Memory Time Machine",
    body: "Reconstruct exactly what an agent could know at any past moment. Observed time and valid time are never conflated.",
    icon: Clock,
    href: "/app/timeline",
  },
  {
    verb: "diff",
    title: "Replay diff",
    body: "Ask the same question against two snapshots. Get added and removed evidence ids, status changes, and the edge that caused them.",
    icon: GitCompareArrows,
    href: "/app/replay",
  },
  {
    verb: "blame",
    title: "Blame",
    body: "Trace any answer back through claim, assertion, source, event, session and agent. Every hop is a graph edge.",
    icon: Search,
    href: "/app/blame",
  },
  {
    verb: "bisect",
    title: "Memory bisect",
    body: "The answer was right yesterday and wrong today. Binary-search recorded memory to find the exact event that flipped it.",
    icon: GitBranch,
    href: "/app/bisect",
  },
  {
    verb: "impact",
    title: "Correction blast radius",
    body: "When a fact is superseded, traverse back to every snapshot, replay and handoff that relied on it.",
    icon: Radar,
    href: "/app/impact",
  },
  {
    verb: "handoff",
    title: "Uncertainty-preserving handoff",
    body: "Pass a versioned snapshot to the next agent. Open conflicts are copied by the server and cannot be dropped by the client.",
    icon: GitPullRequestArrow,
    href: "/app/handoff",
  },
] as const;

/* From apps/api/benchmarks/suite.json (make benchsuite, seed 42): 1,213 generated questions, no LLM. */
const BENCH = [
  { method: "Key-value store", note: "last write wins, no history", correct: 216, wrongTime: 413, untrusted: 93, conflicts: 0 },
  { method: "Log, latest reviewed line", note: "strongest baseline", correct: 1122, wrongTime: 0, untrusted: 0, conflicts: 0 },
  { method: "Faultline", note: "FalkorDB edges + policy", correct: 1213, wrongTime: 0, untrusted: 0, conflicts: 91 },
] as const;
const BENCH_TOTAL = 1213;
const BENCH_CONFLICTS = 91;

const CYPHER = `MATCH (a:Assertion)-[:ABOUT]->(e:Entity)
WHERE a.observed_at <= $as_of
MATCH (a)-[:SUPPORTED_BY]->(s:Source)
RETURN a.id, a.value, s.id, s.trust_tier,
  [(a)-[:SUPERSEDES]->(old) | old.id]      AS supersedes,
  [(new)-[:SUPERSEDES]->(a) | new.id]      AS superseded_by,
  [(a)-[:CONFLICTS_WITH]-(other) | other.id] AS conflicts`;

export default function Landing() {
  return (
    <div className="relative overflow-hidden">
      <div className="glow-fault pointer-events-none absolute inset-x-0 top-0 h-[640px]" aria-hidden />
      <div className="grid-bg pointer-events-none absolute inset-x-0 top-0 h-[720px] [mask-image:linear-gradient(to_bottom,black,transparent)]" aria-hidden />

      <header className="relative z-10 mx-auto flex max-w-6xl items-center gap-6 px-4 py-5 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <Logo />
          <span className="font-semibold tracking-tight">Faultline</span>
        </Link>
        <nav className="hidden items-center gap-5 text-sm text-muted md:flex">
          <a href="#verbs" className="hover:text-ink">Product</a>
          <a href="#graph" className="hover:text-ink">How it works</a>
          <a href="#bench" className="hover:text-ink">Benchmark</a>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <a href={GITHUB_URL} className="btn btn-ghost !px-3 !py-1.5 text-xs">
            <GithubMark className="size-3.5" /> <span className="hidden sm:inline">GitHub</span>
          </a>
          <Link href="/app/timeline" className="btn btn-primary !px-3 !py-1.5 text-xs">
            Open live demo <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </header>

      <section className="relative z-10 mx-auto grid max-w-6xl items-center gap-12 px-4 pt-10 pb-20 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pt-16">
        <div className="fade-up">
          <a
            href="https://www.wemakedevs.org/hackathons/falkordb"
            className="pill pill-neutral !px-3 !py-1 !text-xs hover:text-ink"
          >
            <span className="size-1.5 rounded-full bg-fault" /> Graph Hacks · Track 02 · Built on FalkorDB
          </a>
          <h1 className="mt-6 text-5xl font-semibold tracking-[-0.035em] sm:text-6xl lg:text-7xl">
            git for
            <br />
            <span className="bg-gradient-to-r from-fault via-fault2 to-[#fde68a] bg-clip-text text-transparent">agent memory.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-muted">
            Blame, diff, bisect and test what your AI agents remembered. Faultline stores every fact with its source,
            its time, and the edges that corrected or contradicted it — so you can see why an answer changed.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/app/timeline" className="btn btn-primary !px-5 !py-2.5">
              Open live demo <ArrowRight className="size-4" />
            </Link>
            <a href={GITHUB_URL} className="btn btn-ghost !px-5 !py-2.5">
              <GithubMark /> Read the code
            </a>
          </div>
          <div className="mono mt-10 flex flex-wrap gap-x-6 gap-y-2 text-xs text-dim">
            <span>14 node labels</span>
            <span>20+ relationship types</span>
            <span>1 graph per tenant</span>
            <span>0 silent overwrites</span>
          </div>
        </div>
        <div className="fade-up fade-up-delay">
          <HeroGraph />
        </div>
      </section>

      <section className="relative z-10 border-y border-line bg-panel/40">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-14 sm:px-6 md:grid-cols-3">
          {[
            {
              icon: TriangleAlert,
              title: "Agents repeat stale facts",
              body: "Memory stores overwrite or summarize. When the deploy region was corrected, nothing records that the old answer was ever believed.",
            },
            {
              icon: Search,
              title: "Nobody can say why",
              body: "A changed answer has no diff. You can't reconstruct what the agent knew, or which source moved it.",
            },
            {
              icon: GitPullRequestArrow,
              title: "Handoffs flatten doubt",
              body: "The next agent gets a confident summary. The unresolved on-call dispute silently disappears.",
            },
          ].map((item, index) => (
            <Reveal key={item.title} delay={index * 0.08}>
              <item.icon className="size-5 text-fault" />
              <h3 className="mt-4 font-medium">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted">{item.body}</p>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="verbs" className="relative z-10 mx-auto max-w-6xl px-4 py-24 sm:px-6">
        <Reveal className="max-w-2xl">
          <p className="eyebrow">The toolkit</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            The verbs you use on code, for what your agents remember.
          </h2>
          <p className="mt-4 text-muted">
            Every command is a graph query against FalkorDB. Click any line to run it on the live Project Atlas graph.
          </p>
        </Reveal>
        <div className="mt-12 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <Reveal>
            <TerminalDemo />
          </Reveal>
          <div className="grid gap-3 sm:grid-cols-2">
            {VERBS.map((item, index) => (
              <Reveal key={item.verb} delay={index * 0.05}>
                <Link
                  href={item.href}
                  className="group flex h-full flex-col rounded-xl border border-line bg-panel/70 p-4 transition hover:border-fault/40 hover:bg-panel2"
                >
                  <div className="flex items-center justify-between">
                    <item.icon className="size-4 text-fault" />
                    <span className="mono text-[10px] text-dim group-hover:text-fault">{item.verb}</span>
                  </div>
                  <h3 className="mt-3 text-sm font-medium">{item.title}</h3>
                  <p className="mt-1.5 text-xs leading-5 text-muted">{item.body}</p>
                </Link>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section id="graph" className="relative z-10 border-y border-line bg-panel/40">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-24 sm:px-6 lg:grid-cols-2">
          <Reveal>
            <p className="eyebrow">How the graph does the work</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight">Delete an edge and the answer changes.</h2>
            <p className="mt-4 leading-7 text-muted">
              FalkorDB isn&apos;t a picture of the memory. It is the memory. As-of retrieval needs the{" "}
              <span className="mono text-ink">SUPPORTED_BY</span> edge, and status comes from{" "}
              <span className="mono text-ink">SUPERSEDES</span> and <span className="mono text-ink">CONFLICTS_WITH</span>{" "}
              edges visible at the cutoff.
            </p>
            <ul className="mt-6 space-y-3 text-sm">
              {[
                ["Remove SUPPORTED_BY", "region-b is no longer a source-backed answer."],
                ["Remove SUPERSEDES", "both regions stay current, and Faultline refuses to choose."],
                ["Restore both", "the original answer comes back, byte for byte."],
              ].map(([title, body]) => (
                <li key={title} className="flex gap-3">
                  <ShieldCheck className="mt-0.5 size-4 shrink-0 text-ok" />
                  <span>
                    <span className="mono text-ink">{title}</span> <span className="text-muted">— {body}</span>
                  </span>
                </li>
              ))}
            </ul>
            <Link href="/app/bench" className="btn btn-fault mt-8">
              Run the ablation live <ArrowRight className="size-4" />
            </Link>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="overflow-hidden rounded-2xl border border-line2 bg-[#09090c]">
              <div className="mono border-b border-line px-4 py-2.5 text-[11px] text-dim">as_of_retrieval.cypher</div>
              <pre className="mono overflow-x-auto p-5 text-[12px] leading-6 text-muted">
                {CYPHER.split("\n").map((line) => (
                  <div key={line}>
                    {line.split(/(MATCH|WHERE|RETURN|AS)/).map((part, index) =>
                      ["MATCH", "WHERE", "RETURN", "AS"].includes(part) ? (
                        <span key={index} className="text-fault">{part}</span>
                      ) : (
                        <span key={index} className={part.includes(":") ? "text-ink" : undefined}>{part}</span>
                      ),
                    )}
                  </div>
                ))}
              </pre>
            </div>
          </Reveal>
        </div>
      </section>

      <section id="bench" className="relative z-10 mx-auto max-w-6xl px-4 py-24 sm:px-6">
        <Reveal className="max-w-2xl">
          <p className="eyebrow">Benchmark</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight">1,213 questions. Same data. Different memory.</h2>
          <p className="mt-4 text-muted">
            400 generated memory stories (corrections, conflicts, unreviewed notes), questions asked before, between and after
            each note. Every method reads the same rows from FalkorDB; only Faultline uses the edges.
          </p>
        </Reveal>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {BENCH.map((row, index) => {
            const hero = row.method === "Faultline";
            return (
              <Reveal key={row.method} delay={index * 0.08}>
                <div
                  className={`h-full rounded-xl border p-5 ${
                    hero ? "border-fault/40 bg-fault/[0.05] shadow-[0_0_60px_-20px_rgba(245,158,11,0.5)]" : "border-line bg-panel/70"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-medium">{row.method}</h3>
                    {hero ? <ChartColumn className="size-4 text-fault" /> : null}
                  </div>
                  <p className="text-[11px] text-dim">{row.note}</p>
                  <p className="mt-5 text-5xl font-semibold tracking-tight">
                    {((row.correct / BENCH_TOTAL) * 100).toFixed(1)}
                    <span className="text-2xl text-dim">%</span>
                  </p>
                  <p className="mono text-xs text-dim">
                    {row.correct.toLocaleString()} / {BENCH_TOTAL.toLocaleString()} correct
                  </p>
                  <dl className="mono mt-5 grid grid-cols-3 gap-2 text-[11px]">
                    <div>
                      <dt className="text-dim">future values</dt>
                      <dd className={row.wrongTime ? "text-disputed" : "text-ink"}>{row.wrongTime}</dd>
                    </div>
                    <div>
                      <dt className="text-dim">untrusted</dt>
                      <dd className={row.untrusted ? "text-disputed" : "text-ink"}>{row.untrusted}</dd>
                    </div>
                    <div>
                      <dt className="text-dim">conflicts</dt>
                      <dd className={row.conflicts === BENCH_CONFLICTS ? "text-ok" : "text-disputed"}>
                        {row.conflicts}/{BENCH_CONFLICTS}
                      </dd>
                    </div>
                  </dl>
                </div>
              </Reveal>
            );
          })}
        </div>
        <div className="mono mt-6 flex flex-wrap gap-x-6 gap-y-2 text-[11px] text-muted">
          <span>as-of read p50 <span className="text-ink">4.7 ms</span> at 17,100 nodes</span>
          <span>bisect <span className="text-ink">9 probes</span> for 512 notes</span>
          <span>
            gpt-oss-20b: <span className="text-ink">46/50</span> with raw notes, <span className="text-ink">50/50</span> with Faultline
            evidence
          </span>
          <span>memory regression tests in CI on every push</span>
        </div>
        <p className="mt-4 text-xs leading-5 text-dim">
          Synthetic stories, so this shows the memory semantics hold end to end through the graph, not intelligence. A log that
          keeps only reviewed notes ties Faultline on plain corrections. Full results, scale and the LLM run are on the{" "}
          <Link href="/app/bench" className="text-muted underline underline-offset-2 hover:text-ink">
            Bench page
          </Link>
          . Reproduce with <span className="mono">make benchsuite</span>.
        </p>
      </section>

      <section className="relative z-10 mx-auto max-w-6xl px-4 pb-24 sm:px-6">
        <Reveal>
          <div className="relative overflow-hidden rounded-2xl border border-line2 bg-panel px-6 py-14 text-center sm:px-12">
            <div className="glow-fault pointer-events-none absolute inset-0" aria-hidden />
            <h2 className="relative text-3xl font-semibold tracking-tight sm:text-4xl">See why the answer changed.</h2>
            <p className="relative mx-auto mt-4 max-w-xl text-muted">
              Scrub through Project Atlas, replay a question across snapshots, and hand the task to another agent with the dispute intact.
            </p>
            <div className="relative mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/app/timeline" className="btn btn-primary !px-5 !py-2.5">
                Open live demo <ArrowRight className="size-4" />
              </Link>
              <a href={GITHUB_URL} className="btn btn-ghost !px-5 !py-2.5">
                <GithubMark /> maannaan/faultline
              </a>
            </div>
          </div>
        </Reveal>
      </section>

      <footer className="relative z-10 border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-8 text-xs text-dim sm:px-6">
          <span className="flex items-center gap-2">
            <Logo className="size-5" /> Faultline
          </span>
          <span>Graph Hacks 2026 · Track 02: Agent Memory and Coordination</span>
          <span className="sm:ml-auto">Synthetic data only. Powered by FalkorDB.</span>
        </div>
      </footer>
    </div>
  );
}
