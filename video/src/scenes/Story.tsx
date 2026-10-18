/* Motion-graphic scenes: cold open, problem, insight and logo. */
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, MONO } from "../lib/theme";
import { Background, Logo, Pill, Words, center, useSpring } from "../lib/ui";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export function ColdOpen() {
  const frame = useCurrentFrame();
  const line = "agent › deploy_region = ";
  const typed = Math.floor(interpolate(frame, [8, 50], [0, line.length], clamp));
  const flipped = frame >= 96;
  const glitch = frame >= 88 && frame < 104;
  const jitter = glitch ? Math.sin(frame * 7) * 10 : 0;
  const lift = interpolate(frame, [118, 140], [0, -150], { ...clamp, easing: (t) => 1 - (1 - t) ** 3 });
  return (
    <AbsoluteFill>
      <Background glow={interpolate(frame, [100, 160], [0, 1], clamp)} />
      <AbsoluteFill style={{ ...center, transform: `translateY(${lift}px)` }}>
        <div style={{ fontFamily: MONO, fontSize: 64, position: "relative" }}>
          <span style={{ color: C.dim }}>{line.slice(0, typed)}</span>
          {typed >= line.length ? (
            <span style={{ position: "relative", display: "inline-block" }}>
              {glitch ? (
                <>
                  <span style={{ position: "absolute", left: jitter, color: "#ff3b6b", opacity: 0.7 }}>region-b</span>
                  <span style={{ position: "absolute", left: -jitter, color: "#3bd1ff", opacity: 0.7 }}>region-a</span>
                </>
              ) : null}
              <span style={{ color: flipped ? C.fault : C.ink, opacity: glitch ? 0.4 : 1 }}>
                {frame >= 60 ? (flipped ? "region-b" : "region-a") : ""}
              </span>
            </span>
          ) : null}
          <span style={{ opacity: Math.floor(frame / 8) % 2 ? 0 : 1, color: C.fault, marginLeft: 6 }}>▍</span>
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ ...center, top: 120 }}>
        <Words text="Your agent changed its answer." delay={122} style={{ fontSize: 92, fontWeight: 600, letterSpacing: -2 }} />
        <Words
          text="Nobody knows why."
          delay={160}
          accent={["Nobody", "knows", "why"]}
          style={{ fontSize: 92, fontWeight: 600, letterSpacing: -2, marginTop: 8 }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

const PROBLEMS = [
  { title: "Stale.", body: "It still believes a fact that was corrected yesterday." },
  { title: "Contradictory.", body: "Two sources disagree, and it quietly picks one." },
  { title: "Lost in handoff.", body: "The next agent never hears there was a dispute." },
];

export function Problem() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const each = 100;
  const index = Math.min(2, Math.floor(frame / each));
  const local = frame - index * each;
  const enter = spring({ frame: local, fps, config: { damping: 20, stiffness: 180 } });
  const item = PROBLEMS[index];
  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill style={{ ...center, gap: 64 }}>
        <div style={{ display: "flex", gap: 14 }}>
          {PROBLEMS.map((_, i) => (
            <div key={i} style={{ width: 80, height: 6, borderRadius: 9, background: i <= index ? C.fault : C.line2 }} />
          ))}
        </div>
        <div
          style={{
            ...center,
            gap: 18,
            transform: `translateX(${(1 - enter) * 260}px) scale(${0.94 + enter * 0.06})`,
            opacity: enter,
            filter: `blur(${(1 - enter) * 10}px)`,
          }}
        >
          <div style={{ fontSize: 120, fontWeight: 700, letterSpacing: -4 }}>{item.title}</div>
          <div style={{ fontSize: 40, color: C.muted }}>{item.body}</div>
        </div>
        <div style={{ height: 230, ...center }}>
          {index === 0 ? <StaleCard local={local} /> : index === 1 ? <ConflictCard local={local} /> : <HandoffCard local={local} />}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

function Card({ children, color = C.line2 }: { children: React.ReactNode; color?: string }) {
  return (
    <div
      style={{
        padding: "26px 36px",
        borderRadius: 20,
        border: `1px solid ${color}`,
        background: C.panel,
        fontFamily: MONO,
        fontSize: 40,
        boxShadow: "0 30px 80px rgba(0,0,0,0.6)",
      }}
    >
      {children}
    </div>
  );
}

function StaleCard({ local }: { local: number }) {
  const { fps } = useVideoConfig();
  const stamp = spring({ frame: local - 30, fps, config: { damping: 11, stiffness: 220 } });
  return (
    <div style={{ position: "relative" }}>
      <Card>
        <span style={{ color: C.dim }}>deploy_region = </span>
        <span style={{ color: local > 30 ? C.superseded : C.ink, textDecoration: local > 30 ? "line-through" : "none" }}>
          region-a
        </span>
      </Card>
      <div
        style={{
          position: "absolute",
          right: -60,
          top: -40,
          padding: "8px 22px",
          border: `5px solid ${C.disputed}`,
          color: C.disputed,
          borderRadius: 10,
          fontFamily: MONO,
          fontWeight: 500,
          fontSize: 38,
          transform: `rotate(-10deg) scale(${interpolate(stamp, [0, 1], [2.6, 1])})`,
          opacity: stamp,
        }}
      >
        OUTDATED
      </div>
    </div>
  );
}

function ConflictCard({ local }: { local: number }) {
  const pulse = 0.5 + Math.sin(local / 4) * 0.5;
  const s = useSpring(10);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
      <Card color={`${C.disputed}88`}>on-call: Priya</Card>
      <div style={{ fontSize: 64, color: C.disputed, opacity: 0.4 + pulse * 0.6, transform: `scale(${s})` }}>⟷</div>
      <Card color={`${C.disputed}88`}>on-call: Jordan</Card>
    </div>
  );
}

