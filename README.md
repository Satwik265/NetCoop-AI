# NetCoop AI

NetCoop AI is a distributed, multi-agent network fault diagnosis and simulated remediation platform engineered for the IIT Bhubaneswar Agentic AI Grand Finale.

## Overview

NetCoop AI diagnoses complex network outages and degradations by orchestrating five specialized agents that communicate strictly through a versioned message envelope protocol. The system is designed around offline determinism: diagnostic reasoning, multi-point evidence correlation, conflict resolution, and simulated remediation are computed locally without relying on external cloud APIs or LLMs.

An optional Gemini integration provides supplementary plain-language executive summaries when `GEMINI_API_KEY` is present, but degrades gracefully to deterministic offline templates when absent.

---

## 1. Hackathon Scoring Alignment

| Evaluation Pillar | Hackathon Weight | NetCoop AI Implementation |
| :--- | :---: | :--- |
| **Interoperability & Protocol Design** | 30% | Versioned JSON schema envelope (v1.0.0), strict Pydantic v2 validation, explicit field semantics, SI unit enforcement, zero internal state leakage between agents (`docs/protocol.md`, `schemas/envelope.json`, `gateway/adapters/organizer_adapter.py`). |
| **Diagnostic Accuracy & Evidence Quality** | 25% | Multi-evidence correlation graph, timestamp alignment, 19 ground-truth benchmark scenarios, and strict enforcement of `status: "insufficient_evidence"` when criteria are unmet. |
| **Orchestration & Conflict Resolution** | 15% | LangGraph state graph with supervisory mediation, message bus pub/sub, targeted peer inquiry passes, dynamic hypothesis ranking, and deterministic conflict arbitration matrix (`orchestrator/`, `core/bus.py`). |
| **Robustness to Missing / Incompatible Data** | 15% | Clock skew normalization, unit converter layer (bps/Kbps/Mbps/Gbps, ms/us), fuzzy device alias mapping, and Hypothesis property-based fuzzing (`core/normalizer.py`, `gateway/adapters/organizer_adapter.py`, `tests/test_robustness_hypothesis.py`). |
| **Innovation, Usability, Extensibility** | 10% | Model Context Protocol (MCP) server for external AI tools, Human-in-the-Loop (HITL) approval gates, pause/resume persistence via SQLite, simulated remediation sandbox, twin UI (Web Dashboard + Typer CLI), seeded generator with chaos knobs (`data/generator.py`, `mcp_server/`, `dashboard/`, `cli/`). |
| **Code Quality, Docs, and Demo** | 5% | 100% typed codebase, docstrings, structured logging, zero emojis, unified JSON output report, comprehensive setup scripts, reproducible tests, Makefile, Docker Compose. |

---

## 2. Five Collaborating Agents

1. **Telemetry & Metric Analyzer (`telemetry_agent`)**: Analyzes queue drops, optical receiver power (dBm), Frame Check Sequence (FCS) / CRC errors, jitter, and interface counters.
2. **Topology & Routing Analyzer (`topology_agent`)**: Analyzes link-state graph, BGP neighbor states, OSPF LSDB changes, and Spanning Tree root bridge/loop anomalies.
3. **Configuration & Audit Analyzer (`config_agent`)**: Analyzes commit diffs, path MTU disparities, trunk VLAN pruning, and BPDU filter misconfigurations.
4. **Anomaly Correlation & Log Analyzer (`log_agent`)**: Correlates RFC 5424 syslog bursts, BFD neighbor drops, route flap damping penalties, and transceiver DOM alarms.
5. **Root Cause & Synthesis Agent (`synthesizer_agent`)**: Correlates multi-agent evidence chains, resolves conflicting hypotheses, calculates composite confidence, and strictly enforces the insufficient evidence guarantee.

---

## 3. Repository Architecture & Scaffold

