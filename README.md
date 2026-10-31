# NetCoop AI

NetCoop AI is a distributed, multi-agent network fault diagnosis and simulated remediation platform engineered for the IIT Bhubaneswar Agentic AI Grand Finale.

## Overview

NetCoop AI diagnoses complex network outages and degradations by orchestrating five specialized agents that communicate strictly through a versioned message envelope protocol. The system is designed around offline determinism: diagnostic reasoning, multi-point evidence correlation, conflict resolution, and simulated remediation are computed locally without relying on external cloud APIs or LLMs.

An optional Gemini integration provides supplementary plain-language executive summaries when `GEMINI_API_KEY` is present, but degrades gracefully to deterministic offline templates when absent.

---

## 1. Hackathon Scoring Alignment

| Evaluation Pillar | Hackathon Weight | NetCoop AI Implementation |
| :--- | :---: | :--- |
| **Interoperability & Protocol Design** | 30% | Versioned JSON schema envelope (v1.0.0), strict Pydantic v2 validation, explicit field semantics, SI unit enforcement, zero internal state leakage between agents (`docs/protocol.md`, `schemas/envelope.json`). |
| **Diagnostic Accuracy & Evidence Quality** | 25% | Multi-evidence correlation graph, timestamp alignment, and strict enforcement of `status: "insufficient_evidence"` when criteria are unmet. |
| **Orchestration & Conflict Resolution** | 15% | LangGraph state graph with supervisory mediation, targeted peer inquiry passes, dynamic hypothesis ranking, and deterministic conflict arbitration matrix (`netcoop/orchestrator/`). |
| **Robustness to Missing / Incompatible Data** | 15% | Clock skew normalization, unit converter layer (bps/Kbps/Mbps/Gbps, ms/us), fuzzy device alias mapping, and Hypothesis property-based fuzzing (`netcoop/core/normalizer.py`, `tests/test_robustness_hypothesis.py`). |
| **Innovation, Usability, Extensibility** | 10% | Model Context Protocol (MCP) server for external AI tools, Human-in-the-Loop (HITL) approval gates, pause/resume persistence via SQLite, simulated remediation sandbox, twin UI (Web Dashboard + Typer CLI). |
| **Code Quality, Docs, and Demo** | 5% | 100% typed codebase, docstrings, structured logging, zero emojis, unified JSON output report, comprehensive setup scripts, reproducible tests, Docker Compose. |

---

## 2. Five Collaborating Agents

1. **Telemetry & Metric Analyzer (`telemetry_agent`)**: Analyzes queue drops, optical receiver power (dBm), Frame Check Sequence (FCS) / CRC errors, jitter, and interface counters.
2. **Topology & Routing Analyzer (`topology_agent`)**: Analyzes link-state graph, BGP neighbor states, OSPF LSDB changes, and Spanning Tree root bridge/loop anomalies.
3. **Configuration & Audit Analyzer (`config_agent`)**: Analyzes commit diffs, path MTU disparities, trunk VLAN pruning, and BPDU filter misconfigurations.
4. **Anomaly Correlation & Log Analyzer (`log_agent`)**: Correlates RFC 5424 syslog bursts, BFD neighbor drops, route flap damping penalties, and transceiver DOM alarms.
5. **Root Cause & Synthesis Agent (`synthesizer_agent`)**: Correlates multi-agent evidence chains, resolves conflicting hypotheses, calculates composite confidence, and strictly enforces the insufficient evidence guarantee.

---

## 3. Protocol Envelope (v1.0.0)

Agents communicate exclusively using standard JSON messages conforming to `schemas/envelope.json`:
- `header`: Unique `message_id`, invariant `correlation_id`, ISO 8601 UTC timestamp, sender, recipient, SemVer `schema_version`, and `message_type`.
- `payload`: Network `scope`, factual `observations` with mandatory SI units, inferred `hypotheses` with supporting observation IDs, and cross-agent `inquiries`.
- `context`: Execution round iteration and environment simulation flags.

Detailed protocol semantics, field definitions, unit conversion tables, and error codes are documented in `docs/protocol.md`.

---

## 4. Benchmark Scenarios Suite

NetCoop AI includes 5 reproducible incident datasets in `data/scenarios/`:
1. `01_mtu_mismatch_blackhole.json`: Path MTU size disparity between Leaf-01 (9000B) and Spine-01 (1500B) causing packet drops on jumbo frames.
2. `02_bgp_route_flap_damping.json`: Flapping eBGP link on WAN-01 interface triggering route suppression.
3. `03_optical_crc_degradation.json`: Failing SFP transceiver optic on Core-A to Core-B link (Rx power -19.4 dBm) causing physical CRC errors.
4. `04_stp_split_brain_loop.json`: Accidental BPDU filter configuration on Access-02 trunk port triggering a broadcast storm and 98% CPU utilization.
5. `05_insufficient_evidence_sparse.json`: Sparse, isolated counter anomaly without cross-domain corroboration; strictly returns `status: "insufficient_evidence"`.

---

## 5. Quickstart Guide

### 5.1 Local Installation
```bash
# 1. Clone and enter directory
git clone https://github.com/Satwik265/Team_inSANE_MITRA_NetCoop-AI.git
cd Team_inSANE_MITRA_NetCoop-AI

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\activate  # On Windows
# source .venv/bin/activate  # On Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt
pip install -e .

# 4. Run test suite
pytest tests/ -v
```

### 5.2 Running via Docker Compose
```bash
docker compose up --build
```
The platform will be accessible at `http://localhost:8000`.

### 5.3 Using the CLI
```bash
# Diagnose a scenario
netcoop diagnose --file data/scenarios/01_mtu_mismatch_blackhole.json

# List past incidents
netcoop incidents list

# Inspect auditable envelope message trace
netcoop envelopes trace inc-mtu-001

# Approve and simulate remediation action
netcoop remediate approve inc-mtu-001 act-mtu-spine-01

# Launch Model Context Protocol stdio server
netcoop mcp-serve
```

### 5.4 Using the Web Dashboard
Start the FastAPI server:
```bash
uvicorn netcoop.main:app --port 8000
```
Open `http://localhost:8000` in your web browser. The dashboard adheres to the strict minimalist monochrome visual palette:
- Background: `#0F0F10`, Surface: `#161618`, Border: `#2A2A2D`, Text: `#EDEDEA`, Accent: `#475569`.
- Status Indicators: OK `#5E7A6A`, Warning `#A08A5B`, Critical `#9A5B5B`.
- Typography: Inter and JetBrains Mono.

---

## 6. Safety Guarantee

NetCoop AI strictly enforces the safety invariant: **never touch real hardware**. All remediation actions are simulated in a sandbox environment with blast-radius boundaries, automated rollback command generation, and Human-in-the-Loop operator gates.
