# NetCoop AI

NetCoop AI is a distributed, multi-agent network fault diagnosis and simulated remediation platform engineered for the IIT Bhubaneswar Agentic AI Grand Finale.

## Overview

NetCoop AI diagnoses complex campus and data center network outages and degradations by orchestrating seven specialized microservices that communicate strictly through a versioned message envelope protocol. The system is designed around offline determinism: diagnostic reasoning, multi-point evidence correlation, conflict resolution, learned conformal evaluation, and simulated remediation are computed locally without mandatory cloud APIs or LLM dependencies.

An optional Gemini integration provides supplementary plain-language executive summaries when `GEMINI_API_KEY` is present, but degrades gracefully to deterministic offline templates when absent.

---

## 1. Hackathon Scoring Alignment

| Evaluation Pillar | Hackathon Weight | NetCoop AI Implementation |
| :--- | :---: | :--- |
| **Interoperability & Protocol Design** | 30% | Versioned JSON schema envelope (v1.0.0), strict Pydantic v2 validation, explicit field semantics, SI unit enforcement, zero internal state leakage between agents (`docs/protocol.md`, `schemas/envelope.json`, `gateway/adapters/organizer_adapter.py`). |
| **Diagnostic Accuracy & Evidence Quality** | 25% | Multi-evidence correlation graph, timestamp alignment, 21 ground-truth benchmark scenarios (100% accuracy), and strict enforcement of `status: "insufficient_evidence"` when criteria are unmet. |
| **Orchestration & Conflict Resolution** | 15% | LangGraph state graph with supervisory mediation, message bus pub/sub, targeted peer inquiry passes, dynamic hypothesis ranking, and deterministic conflict arbitration matrix (`orchestrator/`, `core/bus.py`). |
| **Robustness to Missing / Incompatible Data** | 15% | Clock skew normalization, unit converter layer (bps/Kbps/Mbps/Gbps, ms/us), fuzzy device alias mapping, and Hypothesis property-based fuzzing (`core/normalizer.py`, `gateway/adapters/organizer_adapter.py`, `tests/test_robustness_hypothesis.py`, `tests/test_chaos.py`). |
| **Innovation, Usability, Extensibility** | 10% | Model Context Protocol (MCP) server for external AI tools, Human-in-the-Loop (HITL) approval gates, pause/resume persistence via SQLite, simulated remediation sandbox, twin UI (Web Dashboard + Typer CLI), seeded generator with chaos knobs (`data/generator.py`, `mcp_server/`, `dashboard/`, `cli/`). |
| **Code Quality, Docs, and Demo** | 5% | 100% typed codebase, docstrings, structured logging, zero emojis, unified JSON output report, comprehensive setup scripts, 125 reproducible tests, Makefile, Docker Compose. |

---

## 2. Seven Collaborating Agents

1. **Telemetry & Metric Analyzer (`telemetry_agent`)**: Analyzes queue drops, optical receiver power (dBm), Frame Check Sequence (FCS) / CRC errors, jitter, and interface counters.
2. **Topology & Routing Analyzer (`topology_agent`)**: Analyzes link-state graph, BGP neighbor states, OSPF LSDB changes, and Spanning Tree root bridge/loop anomalies.
3. **Configuration & Audit Analyzer (`config_agent`)**: Analyzes commit diffs, path MTU disparities, trunk VLAN pruning, and BPDU filter misconfigurations.
4. **Anomaly Correlation & Log Analyzer (`log_agent`)**: Correlates RFC 5424 syslog bursts, BFD neighbor drops, route flap damping penalties, and transceiver DOM alarms.
5. **Root Cause & Synthesis Agent (`synthesizer_agent`)**: Correlates multi-agent evidence chains, resolves conflicting hypotheses, calculates composite confidence, and strictly enforces the insufficient evidence guarantee.
6. **Wi-Fi & Network Services Agent (`wifi_services_agent`)**: Evaluates RSSI/SNR degradation, client density, frame retransmissions, DNS resolution latency, and DHCP lease failures.
7. **Empirical ML Classifier Agent (`classifier_agent`)**: Provides Platt-calibrated empirical predictions, split conformal prediction sets with coverage guarantees, and statistical abstention.

