# NetCoop AI Cross-Team System Contract (v1.0.0)

This contract defines the strict inter-process boundaries, network endpoints, communication formats, and responsibilities agreed upon by all three team members (Member A, Member B, and Member C).

---

## 1. Team Responsibilities and Allocation

| Team Member | Subsystem Ownership | Branch | Key Deliverables |
| :--- | :--- | :--- | :--- |
| **Member A** (Integrator & Lead) | Orchestrator, Core Protocol, State Graph, Replay, CI/CD | `main` | LangGraph state machine, mediator, conflict resolution, SQLite event log, `netcoop replay`, integration merges |
| **Member B** (Specialist Agents) | Specialist Domain Agents (Isolated Processes) | `feat/agents` | Telemetry Agent, Topology Agent, Config Agent, Log Agent, Synthesizer Agent, agent FastAPI runners, health probes |
| **Member C** (Gateway & UI) | Gateway Ingestion, REST API, WebSocket & Dashboard | `feat/gateway`, `feat/ui` | `/ingest` pipeline, organizer adapters, WebSocket event streaming, React minimalist dashboard, CLI commands |

---

## 2. Process Architecture and Port Allocations

Specialist agents and subsystems run as decoupled, isolated micro-services communicating exclusively over HTTP loopback endpoints:

| Service / Agent | Process Type | Host Binding | HTTP Port | Primary Endpoints |
| :--- | :--- | :--- | :---: | :--- |
| **Orchestrator & API** | FastAPI / Uvicorn | `127.0.0.1` | **8000** | `GET /api/health`<br/>`POST /api/diagnose`<br/>`GET /api/incidents`<br/>`WS /ws/events` |
| **Telemetry Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8001** | `GET /health`<br/>`POST /process` |
| **Topology Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8002** | `GET /health`<br/>`POST /process` |
| **Config Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8003** | `GET /health`<br/>`POST /process` |
| **Log Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8004** | `GET /health`<br/>`POST /process` |
| **Synthesizer Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8005** | `GET /health`<br/>`POST /process` |
| **Gateway Ingestion** | FastAPI / Uvicorn | `127.0.0.1` | **8006** | `GET /health`<br/>`POST /ingest` |

---

## 3. Inter-Agent Communication Contract

1. **Zero In-Process Sharing**: Agents run in distinct OS processes with dedicated Python interpreters. No direct method calls, shared memory, or shared mutable variables are allowed.
2. **Wire Format**: All inter-agent requests and responses are transmitted as HTTP `POST` requests to `/process` with Content-Type `application/json`.
3. **Envelope Schema**: Every message envelope must strictly validate against `schemas/envelope.json`.
4. **Header Integrity**:
   - `correlation_id`: Preserved unchanged throughout the entire diagnosis lifecycle.
   - `sender` and `recipient`: Must match the enum roles in `core.envelope.AgentRole`.
   - `message_type`: Must match one of `telemetry_dispatch`, `finding_submission`, `inquiry_request`, `inquiry_response`, `synthesis_submission`, `protocol_error`.
5. **Timeouts and Fallbacks**:
   - The Orchestrator enforces a 5.0-second HTTP timeout per agent turn.
   - An unresponsive agent produces an error envelope logged to SQLite and marks that domain as unresponsive in the final diagnostic report.

---

## 4. Ingestion Gateway Contract (`POST /ingest`)

- **Input Payload**: Arbitrary raw JSON dictionary containing telemetry lists, topology graphs, config diffs, or external Colab generator feeds.
- **Normalization Guarantees**:
  - Aliases mapped to canonical fields (e.g. `loss` -> `packet_loss_pct`, `util` -> `link_utilization_pct`).
  - Unit normalization: Bandwidth to `bps`, time duration to `ms`, memory/volume to `bytes`, ratios to `percent`.
  - Sanitization of `null`, `NaN`, `Inf` values to zero baselines or valid fallback bounds.
  - Timestamps parsed, converted to ISO 8601 UTC, and sorted chronologically.
- **Output**: Validated canonical incident payload conforming strictly to `schemas/telemetry.json`.

---

## 5. WebSocket Event Streaming Contract (`WS /ws/events`)

The Orchestrator and API broadcast diagnostic events to connected dashboard clients in real-time over WebSocket.

### Event Format

```json
{
  "event_type": "envelope_logged",
  "correlation_id": "inc-20261031-001",
  "timestamp_utc": "2026-10-31T14:00:00.000Z",
  "sender": "telemetry_agent",
  "recipient": "orchestrator",
  "message_type": "finding_submission",
  "summary": "Reported 2 observations, 1 hypothesis (confidence: 0.85)",
  "envelope": { ... }
}
```

### Supported `event_type` Values
- `diagnosis_started`: Ingestion completed, graph execution initiated.
- `envelope_logged`: An `AgentEnvelope` has been transmitted and logged to SQLite.
- `conflict_detected`: Conflict resolver identified competing hypotheses.
- `inquiry_turn`: Targeted cross-inquiry sent to resolve ambiguity.
- `diagnosis_completed`: Synthesis finished and Unified Diagnostic Report saved.
- `remediation_simulated`: Simulated remediation action executed with safety gates.

---

## 6. Zero Hallucination and Evidence Standard

1. **No Guessing**: A root cause hypothesis may only be accepted when supporting observations satisfy domain correlation rules.
2. **Ambiguity / Missing Telemetry**: If prerequisite corroboration is absent or uncertainty is high, status must be `insufficient_evidence`.
3. **Simulated Remediation Only**: All remediation commands are simulated and sandboxed; real network hardware is never contacted.

