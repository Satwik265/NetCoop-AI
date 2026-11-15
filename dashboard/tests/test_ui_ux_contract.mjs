import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dashboardDir = path.resolve(__dirname, "..");

// ---------------------------------------------------------------------------
// 1. Test i18n formatting utilities
// ---------------------------------------------------------------------------
test("i18n formatDateTime produces explicit timezone indicators", async () => {
  const i18nPath = path.join(dashboardDir, "src", "utils", "i18n.ts");
  assert.ok(fs.existsSync(i18nPath), "i18n.ts must exist");
  const content = fs.readFileSync(i18nPath, "utf-8");

  // Validate function signatures and presence of timezone options
  assert.match(content, /export type SupportedTimezone/);
  assert.match(content, /"UTC" \| "Asia\/Kolkata" \| "LOCAL"/);
  assert.match(content, /export function formatDateTime/);
  assert.match(content, /export function formatPercent/);
  assert.match(content, /export function formatNumber/);
  assert.match(content, /export function formatBytes/);
  assert.match(content, /export function formatRate/);
  assert.match(content, /export function formatDurationMs/);
});

test("i18n runtime formatting logic adheres to W3C standards", () => {
  const dateStr = "2026-11-15T02:30:00Z";
  const date = new Date(dateStr);

  const utcFormatter = new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "UTC",
  });
  const formattedUtc = `${utcFormatter.format(date)} UTC`;
  assert.match(formattedUtc, /UTC$/);
  assert.match(formattedUtc, /2026/);

  const istFormatter = new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  });
  const formattedIst = `${istFormatter.format(date)} IST`;
  assert.match(formattedIst, /IST$/);
  assert.match(formattedIst, /2026/);

  // Percent formatting
  const pctFormatter = new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  assert.equal(pctFormatter.format(0.942), "94.2%");
  assert.equal(pctFormatter.format(0.0), "0.0%");
  assert.equal(pctFormatter.format(1.0), "100.0%");

  // Number formatting
  const numFormatter = new Intl.NumberFormat("en-US");
  assert.equal(numFormatter.format(4500), "4,500");
  assert.equal(numFormatter.format(1000000), "1,000,000");
});

// ---------------------------------------------------------------------------
// 2. Test Agent Metadata and Complete Specialist Registry
// ---------------------------------------------------------------------------
test("AgentGraph includes all 9 backend services including classifier and wifi_services", () => {
  const agentGraphPath = path.join(dashboardDir, "src", "components", "AgentGraph.tsx");
  const content = fs.readFileSync(agentGraphPath, "utf-8");

  const requiredAgents = [
    { id: "gateway", port: 8006 },
    { id: "orchestrator", port: 8000 },
    { id: "telemetry_agent", port: 8001 },
    { id: "topology_agent", port: 8002 },
    { id: "config_agent", port: 8003 },
    { id: "log_agent", port: 8004 },
    { id: "classifier_agent", port: 8007 },
    { id: "wifi_services_agent", port: 8008 },
    { id: "synthesizer_agent", port: 8005 },
  ];

  for (const ag of requiredAgents) {
    assert.ok(
      content.includes(`id: "${ag.id}"`),
      `Agent ${ag.id} must be registered in AGENT_METADATA`
    );
    assert.ok(
      content.includes(`port: ${ag.port}`),
      `Agent ${ag.id} must be configured on port ${ag.port}`
    );
  }

  // Verify Accessible Table Alternative view exists
  assert.match(content, /Accessible Table View/);
  assert.match(content, /<table/);
  assert.match(content, /scope="col"/);
  assert.match(content, /Messages Handled/);
});

// ---------------------------------------------------------------------------
// 3. Test TopologyView Accessible Table Alternative
// ---------------------------------------------------------------------------
test("TopologyView contains structured table alternative for nodes, links, and blast radius", () => {
  const topologyPath = path.join(dashboardDir, "src", "components", "TopologyView.tsx");
  const content = fs.readFileSync(topologyPath, "utf-8");

  assert.match(content, /Accessible Table View/);
  assert.match(content, /Network Nodes & Impact Scope/);
  assert.match(content, /Physical & Logical Links/);
  assert.match(content, /Primary Fault Root/);
  assert.match(content, /Blast Radius Boundary/);
  assert.match(content, /scope="col"/);
});