function HandoffCard({ local }: { local: number }) {
  const travel = interpolate(local, [10, 55], [0, 1], { ...clamp, easing: (t) => t * t * (3 - 2 * t) });
  const fall = interpolate(local, [32, 70], [0, 1], clamp);
  return (
    <div style={{ position: "relative", width: 1000, height: 200 }}>
      <Agent x={0} label="agent-planner" />
      <Agent x={780} label="agent-release" />
      <div style={{ position: "absolute", left: 240, right: 240, top: 72, height: 4, background: C.line2 }} />
      <div style={{ position: "absolute", left: 230 + travel * 470, top: 46 }}>
        <div style={{ width: 70, height: 56, borderRadius: 10, background: C.fault, boxShadow: `0 0 30px ${C.fault}` }} />
        <div
          style={{
            position: "absolute",
            top: -46,
            left: -20,
            transform: `translateY(${fall * fall * 200}px) rotate(${fall * 70}deg)`,
            opacity: 1 - fall,
          }}
        >
          <Pill color={C.disputed}>disputed</Pill>
        </div>
      </div>
    </div>
  );
}

function Agent({ x, label }: { x: number; label: string }) {
  return (
    <div style={{ position: "absolute", left: x, top: 20, width: 220, ...center, gap: 14 }}>
      <div style={{ width: 110, height: 110, borderRadius: 999, border: `2px solid ${C.line2}`, background: C.panel2, ...center, fontSize: 48 }}>
        ◎
      </div>
      <div style={{ fontFamily: MONO, fontSize: 24, color: C.muted }}>{label}</div>
    </div>
  );
}

const VERBS = ["blame", "diff", "bisect"];