---

## 3. Repository Architecture & Scaffold

```text
Team_inSANE_MITRA_NetCoop-AI/
├── agents/             # Specialist microservice adapters
├── core/               # Envelope protocol, message bus, evidence scoring, normalizer, report
├── gateway/            # Ingress adapter mapping external/organizer telemetry to NetCoop schema
│   └── adapters/
│       ├── field_matcher.py
│       ├── organizer_adapter.py
│       └── unit_inference.py
├── orchestrator/       # LangGraph state graph, conflict resolution engine, mediator
├── mcp_server/         # Model Context Protocol (MCP) stdio server
├── api/                # FastAPI REST & WebSocket endpoints
├── cli/                # Typer + Rich CLI interface (gen, diagnose, incidents, envelopes, remediate)
├── dashboard/          # React + Vite + TypeScript + Tailwind minimalist monochrome dashboard
├── data/               # Seeded synthetic telemetry generator and ground-truth scenario library
│   ├── generator.py
│   ├── heldout_generator.py
│   ├── organizer/
│   │   ├── organizer_generator.py
│   │   └── samples/
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
├── docs/               # Technical specs (contract.md, confidence.md, robustness.md, etc.)
├── schemas/            # Formal JSON Schemas (envelope, telemetry, diagnostic_report, remediation_plan)
├── tests/              # 125 reproducible tests (unit, scenarios, Hypothesis fuzzing, chaos)
├── Makefile            # Setup, demo, test, eval, assets, run, clean
├── Dockerfile          # Multi-stage Docker build
├── docker-compose.yml  # Standalone containerized deployment
├── pyproject.toml      # Package setup and build configuration
└── README.md
```

---

## 4. Quickstart Guide (PowerShell & Cross-Platform)

The core diagnostic pipeline executes 100% offline with zero required API keys.

### 4.1 Setup & Installation

```powershell
# 1. Create and activate Python 3.13 virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Upgrade pip and install package with development/test dependencies
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 4.2 Run Test Suites & Evaluation

```powershell
# Run complete test suite (125 tests passed)
python -m pytest -q

# Run ground-truth evaluation benchmark (21/21 scenarios, 100% accuracy)
python scripts/eval_benchmark.py

# Run chaos and fuzzer tests
python -m pytest tests/test_chaos.py -v
```

### 4.3 Run Demonstrations

```powershell
# Run end-to-end multi-scenario CLI demo
python scripts/demo.py

# Run hackathon organizer format pipeline demo
python scripts/demo_organizer.py --sample hardware_failure
python scripts/demo_organizer.py --sample normal
python scripts/demo_organizer.py --sample latency_spike
```

### 4.4 Start Backend Server & Dashboard

```powershell
# Start FastAPI backend on port 8000
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```
Open `http://localhost:8000` to interact with the monochrome web dashboard.

---

## 5. CLI Commands

```powershell
# Generate synthetic telemetry with chaos knobs
netcoop gen --scenario link_congestion --seed 42 --noise 0.1 --drop-rate 0.05

# Diagnose an incident from scenario file
netcoop diagnose --file data/scenarios/link_congestion.json

# Pause and resume diagnostic session
netcoop pause inc-link-congestion-42
netcoop resume inc-link-congestion-42

# Inspect auditable envelope message trace
netcoop envelopes trace inc-link-congestion-42

# Human-in-the-Loop remediation actions
netcoop approve act-mtu-spine-01 --operator noc_admin --rationale "Verified MTU mismatch"
netcoop reject act-mtu-spine-01 --operator noc_admin --rationale "Maintenance window needed"
netcoop modify act-mtu-spine-01 --cmd "interface et-0/0/1" --cmd "mtu 9216"

# Run Model Context Protocol (MCP) server
netcoop mcp-serve
```

---

## 6. Safety Guarantee

NetCoop AI strictly enforces the safety invariant: **never touch real hardware**. All remediation actions are simulated in a sandbox environment with blast-radius boundaries, automated rollback command generation, and Human-in-the-Loop operator gates.
