/* The evidence graph assembles node by node on the beat, then a correction and a dispute land as edges. */
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, MONO } from "../lib/theme";
import { Background, Words } from "../lib/ui";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

type Node = { id: string; kind: string; x: number; y: number; at: number };

const NODES: Node[] = [
  { id: "agent-planner", kind: "Agent", x: 230, y: 420, at: 6 },
  { id: "session-01", kind: "Session", x: 560, y: 420, at: 18 },
  { id: "evt-…", kind: "MemoryEvent", x: 890, y: 420, at: 30 },
  { id: "region-a", kind: "Assertion", x: 1260, y: 230, at: 42 },
  { id: "region-b", kind: "Assertion", x: 1260, y: 470, at: 54 },
  { id: "source-design-001", kind: "Source", x: 1660, y: 230, at: 66 },
  { id: "source-change-002", kind: "Source", x: 1660, y: 470, at: 78 },
  { id: "on-call: Priya", kind: "Assertion", x: 1080, y: 720, at: 90 },
  { id: "on-call: Jordan", kind: "Assertion", x: 1500, y: 720, at: 102 },
];

const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));

const EDGES: [string, string, string][] = [
  ["agent-planner", "session-01", "RAN"],
  ["session-01", "evt-…", "EMITTED"],
  ["evt-…", "region-a", "ASSERTED"],
  ["evt-…", "region-b", "ASSERTED"],
  ["region-a", "source-design-001", "SUPPORTED_BY"],
  ["region-b", "source-change-002", "SUPPORTED_BY"],
  ["evt-…", "on-call: Priya", "ASSERTED"],
  ["evt-…", "on-call: Jordan", "ASSERTED"],
];

const SUPERSEDES_AT = 170;
const CONFLICT_AT = 225;

export function Graph() {
  const frame = useCurrentFrame();
  const zoom = interpolate(frame, [0, 360], [0.94, 1.03]);
  const panX = interpolate(frame, [SUPERSEDES_AT - 10, SUPERSEDES_AT + 40], [0, -30], {
    ...clamp,
    easing: (t) => t * t * (3 - 2 * t),
  });
  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill style={{ transform: `scale(${zoom}) translateX(${panX}px)` }}>
        <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
          {EDGES.map(([from, to, label]) => (
            <Edge key={from + to} from={byId[from]} to={byId[to]} label={label} />
          ))}
          <Edge
            from={byId["region-b"]}
            to={byId["region-a"]}
            label="SUPERSEDES"
            color={C.fault}
            start={SUPERSEDES_AT}
            width={5}
            bend={-150}
          />
          <Edge
            from={byId["on-call: Priya"]}
            to={byId["on-call: Jordan"]}
            label="CONFLICTS_WITH"
            color={C.disputed}
            start={CONFLICT_AT}
            width={4}
            dashed
          />
        </svg>
        {NODES.map((node) => (
          <NodeCard key={node.id} node={node} />
        ))}
      </AbsoluteFill>
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 90 }}>
        {frame < SUPERSEDES_AT - 15 ? (
          <Words text="Every fact keeps its source and its time." delay={110} style={{ fontSize: 56, fontWeight: 600 }} />
        ) : (
          <Words
            text="Corrections and conflicts are edges. Nothing is overwritten."
            delay={SUPERSEDES_AT - 10}
            accent={["edges", "overwritten"]}
            style={{ fontSize: 56, fontWeight: 600 }}
          />
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

function statusOf(id: string, frame: number) {
  if (id === "region-a" && frame >= SUPERSEDES_AT + 12) return { color: C.superseded, label: "superseded" };
  if (id === "region-a" || id === "region-b") return { color: C.ok, label: "current" };
  if (id.startsWith("on-call") && frame >= CONFLICT_AT + 10) return { color: C.disputed, label: "disputed" };
  if (id.startsWith("on-call")) return { color: C.ok, label: "current" };
  return null;
}

function NodeCard({ node }: { node: Node }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - node.at, fps, config: { damping: 12, stiffness: 200 } });
  const status = statusOf(node.id, frame);
  const fresh = interpolate(frame, [SUPERSEDES_AT + 12, SUPERSEDES_AT + 30], [1, 0], clamp);
  const greyed = node.id === "region-a" && frame >= SUPERSEDES_AT + 12;
  return (
    <div
      style={{
        position: "absolute",
        left: node.x,
        top: node.y,
        transform: `translate(-50%, -50%) scale(${s})`,
        opacity: greyed ? 0.55 + fresh * 0.45 : 1,
        padding: "16px 22px",
        minWidth: 230,
        borderRadius: 16,
        border: `1.5px solid ${status ? `${status.color}88` : C.line2}`,
        background: C.panel,
        boxShadow: status ? `0 0 40px ${status.color}22` : "0 20px 50px rgba(0,0,0,0.5)",
        fontFamily: MONO,
      }}
    >
      <div style={{ fontSize: 17, color: C.dim, letterSpacing: 1, textTransform: "uppercase" }}>{node.kind}</div>
      <div style={{ fontSize: 28, color: greyed ? C.superseded : C.ink, textDecoration: greyed ? "line-through" : "none" }}>
        {node.id}
      </div>
      {status ? (
        <div style={{ marginTop: 8, fontSize: 18, color: status.color }}>● {status.label}</div>
      ) : null}
    </div>
  );
}

function Edge({
  from,
  to,
  label,
  color = "rgba(255,255,255,0.22)",
  start,
  width = 2,
  dashed = false,
  bend = 0,
}: {
  from: Node;
  to: Node;
  label: string;
  color?: string;
  start?: number;
  width?: number;
  dashed?: boolean;
  bend?: number;
}) {
  const frame = useCurrentFrame();
  const begin = start ?? Math.max(from.at, to.at) + 6;
  const p = interpolate(frame, [begin, begin + 18], [0, 1], { ...clamp, easing: (t) => 1 - (1 - t) ** 3 });
  if (p <= 0) return null;
  const mx = (from.x + to.x) / 2 + bend;
  const my = (from.y + to.y) / 2;
  const d = `M${from.x} ${from.y} Q${mx} ${my} ${to.x} ${to.y}`;
  const strong = start !== undefined;
  const pulse = strong ? 0.6 + Math.sin(frame / 5) * 0.4 : 1;
  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth={width}
        pathLength={1}
        strokeDasharray={dashed ? "0.02 0.015" : 1}
        strokeDashoffset={dashed ? 0 : 1 - p}
        opacity={dashed ? p * pulse : 1}
        style={strong ? { filter: `drop-shadow(0 0 12px ${color})` } : undefined}
      />
      {strong ? (
        <text
          x={mx - bend / 2}
          y={my - 14}
          textAnchor="middle"
          fill={color}
          fontFamily={MONO}
          fontSize={24}
          opacity={interpolate(p, [0.6, 1], [0, 1], clamp)}
        >
          {label}
        </text>
      ) : null}
    </g>
  );
}
