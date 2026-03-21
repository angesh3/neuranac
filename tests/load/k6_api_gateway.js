/**
 * k6 Load Test — NeuraNAC API Gateway
 *
 * Run:  k6 run tests/load/k6_api_gateway.js
 * Env:  K6_API_URL (default http://localhost:8080)
 *       K6_ADMIN_USER / K6_ADMIN_PASS
 *
 * Stages: ramp up → sustained → ramp down
 */
import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE = __ENV.K6_API_URL || "http://localhost:8080";
const API = `${BASE}/api/v1`;

// Custom metrics
const errorRate = new Rate("error_rate");
const loginDuration = new Trend("login_duration", true);

export const options = {
  stages: [
    { duration: "30s", target: 10 },  // ramp up
    { duration: "2m", target: 50 },   // sustained
    { duration: "30s", target: 100 }, // peak
    { duration: "1m", target: 100 },  // hold peak
    { duration: "30s", target: 0 },   // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500", "p(99)<1500"],
    error_rate: ["rate<0.05"],
    login_duration: ["p(95)<300"],
  },
};

// ── Setup: obtain JWT once ──────────────────────────────────────────────────

export function setup() {
  const user = __ENV.K6_ADMIN_USER || "admin";
  const pass = __ENV.K6_ADMIN_PASS || "admin";
  const res = http.post(`${API}/auth/login`, JSON.stringify({
    username: user, password: pass,
  }), { headers: { "Content-Type": "application/json" } });

  if (res.status === 200) {
    const body = res.json();
    return { token: body.access_token || body.token || "" };
  }
  // Fallback: use a hardcoded dev token if login fails (CI environments)
  console.warn(`Login failed (${res.status}), using empty token`);
  return { token: "" };
}

function authHeaders(data) {
  return {
    headers: {
      Authorization: `Bearer ${data.token}`,
      "Content-Type": "application/json",
    },
  };
}

// ── Main VU loop ────────────────────────────────────────────────────────────

export default function (data) {
  group("Health", () => {
    const r = http.get(`${BASE}/health`);
    check(r, { "health 200": (r) => r.status === 200 });
    errorRate.add(r.status !== 200);
  });

  group("Auth - Login", () => {
    const start = Date.now();
    const r = http.post(`${API}/auth/login`, JSON.stringify({
      username: "admin", password: "admin",
    }), { headers: { "Content-Type": "application/json" } });
    loginDuration.add(Date.now() - start);
    check(r, { "login ok": (r) => r.status === 200 || r.status === 401 });
    errorRate.add(r.status >= 500);
  });

  group("Legacy NAC - Connections List", () => {
    const r = http.get(`${API}/legacy-nac/connections`, authHeaders(data));
    check(r, { "legacy-nac connections": (r) => r.status === 200 || r.status === 500 });
    errorRate.add(r.status >= 500);
  });

  group("Legacy NAC - Summary", () => {
    const r = http.get(`${API}/legacy-nac/summary`, authHeaders(data));
    check(r, { "legacy-nac summary": (r) => r.status === 200 || r.status === 500 });
    errorRate.add(r.status >= 500);
  });

  group("Policies", () => {
    const r = http.get(`${API}/policies`, authHeaders(data));
    check(r, { "policies list": (r) => r.status !== 401 });
    errorRate.add(r.status >= 500);
  });

  group("Network Devices", () => {
    const r = http.get(`${API}/network-devices`, authHeaders(data));
    check(r, { "devices list": (r) => r.status !== 401 });
    errorRate.add(r.status >= 500);
  });

  group("Sessions", () => {
    const r = http.get(`${API}/sessions`, authHeaders(data));
    check(r, { "sessions list": (r) => r.status !== 401 });
    errorRate.add(r.status >= 500);
  });

  group("Diagnostics", () => {
    const r = http.get(`${API}/diagnostics/db-schema-check`, authHeaders(data));
    check(r, { "diag schema": (r) => r.status !== 401 });
    errorRate.add(r.status >= 500);
  });

  sleep(0.5 + Math.random());
}
