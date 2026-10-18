/* Records short clips of the live site for the video. Each clip gets its own browser
   context so the recording starts clean; `public/clips/offsets.json` stores how many
   seconds of page load to skip at the start of each file. */
import { chromium, type Locator, type Page } from "playwright";
import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";

const SITE = process.env.SITE ?? "https://faultline.mannnan.com";
const OUT = path.resolve("public/clips");
const SIZE = { width: 1600, height: 900 };

/* A soft cursor dot, since headless recordings have no pointer. */
const CURSOR = `
  window.addEventListener("DOMContentLoaded", () => {
    const dot = document.createElement("div");
    dot.style.cssText = "position:fixed;z-index:99999;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:rgba(245,158,11,.35);border:2px solid #f59e0b;pointer-events:none;transition:transform .12s ease;box-shadow:0 0 18px rgba(245,158,11,.6)";
    document.body.appendChild(dot);
    document.addEventListener("mousemove", (e) => { dot.style.left = e.clientX + "px"; dot.style.top = e.clientY + "px"; });
    document.addEventListener("mousedown", () => { dot.style.transform = "scale(.6)"; });
    document.addEventListener("mouseup", () => { dot.style.transform = "scale(1)"; });
  });
`;

async function glide(page: Page, target: Locator) {
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (!box) throw new Error("target not visible");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 28 });
  await page.waitForTimeout(250);
}

async function click(page: Page, target: Locator) {
  await glide(page, target);
  await page.mouse.down();
  await page.waitForTimeout(90);
  await page.mouse.up();
}

const button = (page: Page, name: string | RegExp) => page.getByRole("button", { name }).first();

type Clip = { name: string; path: string; run: (page: Page) => Promise<void> };

const CLIPS: Clip[] = [
  {
    name: "timeline",
    path: "/app/timeline",
    run: async (page) => {
      await click(page, button(page, /Play time travel|Replay history/i));
      await page.waitForTimeout(9000);
    },
  },
  {
    name: "replay",
    path: "/app/replay",
    run: async (page) => {
      await click(page, button(page, /Run replay/i));
      await page.waitForTimeout(3500);
      await click(page, page.getByText(/Counterfactual/i).first());
      await page.waitForTimeout(500);
      await click(page, button(page, /Run replay/i));
      await page.waitForTimeout(3500);
    },
  },
  {
    name: "blame",
    path: "/app/blame",
    run: async (page) => {
      await click(page, button(page, /Region · 16 Oct/i));
      await page.waitForTimeout(5000);
    },
  },
  {
    name: "bisect",
    path: "/app/bisect",
    run: async (page) => {
      await click(page, button(page, /Run bisect/i));
      await page.waitForTimeout(6500);
    },
  },
  {
    name: "impact",
    path: "/app/impact",
    run: async (page) => {
      await click(page, button(page, /Simulate an agent/i));
      await page.waitForTimeout(5000);
    },
  },
  {
    name: "handoff",
    path: "/app/handoff",
    run: async (page) => {
      await click(page, button(page, /Create handoff/i));
      await page.waitForTimeout(2000);
      await click(page, button(page, /Accept as/i));
      await page.waitForTimeout(2000);
      await click(page, button(page, /expired handoff/i));
      await page.waitForTimeout(2500);
    },
  },
  {
    name: "bench",
    path: "/app/bench",
    run: async (page) => {
      await page.waitForTimeout(1500);
      await click(page, button(page, /Run ablation/i));
      await page.waitForTimeout(5000);
    },
  },
];

async function main() {
  mkdirSync(OUT, { recursive: true });
  const only = process.argv.slice(2);
  const browser = await chromium.launch();
  const offsets: Record<string, number> = {};
  for (const clip of CLIPS) {
    if (only.length && !only.includes(clip.name)) continue;
    const started = Date.now();
    const context = await browser.newContext({
      viewport: SIZE,
      colorScheme: "dark",
      recordVideo: { dir: OUT, size: SIZE },
    });
    await context.addInitScript(CURSOR);
    const page = await context.newPage();
    await page.goto(SITE + clip.path, { waitUntil: "networkidle" });
    await page.mouse.move(SIZE.width / 2, SIZE.height * 0.7);
    await page.waitForTimeout(600);
    offsets[clip.name] = (Date.now() - started) / 1000;
    try {
      await clip.run(page);
    } catch (error) {
      console.error(`clip ${clip.name} failed:`, error);
    }
    const video = page.video();
    await context.close();
    if (video) {
      const webm = path.join(OUT, `${clip.name}.webm`);
      renameSync(await video.path(), webm);
      execFileSync("ffmpeg", [
        "-y", "-loglevel", "error", "-ss", String(offsets[clip.name]), "-i", webm,
        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-r", "30",
        path.join(OUT, `${clip.name}.mp4`),
      ]);
      const seconds = execFileSync("ffprobe", [
        "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
        path.join(OUT, `${clip.name}.mp4`),
      ]).toString().trim();
      console.log(`${clip.name}: ${seconds}s`);
    }
  }
  await browser.close();
  writeFileSync(path.join(OUT, "offsets.json"), JSON.stringify(offsets, null, 2));
}

main();
