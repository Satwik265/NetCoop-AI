# NetCoop AI: Protocol & Contract Change Governance (v1.0.0)

This document formalizes the operational procedure for proposing, evaluating, and adopting changes to the NetCoop AI inter-agent contract, wire protocols, schema definitions, and microservice interfaces.

---

## 1. Core Principle: Mandatory Three-Member Consensus

No individual developer or subsystem owner (Member A, Member B, or Member C) may unilaterally modify:
- `/schemas/*.json` (Envelope, Telemetry, Diagnostic Report, Remediation Plan)
- Port allocations or microservice endpoints (`/core/config.py`)
- Wire envelope serialization models (`core/envelope.py`)
- Gateway ingestion interfaces (`/gateway/api.py`, `OrganizerAdapter`)
- WebSocket event payloads (`/ws/events`)

**Every proposed contract modification requires unanimous agreement from all three team members before any code is merged into `main`.**

---

## 2. Team Member Review Responsibilities

| Role | Domain Authority | Contract Review Focus |
| :--- | :--- | :--- |
| **Member A** (Integrator & Lead) | Orchestrator, Core Protocol, State Graph | Verifies backward compatibility, LangGraph state machine stability, conflict resolution determinism, and SQLite audit logging integrity. |
| **Member B** (Specialist Agents) | Domain Specialist Microservices (Ports 8001–8005) | Verifies that domain agents can parse modified fields without regression, that SI units remain unambiguous, and that evidence scoring is unaffected. |
| **Member C** (Gateway & UI) | Gateway (Port 8006), REST/WS (Port 8000), Dashboard | Verifies that Gateway adapters correctly normalize external inputs, that WebSocket streamers deliver expected fields, and that dashboard components render without errors. |

---

## 3. Contract Change Workflow

```mermaid
flowchart TD
    A["Step 1: Draft RFC<br/>(docs/rfcs/RFC-NNN.md)"] --> B["Step 2: SemVer Impact Analysis<br/>(Patch, Minor, Major)"]
    B --> C["Step 3: Multi-Process Compatibility Check<br/>(make test across all agents)"]
    C --> D{"Step 4: Consensus Review<br/>(Unanimous A + B + C Approval)"}
    D -- Rejected --> E["Closed or Revised"]
    D -- Approved --> F["Step 5: Feature Branch Implementation<br/>(feat/gateway -> feat/agents -> feat/ui)"]
    F --> G["Step 6: Member A Gatekeeper Merge into main"]
```

### Step 1: Draft RFC
The proposing member creates a markdown RFC in `/docs/rfcs/` specifying:
- **Motivation**: Why the current contract is insufficient.
- **Affected Artifacts**: JSON Schemas, port mappings, or Pydantic models.
- **Proposed Diff**: Exact JSON Schema and model changes.
- **Backward Compatibility Plan**: How existing scenarios and tests continue to function.

### Step 2: SemVer Impact Classification
- **Patch (1.0.x)**: Non-breaking clarifications, comments, docstring updates, or expanded regex aliases in the Gateway adapter.
- **Minor (1.x.0)**: New optional fields in `EnvelopePayload` or new message types that unupdated agents can safely ignore.
- **Major (2.0.0)**: Breaking changes to required fields, modified port assignments, or changed SI units. Requires unanimous agreement and simultaneous branch updates.

### Step 3: Automated Contract Validation
Before review, the proposer must run:
```bash
make test
pytest tests/test_protocol_envelope.py tests/test_agent_http.py tests/test_gateway_api.py -v
```
All schema validation and microservice HTTP tests must pass cleanly.

### Step 4: Three-Way Sign-Off Gate
All three members must record explicit written consensus in the RFC tracking table:

```markdown
| Team Member | Decision | Date | Notes |
| :--- | :---: | :---: | :--- |
| Member A (Lead / Orchestrator) | APPROVED | 2026-10-31 | Verified backward compatibility with LangGraph |
| Member B (Specialist Agents)   | APPROVED | 2026-10-31 | Verified agent parser compatibility |
| Member C (Gateway & UI)        | APPROVED | 2026-10-31 | Verified dashboard and WebSocket format |
```

