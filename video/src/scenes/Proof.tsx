/* Motion graphics for the hero moments: bisect halving, impact ripple, regression tests. */
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { BEAT, C, MONO } from "../lib/theme";
import { Background, Command, Pill, Words, center } from "../lib/ui";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/* 16 recorded events between "good" (15 Oct) and "bad" (16 Oct); the culprit is index 11. */
const EVENTS = 16;
const CULPRIT = 11;
const STEPS = (() => {
  const ranges: [number, number][] = [[0, EVENTS - 1]];
  let [lo, hi] = [0, EVENTS - 1];
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (CULPRIT <= mid) hi = mid;
    else lo = mid + 1;
    ranges.push([lo, hi]);
  }
  return ranges;
})();

export function BisectGraphic() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const step = Math.min(STEPS.length - 1, Math.max(0, Math.floor((frame - 40) / (BEAT * 2))));
  const [lo, hi] = STEPS[step];
  const found = lo === hi && frame >= 40 + (STEPS.length - 1) * BEAT * 2;
  const foundAt = 40 + (STEPS.length - 1) * BEAT * 2;
  const hit = spring({ frame: frame - foundAt, fps, config: { damping: 10, stiffness: 200 } });
  const width = 1500;
  const cell = width / EVENTS;
  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill style={{ ...center, gap: 70 }}>
        <Command delay={0}>faultline bisect --good 15-Oct --bad 16-Oct</Command>
        <div style={{ position: "relative", width, height: 160 }}>
          <div
            style={{
              position: "absolute",
              left: lo * cell,
              width: (hi - lo + 1) * cell,
              top: 0,
              bottom: 0,
              borderRadius: 14,
              background: found ? `${C.fault}22` : "rgba(255,255,255,0.05)",
              border: `2px solid ${found ? C.fault : C.line2}`,
              transition: "none",
            }}
          />
          {Array.from({ length: EVENTS }, (_, i) => {
            const inside = i >= lo && i <= hi;
            const culprit = found && i === CULPRIT;
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: i * cell + cell / 2 - 5,
                  top: culprit ? 30 - hit * 14 : 40,
                  width: 10,
                  height: culprit ? 100 + hit * 28 : 80,
                  borderRadius: 6,
                  background: culprit ? C.fault : i < CULPRIT ? C.ok : C.disputed,
                  opacity: inside ? 1 : 0.18,
                  boxShadow: culprit ? `0 0 ${30 * hit}px ${C.fault}` : "none",
                }}
              />
            );
          })}
          <div style={{ position: "absolute", left: 0, top: 180, fontFamily: MONO, fontSize: 24, color: C.ok }}>good · 15 Oct</div>
          <div style={{ position: "absolute", right: 0, top: 180, fontFamily: MONO, fontSize: 24, color: C.disputed }}>bad · 16 Oct</div>
        </div>
        <div style={{ fontFamily: MONO, fontSize: 30, color: C.muted, height: 40 }}>
          {found ? (
            <span style={{ color: C.ink }}>
              binary search · log₂ n as-of queries, not n
            </span>
          ) : (
            <span>
              step {step + 1} · checking {hi - lo + 1} events
            </span>
          )}
        </div>
        <div style={{ height: 150, ...center, gap: 12, opacity: hit, transform: `scale(${0.9 + hit * 0.1})` }}>
          <div style={{ fontSize: 72, fontWeight: 700, letterSpacing: -2 }}>
            First bad moment <span style={{ color: C.fault }}>16 Oct · 10:00</span>
          </div>
          <div style={{ fontFamily: MONO, fontSize: 30, color: C.muted }}>culprit source-change-002 · evt-assert-region-b</div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

const RELIED = [
  { kind: "Snapshot", id: "as of 15 Oct", angle: -150 },
  { kind: "Replay", id: "answer: region-a", angle: -60 },
  { kind: "Handoff", id: "rollout checklist", angle: 30 },
  { kind: "Agent run", id: "acted on 15 Oct", angle: 120 },
];

