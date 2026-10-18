import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { AbsoluteFill, interpolate } from "remotion";
import { C } from "./theme";

type NoProps = Record<string, never>;

/* Whip: a fast horizontal pan with motion blur. */
function Whip({ children, presentationDirection, presentationProgress: p }: TransitionPresentationComponentProps<NoProps>) {
  const entering = presentationDirection === "entering";
  const x = entering ? interpolate(p, [0, 1], [100, 0]) : interpolate(p, [0, 1], [0, -100]);
  const blur = Math.sin(p * Math.PI) * 18;
  return (
    <AbsoluteFill style={{ transform: `translateX(${x}%)`, filter: `blur(${blur}px)` }}>{children}</AbsoluteFill>
  );
}

/* Punch: the old scene zooms through the lens while the new one settles in. */
function Punch({ children, presentationDirection, presentationProgress: p }: TransitionPresentationComponentProps<NoProps>) {
  if (presentationDirection === "exiting") {
    return (
      <AbsoluteFill style={{ transform: `scale(${1 + p * 0.35})`, opacity: 1 - p, filter: `blur(${p * 10}px)` }}>
        {children}
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ transform: `scale(${0.82 + p * 0.18})`, opacity: Math.min(1, p * 1.6) }}>
      {children}
    </AbsoluteFill>
  );
}

const CRACK = [
  [0, 560], [380, 548], [520, 470], [700, 612], [930, 492], [1150, 590], [1380, 506], [1600, 560], [1920, 532],
];
const crackPath = CRACK.map(([x, y], i) => `${i ? "L" : "M"}${x} ${y}`).join(" ");
const top = `polygon(${["0px 0px", "1920px 0px", ...[...CRACK].reverse().map(([x, y]) => `${x}px ${y}px`)].join(",")})`;
const bottom = `polygon(${[...CRACK.map(([x, y]) => `${x}px ${y}px`), "1920px 1080px", "0px 1080px"].join(",")})`;

/* Crack: the brand's fault line tears the frame open onto the next scene. */
function Crack({ children, presentationDirection, presentationProgress: p }: TransitionPresentationComponentProps<NoProps>) {
  const line = interpolate(p, [0, 0.35], [0, 1], { extrapolateRight: "clamp" });
  const open = interpolate(p, [0.3, 1], [0, 1], { extrapolateLeft: "clamp" });
  const shift = open * open * 620;
  if (presentationDirection === "entering") {
    /* Only the gap between the two halves shows the new scene, whatever the stacking order. */
    const gap = `polygon(${[
      ...CRACK.map(([x, y]) => `${x - open * 40}px ${y - shift - 2}px`),
      ...[...CRACK].reverse().map(([x, y]) => `${x + open * 40}px ${y + shift + 2}px`),
    ].join(",")})`;
    return (
      <AbsoluteFill style={{ clipPath: p >= 1 ? undefined : gap, transform: `scale(${1.08 - open * 0.08})` }}>
        {children}
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ clipPath: top, transform: `translate(${-open * 40}px, ${-shift}px) rotate(${-open * 2}deg)` }}>
        {children}
      </AbsoluteFill>
      <AbsoluteFill style={{ clipPath: bottom, transform: `translate(${open * 40}px, ${shift}px) rotate(${open * 2}deg)` }}>
        {children}
      </AbsoluteFill>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0, opacity: 1 - open }}>
        <path
          d={crackPath}
          fill="none"
          stroke={C.fault}
          strokeWidth={6}
          strokeLinejoin="round"
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - line}
          style={{ filter: `drop-shadow(0 0 18px ${C.fault})` }}
        />
      </svg>
    </AbsoluteFill>
  );
}

export const whip = (): TransitionPresentation<NoProps> => ({ component: Whip, props: {} });
export const punch = (): TransitionPresentation<NoProps> => ({ component: Punch, props: {} });
export const crack = (): TransitionPresentation<NoProps> => ({ component: Crack, props: {} });