### Step 5: Implementation and Staged Merge
Once approved:
1. Member C updates `feat/gateway` (adapters and schemas).
2. Member B updates `feat/agents` (agent implementations).
3. Member C updates `feat/ui` (WebSocket streaming and dashboard).
4. Member A verifies tests and merges `feat/gateway`, `feat/agents`, and `feat/ui` sequentially into `main`.

---

## 4. Inviolable Invariants (Non-Negotiable)

1. **Zero Hallucination**: No contract change may allow an agent to declare a definitive diagnosis when corroborating evidence is missing or ambiguous. The status `insufficient_evidence` must remain preserved.
2. **Offline Core Pipeline**: The core multi-agent diagnosis must execute completely offline with zero mandatory internet or LLM dependencies.
3. **Simulated Remediation Only**: All remediation definitions in `schemas/remediation_plan.json` must remain strictly simulated; commands may never be executed on real network interfaces.
4. **Isolated Memory**: Agents must communicate solely through HTTP payloads conforming to `schemas/envelope.json`. In-process memory sharing or shared mutable state is prohibited.
5. **Monochrome Design Tokens**: Any UI or CLI output additions must adhere strictly to the monochrome design tokens (#FAFAF9 / #0F0F10, slate #475569, box.SQUARE, zero emojis).



---

## 5. RFC-004: Orchestrator Checkpointing (Pause/Resume) & Human-in-the-Loop (HITL) Workflow

### 5.1 Motivation & Scope
In production enterprise network operations, automated diagnostics must support checkpoint persistence for long-running investigations, operator pause/resume signals, and Human-in-the-Loop (HITL) approval gates before simulated configuration changes execute.

### 5.2 Feature Flags
Managed in `netcoop/config.py` (and mirrored in `core/config.py`):
- `FEATURE_RESUME: bool = True` (Default enabled for demo/interactive use; when False, orchestrator runs without storing node checkpoints).
- `FEATURE_HITL: bool = True` (Default enabled for demo/interactive use; when False, recommended remediation actions run directly in simulated sandbox without manual operator gating).

### 5.3 REST API Endpoints Specification

#### 1. Signal Diagnosis Pause
- **Endpoint**: `POST /api/orchestrator/pause`
- **Request Body**:
```json
{
  "session_id": "inc-20261031-101",
  "rationale": "Manual inspection requested by Network Operations Center"
}
```
- **Response (200 OK)**:
```json
{
  "session_id": "inc-20261031-101",
  "status": "paused",
  "message": "Diagnostic session inc-20261031-101 marked as paused.",
  "rationale": "Manual inspection requested by Network Operations Center"
}
```

#### 2. Resume Diagnosis from Checkpoint
- **Endpoint**: `POST /api/orchestrator/resume/{session_id}`
- **Response (200 OK)**: Full `UnifiedDiagnosticReport` object conforming to `schemas/diagnostic_report.json`.
- **Response (404 Not Found)**:
```json
{
  "detail": "No checkpoint found for session 'inc-20261031-101'. Cannot resume."
}
```

#### 3. List Session Checkpoints
- **Endpoint**: `GET /api/orchestrator/checkpoints/{session_id}`
- **Response (200 OK)**:
```json
[
  {
    "id": 1,
    "session_id": "inc-20261031-101",
    "node_name": "specialists",
    "iteration": 0,
    "is_paused": false,
    "created_at": "2026-10-31T14:00:00Z",
    "state": {
      "incident_id": "inc-20261031-101",
      "network_id": "campus-lan-01",
      "status": "initialized"
    }
  }
]
```

#### 4. List Pending Remediation Actions
- **Endpoint**: `GET /api/remediation/pending`
- **Response (200 OK)**:
```json
[
  {
    "id": 4,
    "incident_id": "inc-20261031-101",
    "action_id": "act-mtu-harmonize-01",
    "device": "spine-01",
    "commands": [
      "configure terminal",
      "interface et-0/0/1",
      "mtu 9000",
      "commit"
    ],
    "rollback_commands": [
      "configure terminal",
      "interface et-0/0/1",
      "mtu 1500",
      "commit"
    ],
    "risk_level": "medium",
    "status": "pending",
    "approved_by": null,
    "rationale": null,
    "modified_commands": null,
    "simulated_at": null,
    "decision_timestamp": "2026-10-31T14:05:00Z"
  }
]
```

#### 5. List All Remediation Actions
- **Endpoint**: `GET /api/remediation/actions?incident_id={incident_id}&status={status}`
- **Query Parameters**:
  - `incident_id` (string, optional)
  - `status` (string, optional: `pending`, `approved`, `rejected`, `modified`, `simulated_executed`)

#### 6. Approve Remediation Action
- **Endpoint**: `POST /api/remediation/{action_id}/approve`
- **Request Body**:
```json
{
  "operator": "netops_alice",
  "rationale": "Verified MTU mismatch symptoms; approved for simulated execution"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "action_id": "act-mtu-harmonize-01",
  "status": "approved",
  "operator": "netops_alice",
  "rationale": "Verified MTU mismatch symptoms; approved for simulated execution",
  "simulation": {
    "success": true,
    "message": "Successfully simulated remediation action act-mtu-harmonize-01 on spine-01.",
    "executed_commands": [
      "configure terminal",
      "interface et-0/0/1",
      "mtu 9000",
      "commit"
    ],
    "checks": [
      {"check": "Blast radius within bounds", "passed": true},
      {"check": "Rollback procedure defined", "passed": true}
    ]
  }
}
```

#### 7. Reject Remediation Action
- **Endpoint**: `POST /api/remediation/{action_id}/reject`
- **Request Body**:
```json
{
  "operator": "netops_bob",
  "rationale": "Scheduled maintenance window required for spine core changes"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "action_id": "act-mtu-harmonize-01",
  "status": "rejected",
  "operator": "netops_bob",
  "rationale": "Scheduled maintenance window required for spine core changes"
}
```

#### 8. Modify Remediation Action
- **Endpoint**: `POST /api/remediation/{action_id}/modify`
- **Request Body**:
```json
{
  "commands": [
    "configure terminal",
    "interface et-0/0/1",
    "mtu 9216",
    "commit"
  ],
  "operator": "netops_charlie",
  "rationale": "Increased target jumbo frame MTU to 9216 standard"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "action_id": "act-mtu-harmonize-01",
  "status": "modified",
  "modified_commands": [
    "configure terminal",
    "interface et-0/0/1",
    "mtu 9216",
    "commit"
  ],
  "operator": "netops_charlie",
  "rationale": "Increased target jumbo frame MTU to 9216 standard"
}
```

### 5.4 Auditing & Invariants
- **Envelope Audit Trail**: Every operator decision emits an audit log record with `message_type="REMEDIATION_DECISION"`, `sender=operator`, and `recipient="remediation_engine"`.
- **Simulation Sandbox Only**: All commands remain strictly simulated in sandbox test environments. No actual network interface changes occur.
- **Monochrome & Clean Output**: Zero emojis across API responses, CLI logs, and documentation.


---

## 6. RFC-005: In-Memory Remediation Simulation & MCP Extensions

| :

---

### 6.2 MCP Protocol Extensions

The Model Context Protocol server (`netcoop/mcp/server.py`) exposes these exact simulation capabilities through JSON-RPC 2.0 tool invocation:

- `simulate_remediation`: Accepts `incident_id`, `action_id`, and `action_type`.
- `explain_finding`: Returns root cause analysis and evidentiary metric breakdowns for any finding ID.
- `get_telemetry`: Returns recent telemetry windows for specific network nodes.
- `get_topology`: Returns topology graph or gracefully reports `"topology unavailable"`.
- `run_diagnosis`: Runs diagnosis against scenario files, organizer samples, or inline telemetry.
- `list_devices`: Enumerates known devices across all loaded contexts.
- Resources (`scenario://*`, `organizer://*`, `report://latest`).
