# NetCoop-AI Dashboard Architecture & RBAC Specification

This document details the frontend architecture, Role-Based Access Control (RBAC) model, component hierarchy, and integration points for the NetCoop-AI enterprise dashboard.

---

## 1. Architectural Principles

1. **Unified Enterprise Shell**: Rather than creating eight fragmented applications, NetCoop-AI employs a unified enterprise layout with a persistent role-aware sidebar, dynamic route switcher, and shared state context.
2. **Formal Role-Based Access Control (RBAC)**: All administrative, diagnostic, and remediation actions are guarded by granular permissions defined in `dashboard/src/rbac/roles.ts`. Privilege checks are enforced at both navigation and component action layers.
3. **Resilient Real-Time Event Streaming**: The UI connects to `/ws/events` via the `useWebSocket` hook, featuring exponential backoff auto-reconnection (1s–10s delay) and message ID deduplication.
4. **Strict Monochrome Design System**: Follows a focused monochrome palette (`#FAFAF9` / `#0F0F10`, `#FFFFFF` / `#161618`, slate `#475569`, status accents `#5E7A6A`, `#A08A5B`, `#9A5B5B`). Zero emojis across all UI surfaces, code, and documentation.
5. **Remediation Sandboxing & Safety**: All remediation proposals carry explicit blast radius calculations and rollback scripts. All command executions are confined to simulated sandboxes with non-dismissible safety notices.

---

## 2. RBAC Permission Matrix

The platform defines nine granular permissions mapped across eight specialized enterprise roles:

| Permission Identifier | Description |
| :--- | :--- |
| `view_incidents` | Read access to active incident queues and telemetry streams |
| `edit_incident_assignments` | Ability to update incident handlers, assign triage leads, and update notes |
| `view_diagnostic_evidence` | Inspection access to raw multi-agent evidence ledgers and envelope traces |
| `create_remediation_proposals`| Ability to author or configure simulated remediation actions |
| `approve_remediation` | Privilege to issue human-in-the-loop (HITL) approvals with written rationale |
| `execute_remediation` | Privilege to trigger simulated sandbox execution and rollback commands |
| `view_audit_records` | Read access to immutable SQLite remediation decision records and hashes |
| `manage_platform_settings` | Configuration of microservices, checkpointing, and engine parameters |
| `manage_network_devices` | Device inventory manipulation, interface provisioning, and maintenance scheduling |

### Role to Permission Mapping

| Role | Department | Assigned Permissions | Primary Dashboard |
| :--- | :--- | :--- | :--- |
| **NOC Operator** (`noc_operator`) | Network Operations Center | `view_incidents`, `edit_incident_assignments`, `view_diagnostic_evidence` | `NocView` |
| **Network Engineer** (`network_engineer`) | Infrastructure Engineering | `view_incidents`, `view_diagnostic_evidence`, `create_remediation_proposals`, `execute_remediation` | `EngineerView` |
| **Network Administrator** (`network_admin`) | Systems & Infrastructure | `view_incidents`, `manage_network_devices`, `view_audit_records` | `AdminView` |
| **Security Analyst** (`security_analyst`) | SecOps & Cyber Defense | `view_incidents`, `view_diagnostic_evidence`, `view_audit_records` | `SecurityView` |
| **IT Manager** (`it_manager`) | Leadership & Service Delivery | `view_incidents`, `view_audit_records` | `ItManagerView` |
| **Platform Administrator** (`platform_admin`) | Site Reliability Engineering | `view_incidents`, `manage_platform_settings`, `view_audit_records` | `PlatformAdminView` |
| **Auditor / Compliance** (`auditor`) | Governance, Risk & Compliance | `view_incidents`, `view_diagnostic_evidence`, `view_audit_records` | `AuditorView` |
| **Helpdesk Operator** (`helpdesk`) | User Support & Service Desk | `view_incidents`, `edit_incident_assignments` | `HelpdeskView` |

---

## 3. Dedicated Role Workspaces

