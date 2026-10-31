# NetCoop AI: Hackathon Demonstration and Evaluation Guide

## 1. Quick Start

### 1.1 Running Tests
Execute the comprehensive test suite covering protocol contracts, individual agents, LangGraph orchestration, conflict resolution, benchmark scenarios, and Hypothesis property-based fuzzing:
```bash
pytest tests/ -v
```

### 1.2 Starting the Platform
Launch the backend and dashboard:
```bash
uvicorn netcoop.main:app --host 127.0.0.1 --port 8000
```
Open your browser at `http://localhost:8000` to interact with the minimalist monochrome dashboard.

---

## 2. Command-Line Interface (CLI) Walkthrough

### 2.1 Diagnosing Scenarios via CLI
Diagnose the Path MTU Mismatch benchmark scenario:
```bash
netcoop diagnose --file data/scenarios/01_mtu_mismatch_blackhole.json
```
Output displays:
- Rich formatted Diagnostic Report with 95% confidence
- Corroborated evidence table combining TelemetryAgent and ConfigAgent findings
- Recommended simulated remediation action with target device and commands

### 2.2 Verifying the Hard Rule: Insufficient Evidence
Diagnose the sparse telemetry scenario:
```bash
netcoop diagnose --file data/scenarios/05_insufficient_evidence_sparse.json
```
Output displays:
- Status: `insufficient_evidence`
- Probable Cause: `None`
- Uncertainty Score: High (>0.50)
- Explicit listing of missing prerequisite corroboration domains

### 2.3 Inspecting Auditable Envelope Traces
Print the inter-agent envelope message trace for an incident:
```bash
netcoop envelopes trace inc-mtu-001
```

### 2.4 Simulating Remediation with Safety Gates
Approve and simulate configuration rollback:
```bash
netcoop remediate approve inc-mtu-001 act-mtu-spine-01
```

---

## 3. Web Dashboard Walkthrough

Navigate to `http://localhost:8000`:

1. **Scenario Selection**:
   - Use the top dropdown to select `01_mtu_mismatch_blackhole.json`.
   - Click `Run Diagnosis`.
2. **Overview Tab**:
   - Review Incident Header (Status, Confidence, Affected Nodes, Executive Summary).
   - Inspect Corroborated Evidence Chains with exact SI units and severity badges.
   - Inspect Interactive Topology Graph with affected node highlights.
3. **Envelope Trace Tab**:
   - Inspect the complete inter-agent message envelope trace.
   - Filter by sender role (Telemetry, Topology, Config, Log, Synthesizer).
   - Click any envelope row to expand the full JSON schema payload.
4. **Remediation Gateway**:
   - Review proposed configuration commands and rollback scripts.
   - Click `Approve & Simulate Execution` to verify simulated execution.
5. **Protocol Specification Tab**:
   - View formal JSON schemas for `envelope`, `telemetry`, `diagnostic_report`, and `remediation_plan`.

---

## 4. Model Context Protocol (MCP) Integration

External agentic AI assistants can connect to NetCoop AI via MCP:
```bash
netcoop mcp-serve
```
Exposed MCP tools:
- `diagnose_network`: Runs full multi-agent diagnostic cycle on provided payload.
- `get_incident_status`: Retrieves report and status for an incident ID.
- `get_envelope_trace`: Inspects auditable envelope message trace.
- `simulate_remediation`: Executes simulated remediation with safety gates.
- `get_protocol_schema`: Inspects formal JSON schemas.

