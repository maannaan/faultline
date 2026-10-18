"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

/**
 * A looping, illustrative replay of the seeded Project Atlas story:
 * region-a is current, a reviewed correction arrives, SUPERSEDES is drawn,
 * then two equally trusted on-call sources disagree and stay disputed.
 */
const STEPS = [
  { at: "15 Oct 09:00", caption: "Design note records deploy_region = region-a" },
  { at: "16 Oct 10:00", caption: "A reviewed change record corrects it to region-b" },
  { at: "16 Oct 10:00", caption: "SUPERSEDES edge: region-b replaces region-a" },
  { at: "16 Oct 12:00", caption: "Two reviewed sources disagree on on-call. Faultline refuses to pick." },
] as const;

export function HeroGraph() {
  const reduce = useReducedMotion();
  const [step, setStep] = useState(reduce ? 3 : 0);

  useEffect(() => {
    if (reduce) return;
    const timer = setInterval(() => setStep((value) => (value + 1) % STEPS.length), 2400);
    return () => clearInterval(timer);
  }, [reduce]);

  const regionB = step >= 1;
  const supersedes = step >= 2;
  const dispute = step >= 3;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-line2 bg-[#0b0b0e] shadow-[0_30px_120px_-30px_rgba(245,158,11,0.25)]">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-white/10" />
        <span className="size-2.5 rounded-full bg-white/10" />
        <span className="size-2.5 rounded-full bg-white/10" />
        <span className="mono ml-2 text-[11px] text-dim">faultline · project-atlas</span>
        <span className="mono ml-auto rounded border border-line px-1.5 py-0.5 text-[10px] text-fault">
          as of {STEPS[step].at}
        </span>
      </div>
      <div className="grid-bg relative">
        <svg viewBox="0 0 560 300" className="block w-full" role="img" aria-label="Animated memory graph">
          <defs>
            <marker id="hero-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0 0L10 5L0 10z" fill="#f59e0b" />
            </marker>
          </defs>

          {/* Source edges */}
          <Edge d="M150 70 L250 70" show />
          <Edge d="M150 150 L250 150" show={regionB} />
          <Edge d="M150 225 L250 225" show={dispute} />
          <Edge d="M150 275 L250 275" show={dispute} />

          {/* Entity edges */}
          <Edge d="M410 70 C460 70 460 150 490 150" show faint />
          <Edge d="M410 150 L490 150" show={regionB} faint />
          <Edge d="M410 225 C460 225 460 150 490 150" show={dispute} faint />
          <Edge d="M410 275 C460 275 460 150 490 150" show={dispute} faint />

          {/* SUPERSEDES arc */}
          <motion.path
            d="M410 140 C440 120 440 95 410 80"
            fill="none"
            stroke="#f59e0b"
            strokeWidth="2"
            strokeDasharray="5 5"
            markerEnd="url(#hero-arrow)"
            initial={false}
            animate={{ pathLength: supersedes ? 1 : 0, opacity: supersedes ? 1 : 0 }}
            transition={{ duration: 0.8, ease: "easeInOut" }}
          />
          <motion.text
            x="446"
            y="113"
            className="mono"
            fontSize="9"
            fill="#f59e0b"
            initial={false}
            animate={{ opacity: supersedes ? 1 : 0 }}
          >
            SUPERSEDES
          </motion.text>

          {/* CONFLICTS_WITH */}
          <motion.path
            d="M410 232 C432 240 432 260 410 268"
            fill="none"
            stroke="#fb7185"
            strokeWidth="2"
            strokeDasharray="2 4"
            initial={false}
            animate={{ opacity: dispute ? [0.5, 1, 0.5] : 0 }}
            transition={{ duration: 1.4, repeat: dispute ? Infinity : 0 }}
          />

          <Chip x={20} y={52} label="source-design-001" show />
          <Chip x={20} y={132} label="source-change-002" show={regionB} />
          <Chip x={20} y={207} label="source-runbook-003" show={dispute} />
          <Chip x={20} y={257} label="source-slack-004" show={dispute} />

          <Fact x={250} y={50} label="region-a" status={supersedes ? "superseded" : "current"} show />
          <Fact x={250} y={130} label="region-b" status="current" show={regionB} />
          <Fact x={250} y={205} label="Priya" status="disputed" show={dispute} />
          <Fact x={250} y={255} label="Jordan" status="disputed" show={dispute} />

          <g>
            <rect x="490" y="132" width="60" height="36" rx="9" fill="#141418" stroke="rgba(245,158,11,0.5)" />
            <text x="520" y="154" textAnchor="middle" fontSize="10" fill="#f4f4f5">Atlas</text>
          </g>
        </svg>
      </div>
      <div className="h-12 border-t border-line px-4 py-3">
        <AnimatePresence mode="wait">
          <motion.p
            key={step}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.25 }}
            className="text-xs text-muted"
          >
            <span className="mono mr-2 text-fault">{String(step + 1).padStart(2, "0")}</span>
            {STEPS[step].caption}
          </motion.p>
        </AnimatePresence>
      </div>
    </div>
  );
}

function Edge({ d, show, faint = false }: { d: string; show: boolean; faint?: boolean }) {
  return (
    <motion.path
      d={d}
      fill="none"
      stroke={faint ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.28)"}
      strokeWidth="1.3"
      initial={false}
      animate={{ pathLength: show ? 1 : 0, opacity: show ? 1 : 0 }}
      transition={{ duration: 0.6 }}
    />
  );
}

function Chip({ x, y, label, show }: { x: number; y: number; label: string; show: boolean }) {
  return (
    <motion.g initial={false} animate={{ opacity: show ? 1 : 0.06 }} transition={{ duration: 0.5 }}>
      <rect x={x} y={y} width="130" height="36" rx="8" fill="#111115" stroke="rgba(255,255,255,0.1)" />
      <text x={x + 12} y={y + 22} fontSize="9.5" fill="#a1a1aa" className="mono">
        {label}
      </text>
    </motion.g>
  );
}

const STATUS_COLOR = { current: "#34d399", superseded: "#8b8b94", disputed: "#fb7185" } as const;

function Fact({
  x,
  y,
  label,
  status,
  show,
}: {
  x: number;
  y: number;
  label: string;
  status: keyof typeof STATUS_COLOR;
  show: boolean;
}) {
  const color = STATUS_COLOR[status];
  return (
    <motion.g initial={false} animate={{ opacity: show ? 1 : 0.06 }} transition={{ duration: 0.5 }}>
      <motion.rect
        x={x}
        y={y}
        width="160"
        height="40"
        rx="10"
        fill="#121216"
        initial={false}
        animate={{ stroke: `${color}99` }}
        transition={{ duration: 0.6 }}
      />
      <text
        x={x + 14}
        y={y + 25}
        fontSize="12"
        fill={status === "superseded" ? "#8b8b94" : "#f4f4f5"}
        textDecoration={status === "superseded" ? "line-through" : undefined}
      >
        {label}
      </text>
      <motion.circle cx={x + 100} cy={y + 20} r="3" initial={false} animate={{ fill: color }} />
      <motion.text x={x + 108} y={y + 23.5} fontSize="9" initial={false} animate={{ fill: color }}>
        {status}
      </motion.text>
    </motion.g>
  );
}
