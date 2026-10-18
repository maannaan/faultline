import { TransitionSeries, linearTiming } from "@remotion/transitions";
import type { TransitionPresentation } from "@remotion/transitions";
import type { ReactNode } from "react";
import { AbsoluteFill, Audio, Composition, getStaticFiles, interpolate, staticFile } from "remotion";
import { crack, punch, whip } from "./lib/transitions";
import { BEAT, C, FPS, SANS } from "./lib/theme";
import { Clip } from "./scenes/Clip";
import { Graph } from "./scenes/Graph";
import { BisectGraphic, ImpactGraphic, TestGraphic } from "./scenes/Proof";
import { Close, ColdOpen, Insight, Problem } from "./scenes/Story";

type Step = { frames: number; scene: ReactNode; out?: () => TransitionPresentation<Record<string, never>> };

/* Durations are in frames at 30 fps; every scene and transition is a whole number of beats. */
const STEPS: Step[] = [
  { frames: 16 * BEAT, scene: <ColdOpen />, out: crack },
  { frames: 20 * BEAT, scene: <Problem />, out: whip },
  { frames: 22 * BEAT, scene: <Insight />, out: punch },
  { frames: 22 * BEAT, scene: <Graph />, out: punch },
  {
    frames: 22 * BEAT,
    out: whip,
    scene: (
      <Clip
        src="clips/timeline.mp4"
        from={3.5}
        path="/app/timeline"
        command="faultline checkout --as-of 15-Oct"
        headline="Check out memory at any moment."
        accent={["any", "moment"]}
        shots={[{ at: 0, scale: 1, x: 0.57, y: 0.55 }, { at: 45, scale: 1.3, x: 0.57, y: 0.55 }, { at: 230, scale: 1.3, x: 0.57, y: 0.55 }, { at: 290, scale: 1.8, x: 0.52, y: 0.48 }, { at: 330, scale: 1.8, x: 0.52, y: 0.48 }, ]}
      />
    ),
  },
  {
    frames: 20 * BEAT,
    out: whip,
    scene: (
      <Clip
        src="clips/replay.mp4"
        path="/app/replay"
        command="faultline diff early late"
        headline="Diff a question across time. See the edge that changed it."
        accent={["edge"]}
        segments={[{ at: 0, from: 1.5 }, { at: 150, from: 15.5 }]}
        shots={[{ at: 0, scale: 1, x: 0.5, y: 0.5 }, { at: 50, scale: 1.6, x: 0.69, y: 0.62 }, { at: 140, scale: 1.6, x: 0.69, y: 0.62 }, { at: 150, scale: 1.25, x: 0.69, y: 0.4 }, { at: 200, scale: 1.55, x: 0.69, y: 0.35 }, { at: 300, scale: 1.55, x: 0.69, y: 0.35 }, ]}
      />
    ),
  },
  {
    frames: 13 * BEAT,
    out: punch,
    scene: (
      <Clip
        src="clips/blame.mp4"
        from={0.5}
        path="/app/blame"
        command="faultline blame <replay>"
        headline="Trace any answer back to the agent that wrote it."
        accent={["agent"]}
        shots={[{ at: 0, scale: 1, x: 0.5, y: 0.5 }, { at: 50, scale: 1.55, x: 0.8, y: 0.5 }, { at: 195, scale: 1.6, x: 0.8, y: 0.5 }, ]}
      />
    ),
  },
  { frames: 18 * BEAT, scene: <BisectGraphic />, out: crack },
  {
    frames: 12 * BEAT,
    out: whip,
    scene: (
      <Clip
        src="clips/bisect.mp4"
        from={1}
        path="/app/bisect"
        command="faultline bisect"
        headline="Find the exact event that flipped the answer."
        accent={["exact", "event"]}
        shots={[{ at: 0, scale: 1.2, x: 0.69, y: 0.35 }, { at: 40, scale: 1.6, x: 0.69, y: 0.65 }, { at: 180, scale: 1.65, x: 0.69, y: 0.65 }, ]}
      />
    ),
  },
  { frames: 12 * BEAT, scene: <ImpactGraphic />, out: punch },
  {
    frames: 12 * BEAT,
    out: whip,
    scene: (
      <Clip
        src="clips/impact.mp4"
        from={1.5}
        path="/app/impact"
        command="faultline impact assert-region-a"
        headline="Every decision that relied on it, flagged."
        accent={["flagged"]}
        shots={[{ at: 0, scale: 1.2, x: 0.5, y: 0.5 }, { at: 40, scale: 1.5, x: 0.6, y: 0.45 }, { at: 180, scale: 1.55, x: 0.6, y: 0.55 }, ]}
      />
    ),
  },
  {
    frames: 18 * BEAT,
    out: punch,
    scene: (
      <Clip
        src="clips/handoff.mp4"
        path="/app/handoff"
        command="faultline handoff"
        headline="Unresolved conflicts travel with the handoff."
        accent={["conflicts"]}
        segments={[{ at: 0, from: 1 }, { at: 150, from: 9.8 }]}
        shots={[{ at: 0, scale: 1, x: 0.5, y: 0.5 }, { at: 40, scale: 1.6, x: 0.69, y: 0.45 }, { at: 140, scale: 1.6, x: 0.69, y: 0.45 }, { at: 150, scale: 1.5, x: 0.69, y: 0.75 }, { at: 200, scale: 1.7, x: 0.69, y: 0.85 }, { at: 270, scale: 1.7, x: 0.69, y: 0.85 }, ]}
      />
    ),
  },
  { frames: 16 * BEAT, scene: <TestGraphic />, out: punch },
  { frames: 16 * BEAT, scene: <Close /> },
];

const TOTAL = STEPS.reduce((sum, step) => sum + step.frames, 0) - (STEPS.length - 1) * BEAT;

const hasMusic = () => getStaticFiles().some((file) => file.name === "music.mp3");

function Film() {
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg, color: C.ink, fontFamily: SANS }}>
      <TransitionSeries>
        {STEPS.flatMap((step, index) => {
          const items = [
            <TransitionSeries.Sequence key={`s${index}`} durationInFrames={step.frames}>
              {step.scene}
            </TransitionSeries.Sequence>,
          ];
          if (step.out) {
            items.push(
              <TransitionSeries.Transition
                key={`t${index}`}
                presentation={step.out()}
                timing={linearTiming({ durationInFrames: BEAT })}
              />,
            );
          }
          return items;
        })}
      </TransitionSeries>
      {hasMusic() ? (
        <Audio
          src={staticFile("music.mp3")}
          volume={(f) => interpolate(f, [0, 20, TOTAL - 60, TOTAL], [0, 0.9, 0.9, 0], { extrapolateRight: "clamp" })}
        />
      ) : null}
    </AbsoluteFill>
  );
}

export function Root() {
  return (
    <Composition id="Faultline" component={Film} durationInFrames={TOTAL} fps={FPS} width={1920} height={1080} />
  );
}
