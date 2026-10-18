"use client";

import { useReducedMotion } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";

const LINES = [
  {
    cmd: "faultline checkout --as-of 2026-10-15T12:00Z",
    out: "deploy_region = region-a   current   ← source-design-001",
    href: "/app/timeline",
  },
  {
    cmd: "faultline diff early late",
    out: "+ assert-region-b   assert-region-a current → superseded (SUPERSEDES)",
    href: "/app/replay",
  },
  {
    cmd: "faultline blame <replay>",
    out: "region-b ← assert-region-b ← source-change-002 ← evt-assert-region-b",
    href: "/app/blame",
  },
  {
    cmd: "faultline bisect --good 10-15 --bad 10-16",
    out: "first bad moment 2026-10-16T10:00Z · culprit source-change-002",
    href: "/app/bisect",
  },
  {
    cmd: "faultline impact assert-region-a",
    out: "snapshots, replays and handoffs that relied on it → flagged stale",
    href: "/app/impact",
  },
  {
    cmd: "faultline test memory-tests.yaml",
    out: "memory regression cases run in CI on every push",
    href: "/app/bench",
  },
] as const;

export function TerminalDemo() {
  const reduce = useReducedMotion();
  const [line, setLine] = useState(reduce ? LINES.length : 0);
  const [chars, setChars] = useState(0);

  useEffect(() => {
    if (reduce || line >= LINES.length) return;
    const target = LINES[line].cmd.length;
    if (chars < target) {
      const timer = setTimeout(() => setChars((value) => value + 1), 22);
      return () => clearTimeout(timer);
    }
    const timer = setTimeout(() => {
      setLine((value) => value + 1);
      setChars(0);
    }, 650);
    return () => clearTimeout(timer);
  }, [line, chars, reduce]);

  return (
    <div className="overflow-hidden rounded-2xl border border-line2 bg-[#09090c]">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-[#ff5f57]/70" />
        <span className="size-2.5 rounded-full bg-[#febc2e]/70" />
        <span className="size-2.5 rounded-full bg-[#28c840]/70" />
        <span className="mono ml-2 text-[11px] text-dim">~/agent-app — faultline</span>
      </div>
      <div className="mono min-h-[300px] space-y-3 p-4 text-[12px] leading-5 sm:p-5 sm:text-[13px]">
        {LINES.map((item, index) => {
          if (index > line) return null;
          const typing = index === line;
          const shown = typing ? item.cmd.slice(0, chars) : item.cmd;
          return (
            <Link key={item.cmd} href={item.href} className="group block rounded-md -mx-2 px-2 py-0.5 hover:bg-white/[0.03]">
              <p className="break-all text-ink">
                <span className="text-fault">$ </span>
                {shown}
                {typing ? <span className="ml-0.5 inline-block h-4 w-2 translate-y-0.5 animate-pulse bg-fault" /> : null}
              </p>
              {!typing ? (
                <p className="break-all text-dim group-hover:text-muted">
                  <span className="text-ok">✓ </span>
                  {item.out}
                </p>
              ) : null}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