### 1. NOC Operator (`dashboard/src/components/views/NocView.tsx`)
- **Focus**: High-tempo situational awareness and triage.
- **Key Capabilities**:
  - Live campus fabric health KPI banner.
  - Real-time unacknowledged alert queue with severity filtering (`critical`, `warning`, `info`).
  - Single-click alert acknowledgement and escalation assignment.
  - Active incident card linking directly to deep technical investigation.

### 2. Network Engineer (`dashboard/src/components/views/EngineerView.tsx`)
- **Focus**: In-depth root-cause analysis and remediation design.
- **Key Capabilities**:
  - Technical telemetry matrix comparing observed vs nominal metrics (link utilization, queue drops, packet loss, RTT jitter).
  - Transparent AI evidence corroboration chain detailing contributing specialist agents.
  - Direct shortcuts to launch simulated remediation and review HITL approval queues.

### 3. Network Administrator (`dashboard/src/components/views/AdminView.tsx`)
- **Focus**: Infrastructure lifecycle, device inventory, and change control.
- **Key Capabilities**:
  - Real-time inventory table of campus devices (`spine-01`, `spine-02`, `leaf-01`, `leaf-02`, `leaf-03`, `wan-01`, `ap-hostel-04`) fetched from `/api/devices`.
  - Maintenance window scheduler with reason tracking and device status inspection.
  - Configuration change viewer comparing staged vs running configurations.

### 4. Security Analyst (`dashboard/src/components/views/SecurityView.tsx`)
- **Focus**: Telemetry-grounded threat detection and forensic investigation.
- **Key Capabilities**:
  - Threat indicator breakdown for security-relevant network anomalies (traffic microbursts, ACL drop surges, MTU blackholing).
  - Telemetry corroboration ledger linking observed anomalies to security indicators.
  - Forensic scope analyzer isolating impacted subnets and egress gateways.

### 5. IT Manager (`dashboard/src/components/views/ItManagerView.tsx`)
- **Focus**: Executive SLAs, service availability, and team performance metrics.
- **Key Capabilities**:
  - High-level KPIs: Fabric availability %, Mean Time to Detect (MTTD), Mean Time to Resolve (MTTR), and remediation success rate.
  - Incident category breakdown quantifying technical debt across failure modes.
  - Recurring incident pattern drill-down highlighting repeat operational pain points.

### 6. Platform Administrator (`dashboard/src/components/views/PlatformAdminView.tsx`)
- **Focus**: AI platform health, microservice reliability, and persistence monitoring.
- **Key Capabilities**:
  - Real-time microservice status grid monitoring all eight engine ports (`8000`–`8008`) fetched from `/api/platform/status`.
  - SQLite database connectivity, WAL mode verification, and checkpoint persistence statistics.
  - Model Context Protocol (MCP) transport status and active WebSocket client count.

### 7. Auditor / Compliance Officer (`dashboard/src/components/views/AuditorView.tsx`)
- **Focus**: Immutable audit trail verification and regulatory compliance.
- **Key Capabilities**:
  - Strictly read-only compliance vault ensuring zero mutation capability.
  - Complete history of operator remediation decisions fetched from `/api/remediation/logs`.
  - Side-by-side inspection of proposed target commands vs validated rollback commands with mandatory written rationales.
  - One-click cryptographic audit export (JSON).

### 8. Helpdesk Operator (`dashboard/src/components/views/HelpdeskView.tsx`)
- **Focus**: End-user ticket triage, communication, and handoff.
- **Key Capabilities**:
  - User support tickets queue with priority filtering and location mapping.
  - Plain-language client advisory bulletin generator converting network telemetry into non-technical user notices.
  - Escalation workflow to Tier-2 Infrastructure Engineering with diagnostic handoff notes.
  - Non-privileged execution guardrails preventing accidental or unauthorized infrastructure mutations.

---

## 4. Platform Subsystems & Navigation Tree

