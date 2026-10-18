# Faultline demo video

A 1:53 launch-style video made with [Remotion](https://remotion.dev). The motion graphics reuse Faultline's colours and Geist fonts. The product shots are real recordings of https://faultline.mannnan.com.

```bash
npm install
npm run clips            # record the live-site clips with Playwright into public/clips/
npm run studio           # preview and scrub in the browser
npm run render           # writes out/faultline.mp4 (1920×1080, 30 fps)
```

**Music:** put a licensed 120 BPM track at `public/music.mp3` and re-render. It fades in and out automatically, and every cut is timed to 120 BPM (one beat = 15 frames).

**Structure:**
- `src/Root.tsx` holds the timeline: scene lengths in beats, plus the transition between each pair of scenes.
- `src/lib/transitions.tsx` defines the Whip, Punch and Crack transitions.
- `src/scenes/` has the cold open, problem, insight, evidence graph, clip scenes, bisect, impact, tests and close.
