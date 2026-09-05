/**
 * Capture the README screenshots from a running instance.
 *
 * The screenshots in `docs/screenshots/` are generated, not hand-taken, so
 * they never drift from the UI and anyone can regenerate them after a change.
 * Every verdict shown is produced by really submitting that code to a real
 * judge — nothing is mocked.
 *
 * Usage:
 *
 *   # 1. point the frontend at whichever API you want to document
 *   cd frontend && npm run build && npx vite preview --port 4173
 *
 *   # 2. in another terminal
 *   npm --prefix scripts install playwright   # first run only
 *   npx playwright install chromium           # first run only
 *   node scripts/capture_screenshots.mjs
 *
 * Environment:
 *   APP_URL     frontend to screenshot   (default http://localhost:4173)
 *   API_URL     API, for the docs shot   (default http://localhost:8000)
 *   DEMO_EMAIL  account to sign in as    (default demo@example.com)
 *   DEMO_PASSWORD                        (default DemoPass123)
 */

import { chromium } from "playwright";
import { mkdirSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

const APP = process.env.APP_URL ?? "http://localhost:4173";
const API = process.env.API_URL ?? "http://localhost:8000";
const EMAIL = process.env.DEMO_EMAIL ?? "demo@example.com";
const PASSWORD = process.env.DEMO_PASSWORD ?? "DemoPass123";

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), "../docs/screenshots");
mkdirSync(OUT, { recursive: true });

const captured = [];

async function shot(page, name, { full = false, wait = 800 } = {}) {
  await page.waitForTimeout(wait);
  await page.screenshot({ path: `${OUT}/${name}`, fullPage: full });
  captured.push(name);
  console.log("  captured", name);
}

/** Replace the editor contents. CodeMirror types over auto-closed brackets. */
async function setCode(page, code) {
  await page.click(".cm-content");
  await page.keyboard.press("Control+A");
  await page.keyboard.press("Delete");
  await page.keyboard.type(code, { delay: 4 });
}

async function submitAndWait(page) {
  await page.getByRole("button", { name: /submit solution/i }).click();
  await page
    .locator("text=/Accepted|Wrong Answer|Runtime Error|Time Limit|Compilation/")
    .first()
    .waitFor({ timeout: 180_000 });
  await page.waitForTimeout(700);
}

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2, // retina-quality output
});
const page = await context.newPage();
page.setDefaultTimeout(90_000);

console.log("→ landing");
await page.goto(`${APP}/`, { waitUntil: "networkidle" });
await shot(page, "01-landing-hero.png", { wait: 2200 });
await page.evaluate(() => window.scrollTo(0, 980));
await shot(page, "02-landing-features.png");

console.log("→ sign in");
await page.goto(`${APP}/login`, { waitUntil: "networkidle" });
await shot(page, "03-login.png", { wait: 1200 });
await page.fill("#field-email", EMAIL);
await page.fill("#field-password", PASSWORD);
await page.getByRole("button", { name: /^sign in$/i }).click();
await page.waitForURL("**/problems", { timeout: 120_000 });
await shot(page, "04-problems.png", { wait: 2000 });

console.log("→ solve page");
await page.goto(`${APP}/problems/sum-of-two-numbers`, { waitUntil: "networkidle" });
await page.waitForSelector(".cm-content", { timeout: 60_000 });
await shot(page, "05-solve-editor.png", { wait: 1800 });

// Each verdict below is genuinely produced by the judge.
const VERDICTS = [
  ["06-verdict-accepted.png", "a, b = map(int, input().split())\nprint(a + b)"],
  ["07-verdict-wrong-answer.png", "a, b = map(int, input().split())\nprint(a - b)"],
  ["08-verdict-tle.png", "while True:\n    pass"],
  ["09-verdict-compile-error.png", "def broken(:"],
];

for (const [name, code] of VERDICTS) {
  console.log("→", name);
  await page.evaluate(() => window.scrollTo(0, 0));
  await setCode(page, code);
  await submitAndWait(page);
  await page.evaluate(() => window.scrollTo(0, 610));
  await shot(page, name, { wait: 900 });
}

console.log("→ contests");
await page.goto(`${APP}/contests`, { waitUntil: "networkidle" });
await shot(page, "10-contests.png", { wait: 1600 });

const card = page.locator("a[href^='/contests/']").first();
if (await card.count()) {
  await card.click();
  await page.waitForTimeout(2500);
  await shot(page, "11-contest-leaderboard.png", { full: true, wait: 1200 });
}

console.log("→ submissions");
await page.goto(`${APP}/submissions`, { waitUntil: "networkidle" });
await shot(page, "12-submissions.png", { wait: 1800 });

console.log("→ dashboard");
await page.goto(`${APP}/dashboard`, { waitUntil: "networkidle" });
await shot(page, "13-dashboard.png", { full: true, wait: 2200 });

console.log("→ mobile");
const mobile = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
});
const mobilePage = await mobile.newPage();
await mobilePage.goto(`${APP}/`, { waitUntil: "networkidle" });
await mobilePage.waitForTimeout(2200);
await mobilePage.screenshot({ path: `${OUT}/14-mobile-landing.png` });
captured.push("14-mobile-landing.png");
console.log("  captured 14-mobile-landing.png");

console.log("→ api docs");
const docs = await context.newPage();
await docs.goto(`${API}/docs`, { waitUntil: "networkidle", timeout: 120_000 });
await docs.waitForTimeout(3000);
await docs.screenshot({ path: `${OUT}/15-api-docs.png` });
captured.push("15-api-docs.png");
console.log("  captured 15-api-docs.png");

await browser.close();
console.log(`\nDone — ${captured.length} screenshots written to docs/screenshots/`);
