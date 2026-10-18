"use client";

import {
  BaseEdge,
  type Edge,
  EdgeLabelRenderer,
  type EdgeProps,
  Handle,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  Controls,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Bot, Box, Diamond, FileText, MessagesSquare, Pause, Play, RotateCcw, X, Zap } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EvidencePath, GraphEdge, GraphNode, GraphView } from "@/lib/types";
import { formatTime, KeyValue, StatusPill, statusTone } from "./ui";

type Props = {
  entityId: string;
  /** "scrub" loads every recorded moment and adds a time slider. "fixed" shows one cutoff. */
  mode?: "scrub" | "fixed";
  asOf?: string;
  excludeSourceIds?: string[];
  highlightIds?: string[];
  height?: number;
  title?: string;
};

type FlowData = { node: GraphNode; highlighted: boolean };
type FlowNode = Node<FlowData, "fl">;
type ArcData = { kind: string; visible: boolean };
type FlowEdge = Edge<ArcData>;

const COLUMN_X: Record<GraphNode["kind"], number> = {
  agent: 0,
  session: 0,
  event: 250,
  assertion: 500,
  source: 880,
  entity: 1170,
};
const ROW = 96;
const GROUP_GAP = 36;

const TONE_COLOR: Record<string, string> = {
  current: "#34d399",
  superseded: "#8b8b94",
  disputed: "#fb7185",
  unverified: "#facc15",
  neutral: "#71717a",
};

export function EvidenceGraph({
  entityId,
  mode = "scrub",
  asOf,
  excludeSourceIds = [],
  highlightIds = [],
  height = 500,
  title = "Evidence graph",
}: Props) {
  const [frames, setFrames] = useState<GraphView[]>([]);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const excludeKey = excludeSourceIds.join(",");

  useEffect(() => {
    let alive = true;
    setError(null);
    async function load() {
      try {
        if (mode === "fixed") {
          const view = await fetchView(entityId, asOf, excludeKey);
          if (!alive) return;
          setFrames([view]);
          setFrameIndex(0);
          return;
        }
        const now = await fetchView(entityId, undefined, excludeKey);
        const cutoffs = [
          shiftMinutes(now.moments[0] ?? now.as_of, -60),
          ...now.moments,
        ];
        const views = await Promise.all(cutoffs.map((cutoff) => fetchView(entityId, cutoff, excludeKey)));
        if (!alive) return;
        const all = [...views, now];
        setFrames(all);
        setFrameIndex(all.length - 1);
      } catch (caught) {
        if (alive) setError(caught instanceof Error ? caught.message : "The graph could not be loaded.");
      }
    }
    if (entityId) load();
    return () => {
      alive = false;
    };
  }, [entityId, mode, asOf, excludeKey]);

  useEffect(() => {
    if (!playing) return;
    if (frameIndex >= frames.length - 1) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => setFrameIndex((index) => index + 1), 1500);
    return () => clearTimeout(timer);
  }, [playing, frameIndex, frames.length]);

  const view = frames[frameIndex] ?? null;
  const positions = useMemo(() => layout(frames[frames.length - 1] ?? null), [frames]);
  const highlightKey = highlightIds.join(",");

  const nodes: FlowNode[] = useMemo(() => {
    if (!view) return [];
    const highlights = new Set(highlightKey ? highlightKey.split(",") : []);
    return view.nodes.map((node) => ({
      id: node.id,
      type: "fl",
      position: positions.get(node.id) ?? { x: 0, y: 0 },
      data: { node, highlighted: highlights.has(node.id) },
      draggable: false,
    }));
  }, [view, positions, highlightKey]);

  const edges: FlowEdge[] = useMemo(() => (view ? view.edges.map(toFlowEdge) : []), [view]);

  const onNodeClick = useCallback((_: unknown, node: FlowNode) => setSelected(node.data.node), []);

  function play() {
    if (frameIndex >= frames.length - 1) setFrameIndex(0);
    setPlaying(true);
  }

  const counts = useMemo(() => summarize(view), [view]);

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-medium">{title}</h2>
          {view ? (
            <span className="mono text-[11px] text-dim">
              as of <span className="text-ink">{formatTime(view.as_of)}</span> · {view.time_mode}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {counts.map(([tone, count]) => (
            <span key={tone} className={`pill pill-${tone}`}>
              {count} {tone}
            </span>
          ))}
        </div>
      </div>

      <div className="relative grid-bg" style={{ height }}>
        {error ? (
          <div className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-disputed">{error}</div>
        ) : !view ? (
          <div className="absolute inset-0 grid place-items-center">
            <span className="mono animate-pulse text-xs text-dim">Querying FalkorDB…</span>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            edgeTypes={EDGE_TYPES}
            onNodeClick={onNodeClick}
            fitView
            fitViewOptions={{ padding: 0.12 }}
            minZoom={0.3}
            maxZoom={1.6}
            nodesConnectable={false}
            nodesDraggable={false}
            zoomOnScroll={false}
            preventScrolling={false}
            proOptions={{ hideAttribution: true }}
          >
            <Controls showInteractive={false} position="bottom-right" />
          </ReactFlow>
        )}
        <AnimatePresence>
          {selected ? <NodeSheet node={selected} onClose={() => setSelected(null)} /> : null}
        </AnimatePresence>
      </div>

      {mode === "scrub" && frames.length > 1 ? (
        <Scrubber
          frames={frames}
          index={frameIndex}
          playing={playing}
          onChange={(index) => {
            setPlaying(false);
            setFrameIndex(index);
          }}
          onPlay={play}
          onPause={() => setPlaying(false)}
        />
      ) : null}
      <Legend />
    </section>
  );
}

