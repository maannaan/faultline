"use client";

import {
  Activity,
  ChartColumn,
  Clock,
  GitBranch,
  GitCompareArrows,
  GitPullRequestArrow,
  Radar,
  Search,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { GithubMark, Logo } from "./logo";

export const NAV = [
  { href: "/app/timeline", label: "Timeline", verb: "checkout", icon: Clock },
  { href: "/app/replay", label: "Replay / Diff", verb: "diff", icon: GitCompareArrows },
  { href: "/app/blame", label: "Blame", verb: "blame", icon: Search },
  { href: "/app/bisect", label: "Bisect", verb: "bisect", icon: GitBranch },
  { href: "/app/impact", label: "Impact", verb: "impact", icon: Radar },
  { href: "/app/handoff", label: "Handoff", verb: "handoff", icon: GitPullRequestArrow },
  { href: "/app/bench", label: "Bench", verb: "test", icon: ChartColumn },
] as const;

export const GITHUB_URL = "https://github.com/maannaan/faultline";

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-panel/60 px-3 py-4 lg:flex">
      <Link href="/" className="flex items-center gap-2 px-2 py-1">
        <Logo />
        <span className="text-[15px] font-semibold tracking-tight">Faultline</span>
      </Link>
      <p className="mono mt-6 px-2 text-[10px] tracking-[0.18em] text-dim uppercase">Memory tools</p>
      <nav className="mt-2 flex flex-col gap-0.5">
        {NAV.map((item) => {
          const active = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition ${
                active ? "bg-white/[0.07] text-ink" : "text-muted hover:bg-white/[0.04] hover:text-ink"
              }`}
            >
              <Icon className={`size-4 ${active ? "text-fault" : "text-dim group-hover:text-muted"}`} />
              <span className="flex-1">{item.label}</span>
              <span className="mono text-[10px] text-dim">{item.verb}</span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto space-y-3 px-2">
        <div className="rounded-lg border border-line bg-black/30 p-3">
          <p className="mono text-[10px] tracking-[0.16em] text-dim uppercase">Tenant</p>
          <p className="mono mt-1 text-xs text-ink">tenant-synthetic</p>
          <p className="mt-1 text-[11px] leading-4 text-dim">Synthetic Project Atlas data. One FalkorDB graph per tenant.</p>
        </div>
        <a href={GITHUB_URL} className="flex items-center gap-2 text-xs text-dim hover:text-ink">
          <GithubMark className="size-3.5" /> maannaan/faultline
        </a>
      </div>
    </aside>
  );
}

export function TopBar() {
  const pathname = usePathname();
  const current = NAV.find((item) => pathname.startsWith(item.href));
  return (
    <div className="sticky top-0 z-20 border-b border-line bg-bg/80 backdrop-blur-md">
      <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 lg:hidden">
          <Logo />
        </Link>
        <div className="mono flex min-w-0 items-center gap-2 text-xs text-dim">
          <span className="hidden sm:inline">faultline</span>
          <span className="hidden sm:inline">/</span>
          <span className="truncate text-ink">{current ? `${current.verb}` : "app"}</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <HealthPill />
          <a href={GITHUB_URL} className="btn btn-ghost hidden !px-2.5 !py-1.5 sm:inline-flex" aria-label="GitHub repository">
            <GithubMark className="size-4" />
          </a>
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-3 pb-2 lg:hidden" aria-label="Sections">
        {NAV.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`shrink-0 rounded-md px-2.5 py-1 text-xs ${
                active ? "bg-white/[0.08] text-ink" : "text-muted"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function HealthPill() {
  const [state, setState] = useState<"checking" | "ok" | "down">("checking");
  useEffect(() => {
    let alive = true;
    async function check() {
      try {
        const response = await fetch("/api/faultline/health/ready", { cache: "no-store" });
        if (alive) setState(response.ok ? "ok" : "down");
      } catch {
        if (alive) setState("down");
      }
    }
    check();
    const timer = setInterval(check, 15000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);
  const tone =
    state === "ok"
      ? "border-ok/30 text-ok"
      : state === "down"
        ? "border-disputed/30 text-disputed"
        : "border-line2 text-dim";
  return (
    <span className={`pill ${tone} bg-white/[0.02]`}>
      <Activity className="size-3" />
      {state === "ok" ? "FalkorDB connected" : state === "down" ? "Graph unavailable" : "Checking graph"}
    </span>
  );
}
