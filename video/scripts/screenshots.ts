/* Retina screenshots of the live site for the blog post. */
import { chromium, type Page } from "playwright";

const SITE = "https://faultline.mannnan.com";
const OUT = "../docs/blog/images";

const click = async (page: Page, name: RegExp) => {
  await page.getByRole("button", { name }).first().click();
};

const SHOTS: { file: string; path: string; run?: (page: Page) => Promise<void>; full?: boolean }[] = [
  { file: "01-landing.png", path: "/" },
  { file: "02-timeline.png", path: "/app/timeline" },
  { file: "03-replay-diff.png", path: "/app/replay", run: async (p) => { await click(p, /Run replay/i); await p.waitForTimeout(3500); } },
  { file: "04-blame.png", path: "/app/blame", run: async (p) => { await click(p, /Region · 16 Oct/i); await p.waitForTimeout(3000); } },
  { file: "05-bisect.png", path: "/app/bisect", run: async (p) => { await click(p, /Run bisect/i); await p.waitForTimeout(5000); } },
  { file: "06-impact.png", path: "/app/impact", run: async (p) => { await p.waitForTimeout(2500); } },
  { file: "07-handoff.png", path: "/app/handoff", run: async (p) => { await click(p, /Create handoff/i); await p.waitForTimeout(3000); } },
  { file: "08-bench.png", path: "/app/bench", run: async (p) => { await click(p, /Run ablation/i); await p.waitForTimeout(4500); } },
];

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, colorScheme: "dark" });
for (const shot of SHOTS) {
  const page = await context.newPage();
  await page.goto(SITE + shot.path, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  try { await shot.run?.(page); } catch (e) { console.error(shot.file, e); }
  await page.screenshot({ path: `${OUT}/${shot.file}` });
  console.log("saved", shot.file);
  await page.close();
}
await browser.close();