function Scrubber({
  frames,
  index,
  playing,
  onChange,
  onPlay,
  onPause,
}: {
  frames: GraphView[];
  index: number;
  playing: boolean;
  onChange: (index: number) => void;
  onPlay: () => void;
  onPause: () => void;
}) {
  const last = frames.length - 1;
  return (
    <div className="flex flex-col gap-3 border-t border-line px-4 py-3 sm:flex-row sm:items-center sm:px-5">
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="btn btn-primary !px-2.5 !py-1.5"
          onClick={playing ? onPause : onPlay}
          aria-label={playing ? "Pause time travel" : "Play time travel"}
        >
          {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
          <span className="text-xs">{playing ? "Pause" : "Replay history"}</span>
        </button>
        <button
          type="button"
          className="btn btn-ghost !px-2 !py-1.5"
          onClick={() => onChange(last)}
          aria-label="Jump to now"
        >
          <RotateCcw className="size-3.5" />
        </button>
      </div>
      <div className="min-w-0 flex-1">
        <input
          type="range"
          min={0}
          max={last}
          step={1}
          value={index}
          onChange={(event) => onChange(Number(event.target.value))}
          className="w-full accent-[#f59e0b]"
          aria-label="Memory cutoff"
        />
        <div className="mono mt-1 flex justify-between gap-2 text-[10px] text-dim">
          {frames.map((frame, frameIndex) => (
            <button
              key={`${frame.as_of}-${frameIndex}`}
              type="button"
              onClick={() => onChange(frameIndex)}
              className={`truncate ${frameIndex === index ? "text-fault" : "hover:text-muted"}`}
            >
              {frameIndex === 0 ? "before" : frameIndex === last ? "now" : formatTime(frame.as_of).replace(" UTC", "")}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Legend() {
  const items: Array<[string, string]> = [
    ["current", "current"],
    ["superseded", "superseded"],
    ["disputed", "disputed"],
    ["unverified", "unverified"],
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line px-4 py-2.5 text-[11px] text-dim sm:px-5">
      {items.map(([tone, label]) => (
        <span key={tone} className="flex items-center gap-1.5">
          <span className="size-2 rounded-full" style={{ background: TONE_COLOR[tone] }} />
          {label}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <svg width="22" height="6" aria-hidden>
          <line x1="0" y1="3" x2="22" y2="3" stroke="#f59e0b" strokeWidth="2" strokeDasharray="5 4" />
        </svg>
        SUPERSEDES
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="22" height="6" aria-hidden>
          <line x1="0" y1="3" x2="22" y2="3" stroke="#fb7185" strokeWidth="2" strokeDasharray="2 4" />
        </svg>
        CONFLICTS_WITH
      </span>
      <span className="ml-auto hidden sm:inline">Click a node to trace its evidence</span>
    </div>
  );
}

const KIND_ICON = {
  entity: Box,
  assertion: Diamond,
  source: FileText,
  event: Zap,
  session: MessagesSquare,
  agent: Bot,
} as const;

function FaultNode({ data }: NodeProps<FlowNode>) {
  const { node, highlighted } = data;
  const Icon = KIND_ICON[node.kind];
  const tone = node.kind === "assertion" ? statusTone(node.status) : "neutral";
  const color = TONE_COLOR[tone];
  const isAssertion = node.kind === "assertion";
  const isEntity = node.kind === "entity";
  return (
    <div
      className="transition-all duration-700 ease-out"
      style={{
        opacity: node.visible ? (node.excluded ? 0.35 : 1) : 0.07,
        transform: node.visible ? "scale(1)" : "scale(0.94)",
        filter: node.visible ? "none" : "grayscale(1)",
      }}
    >
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
      <Handle type="source" position={Position.Right} id="arc-s" style={{ top: "30%" }} />
      <Handle type="target" position={Position.Right} id="arc-t" style={{ top: "70%" }} />
      <div
        className={`relative rounded-xl border bg-[#101014]/95 px-3 py-2.5 shadow-[0_8px_30px_rgba(0,0,0,0.35)] transition-colors duration-700 ${
          isAssertion ? "w-[230px]" : isEntity ? "w-[170px]" : "w-[190px]"
        } ${highlighted ? "ring-2 ring-fault/70" : ""} ${node.excluded ? "border-dashed" : ""}`}
        style={{
          borderColor: isAssertion && node.visible ? `${color}66` : "rgb(255 255 255 / 0.1)",
          boxShadow: isAssertion && node.visible && tone !== "superseded" ? `0 0 28px -8px ${color}88` : undefined,
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="grid size-6 shrink-0 place-items-center rounded-md border border-white/10 bg-white/[0.04]"
            style={{ color: isAssertion ? color : isEntity ? "#f59e0b" : "#a1a1aa" }}
          >
            <Icon className="size-3.5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className={`truncate text-[12px] font-medium ${tone === "superseded" ? "text-muted line-through decoration-white/30" : "text-ink"}`}>
              {node.label}
            </p>
            <p className="mono truncate text-[10px] text-dim">{node.sublabel}</p>
          </div>
        </div>
        {isAssertion ? (
          <div className="mt-2 flex items-center justify-between gap-2">
            {node.visible ? <StatusPill status={node.status} /> : <span className="pill pill-neutral">not yet known</span>}
            <span className="mono text-[10px] text-dim">{formatTime(node.observed_at).replace(" UTC", "")}</span>
          </div>
        ) : null}
        {node.excluded ? <p className="mono mt-1.5 text-[10px] text-unverified">excluded from snapshot</p> : null}
      </div>
    </div>
  );
}

function ArcEdge({ id, sourceX, sourceY, targetX, targetY, data }: EdgeProps<FlowEdge>) {
  const conflict = data?.kind === "CONFLICTS_WITH";
  const bulge = 74;
  const path = `M ${sourceX} ${sourceY} C ${sourceX + bulge} ${sourceY}, ${targetX + bulge} ${targetY}, ${targetX} ${targetY}`;
  const labelX = Math.max(sourceX, targetX) + bulge * 0.78;
  const labelY = (sourceY + targetY) / 2;
  const color = conflict ? "#fb7185" : "#f59e0b";
  const visible = data?.visible ?? false;
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        className={visible ? (conflict ? "edge-conflict" : "edge-supersedes") : ""}
        style={{ stroke: color, strokeWidth: 2, opacity: visible ? 1 : 0.06, transition: "opacity 0.7s" }}
        markerEnd={conflict ? undefined : "url(#fl-arrow)"}
      />
      <EdgeLabelRenderer>
        <div
          className="mono pointer-events-none absolute rounded-md border px-1.5 py-0.5 text-[9px] font-medium tracking-wide transition-opacity duration-700"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            opacity: visible ? 1 : 0,
            color,
            borderColor: `${color}55`,
            background: "#0b0b0e",
          }}
        >
          {conflict ? "CONFLICTS_WITH" : "SUPERSEDES"}
        </div>
      </EdgeLabelRenderer>
      <svg width="0" height="0" aria-hidden>
        <defs>
          <marker id="fl-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
          </marker>
        </defs>
      </svg>
    </>
  );
}

const NODE_TYPES = { fl: FaultNode };
const EDGE_TYPES = { arc: ArcEdge };

function toFlowEdge(edge: GraphEdge): FlowEdge {
  if (edge.type === "SUPERSEDES" || edge.type === "CONFLICTS_WITH") {
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: "arc-s",
      targetHandle: "arc-t",
      type: "arc",
      data: { kind: edge.type, visible: edge.visible },
      zIndex: 5,
    };
  }
  const strong = edge.type === "SUPPORTED_BY" || edge.type === "CREATED_ASSERTION";
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: "out",
    targetHandle: "in",
    animated: edge.visible && edge.type === "SUPPORTED_BY",
    label: edge.visible && strong ? edge.type : undefined,
    labelStyle: { fill: "#71717a", fontSize: 9, fontFamily: "var(--font-geist-mono)" },
    labelBgStyle: { fill: "#0b0b0e" },
    labelBgPadding: [4, 2],
    style: {
      stroke: strong ? "rgb(255 255 255 / 0.32)" : "rgb(255 255 255 / 0.14)",
      strokeWidth: strong ? 1.5 : 1,
      opacity: edge.visible ? 1 : 0.05,
      transition: "opacity 0.7s",
    },
  };
}

function layout(view: GraphView | null): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  if (!view) return positions;
  const assertions = view.nodes
    .filter((node) => node.kind === "assertion")
    .sort((a, b) => (a.observed_at ?? "").localeCompare(b.observed_at ?? ""));
  const predicateOrder: string[] = [];
  for (const node of assertions) {
    const predicate = node.label.split(" = ")[0];
    if (!predicateOrder.includes(predicate)) predicateOrder.push(predicate);
  }
  const ordered = predicateOrder.flatMap((predicate) =>
    assertions.filter((node) => node.label.split(" = ")[0] === predicate),
  );
  const rowY = new Map<string, number>();
  let y = 0;
  let lastPredicate = "";
  for (const node of ordered) {
    const predicate = node.label.split(" = ")[0];
    if (lastPredicate && predicate !== lastPredicate) y += GROUP_GAP;
    rowY.set(node.id, y);
    positions.set(node.id, { x: COLUMN_X.assertion, y });
    y += ROW;
    lastPredicate = predicate;
  }
  const height = Math.max(y - ROW, 0);
  const center = height / 2;
  for (const edge of view.edges) {
    if (edge.type === "CREATED_ASSERTION" && rowY.has(edge.target) && !positions.has(edge.source)) {
      positions.set(edge.source, { x: COLUMN_X.event, y: rowY.get(edge.target)! + 6 });
    }
    if (edge.type === "SUPPORTED_BY" && rowY.has(edge.source) && !positions.has(edge.target)) {
      positions.set(edge.target, { x: COLUMN_X.source, y: rowY.get(edge.source)! + 6 });
    }
  }
  const actors = view.nodes.filter((node) => node.kind === "agent" || node.kind === "session");
  actors.forEach((node, index) => {
    const offset = (index - (actors.length - 1) / 2) * 110;
    positions.set(node.id, { x: COLUMN_X[node.kind], y: center + offset });
  });
  for (const node of view.nodes) {
    if (node.kind === "entity") positions.set(node.id, { x: COLUMN_X.entity, y: center });
    if (!positions.has(node.id)) positions.set(node.id, { x: COLUMN_X[node.kind], y: height + ROW });
  }
  return positions;
}

function summarize(view: GraphView | null): Array<[string, number]> {
  if (!view) return [];
  const counts = new Map<string, number>();
  for (const node of view.nodes) {
    if (node.kind !== "assertion" || !node.visible) continue;
    const tone = statusTone(node.status);
    counts.set(tone, (counts.get(tone) ?? 0) + 1);
  }
  return ["current", "superseded", "disputed", "unverified"]
    .filter((tone) => counts.has(tone))
    .map((tone) => [tone, counts.get(tone)!]);
}

function NodeSheet({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  const [evidence, setEvidence] = useState<EvidencePath | null>(null);
  const [failed, setFailed] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    setEvidence(null);
    setFailed(false);
    if (node.kind !== "assertion") return;
    let alive = true;
    fetch(`/api/faultline/v1/assertions/${encodeURIComponent(node.id)}/evidence`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const body = (await response.json()) as EvidencePath;
        if (alive) setEvidence(body);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [node]);

  return (
    <motion.aside
      initial={{ x: 24, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 24, opacity: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className="absolute top-3 right-3 bottom-3 z-10 w-[min(340px,calc(100%-24px))] overflow-y-auto rounded-xl border border-line2 bg-[#0c0c0f]/95 p-4 shadow-2xl backdrop-blur"
      aria-label={`Details for ${node.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="eyebrow">{node.kind}</p>
          <p className="mt-1.5 text-sm font-medium break-words">{node.label}</p>
        </div>
        <button ref={closeRef} type="button" onClick={onClose} className="btn btn-ghost !p-1.5" aria-label="Close details">
          <X className="size-4" />
        </button>
      </div>
      {node.kind === "assertion" ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {node.visible ? <StatusPill status={node.status} prefix="at cutoff" /> : <span className="pill pill-neutral">not yet known at cutoff</span>}
          <StatusPill status={node.status_now} prefix="now" />
        </div>
      ) : null}
      <div className="mt-4">
        <KeyValue
          rows={[
            ["Id", node.id],
            ["Observed", formatTime(node.observed_at)],
            ...(node.kind === "assertion"
              ? ([
                  ["Source", evidence?.source_id ?? (failed ? "unavailable" : "…")],
                  ["Event", evidence?.event_id ?? (failed ? "unavailable" : "…")],
                  ["Session", evidence?.session_id ?? "—"],
                  ["Supersedes", evidence ? evidence.supersedes_ids.join(", ") || "—" : "…"],
                  ["Conflicts", evidence ? evidence.conflicts_with_ids.join(", ") || "—" : "…"],
                ] as Array<[string, string]>)
              : ([["Detail", node.sublabel || "—"]] as Array<[string, string]>)),
          ]}
        />
      </div>
      {node.kind === "assertion" ? (
        <p className="mt-4 text-xs leading-5 text-dim">
          Path: <span className="mono text-muted">MemoryEvent → Assertion → Source</span>. The status at the cutoff is computed from
          edges visible at that time; the node&apos;s stored status is never rewritten.
        </p>
      ) : null}
    </motion.aside>
  );
}

async function fetchView(entityId: string, asOf: string | undefined, exclude: string): Promise<GraphView> {
  const params = new URLSearchParams({ entity_id: entityId, time_mode: "known" });
  if (asOf) params.set("as_of", asOf);
  if (exclude) params.set("exclude_source_ids", exclude);
  const response = await fetch(`/api/faultline/v1/graph?${params.toString()}`, { cache: "no-store" });
  const body = (await response.json()) as GraphView & { error?: { message?: string } };
  if (!response.ok) throw new Error(body.error?.message || "The graph could not be loaded.");
  return body;
}

function shiftMinutes(iso: string, minutes: number): string {
  return new Date(new Date(iso).getTime() + minutes * 60000).toISOString();
}
