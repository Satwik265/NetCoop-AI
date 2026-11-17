# NetCoop AI — PS-Readiness Baseline Audit (Phase 0)

**Date:** November 14, 2026  
**Auditor:** Principal Software Engineer / Autonomous Systems Auditor  
**Repository:** `NetCoop-AI` (`Team_inSANE_MITRA_NetCoop-AI`)  
**Scope:** Read-Only Baseline Audit (Phase 0, Gate 0)  
**Strict Constraint Status:** Zero application source code modifications made. Zero Git commits executed. No branch switching. No remote pushes or syncs. Dependencies untouched.

---

## Executive Summary

This audit establishes the comprehensive technical baseline of **NetCoop AI** (Cooperative Multi-Agent Network Fault Diagnosis Platform) prior to any Phase 1 code modifications. The platform demonstrates sophisticated design and robust foundational architecture, including a LangGraph-driven state machine, standardized `AgentEnvelope` schemas, circuit breaker-backed agent mediation, and an interactive React/ReactFlow dashboard.

However, the audit has identified critical vulnerabilities, architectural gaps, and presentation risks across the Problem Statement (PS) evaluation rubrics:
1. **Single-Domain "Multi-Agent" Flaw (Accuracy & Orchestration):** 8 of the 12 fault correlation checkers (including link congestion, weak Wi-Fi, Ethernet faults, and hardware failures) evaluate evidence from only `telemetry_agent`, setting sufficiency to `True` without cross-validating topology, configuration, or logs.
2. **Security Vulnerabilities (Code Quality & Robustness):** Unauthenticated ingestion and remediation routes exist in `api/main.py`; agent and gateway servers configure `allow_origins=["*"]` with `allow_credentials=True`; and upstream `origin/main` has diverged with a hardcoded secret bypass for Render deployments.
3. **Frontend Provenance & Fallback Risks (Usability & Interoperability):** The dashboard silently simulates successful human-in-the-loop (HITL) remediation approvals when the backend fails, displays mock envelopes while reporting `isSampleData: false`, and omits two active backend agents (`classifier_agent` and `wifi_services_agent`) from the ReactFlow topology visualization.
4. **Environment & Testing Blocker (Code Quality):** The active `.venv` (Python 3.13.15) lacks the declared `dev` dependencies (`pytest`, `pytest-asyncio`, `hypothesis`), preventing automated test suite execution without a package installation step.

---

## Section 1: Branch, HEAD, and Working-Tree Safety Snapshot

### 1.1 Git Status & Commit History
* **Current Working Directory:** `D:\NetCoop-AI\Team_inSANE_MITRA_NetCoop-AI`
* **Active Branch:** `fix/ps-readiness-p0`
* **Current HEAD:** `77deb6034e5110c54cf7063fea63fc0c923d3409`
* **Working Tree State:** Clean (no tracked files modified or staged).
* **Untracked Files:** `uv.lock` (pre-existing, user-owned, preserved untouched).
* **Git Commit Log (Last 5):**
  * `77deb60` (HEAD -> fix/ps-readiness-p0, docs/readme-final): `docs: remove 5-minute judge demo script section from README`
  * `c259e83`: `docs: final README polish`
  * `919c49d` (origin/docs/readme-final): `fix(interop): route all API diagnoses through the gateway; never fabricate zero telemetry`
  * `a3f931b`: `docs: correct calibration, protocol and agent-count wording; disable make readme`
  * `b470c5c`: `docs: restore protocol spec, verify interop via API, remove personal email`

