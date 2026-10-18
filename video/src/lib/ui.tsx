import type { CSSProperties, ReactNode } from "react";
import {
  AbsoluteFill,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { C, MONO, SANS } from "./theme";

const FONTS: [string, string, string][] = [
  ["Geist", "Geist-Regular.woff2", "400"],
  ["Geist", "Geist-Medium.woff2", "500"],
  ["Geist", "Geist-SemiBold.woff2", "600"],
  ["Geist", "Geist-Bold.woff2", "700"],
  ["Geist Mono", "GeistMono-Regular.woff2", "400"],
  ["Geist Mono", "GeistMono-Medium.woff2", "500"],
];

if (typeof document !== "undefined") {
  const handle = delayRender("fonts");
  Promise.all(
    FONTS.map(([family, file, weight]) => {
      const face = new FontFace(family, `url(${staticFile(`fonts/${file}`)})`, { weight });
      document.fonts.add(face);
      return face.load();
    }),
  ).then(() => continueRender(handle));
}

/* Dark canvas with the site's faint grid and an amber glow that drifts slowly. */
export function Background({ glow = 1 }: { glow?: number }) {
  const frame = useCurrentFrame();
  const drift = Math.sin(frame / 90) * 6;
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg, fontFamily: SANS, color: C.ink }}>
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          backgroundPosition: `${frame * 0.15}px ${frame * 0.3}px`,
          maskImage: "radial-gradient(70% 70% at 50% 45%, black, transparent)",
        }}
      />
      <AbsoluteFill
        style={{
          opacity: glow,
          background: `radial-gradient(55% 45% at ${50 + drift}% 0%, rgba(245,158,11,0.16), transparent 70%)`,
        }}
      />
    </AbsoluteFill>
  );
}

export function useSpring(delay = 0, config: { damping?: number; mass?: number; stiffness?: number } = {}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping: 18, stiffness: 160, ...config } });
}

/* Words rise in one after another, like kinetic type in a launch video. */
export function Words({
  text,
  delay = 0,
  stagger = 3,
  style,
  accent,
}: {
  text: string;
  delay?: number;
  stagger?: number;
  style?: CSSProperties;
  accent?: string[];
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0 0.28em", ...style }}>
      {text.split(" ").map((word, index) => {
        const s = spring({ frame: frame - delay - index * stagger, fps, config: { damping: 16, stiffness: 140 } });
        const clean = word.replace(/[.,]/g, "");
        return (
          <span key={index} style={{ display: "inline-block", overflow: "hidden", paddingBottom: "0.08em" }}>
            <span
              style={{
                display: "inline-block",
                transform: `translateY(${(1 - s) * 105}%)`,
                opacity: s,
                color: accent?.includes(clean) ? C.fault : undefined,
              }}
            >
              {word}
            </span>
          </span>
        );
      })}
    </div>
  );
}

export function Logo({ size = 64 }: { size?: number }) {
  const frame = useCurrentFrame();
  const draw = interpolate(frame, [0, 22], [40, 0], { extrapolateRight: "clamp" });
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none">
      <rect x="0.5" y="0.5" width="23" height="23" rx="6" fill="#121216" stroke="rgba(255,255,255,0.12)" />
      <path
        d="M4 15.5 9.5 10l3 3L20 5.5"
        stroke={C.fault}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={40}
        strokeDashoffset={draw}
      />
      <path d="M4 19h6" stroke="rgba(255,255,255,0.35)" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M13 19h7" stroke="rgba(255,255,255,0.35)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

/* The `faultline <verb>` chip that labels each product moment. */
export function Command({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  const s = useSpring(delay);
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 14,
        padding: "14px 22px",
        borderRadius: 14,
        border: `1px solid ${C.line2}`,
        background: "rgba(14,14,17,0.92)",
        fontFamily: MONO,
        fontSize: 30,
        color: C.ink,
        transform: `translateY(${(1 - s) * 30}px)`,
        opacity: s,
        boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
      }}
    >
      <span style={{ color: C.fault }}>$</span>
      {children}
    </div>
  );
}

export function Pill({ color, children, style }: { color: string; children: ReactNode; style?: CSSProperties }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 14px",
        borderRadius: 999,
        border: `1px solid ${color}55`,
        background: `${color}14`,
        color,
        fontFamily: MONO,
        fontSize: 20,
        ...style,
      }}
    >
      <span style={{ width: 8, height: 8, borderRadius: 99, background: color }} />
      {children}
    </span>
  );
}

export const center: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
};
