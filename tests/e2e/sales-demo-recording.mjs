import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { execSync } from "node:child_process";

// ── Pacing config: title cards, route dwells, gaps (seconds) ─────────────────
const PACING = {
  titleCard: { intro: 6, section: 5, sectionShort: 4, outro: 6 },
  routeDwell: { default: 7, key: 8, quick: 5 },
  gaps: { afterLogin: 3.5, afterToggle: 1.2, afterRadius: 4, betweenRoutes: 0.5 },
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function titleCard(page, title, subtitle, seconds = PACING.titleCard.section) {
  await page.setContent(
    `
    <html>
      <head>
        <style>
          body {
            margin: 0;
            background: radial-gradient(circle at top right, #3b82f6 0%, #0b1020 45%, #05070f 100%);
            color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
          }
          .wrap { text-align: center; max-width: 1100px; padding: 32px; }
          .kicker {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 9999px;
            border: 1px solid rgba(255,255,255,.3);
            font-size: 16px;
            letter-spacing: .03em;
            color: #cbd5e1;
            margin-bottom: 16px;
          }
          h1 { font-size: 52px; margin: 0 0 16px; line-height: 1.1; }
          p { font-size: 24px; margin: 0; color: #dbeafe; line-height: 1.35; }
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="kicker">NeuraNAC Sales Demo</div>
          <h1>${title}</h1>
          <p>${subtitle}</p>
        </div>
      </body>
    </html>
    `,
    { waitUntil: "domcontentloaded" }
  );
  await sleep(seconds * 1000);
}

async function showRoute(page, baseUrl, route, seconds = PACING.routeDwell.default) {
  await page.goto(`${baseUrl}${route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await page.mouse.move(200, 200);
  await sleep(500);
  await page.mouse.move(1200, 260);
  await sleep(500);
  await page.mouse.wheel(0, 600);
  await sleep(1200);
  await page.mouse.wheel(0, -450);
  await sleep(Math.max(0, seconds * 1000 - 2200));
}

async function switchToDashboardViaToggle(page) {
  // Click the Agent/Dash toggle to switch from AI mode to Dashboard (visible on-screen transition).
  const toggle = page.locator('button[title="Switch to Dashboard"]');
  const visible = await toggle.waitFor({ state: "visible", timeout: 5000 }).then(() => true).catch(() => false);
  if (visible) {
    await toggle.click();
    await sleep(1200); // Allow UI to transition
    return;
  }
  // Fallback: force AI mode off via localStorage and reload
  await page.evaluate(() => {
    const raw = localStorage.getItem("neuranac-ai-mode");
    let parsed = { state: {}, version: 0 };
    if (raw) {
      try {
        parsed = JSON.parse(raw);
      } catch {
        parsed = { state: {}, version: 0 };
      }
    }
    parsed.state = { ...(parsed.state || {}), aiMode: false };
    if (typeof parsed.version !== "number") parsed.version = 0;
    localStorage.setItem("neuranac-ai-mode", JSON.stringify(parsed));
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  await sleep(1500);
}

function generateRadiusTraffic() {
  // Uses the demo-tools container (run: docker compose --profile demo up -d demo-tools).
  try {
    execSync(
      "docker exec neuranac-demo-tools bash -lc 'for i in $(seq 1 8); do radtest testuser testing123 radius-server 0 testing123 2>/dev/null || true; done'",
      { stdio: "pipe", cwd: process.cwd(), timeout: 15000 }
    );
  } catch (err) {
    console.warn("RADIUS traffic skipped (demo-tools container may not be running):", err.message);
  }
}

async function main() {
  const baseUrl = process.env.DEMO_BASE_URL || "http://localhost:3001";
  const username = process.env.DEMO_USERNAME || "admin";
  const password = process.env.DEMO_PASSWORD || "admin";

  const outDir = path.resolve("artifacts", "sales-demo");
  await fs.mkdir(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: outDir, size: { width: 1920, height: 1080 } },
  });
  const page = await context.newPage();
  const video = page.video();

  const T = PACING.titleCard;
  const R = PACING.routeDwell;
  const G = PACING.gaps;

  await titleCard(page, "NeuraNAC Full Sales Walkthrough", "Three high-impact enterprise use cases in one integrated platform", T.intro);

  // Login section
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector('input[type="text"]', { state: "visible", timeout: 10000 });
  await page.waitForSelector('input[type="password"]', { state: "visible", timeout: 5000 });
  await page.fill('input[type="text"]', username);
  await page.fill('input[type="password"]', password);
  await sleep(500);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 15000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await sleep(G.afterLogin * 1000);

  // Show AI mode first
  await titleCard(page, "AI Mode Experience", "Start in AI assistant mode to demonstrate natural-language operations", T.sectionShort);
  await showRoute(page, baseUrl, "/", R.default);

  // Switch to Dashboard mode via visible toggle click
  await titleCard(page, "Switching to Dashboard Mode", "Moving from conversational AI to full operational dashboard controls", T.sectionShort);
  await page.goto(`${baseUrl}/`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await switchToDashboardViaToggle(page);
  await sleep(G.afterToggle * 1000);
  await showRoute(page, baseUrl, "/", R.default);

  // Use case 1
  await titleCard(page, "Use Case 1: AI-Aware NAC Governance", "Authenticate AI workloads, detect shadow AI traffic, and enforce policy in one control plane", T.section);
  await showRoute(page, baseUrl, "/", R.default);
  await sleep(G.betweenRoutes * 1000);
  await showRoute(page, baseUrl, "/ai/agents", R.default);
  await showRoute(page, baseUrl, "/ai/data-flow", R.default);
  await showRoute(page, baseUrl, "/ai/shadow", R.default);
  await showRoute(page, baseUrl, "/policies", R.default);

  // Use case 2
  await titleCard(page, "Use Case 2: Hybrid Multi-Site NAC Operations", "Run standalone or hybrid, connect sites securely, and manage federation from one dashboard", T.section);
  await showRoute(page, baseUrl, "/sites", R.default);
  await showRoute(page, baseUrl, "/nodes", R.default);
  await showRoute(page, baseUrl, "/topology", R.default);

  // End-to-end RADIUS simulator
  await titleCard(page, "End-to-End Flow: RADIUS Simulator Traffic", "Running simulated RADIUS authentication traffic to prove live NAC enforcement and visibility", T.section);
  generateRadiusTraffic();
  await sleep(G.afterRadius * 1000);

  // Use case 3
  await titleCard(page, "Use Case 3: Real-Time Access Visibility and Response", "Correlate sessions, endpoint posture, and diagnostics for rapid policy-driven response", T.section);
  await showRoute(page, baseUrl, "/sessions", R.key);
  await showRoute(page, baseUrl, "/endpoints", R.key);
  await showRoute(page, baseUrl, "/posture", R.default);
  await showRoute(page, baseUrl, "/network-devices", R.default);
  await showRoute(page, baseUrl, "/diagnostics", R.default);
  await showRoute(page, baseUrl, "/audit", R.default);

  await titleCard(page, "Why This Demo Wins", "One platform delivering AI governance, hybrid NAC federation, and live response workflows end-to-end", T.outro);

  await context.close();
  await browser.close();

  const videoPath = await video.path();
  console.log(videoPath);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