```
App.tsx (Root Shell)
├── Sidebar.tsx
│   ├── Role Selector (8 roles with persistent localStorage)
│   ├── Active Role Permissions Breakdown
│   ├── Role Dashboards Navigation (NOC, Engineer, Admin, Security, IT Mgr, Platform, Auditor, Helpdesk)
│   ├── Diagnostic Platform Navigation (Workspace, Topology, Report, Interop, Proof)
│   ├── Guarded Remediation Navigation (HITL, Simulated Remediation, Sessions, MCP)
│   └── Live WebSocket Connection Status Badge
│
├── ScenarioPicker.tsx (Universal Scenario Selector, Run Diagnosis, Chaos Fuzzer)
│   └── DataQualityBanner.tsx (Health score, format, typed validation error ledger)
│
├── Main Viewport (Conditional on activeNav & RBAC permissions)
│   ├── Role Views (NocView, EngineerView, AdminView, SecurityView, ItManagerView, PlatformAdminView, AuditorView, HelpdeskView)
│   ├── Consensus Workspace
│   │   ├── AgentGraph.tsx (React Flow node canvas with animated message edges)
│   │   ├── StreamingTimeline.tsx (Envelope message timeline with scrub playback)
│   │   └── CorrelationPanel.tsx (Hypotheses score bars, confidence arc, inquiries)
│   ├── TopologyView.tsx (Network topology map, blast radius highlights, device status)
│   ├── ReportCard.tsx (12-section unified diagnostic report card)
│   ├── InteroperabilityInspector.tsx (Gateway raw vs canonical side-by-side)
│   ├── ProofTab.tsx (Benchmark evaluation, confusion matrix, calibration, ablation)
│   ├── HitlApprovalQueue.tsx (Pending actions, rationale input, approve/reject/modify)
│   ├── SimulatedRemediationView.tsx (Before/after metric charts, sandbox label)
│   ├── SessionListResume.tsx (Saved checkpoints and pause/resume control)
│   └── McpGallery.tsx (Model Context Protocol tool catalog and client config)
│
└── EnvelopeSlideOver.tsx (Formatted envelope JSON wire inspector)
```

---

## 5. The 12-Section Unified Diagnostic Report

The `ReportCard.tsx` component renders diagnostic outputs formatted strictly according to the twelve enterprise sections:

1. **Incident ID & Status**: Incident identifier, network fabric, status badge, execution latency, and JSON/Markdown export controls.
2. **Executive Summary**: High-level synopsis with one-click clipboard copy.
3. **Incident Scope & Topology Footprint**: Affected network, devices, interfaces, and timestamps.
4. **Network Health Metrics**: Quantitative metric readings extracted from evidence with observed units.
5. **Detected Anomalies**: Critical and warning events flagged across telemetry streams.
6. **Root Cause Analysis & Causal Chain**: Primary failure mode and ordered multi-stage causal sequence.
7. **Supporting Evidence Ledger**: Tabular expandable evidence ledger with domain, agent, entity, metric, and severity filters.
8. **Multi-Agent Consensus & Arbitration**: Participating agent ledger and arbitrated hypothesis conflicts.
9. **Confidence Calibration & Uncertainty**: Calibrated confidence score, uncertainty percentage, conformal prediction set ($1 - \alpha = 0.90$), and missing prerequisite evidence constraints.
10. **Remediation Recommendations**: Simulated remediation action catalog with risk levels, target devices, and proposed CLI commands.
11. **Verification Criteria & Rollback Recovery Plan**: Pre-validated rollback scripts and post-remediation verification checklist.
12. **Complete Audit Trail**: Cryptographic provenance, model and ruleset metadata, SQLite WAL storage status, and regulatory sign-off.

---

## 6. Verification & Build Integrity

- **Frontend Compilation**: Built using TypeScript 5 and Vite 5 (`npm run build`), resulting in zero compiler warnings and zero type errors.
- **Backend Test Suite**: Verified against all 156 unit, integration, and scenario tests (`python -m pytest tests/ -q`).
- **Design System Invariant**: Pure monochrome aesthetics with zero emojis across all code, tests, and documentation.