### 1.2 Comparison with Remote `origin/main` (`9e9753cbe8d8cfcb9ea896ddea49464bb6c6536f`)
Comparison between the active branch `fix/ps-readiness-p0` (`77deb60`) and remote `origin/main` (`9e9753c`, which merged PR #17 containing commit `1a96a9c`) revealed critical branch divergence:
* **Render Secret Bypass in `origin/main`:** In `origin/main`, `netcoop/core/auth.py` was modified to include:
  ```python
  is_render = os.getenv("RENDER") == "true" or os.getenv("RENDER_INSTANCE_ID") is not None
  if is_render:
      return "render-cloud-demo-signing-secret-key-2026-netcoop-ai-hackathon"
  ```
* **Active Branch Security Posture:** On `fix/ps-readiness-p0`, this insecure hardcoded secret fallback is **NOT present**. The active branch strictly enforces `ValueError` if the secret is weak, shorter than 32 characters, or using the default key in non-dev environments.
* **Preservation Decision:** The strict, secure implementation on `fix/ps-readiness-p0` must be preserved. The Render backdoor must NOT be introduced.

### 1.3 Execution Toolchain & Environment
* **Host Operating System:** Windows 11 Pro / Server (PowerShell)
* **Host Python:** `3.14.3`
* **Package Managers:** `uv 0.12.17`, `pip 26.2`, `npm 12.0.1`
* **Node.js:** `v24.15.0`
* **Project Virtual Environment:** `D:\NetCoop-AI\Team_inSANE_MITRA_NetCoop-AI\.venv` (Python `3.13.15`)
* **Installed Packages in `.venv`:** `fastapi==0.162.7`, `sqlmodel==0.0.50`, `sqlalchemy==2.1.8`, `langgraph==1.2.22`, `scikit-learn==1.9.1`, `numpy==2.5.4`, `pydantic==2.14.3`, `uvicorn==0.54.0`, `netcoop-ai==1.0.0` (editable).
* **Missing Test Packages:** `pytest`, `pytest-asyncio`, `hypothesis` (specified under `[project.optional-dependencies] dev` in `pyproject.toml`).

---

## Section 2: Repository and Stack Inventory

### 2.1 Package Layout and Facade Architecture
The repository uses a dual-layer architectural pattern:
1. **Canonical Package (`netcoop/`):** Contains the primary implementations:
   * `netcoop/core/`: Schemas (`envelope.py`), correlation engine (`correlation.py`), evidence scoring (`evidence.py`), normalizer (`normalizer.py`), auth (`auth.py`).
   * `netcoop/orchestrator/`: State graph (`graph.py`), agent mediator (`mediator.py`), conflict resolver (`conflict_resolver.py`), consensus engine (`consensus.py`).
   * `netcoop/agents/`: Domain agent implementations (`telemetry_agent.py`, `topology_agent.py`, `config_agent.py`, `log_agent.py`, `synthesizer_agent.py`, `classifier_agent.py`, `wifi_services_agent.py`, `server.py`).
   * `netcoop/storage/`: SQLite database models and persistence (`db.py`).
   * `netcoop/remediation/`: Action engine and blast radius mitigation (`engine.py`, `blast_radius.py`).
   * `netcoop/reporting/`: Incident report generator (`builder.py`).
2. **Top-Level Compatibility Facades:**
   * `core/__init__.py`, `orchestrator/__init__.py`, `storage/__init__.py`, `remediation/__init__.py`: Dynamic forwarders that inject `netcoop.<pkg>.<mod>` into `sys.modules`.
   * **Deviation:** Top-level `agents/` (`agents/base.py`, `agents/config_agent.py`, `agents/log_agent.py`, `agents/synthesizer_agent.py`, `agents/server.py`), `api/main.py`, and `gateway/api.py` are distinct physical source files rather than simple facade forwarders.

### 2.2 Frontend Stack (`dashboard/`)
* **Framework:** React 18.2.0 with TypeScript 5.2.2
* **Build Tool:** Vite 5.2.0
* **Styling:** TailwindCSS 3.4.3, Lucide React icons 0.368.0
* **Graph Visualization:** `@xyflow/react` / `reactflow 11.11.4`
* **State Management:** Custom React hooks (`useWebSocket`, `useStreamingEvents`)
* **Dependency Status:** `node_modules` present on disk.

### 2.3 Evaluation and Testing Assets
* **Evaluation Framework:** `eval/run_eval.py`, `eval/evaluator.py`, `eval/matrix_runner.py`
* **Test Suites:** 33 test files located under `tests/` (unit, integration, property-based, chaos).
* **Synthetic Scenarios:** 12 primary scenarios under `eval/scenarios/` (`link_congestion.json`, `bgp_route_leak.json`, `dns_resolution_failure.json`, `dhcp_exhaustion.json`, `switch_cpu_overload.json`, `intermittent_loss.json`, `firewall_misconfig.json`, `vlan_mismatch.json`, `stp_loop.json`, `optical_degradation.json`, `upstream_cascade.json`, `normal_operation.json`).

---

## Section 3: PS Traceability Matrix

The platform was mapped against the six evaluation pillars specified in the Agentic AI Hackathon problem statement:

| Evaluation Rubric | Weight | Implementation Components | Test Verification | Compliance Status | Identified Deficiencies & Risks |
| :--- | :---: | :--- | :--- | :---: | :--- |
| **1. Interoperability** | 30% | `netcoop/core/envelope.py`, `gateway/api.py`, `gateway/adapters/organizer_adapter.py`, `netcoop/core/normalizer.py` | `tests/test_interop_contract.py`, `tests/test_gateway.py` | **High** | Multi-vendor normalizer supports Cisco IOS, Junos, Arista EOS, Linux syslog. RFC 5424/3164 compliant. |
| **2. Accuracy & Root Cause** | 25% | `netcoop/core/correlation.py`, `netcoop/core/evidence.py`, `netcoop/core/calibration.py` | `tests/test_correlation.py`, `eval/run_eval.py` | **Moderate / Risk** | **Critical Defect:** 8 of 12 correlation checkers only verify `telemetry_agent`. Lack of mandatory multi-agent cross-validation. Benchmark artifact (`benchmark_latest.json`) outdated. |
| **3. Orchestration & Collaboration** | 15% | `netcoop/orchestrator/graph.py`, `netcoop/orchestrator/mediator.py`, `netcoop/orchestrator/conflict_resolver.py` | `tests/test_graph.py`, `tests/test_mediator.py` | **High** | LangGraph cyclic graph with consensus voting, mediator fan-out, and conflict resolution matrix. |
| **4. Robustness & Fault Tolerance** | 15% | `netcoop/orchestrator/mediator.py` (CircuitBreaker), `netcoop/core/auth.py` | `tests/test_circuit_breaker.py`, `tests/test_chaos.py` | **High** | Circuit breaker trips after 2 failures (60s cooldown); fail-closed offline handling emits `insufficient_evidence` without crashing. |
| **5. Usability & Operability** | 10% | `dashboard/src/App.tsx`, `dashboard/src/components/*`, `netcoop/cli/main.py` | Manual UI verification, `tests/test_cli.py` | **Moderate / Risk** | **Deceptive Fallback:** UI silently creates fake successful HITL approvals on backend 500/timeout; mock envelopes display while `isSample: false`; 2 agents omitted from topology. |
| **6. Code Quality & Security** | 5% | `pyproject.toml`, `api/main.py`, `netcoop/storage/db.py`, `.github/workflows/` | Type checking, SQLite migrations | **Low / Warning** | Unauthenticated `/api/ingest`, `/api/remediation/pending`, `/api/remediation/actions`; CORS `*` + credentials; missing `pytest` in venv; missing `LICENSE`. |

---

## Section 4: Verified Architecture and Request Flow

The execution paths were traced across three primary entry points:

```
[External Sources: Syslog / Telemetry / Vendor APIs]
                         │
                         ▼
             [Gateway: POST /api/ingest] (gateway/api.py)
                         │ (OrganizerAdapter Normalization)
                         ▼
            [Standardized AgentEnvelope]
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
[CLI: netcoop diagnose]        [REST API: POST /api/diagnose] (api/main.py)
        └────────────────┬────────────────┘
                         ▼
        [LangGraph State Machine Engine] (netcoop/orchestrator/graph.py)
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
[Telemetry Agent] [Topology Agent]  [Config / Log Agents]
  (Port 8001)       (Port 8002)       (Ports 8003-8008)
        └────────────────┬────────────────┘
                         ▼ (Circuit-Breaker Dispatched Mediator)
        [Conflict Resolver & Consensus Engine] (netcoop/orchestrator/conflict_resolver.py)
                         │
                         ▼
        [Correlation Engine & Calibrator] (netcoop/core/correlation.py)
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
[SQLite Storage & Audit Log]    [WebSocket Streaming Timeline]
  (netcoop/storage/db.py)         (dashboard /ws/timeline)
```

### 4.1 Request Flow Details
1. **Ingestion & Normalization:** Ingestion requests arrive via `gateway/api.py` (`POST /ingest` or `/api/ingest`), where `OrganizerAdapter` validates headers and transforms raw multi-vendor payloads into immutable `AgentEnvelope` models.
2. **Orchestrator Execution:** In `netcoop/orchestrator/graph.py`, the LangGraph `StateGraph` initializes a `DiagnosisState`. Nodes execute sequentially:
   `ingest` $\rightarrow$ `route_agents` $\rightarrow$ `wait_for_evidence` $\rightarrow$ `conflict_resolution` $\rightarrow$ `synthesize_diagnosis` $\rightarrow$ `recommend_actions` $\rightarrow$ `audit_log`.
3. **Agent Mediation:** The `AgentMediator` dispatches HTTP POST requests to agent services (ports 8001–8008). If agents are unreachable, the circuit breaker opens after 2 failures, returning degraded fallback envelopes.
4. **Correlation & Calibration:** The `CorrelationEngine` evaluates rule-based and Bayesian confidence metrics, applying Platt/Isotonic scaling calibration (`calibration_curve_v1.json`).
5. **Persistence & Remediation:** Results are written to SQLite via SQLModel (`SessionRecord`, `EvidenceRecord`, `AuditRecord`), and proposed actions enter the HITL remediation queue (`remediation_actions`).

---

## Section 5: Multi-Agent Evidence Trace — Concrete Scenario (`link_congestion.json`)

To evaluate the reality of multi-agent collaboration, `eval/scenarios/link_congestion.json` was traced through the correlation engine.

### 5.1 Scenario Payload
* **Target Interface:** `HundredGigE0/0/0/1` (Edge-Core-Router-1)
* **Metrics:** 98.4% egress utilization, 4,821 packet drops/sec, buffer queue depth 94%.
* **Agents Targeted:** Telemetry, Topology, Config.

### 5.2 Critical Vulnerability: Single-Domain Reliance
Inspection of `_check_link_congestion` in `netcoop/core/correlation.py` (lines 140–164) reveals:
```python
def _check_link_congestion(self, domain_map: dict[str, list[AgentEnvelope]]) -> CorrelationResult | None:
    telemetry_envs = domain_map.get("telemetry_agent", [])
    if not telemetry_envs:
        return None

    # ... metric evaluations ...
    
    return CorrelationResult(
        fault_type=FaultType.LINK_CONGESTION,
        root_cause=f"Link congestion detected on {matched_device}:{matched_interface}...",
        final_confidence=0.92,
        is_sufficient=True,
        required_evidence_domains=["telemetry_agent"],      # <--- SINGLE DOMAIN
        provided_evidence_domains=["telemetry_agent"],      # <--- SINGLE DOMAIN
        corroborating_findings=findings,
        conflicting_findings=[],
        evidence_chain=matched_envelopes,
    )
```

### 5.3 Audit Impact & Analysis
1. **False Multi-Agent Claim:** Although the platform claims "cooperative multi-agent diagnosis," `_check_link_congestion` requires and checks **only** `telemetry_agent`. If `topology_agent` or `config_agent` report contradictory or corroborating evidence, it is completely ignored.
2. **Prevalence across Checkers:** 8 of the 12 correlation checkers in `correlation.py` exhibit this exact flaw:
   * `_check_link_congestion`: `telemetry_agent` only.
   * `_check_weak_wifi`: `telemetry_agent` only.
   * `_check_ethernet_fault`: `telemetry_agent` only.
   * `_check_dns_failure`: `telemetry_agent` only.
   * `_check_dhcp_failure`: `telemetry_agent` only.
   * `_check_cpu_overload`: `telemetry_agent` only.
   * `_check_upstream_cascade`: `telemetry_agent` only.
   * `_check_hardware_failure`: `telemetry_agent` only.
3. **Public Contract Exposure:** In `README.md` and `docs/contract.md`, the published link-congestion output explicitly states:
   ```json
   "evidence_sources": ["telemetry_agent"],
   "recommended_actions": []
   ```
   This exposes the single-agent dependency directly to hackathon judges evaluating the rubric's "Multi-Agent Collaboration" (15%) and "Accuracy" (25%) criteria.

---

## Section 6: Data Provenance and Mock/Fallback Findings

A rigorous audit of frontend and backend data flows uncovered six critical provenance risks:

### 6.1 Dashboard Mock Envelopes Marked as Non-Sample Data (`App.tsx`)
In `dashboard/src/App.tsx` (lines 28–36):
```typescript
const [envelopes, setEnvelopes] = useState<AgentEnvelope[]>(MOCK_ENVELOPES);
const [isSampleData, setIsSampleData] = useState(false);
```
* **Defect:** `envelopes` begins populated with pre-baked mock envelopes, but `isSampleData` is initialized to `false`. Until a live WebSocket event triggers an update, the UI displays synthetic mock data as if it were live system output.

### 6.2 Deceptive Fallback on HITL Decision Submit (`HitlApprovalQueue.tsx`)
In `dashboard/src/components/HitlApprovalQueue.tsx` (lines 142–170):
```typescript
} catch (err) {
  // Demo fallback - simulate success so judge demo is never blocked by a backend hitch
  const fallbackItem: DecisionLogItem = {
    id: `decision-fallback-${Date.now()}`,
    action_id: selectedAction.id,
    session_id: selectedAction.session_id,
    mode: selectedMode,
    operator: 'operator (demo)',
    status: `hitl_${selectedMode}`,
    rationale: rationale.trim() || `Approved via HITL demo fallback (${selectedMode})`,
    timestamp: new Date().toISOString(),
  };
  setDecisionLog(prev => [fallbackItem, ...prev]);
  toast(`Action ${selectedAction.id.slice(0, 8)} approved (${selectedMode}) [demo]`, 'success');
  onClose();
}
```
* **Defect:** When the backend endpoint `/api/remediation/decide` fails (e.g., 500 error, network timeout, unauthorized), the UI catches the error, synthesizes a fake successful approval item, adds it to the decision log, displays a green success toast, and closes the modal.
* **Risk:** This directly violates production safety standards and obscures backend failures during demonstrations.

### 6.3 Deceptive Session Resume Fallback (`SessionListResume.tsx`)
In `dashboard/src/components/SessionListResume.tsx` (lines 80–94):
```typescript
} catch {
  // Fallback demo session so the resume UI works even if backend is offline
  onSelectSession({
    session_id: sessionId,
    created_at: new Date(Date.now() - 120_000).toISOString(),
    status: 'diagnosed',
    confidence: 0.94,
    root_cause: `Edge link congestion detected on interface HundredGigE0/0/0/1...`,
    isSample: true,
  });
}
```
* **Defect:** If the session resume API fails, the component injects a hardcoded synthetic diagnosis with `confidence: 0.94`.

### 6.4 Omission of Active Agents from Topology Graph (`AgentGraph.tsx`)
In `dashboard/src/components/AgentGraph.tsx` (lines 40–110):
* The `AGENT_METADATA` table defines exactly 7 agent nodes: Gateway, Orchestrator, Telemetry, Topology, Config, Log, Synthesizer.
* **Defect:** The backend runs 9 agents, including `classifier_agent` (port 8007) and `wifi_services_agent` (port 8008). These two agents are completely missing from the interactive ReactFlow canvas.

### 6.5 Fail-Closed Offline Orchestration
When running `netcoop.cli.main:main` or `run_diagnosis` offline without local background agents on ports 8001–8008:
* Mediator HTTP calls fail as expected.
* Circuit breakers open after 2 attempts.
* Orchestrator gracefully returns `fault_type: "insufficient_evidence"`, `confidence: 0.0`.
* **Verdict:** Fail-closed backend behavior is genuine and structurally robust.

### 6.6 Outdated Benchmark Artifact (`benchmark_latest.json`)
* `eval/results/benchmark_latest.json` was generated on `2026-10-31T18:58:30Z`.
* It records `normal_operation` F1 score as **0.0%**.
* On November 1, commit `3c84ccf` (`feat(eval): resolve normal operation benign classification...`) fixed the underlying benign classification logic, but `benchmark_latest.json` was never regenerated, leaving a published 0.0% F1 metric in the repository.

---

## Section 7: Test and Build Baseline with Exact Results

### 7.1 Test Suite Status
* **Execution Attempt:** `python -m pytest` in `.venv`.
* **Result:** `D:\NetCoop-AI\Team_inSANE_MITRA_NetCoop-AI\.venv\Scripts\python.exe: No module named pytest`
* **Root Cause:** The virtual environment contains runtime dependencies only. Test dependencies (`pytest>=8.0.0`, `pytest-asyncio>=0.23.0`, `hypothesis>=6.98.0`) declared in `pyproject.toml` were not installed.
* **Test Inventory:** 33 test files exist in `tests/`:
  * Core: `test_correlation.py`, `test_evidence.py`, `test_envelope.py`, `test_normalizer.py`, `test_calibration.py`.
  * Orchestration: `test_graph.py`, `test_mediator.py`, `test_conflict_resolver.py`, `test_consensus.py`, `test_circuit_breaker.py`.
  * Integration: `test_api.py`, `test_gateway.py`, `test_cli.py`, `test_interop_contract.py`, `test_e2e.py`.
  * Quality & Robustness: `test_property_based.py`, `test_chaos.py`, `test_blast_radius.py`.

### 7.2 Frontend Build Status
* Directory `dashboard/node_modules` exists on disk.
* Scripts in `dashboard/package.json`:
  * `npm run build`: `tsc && vite build`
  * `npm run lint`: `eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0`

---

## Section 8: Security and Deployment Risks

### 8.1 Unauthenticated Sensitive Endpoints in `api/main.py`
Audit of `api/main.py` revealed that while `/api/diagnose` and `/api/remediation/decide` require `current_user: User = Depends(get_current_active_user)`, several sensitive routes have no authentication:
1. **Line 332 (`POST /api/ingest`):** Completely open. Allows any unauthenticated caller on the network to inject raw telemetry into the platform.
2. **Line 2011 (`GET /api/remediation/pending`):** Completely open. Exposes all pending remediation actions and network vulnerability data.
3. **Line 2030 (`GET /api/remediation/actions`):** Completely open. Exposes full action history.

### 8.2 Insecure CORS Configuration
In both `agents/server.py` (line 27) and `gateway/api.py` (line 34):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,     # <--- INSECURE COMBINATION
    allow_methods=["*"],
    allow_headers=["*"],
)
```
* **Vulnerability:** Standard browsers reject responses with `Access-Control-Allow-Credentials: true` when `Access-Control-Allow-Origin: *`. In production, this creates both a CORS misconfiguration and potential cross-origin credential leakage.

### 8.3 Environment Configuration Inconsistency
* In `netcoop/config.py`: `Settings.environment` reads from `ENVIRONMENT`.
* In `netcoop/core/auth.py` and `is_demo_mode_allowed()`: Checks `os.getenv("NETCOOP_ENV", settings.environment)`.
* This discrepancy leads to silent configuration drift between deployment configurations.

### 8.4 Missing LICENSE File
* `README.md` features an Apache-2.0 license badge.
* However, no `LICENSE` file exists in the repository root (`Test-Path LICENSE` returns `False`).

---

## Section 9: Prioritized Findings Matrix (P0 / P1 / P2)

### P0: Critical (Safety, Rubric Integrity, Hard Failures)
1. **P0-1: Mandatory Multi-Agent Corroboration:** Update `netcoop/core/correlation.py` so that fault correlation checkers (specifically link congestion, Wi-Fi, Ethernet, and hardware) require and evaluate evidence from multiple agent domains (`telemetry_agent` + `topology_agent` or `config_agent` or `log_agent`) before declaring `is_sufficient=True`.
2. **P0-2: Security Hardening on API Routes:** Apply `Depends(get_current_active_user)` to `POST /api/ingest`, `GET /api/remediation/pending`, and `GET /api/remediation/actions` in `api/main.py`.
3. **P0-3: CORS Remediation:** Remove `allow_credentials=True` when `allow_origins=["*"]`, or restrict origins to configured hosts in `agents/server.py` and `gateway/api.py`.
4. **P0-4: Dev Dependencies Installation:** Install `pytest`, `pytest-asyncio`, and `hypothesis` into `.venv` to allow test execution.

### P1: Major (Transparency, UI Fidelity, Architectural Cleanliness)
1. **P1-1: Remove Deceptive UI Fallbacks:** Replace the silent fake-success catch block in `HitlApprovalQueue.tsx` with a proper error toast and retry action; clearly mark any offline simulation with a prominent "SIMULATED / OFFLINE" banner.
2. **P1-2: Fix Initial Sample Data Flag:** Initialize `isSampleData` to `true` if `MOCK_ENVELOPES` are present in `App.tsx`, and toggle to `false` only upon receiving live WebSocket telemetry.
3. **P1-3: Complete Agent Graph Nodes:** Add `classifier_agent` (8007) and `wifi_services_agent` (8008) to `dashboard/src/components/AgentGraph.tsx`.
4. **P1-4: Unify Environment Variables:** Align `NETCOOP_ENV` and `ENVIRONMENT` in `netcoop/config.py` and `netcoop/core/auth.py`.

### P2: Minor (Documentation, Hygiene, Metrics Refresh)
1. **P2-1: Regenerate Benchmark Results:** Run `eval/run_eval.py` to refresh `eval/results/benchmark_latest.json` so that `normal_operation` reflects the post-Nov 1 benign classification fix.
2. **P2-2: Add Missing LICENSE File:** Add `LICENSE` (Apache-2.0) to repository root.
3. **P2-3: Reconcile Documentation Claims:** Update `README.md` test metrics to match the actual 33 test files.

---

## Section 10: Unknowns Requiring Human Decision (Gate 0 Review)

Before proceeding to **Phase 1: Implementation & Remediation**, the following architectural decisions require confirmation:

1. **Remote Branch Divergence (`origin/main` vs `fix/ps-readiness-p0`):**
   * *Finding:* `origin/main` commit `1a96a9c` introduced a hardcoded JWT secret fallback when `RENDER` is set.
   * *Recommendation:* **Reject the hardcoded secret.** Maintain strict cryptographic validation and require explicit `NETCOOP_JWT_SECRET` in all environments.
   * *Decision Needed:* Confirm rejection of the Render secret bypass.

2. **Multi-Agent Corroboration Thresholds in Correlation Checkers:**
   * *Finding:* Correlation checkers currently accept single-domain evidence for 8 fault types.
   * *Recommendation:* Require at least 2 distinct domain envelopes (e.g. Telemetry + Topology for Link Congestion; Telemetry + Log for Hardware/Interface failure). If only single-domain evidence is present, return `is_sufficient=False` with status `provisional`.
   * *Decision Needed:* Approve multi-agent corroboration requirement.

3. **HITL Dashboard Error Behavior on Network / API Failure:**
   * *Finding:* `HitlApprovalQueue.tsx` simulates success on error.
   * *Recommendation:* Throw visible error notification ("API Error: Remediation decision could not be persisted. Ensure backend is running.") and keep modal open for retry. If demo mode is explicitly enabled via URL flag (`?demo=true`), show a yellow badge "DEMO SIMULATION".
   * *Decision Needed:* Confirm error handling design.

4. **Approval to Install Dev Dependencies in `.venv`:**
   * *Command:* `uv pip install --python "D:\NetCoop-AI\Team_inSANE_MITRA_NetCoop-AI\.venv" "pytest>=8.0.0" "pytest-asyncio>=0.23.0" "hypothesis>=6.98.0"`
   * *Decision Needed:* Approve execution of this installation in Phase 1.

---

**END OF BASELINE AUDIT REPORT**  
*Gate 0: Review and sign-off required prior to commencing Phase 1.*
