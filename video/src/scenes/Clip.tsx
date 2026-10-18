/* A recorded clip of the live site in a browser window, with a spring camera that pushes in on details. */
import type { ReactNode } from "react";
import { AbsoluteFill, Easing, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { C, MONO } from "../lib/theme";
import { Background, Command, Words } from "../lib/ui";

/* Camera keyframe: at frame `at`, zoom `scale` around (x, y), given as fractions of the clip. */
export type Shot = { at: number; scale: number; x: number; y: number };

export function Clip({
  src,
  from = 0,
  path,
  command,
  headline,
  accent,
  shots,
  segments,
  overlay,
}: {
  src: string;
  from?: number;
  path: string;
  command: string;
  headline: string;
  accent?: string[];
  shots: Shot[];
  /* Jump cuts: at scene frame `at`, play the recording from `from` seconds. */
  segments?: { at: number; from: number }[];
  overlay?: ReactNode;
}) {
  const frame = useCurrentFrame();
  const at = shots.map((s) => s.at);
  const ease = { easing: Easing.bezier(0.65, 0, 0.35, 1), extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  const pick = (key: "scale" | "x" | "y") =>
    shots.length > 1 ? interpolate(frame, at, shots.map((s) => s[key]), ease) : shots[0][key];
  const scale = pick("scale");
  const x = pick("x");
  const y = pick("y");
  const rise = interpolate(frame, [0, 18], [40, 0], { ...ease, easing: Easing.out(Easing.cubic) });

  return (
    <AbsoluteFill>
      <Background glow={0.6} />
      <AbsoluteFill style={{ alignItems: "center", paddingTop: 44 }}>
        <div
          style={{
            width: 1600,
            borderRadius: 18,
            overflow: "hidden",
            border: `1px solid ${C.line2}`,
            background: C.panel,
            boxShadow: "0 40px 120px rgba(0,0,0,0.7), 0 0 80px rgba(245,158,11,0.06)",
            transform: `translateY(${rise}px)`,
          }}
        >
          <div style={{ height: 48, display: "flex", alignItems: "center", gap: 10, padding: "0 18px", borderBottom: `1px solid ${C.line}` }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
              <span key={c} style={{ width: 13, height: 13, borderRadius: 99, background: c, opacity: 0.75 }} />
            ))}
            <div
              style={{
                marginLeft: 20,
                padding: "6px 18px",
                borderRadius: 9,
                background: C.panel2,
                fontFamily: MONO,
                fontSize: 18,
                color: C.muted,
              }}
            >
              <span style={{ color: C.ok }}>🔒 </span>faultline.mannnan.com<span style={{ color: C.ink }}>{path}</span>
            </div>
          </div>
          <div style={{ width: 1600, height: 900, overflow: "hidden", position: "relative" }}>
            <div style={{ width: 1600, height: 900, transform: `scale(${scale})`, transformOrigin: `${x * 100}% ${y * 100}%` }}>
              {(segments ?? [{ at: 0, from }]).map((seg, i, all) => (
                <Sequence key={i} from={seg.at} durationInFrames={i + 1 < all.length ? all[i + 1].at - seg.at : undefined}>
                  <OffthreadVideo src={staticFile(src)} startFrom={Math.round(seg.from * 30)} muted />
                </Sequence>
              ))}
            </div>
            {(segments ?? []).slice(1).map((seg) => (
              <AbsoluteFill
                key={seg.at}
                style={{ background: C.fault, opacity: interpolate(frame, [seg.at, seg.at + 6], [0.18, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) * (frame >= seg.at ? 1 : 0) }}
              />
            ))}
            {overlay}
          </div>
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ justifyContent: "flex-end", padding: "0 0 46px 200px" }}>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 0,
            height: 300,
            background: "linear-gradient(transparent, rgba(8,8,10,0.92) 65%)",
          }}
        />
        <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 18 }}>
          <Command delay={6}>{command}</Command>
          <Words
            text={headline}
            delay={14}
            accent={accent}
            style={{ justifyContent: "flex-start", fontSize: 54, fontWeight: 600, letterSpacing: -1, maxWidth: 1500, textShadow: "0 4px 30px #000" }}
          />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}