```text
Team_inSANE_MITRA_NetCoop-AI/
├── agents/             # Five specialized domain agents
├── core/               # Envelope protocol, message bus, evidence scoring, normalizer, report
├── gateway/            # Ingress adapter mapping external/organizer telemetry to NetCoop schema
│   └── adapters/
│       └── organizer_adapter.py
├── orchestrator/       # LangGraph state graph, conflict resolution engine, mediator
├── mcp_server/         # Model Context Protocol (MCP) stdio server
├── api/                # FastAPI REST & WebSocket endpoints
├── cli/                # Typer + Rich CLI interface (gen, diagnose, incidents, envelopes, remediate)
├── dashboard/          # React + Vite + TypeScript + Tailwind minimalist monochrome dashboard
├── data/               # Seeded synthetic telemetry generator and ground-truth scenario library
│   ├── generator.py
│   └── scenarios/
│       ├── manifest.json
│       ├── normal_operation.json
│       ├── link_congestion.json
│       ├── weak_wifi_signal.json
│       ├── ethernet_interface_fault.json
│       ├── dns_failure.json
│       ├── dhcp_failure.json
│       ├── device_cpu_overload.json
│       ├── upstream_failure_cascade.json
│       ├── ambiguous_multi_fault.json
│       ├── insufficient_data.json
│       └── interop_*.json (9 interoperability failure variants)
├── docs/               # Technical specs (data_and_testing.md, protocol.md, architecture.md, etc.)
├── schemas/            # Formal JSON Schemas (envelope, telemetry, diagnostic_report, remediation_plan)
├── tests/              # 43 reproducible tests (unit, scenarios, Hypothesis fuzzing, adapter)
├── Makefile            # Setup, demo, test, eval, assets, run, clean
├── Dockerfile          # Multi-stage Docker build
├── docker-compose.yml  # Standalone containerized deployment
├── pyproject.toml      # Package setup and build configuration
└── README.md
```

---

## 4. Synthetic Telemetry Generator & Chaos Knobs

The synthetic network telemetry generator (`data/generator.py`) generates deterministic, seeded time-series records across 20 parameters per device and link:
- **Topology Zones**: Hostel Wi-Fi, Department Ethernet, Lecture Halls, Core/Distribution/Access.
- **Device Types**: Routers, Switches, Wireless Access Points, Hosts.
- **Parameters**: Latency, Jitter, Packet Loss %, Throughput, Bandwidth, Link Utilization %, CPU %, Memory %, Queue Drops, Interface Errors, Link Flaps, Wi-Fi RSSI (dBm), Wi-Fi Retransmissions %, DNS Resolution Time, DNS Failure %, DHCP Failure %.
- **Reproducibility**: Seed-governed PRNG guarantees exact mathematical replication across runs.
- **Chaos Knobs**:
  - `--noise`: Gaussian continuous perturbation factor (0.0 to 1.0)
  - `--drop-rate`: Missing sample drop rate (0.0 to 1.0)
  - `--staleness`: Observation timestamp offset in seconds

```bash
# Generate synthetic telemetry via CLI
netcoop gen --scenario link_congestion --seed 42

# Generate with noise and missing samples
netcoop gen --scenario weak_wifi_signal --seed 42 --noise 0.2 --drop-rate 0.1 --output sample.json
```

---

## 5. Quickstart Guide

### 5.1 Using Makefile
```bash
# Setup environment and install dependencies
make setup

# Run complete test suite (43 passed)
make test

# Run 19-scenario evaluation benchmark (100% accuracy)
make eval

# Run sample CLI demo
make demo

# Start local server on port 8000
make run
```

### 5.2 Running via Docker Compose
```bash
docker compose up --build
```
Access the dashboard at `http://localhost:8000`.

### 5.3 CLI Commands
```bash
# Generate synthetic scenario
netcoop gen --scenario link_congestion --seed 42

# Diagnose an incident
netcoop diagnose --file data/scenarios/link_congestion.json

# Inspect auditable envelope message trace
netcoop envelopes trace inc-link-congestion-42

# Approve and simulate remediation action
netcoop remediate approve inc-link-congestion-42

# Start Model Context Protocol stdio server
netcoop mcp-serve
```

---

## 6. Safety Guarantee

NetCoop AI strictly enforces the safety invariant: **never touch real hardware**. All remediation actions are simulated in a sandbox environment with blast-radius boundaries, automated rollback command generation, and Human-in-the-Loop operator gates.