export function Insight() {
  const frame = useCurrentFrame();
  const swap = frame >= 132;
  const out = interpolate(frame, [190, 210], [1, 0], clamp);
  return (
    <AbsoluteFill>
      <Background />
      <AbsoluteFill style={{ ...center, gap: 50, opacity: out, transform: `scale(${1 + (1 - out) * 0.2})` }}>
        <Words
          key={swap ? "b" : "a"}
          text={swap ? "Agent memory doesn't." : "Code has git."}
          delay={swap ? 132 : 4}
          accent={["doesn't"]}
          style={{ fontSize: 110, fontWeight: 700, letterSpacing: -3 }}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 18, fontFamily: MONO, fontSize: 50 }}>
          {VERBS.map((verb, i) => (
            <Verb key={verb} verb={verb} delay={30 + i * 15} swapAt={150 + i * 6} />
          ))}
        </div>
      </AbsoluteFill>
      <Reveal start={200} />
    </AbsoluteFill>
  );
}

function Verb({ verb, delay, swapAt }: { verb: string; delay: number; swapAt: number }) {
  const frame = useCurrentFrame();
  const s = useSpring(delay);
  const swapped = frame >= swapAt;
  const flash = interpolate(frame, [swapAt, swapAt + 8], [1, 0], clamp);
  return (
    <div style={{ transform: `translateX(${(1 - s) * -80}px)`, opacity: s }}>
      <span style={{ color: C.fault }}>$ </span>
      <span style={{ color: swapped ? C.fault : C.muted, textShadow: `0 0 ${flash * 30}px ${C.fault}` }}>
        {swapped ? "faultline" : "git"}
      </span>
      <span> {verb}</span>
    </div>
  );
}

function Reveal({ start }: { start: number }) {
  const frame = useCurrentFrame();
  const local = frame - start;
  const s = useSpring(start, { damping: 14 });
  if (local < 0) return null;
  const zoom = interpolate(local, [0, 110], [1.12, 1], clamp);
  return (
    <AbsoluteFill style={{ ...center, gap: 34, transform: `scale(${zoom})` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 30, transform: `scale(${s})` }}>
        <Logo size={130} />
        <span style={{ fontSize: 140, fontWeight: 700, letterSpacing: -5 }}>Faultline</span>
      </div>
      <Words text="git for agent memory" delay={start + 14} accent={["git"]} style={{ fontSize: 54, color: C.muted }} />
      <div style={{ opacity: interpolate(local, [30, 45], [0, 1], clamp), fontFamily: MONO, fontSize: 26, color: C.dim }}>
        built on FalkorDB
      </div>
    </AbsoluteFill>
  );
}

export function Close() {
  const frame = useCurrentFrame();
  const s = useSpring(0, { damping: 14 });
  const fade = interpolate(frame, [200, 235], [1, 0], clamp);
  const verbs = ["checkout", "diff", "blame", "bisect", "impact", "handoff", "test"];
  return (
    <AbsoluteFill style={{ opacity: fade }}>
      <Background />
      <AbsoluteFill style={{ ...center, gap: 36, transform: `scale(${1.06 - s * 0.06})` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 26, transform: `scale(${s})` }}>
          <Logo size={110} />
          <span style={{ fontSize: 120, fontWeight: 700, letterSpacing: -4 }}>Faultline</span>
        </div>
        <div style={{ display: "flex", gap: 16 }}>
          {verbs.map((verb, i) => {
            const v = spring({ frame: frame - 12 - i * 4, fps: 30, config: { damping: 16 } });
            return (
              <span
                key={verb}
                style={{
                  fontFamily: MONO,
                  fontSize: 28,
                  padding: "8px 18px",
                  borderRadius: 12,
                  border: `1px solid ${C.line2}`,
                  background: C.panel,
                  opacity: v,
                  transform: `translateY(${(1 - v) * 20}px)`,
                }}
              >
                {verb}
              </span>
            );
          })}
        </div>
        <div style={{ marginTop: 30, fontSize: 56, fontWeight: 600, opacity: interpolate(frame, [45, 60], [0, 1], clamp) }}>
          faultline.mannnan.com
        </div>
        <div style={{ fontFamily: MONO, fontSize: 26, color: C.dim, opacity: interpolate(frame, [60, 75], [0, 1], clamp) }}>
          github.com/maannaan/faultline · Graph Hacks · Track 02 · FalkorDB
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}