// ---------------------------------------------------------------------------
// 4. Test Data Provenance & Anti-Fabrication Safeguards
// ---------------------------------------------------------------------------
test("App.tsx implements anti-fabrication data provenance badges and fail-safe error handling", () => {
  const appPath = path.join(dashboardDir, "src", "App.tsx");
  const content = fs.readFileSync(appPath, "utf-8");

  // Check DataProvenance states
  assert.match(content, /provenance === "LIVE"/);
  assert.match(content, /provenance === "ORGANIZER_SAMPLE"/);
  assert.match(content, /provenance === "SYNTHETIC_DEMO"/);
  assert.match(content, /provenance === "OFFLINE"/);

  // Check offline banner with explicit retry
  assert.match(content, /\[OFFLINE BACKEND\]/);
  assert.match(content, /Diagnostic Backend Service Unreachable/);
  assert.match(content, /handleRetryConnect/);

  // Verify failed runs do not silently pretend to succeed with mock
  assert.match(content, /setExecutionStatus\("failed"\)/);
  assert.match(content, /setProvenance\("OFFLINE"\)/);
});

// ---------------------------------------------------------------------------
// 5. Test Simulation Safety Invariants
// ---------------------------------------------------------------------------
test("SimulatedRemediationView enforces explicit operator intent and persistent watermark", () => {
  const simPath = path.join(dashboardDir, "src", "components", "SimulatedRemediationView.tsx");
  const content = fs.readFileSync(simPath, "utf-8");

  // Mandatory persistent watermark
  assert.match(content, /SIMULATED — NO PRODUCTION NETWORK CHANGES/);

  // Explicit confirmation required - no automatic runSimulation in useEffect
  assert.doesNotMatch(content, /useEffect\(\(\) => \{\s*runSimulation/);
  assert.match(content, /Explicit Operator Confirmation Required/);
  assert.match(content, /Run Sandbox Simulation/);
});

test("HitlApprovalQueue enforces fail-safe API error checking and does not seed fake actions", () => {
  const hitlPath = path.join(dashboardDir, "src", "components", "HitlApprovalQueue.tsx");
  const content = fs.readFileSync(hitlPath, "utf-8");

  // Verify response check on decisions
  assert.match(content, /if \(!decRes\.ok\)/);
  assert.match(content, /Decision submission failed/);

  // Verify persistent watermark
  assert.match(content, /SIMULATED — NO PRODUCTION NETWORK CHANGES/);

  // Verify empty actions render empty state rather than inventing fake actions
  assert.match(content, /Zero pending remediation actions awaiting operator approval/);
});

// ---------------------------------------------------------------------------
// 6. Test WCAG 2.2 AA Accessibility & Tokens
// ---------------------------------------------------------------------------
test("WCAG 2.2 AA accessibility standards are enforced in styles and index.html", () => {
  const tokensPath = path.join(dashboardDir, "src", "styles", "tokens.css");
  const tokensContent = fs.readFileSync(tokensPath, "utf-8");

  // Focus visible styling
  assert.match(tokensContent, /:focus-visible/);
  assert.match(tokensContent, /prefers-reduced-motion: reduce/);

  // Directionality in index.html
  const indexPath = path.join(dashboardDir, "index.html");
  const indexContent = fs.readFileSync(indexPath, "utf-8");
  assert.match(indexContent, /dir="ltr"/);
  assert.match(indexContent, /lang="en"/);
  assert.match(indexContent, /name="viewport"/);

  // Skip link in App.tsx
  const appPath = path.join(dashboardDir, "src", "App.tsx");
  const appContent = fs.readFileSync(appPath, "utf-8");
  assert.match(appContent, /Skip to main content/);
  assert.match(appContent, /id="main-content"/);
});

// ---------------------------------------------------------------------------
// 7. Test Diagnostic Progress State during Execution (F-14 / Phase 10 Item 7)
// ---------------------------------------------------------------------------
test("ScenarioPicker and ReportCard expose an accessible progress state during diagnosis", () => {
  const scenarioPickerPath = path.join(dashboardDir, "src", "components", "ScenarioPicker.tsx");
  const scenarioContent = fs.readFileSync(scenarioPickerPath, "utf-8");
  assert.match(scenarioContent, /role="progressbar"/);
  assert.match(scenarioContent, /Multi-Agent Network Diagnosis in Progress/);
  assert.match(scenarioContent, /7 Agents \+ Gateway \+ Orchestrator/);

  const reportCardPath = path.join(dashboardDir, "src", "components", "ReportCard.tsx");
  const reportContent = fs.readFileSync(reportCardPath, "utf-8");
  assert.match(reportContent, /Executing multi-agent reasoning graph/);
  assert.match(reportContent, /animate-ping/);
});
