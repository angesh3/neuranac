import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

async function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function clickIfVisible(page, selector) {
  const el = page.locator(selector).first();
  if (await el.isVisible().catch(() => false)) {
    await el.click();
    return true;
  }
  return false;
}

async function main() {
  const baseUrl = process.env.DEMO_BASE_URL || "http://localhost:3001";
  const username = process.env.DEMO_USERNAME || "admin";
  const password = process.env.DEMO_PASSWORD || "05D93-2npNMpoijWm9Lt4w";

  const outDir = path.resolve("artifacts", "demo-video");
  await fs.mkdir(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    recordVideo: { dir: outDir, size: { width: 1600, height: 900 } },
  });

  const page = await context.newPage();
  const video = page.video();

  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.fill('input[type="text"], input[name="username"]', username);
  await page.fill('input[type="password"], input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await wait(1500);

  const routes = [
    "/",
    "/topology",
    "/policies",
    "/network-devices",
    "/endpoints",
    "/sessions",
    "/ai/agents",
    "/diagnostics",
    "/sites",
  ];

  for (const route of routes) {
    await page.goto(`${baseUrl}${route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
    await wait(1200);
  }

  // Optional AI mode toggle if present.
  await clickIfVisible(page, 'button:has-text("AI Mode")');
  await wait(1500);

  await context.close();
  await browser.close();

  const videoPath = await video.path();
  console.log(videoPath);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