export function ImpactGraphic() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill style={{ ...center }}>
        {[0, 1, 2].map((ring) => {
          const t = ((frame - 10 - ring * 12) % 60) / 60;
          return frame > 10 + ring * 12 ? (
            <div
              key={ring}
              style={{
                position: "absolute",
                width: 200 + t * 900,
                height: 200 + t * 900,
                borderRadius: 9999,
                border: `3px solid ${C.fault}`,
                opacity: (1 - t) * 0.6,
              }}
            />
          ) : null;
        })}
        <div
          style={{
            position: "absolute",
            padding: "20px 30px",
            borderRadius: 18,
            border: `2px solid ${C.superseded}`,
            background: C.panel,
            fontFamily: MONO,
            fontSize: 34,
            color: C.superseded,
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: 18, color: C.dim }}>CORRECTED</div>
          <div style={{ textDecoration: "line-through" }}>region-a</div>
        </div>
        {RELIED.map((item, i) => {
          const at = 22 + i * 10;
          const s = spring({ frame: frame - at, fps, config: { damping: 14 } });
          const stamp = spring({ frame: frame - at - 14, fps, config: { damping: 10, stiffness: 240 } });
          const rad = (item.angle * Math.PI) / 180;
          const r = 400 * s;
          return (
            <div
              key={item.id}
              style={{
                position: "absolute",
                transform: `translate(${Math.cos(rad) * r * 1.3}px, ${Math.sin(rad) * r * 0.8}px)`,
                opacity: s,
              }}
            >
              <div
                style={{
                  padding: "16px 24px",
                  borderRadius: 16,
                  border: `1.5px solid ${C.line2}`,
                  background: C.panel,
                  fontFamily: MONO,
                  position: "relative",
                }}
              >
                <div style={{ fontSize: 17, color: C.dim }}>{item.kind.toUpperCase()}</div>
                <div style={{ fontSize: 28 }}>{item.id}</div>
                <div
                  style={{
                    position: "absolute",
                    right: -30,
                    top: -22,
                    transform: `rotate(-8deg) scale(${interpolate(stamp, [0, 1], [2.2, 1])})`,
                    opacity: stamp,
                  }}
                >
                  <Pill color={C.disputed} style={{ fontSize: 18, background: C.bg }}>
                    outdated
                  </Pill>
                </div>
              </div>
            </div>
          );
        })}
      </AbsoluteFill>
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 70 }}>
        <Words text="Correct a fact. See its blast radius." delay={40} accent={["blast", "radius"]} style={{ fontSize: 60, fontWeight: 600 }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

const TESTS = [
  "early-region",
  "late-region",
  "late-oncall-stays-disputed",
  "counterfactual-without-change-record",
  "no-memory-before-first-note",
  "valid-time-does-not-invent-intervals",
];

export function TestGraphic() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const allPassed = frame >= 30 + TESTS.length * 8;
  const ci = ["api", "web", "deploy"];
  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill style={{ ...center, gap: 40 }}>
        <Command>faultline test memory-tests.yaml</Command>
        <div
          style={{
            width: 1100,
            borderRadius: 20,
            border: `1px solid ${C.line2}`,
            background: C.panel,
            overflow: "hidden",
            fontFamily: MONO,
          }}
        >
          {TESTS.map((name, i) => {
            const s = spring({ frame: frame - 24 - i * 8, fps, config: { damping: 14, stiffness: 220 } });
            return (
              <div
                key={name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                  padding: "16px 28px",
                  borderTop: i ? `1px solid ${C.line}` : "none",
                  fontSize: 28,
                  opacity: 0.25 + s * 0.75,
                }}
              >
                <span style={{ color: C.ok, transform: `scale(${s})`, display: "inline-block", width: 30 }}>✓</span>
                <span>{name}</span>
              </div>
            );
          })}
        </div>
        <div style={{ display: "flex", gap: 20, alignItems: "center", opacity: allPassed ? 1 : 0.2 }}>
          <Pill color={C.ok} style={{ fontSize: 26, padding: "10px 22px" }}>
            6 passed
          </Pill>
          {ci.map((job, i) => {
            const s = spring({ frame: frame - 90 - i * 6, fps, config: { damping: 14 } });
            return (
              <span
                key={job}
                style={{
                  fontFamily: MONO,
                  fontSize: 24,
                  color: C.muted,
                  padding: "10px 20px",
                  borderRadius: 12,
                  border: `1px solid ${C.line2}`,
                  transform: `scale(${s})`,
                  display: "inline-block",
                }}
              >
                <span style={{ color: C.ok }}>●</span> CI · {job}
              </span>
            );
          })}
        </div>
        <Words text="Memory gets regression tests. In CI. On every push." delay={110} accent={["regression", "tests"]} style={{ fontSize: 54, fontWeight: 600 }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
}
