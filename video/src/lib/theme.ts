/* Faultline brand tokens, copied from apps/web/app/globals.css. */
export const C = {
  bg: "#08080a",
  panel: "#0e0e11",
  panel2: "#15151a",
  line: "rgba(255,255,255,0.08)",
  line2: "rgba(255,255,255,0.14)",
  ink: "#f4f4f5",
  muted: "#a1a1aa",
  dim: "#71717a",
  fault: "#f59e0b",
  fault2: "#fb923c",
  ok: "#34d399",
  superseded: "#8b8b94",
  disputed: "#fb7185",
};

export const SANS = "Geist, ui-sans-serif, system-ui, sans-serif";
export const MONO = "Geist Mono, ui-monospace, monospace";

/* 120 BPM: one beat is 15 frames, one bar is 60. Every cut lands on a beat. */
export const FPS = 30;
export const BEAT = 15;
export const BAR = BEAT * 4;
export const TRANSITION = BEAT;
