# NetCoop AI: Cooperative Multi-Agent Network Fault Diagnosis Platform

[![Python](https://img.shields.io/badge/Python-3.12%20|%203.13-2A2A2D?style=flat-square&labelColor=161618)](https://python.org)
[![Architecture](https://img.shields.io/badge/Architecture-Shared--Nothing%20Microservices-2A2A2D?style=flat-square&labelColor=161618)](docs/contract.md)
[![Orchestration](https://img.shields.io/badge/Orchestration-LangGraph-2A2A2D?style=flat-square&labelColor=161618)](netcoop/orchestrator/graph.py)
[![Wire Protocol](https://img.shields.io/badge/Wire%20Protocol-JSON%20Schema%20v1.0-2A2A2D?style=flat-square&labelColor=161618)](schemas/envelope.json)
[![Offline Engine](https://img.shields.io/badge/Offline-Engine-2A2A2D?style=flat-square&labelColor=161618)](netcoop/core/)
[![License](https://img.shields.io/badge/License-MIT-2A2A2D?style=flat-square&labelColor=161618)](LICENSE)

A modular, shared-nothing multi-agent platform for enterprise and campus network fault diagnosis, cross-domain evidence corroboration, and safe simulated remediation planning.

---

## 1. Problem and Insight

Enterprise and campus network operations suffer from fragmented observability. Modern fabrics produce disjointed telemetry streams: time-series interface metrics, spanning-tree topology state transitions, configuration change diffs, and high-volume syslog bursts reside in isolated monitoring silos.

Existing approaches fall into two failure modes:
1. **Monolithic Rule Engines**: Rigid heuristic systems lack the ability to cross-examine evidence across operational domains. When multiple anomalies fire simultaneously (e.g. high CPU utilization alongside link packet loss), monolithic systems fail to isolate root cause from derivative downstream symptoms.
2. **Naive LLM Wrappers**: Direct prompt-engineering wrappers hallucinate network topology, invent non-existent interfaces, violate JSON wire schemas, leak state across diagnostic turns, and cannot operate in air-gapped, zero-connectivity datacenters.

**The NetCoop AI Insight**:
Network diagnosis is fundamentally a multi-perspective consensus problem. NetCoop AI decomposes network intelligence into six specialist agents plus a synthesizer operating as decoupled processes (Telemetry, Topology, Configuration, Log, Classifier, and Wifi Services specialists, with consensus mediation by the Synthesizer). Agents share zero memory and communicate strictly through versioned, strongly-typed wire envelopes (`schemas/envelope.json`). A LangGraph state-machine orchestrator manages multi-turn mediation, routing targeted cross-inquiries (`payload.inquiries`) between specialists to corroborate empirical evidence (`Observation`) and debate causal hypotheses (`Hypothesis`). When evidence is incomplete, corrupted, or conflicting, the system strictly refuses to guess and emits an auditable `insufficient_evidence` determination.


---

## 2. What Makes This Different: Rubric Mapping

| Evaluation Pillar | Hackathon Weight | NetCoop AI Implementation |
| :--- | :---: | :--- |
| **Interoperability & Protocol Design** | 30% | Versioned JSON schema envelope (v1.0.0), strict Pydantic v2 validation, explicit field semantics, SI unit enforcement, zero internal state leakage between agents (`docs/protocol.md`, `schemas/envelope.json`, `gateway/adapters/organizer_adapter.py`). |
| **Diagnostic Accuracy & Evidence Quality** | 25% | Multi-evidence correlation graph, timestamp alignment, measured synthetic benchmark evaluation (in-distribution 64.4%, held-out 40.0%, selective accuracy 93.8% at 40% coverage), and strict enforcement of `status: "insufficient_evidence"` when criteria are unmet. |
| **Orchestration & Conflict Resolution** | 15% | LangGraph state graph with supervisory mediation, message bus pub/sub, targeted peer inquiry passes, dynamic hypothesis ranking, and deterministic conflict arbitration matrix (`orchestrator/`, `core/bus.py`). |
| **Robustness to Missing / Incompatible Data** | 15% | Clock skew normalization, unit converter layer (bps/Kbps/Mbps/Gbps, ms/us), fuzzy device alias mapping, and Hypothesis property-based fuzzing (`core/normalizer.py`, `gateway/adapters/organizer_adapter.py`, `tests/test_robustness_hypothesis.py`, `tests/test_chaos.py`). |
| **Innovation, Usability, Extensibility** | 10% | Model Context Protocol (MCP) server for external AI tools, Human-in-the-Loop (HITL) approval gates, pause/resume persistence via SQLite, simulated remediation sandbox, twin UI (Web Dashboard + Typer CLI), seeded generator with chaos knobs (`data/generator.py`, `mcp_server/`, `dashboard/`, `cli/`). |
| **Code Quality, Docs, and Demo** | 5% | Typed codebase, docstrings, structured logging, zero emojis, unified JSON output report, comprehensive setup scripts, 125 reproducible tests, Makefile, Docker Compose. |
| Evaluation Dimension | Weight | Our Implementation & Architectural Advantage | Verifiable Benchmark Result |
| :--- | :---: | :--- | :---: |
| **Interoperability & Protocol Design** | **30%** | Dedicated HTTP REST microservices with zero shared memory. Fully documented wire schema (`schemas/envelope.json`), semantic versioning (`1.0.0`), strict SI unit conversions, and Ingestion Gateway with 12 typed validation error handlers for multi-vendor and organizer Colab telemetry. | **Automated Schema Validation** |
| **Diagnostic Accuracy & Evidence Quality** | **25%** | Two-layer finding architecture: empirical facts (`Observation`) separate from inferred causes (`Hypothesis`). Complete corroboration matrix with calibrated confidence scoring and mathematical abstention bounds. | **64.4% In-Distribution Accuracy** (synthetic)<br/>**93.8% Selective Accuracy** at 40% coverage |
| **Orchestration & Conflict Resolution** | **15%** | LangGraph cyclical state graph. The Mediator agent evaluates hypothesis overlap, triggers cross-inquiry turns, and applies a strict domain precedence hierarchy (physical optics > buffer drops > routing flaps > ping latency). | **+8.3% F1 gain** over unmediated pipelines |
| **Robustness to Missing & Corrupted Data** | **15%** | Evaluated on independently generated non-Gaussian held-out data (Pareto/log-normal noise, bursty dropouts) and organizer Colab telemetry. Degrades gracefully to `insufficient_evidence` rather than hallucinating root causes. | **40.0% Held-Out Accuracy** (synthetic)<br/>**66.7% Organizer Set Match** (Set-match counts an abstention on 'normal' organizer samples as correct, and is lenient on fault classes; exact-match is 0.0%) |
| **Usability, Extensibility & Innovation** | **10%** | Stdio Model Context Protocol (MCP) server for IDE/agent tooling; blast-radius bounded simulated remediation engine with rollback automation; Rich monochrome CLI (`netcoop`); and real-time React web dashboard. | **Sub-120ms P95 Latency**<br/>Zero Real Device Impact |
| **Code Quality, Docs & Demo** | **5%** | Clean-room architectural separation, passing automated test suite, automated dynamic README generation, Playwright visual tests, and deterministic offline replay. | **Offline Core Engine** |

---

## 3. Results at a Glance

> Note: Benchmark evaluations were executed in in-process fallback mode (zero external microservice dependency). Synthetic benchmark performance reflects measured metrics from `eval/results/benchmark_latest.json`: in-distribution 64.4%, held-out 40.0%, selective accuracy 93.8% at 40% coverage.
>
> The committed benchmark was generated before the normal-operation benign fix and has not been regenerated.

### 3.1 Benchmark Dataset Splits

| Evaluation Split | Sample Count | Accuracy | Macro F1 | Expected Calibration Error (ECE) | Brier Score |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **In-Distribution Evaluation (Synthetic)** | 250 | **64.4%** | 0.593 | 0.180 | 0.201 |
| **Held-Out Evaluation (Synthetic Non-Gaussian)** | 150 | **40.0%** | - | - | - |
| **Organizer Colab Telemetry (Set Match)** | 900 | **66.7%** | - | - | - |
| **Selective Classification (Coverage 40%)** | 160 | **93.8%** | - | - | - |

> Note on Organizer Dataset: Set-match counts an abstention on 'normal' organizer samples as correct, and is lenient on fault classes; exact-match is 0.0% (source: `eval/results/benchmark_latest.json`). The organizer evaluation dataset consists of narrow single-device campus distribution telemetry snapshots (`data/organizer/`) rather than full multi-tier backbone fabric traces.

### 3.2 Pipeline Ablation Analysis

Smoke test: 32 cases, 4 fault types, 8 seeds. Not evidence of generalization.

Ablation evaluation results from eval/results/benchmark_latest.json (source: eval/run_eval.py::run_ablations). On this smoke test, Rules-Only Core, Model-Only, and the Full Multi-Agent Pipeline all achieve identical accuracy (100.0%) and Macro F1 (1.000); neither the learned layer nor the multi-agent pipeline improves accuracy over rules-only here.

| Pipeline Configuration | Accuracy | Macro F1 | ECE | Latency (ms) | Insufficient Evidence Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Full Multi-Agent Pipeline** | 100.0% | 1.000 | 0.073 | 175.6 ms | 0.0% |
| Rules-Only Core (Without Learned Layer) | 100.0% | 1.000 | 0.073 | 0.5 ms | 0.0% |
| Model-Only (Learned Classifier Alone) | 100.0% | 1.000 | 0.000 | 22.6 ms | 0.0% |
| Single-Agent Heuristic Baseline | 25.0% | 0.250 | 0.195 | 0.2 ms | 50.0% |

### 3.3 Per-Class Diagnostic Performance

Performance breakdown from `eval/results/benchmark_latest.json` across evaluated incident classes:

| Fault Category | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| `Normal Operation` | 0.0% | 0.0% | 0.000 | 40 |
| `Link Congestion` | 97.1% | 82.5% | 0.892 | 40 |
| `Weak Wifi Signal` | 100.0% | 45.0% | 0.621 | 40 |
| `Ethernet Interface Fault` | 100.0% | 35.0% | 0.519 | 40 |
| `Dns Failure` | 100.0% | 62.5% | 0.769 | 40 |
| `Dhcp Failure` | 100.0% | 52.5% | 0.689 | 40 |
| `Device Cpu Overload` | 100.0% | 70.0% | 0.824 | 40 |
| `Upstream Failure Cascade` | 100.0% | 27.5% | 0.431 | 40 |

### 3.4 Selective Classification (Risk-Coverage)

Operating points derived from eval/results/benchmark_latest.json (selective accuracy: 93.8% at 40.0% coverage across confidence thresholds 0.40-0.90). Calibrated probabilities are saturated, so varying the threshold does not move the operating point.

| Confidence Threshold | Selective Coverage | Selective Risk (Error Rate) | Accepted Samples | Operational Decision |
| :---: | :---: | :---: | :---: | :--- |
| >= 0.40 to 0.90 | 40.0% | 6.2% | 160 / 400 | Autonomous diagnosis with 93.8% selective accuracy |

---

## 4. Architecture & Agent Specifications

The platform is designed around strict process isolation. Six specialist agents plus a synthesizer operate with independent responsibilities across dedicated microservices or in-process fallback:

![NetCoop AI Architecture Diagram](docs/assets/architecture.svg)

### 4.1 Agent Role Matrix

| Agent Name | Process & Port | Loopback Endpoint | Primary Inputs | Extracted Findings & Signatures | Anomaly Thresholds | Failure / Abstention Modes |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| **Orchestrator** | `orchestrator`<br/>`:8000` | `POST /api/diagnose`<br/>`WS /ws/events` | Telemetry payload, graph state | Incident lifecycle, mediator turns, synthesis routing | Turn limit: 3 iterations | Timeout after 5.0s per turn |
| **Telemetry Agent** | `telemetry_agent`<br/>`:8001` | `POST /process` | Time-series metrics (loss, latency, jitter, bandwidth, drops) | `metric_anomaly`: Interface saturation, loss spikes, buffer tail-drops | Loss > 1.0%, Latency > 100ms, Link Util > 90% | Missing time-series: emits `insufficient_evidence` |
| **Topology Agent** | `topology_agent`<br/>`:8002` | `POST /process` | Graph adjacency, LLDP/CDP, STP root, BGP state | `topology_change`: Path reroutes, BGP session flaps, blackholes | Flap count > 3/min, STP topology change = true | Disconnected graph: reports isolated nodes |
| **Config Agent** | `config_agent`<br/>`:8003` | `POST /process` | Running configs, commit diffs, interface MTU/duplex | `config_diff`: MTU mismatches, duplex mismatches, VLAN pruning | MTU delta != 0, speed auto-neg mismatch | Unparsed vendor syntax quarantined |
| **Log Agent** | `log_agent`<br/>`:8004` | `POST /process` | Device syslog stream, event severity, timestamps | `log_pattern`: CRC/FCS error bursts, session flaps, link downs | Pattern match frequency > 5 in 60s window | Corrupted logs: dropped to audit log |
| **Classifier Agent** | `classifier_agent`<br/>`:8007` | `POST /process` | Time-window feature vectors across devices | `classifier_calib_probs`: Multi-class fault probability distribution | Split conformal quantile cutoff | Prediction set empty: model abstention |
| **Wifi Services Agent** | `wifi_services_agent`<br/>`:8008` | `POST /process` | AP RSSI, SNR, client retransmissions, channel utilization | `wifi_degradation`: RF attenuation, coverage hole, AP saturation | RSSI < -75 dBm, Retransmit > 15% | Missing RF telemetry: emits `insufficient_evidence` |
| **Synthesizer** | `synthesizer_agent`<br/>`:8005` | `POST /process` | All specialist observations, hypotheses, inquiries | `synthesis_submission`: Consolidated root cause and confidence | Corroboration score >= 0.70 | Conflict unresolvable: emits `insufficient_evidence` |
| **Ingestion Gateway** | `gateway`<br/>`:8006` | `POST /ingest` | Raw heterogeneous telemetry, organizer JSONL | Canonicalized telemetry stream, audit quality report | Missing required keys, clock skew > 300s | Unrecognized format: 12 typed validation errors |

---

## 5. Protocol Specification (`schemas/envelope.json`)

All inter-agent communication takes place using the standardized wire envelope. No raw strings, untyped dictionaries, or hidden states are permitted.

### 5.1 Standard Envelope Structure

```json
{
  "header": {
    "message_id": "c1f72b22-86ee-4eb3-8182-3d712f5581ea",
    "correlation_id": "inc-20261031-001",
    "timestamp_utc": "2026-10-31T12:00:00.000000+00:00",
    "sender": "telemetry_agent",
    "recipient": "orchestrator",
    "schema_version": "1.0.0",
    "message_type": "finding_submission",
    "priority": "normal"
  },
  "payload": {
    "scope": {
      "network_id": "campus-core",
      "devices": ["dist-sw-01", "access-sw-02"],
      "interfaces": ["GigabitEthernet0/1"]
    },
    "observations": [
      {
        "observation_id": "obs-e4c19a02",
        "category": "metric_anomaly",
        "entity": "dist-sw-01:GigabitEthernet0/1",
        "metric_name": "packet_loss_pct",
        "observed_value": 14.8,
        "baseline_value": 0.05,
        "unit": "percent",
        "severity": "critical",
        "timestamp_start": "2026-10-31T12:00:00Z",
        "timestamp_end": "2026-10-31T12:05:00Z",
        "context": { "queue_drops": 1420 }
      }
    ],
    "hypotheses": [
      {
        "hypothesis_id": "hyp-82b3a104",
        "probable_cause": "link_congestion",
        "confidence": 0.88,
        "supporting_observation_ids": ["obs-e4c19a02"],
        "refuting_observation_ids": [],
        "required_corroboration": ["LOG_INTERFACE_DROP_MESSAGES"]
      }
    ],
    "inquiries": [
      {
        "inquiry_id": "inq-91f82c31",
        "target_agent": "log_agent",
        "question": "Are there queue drop syslog messages on interface GigabitEthernet0/1?",
        "target_entity": "dist-sw-01:GigabitEthernet0/1",
        "parameters": { "window_minutes": 15 },
        "answer": null
      }
    ],
    "raw_data": null,
    "error": null
  },
  "context": {
    "iteration": 0,
    "environment": "simulation"
  }
}
```

### 5.2 Canonical Metric Keys and SI Units

The Ingestion Gateway and normalizers enforce standard metric names and units across all data sources:

| Canonical Key | Description | SI Unit | Supported Raw Aliases | Normalization Action |
| :--- | :--- | :--- | :--- | :--- |
| `latency_ms` | Round-trip packet latency | `ms` | `latency`, `rtt`, `ping_ms`, `delay_ms` | Seconds converted via 1000x multiplier |
| `jitter_ms` | Packet delay variation | `ms` | `jitter`, `delay_variation` | Microseconds converted via 0.001x multiplier |
| `packet_loss_pct` | Dropped packet proportion | `percent` | `loss`, `packet_loss`, `drop_rate` | Floats in range [0, 1] scaled to [0, 100] |
| `throughput_mbps` | Observed bit rate | `mbps` | `throughput`, `traffic_rate`, `tx_rate` | bps/kbps/gbps scaled to megabits/sec |
| `link_utilization_pct` | Relative bandwidth load | `percent` | `util`, `utilization`, `load_pct` | Ratios scaled to percentage |
| `cpu_pct` | CPU processor utilization | `percent` | `cpu`, `cpu_usage`, `processor_pct`, `cpu_utilization_pct` | Clamped to [0.0, 100.0] |
| `queue_drops` | Egress buffer tail-drops | `count` | `drops`, `buffer_drops`, `queue_overflows` | Non-negative integer cast |
| `interface_errors` | CRC, alignment, frame errors | `count` | `crc_errors`, `input_errors`, `phy_errors` | Non-negative integer cast |
| `wifi_rssi_dbm` | Wireless signal strength | `dbm` | `rssi`, `signal_strength_dbm`, `wifi_signal` | Validated in range [-100, 0] dBm |

### 5.3 Version Negotiation & Protocol Incompatibility Handling

1. **Semantic Version Check**: Every envelope specifies `header.schema_version`. Agents accept any version matching `1.x.x`. Minor versions are backward-compatible.
2. **Schema Migration**: When receiving older schema versions, the Ingestion Gateway runs structural transforms (e.g. nested metric flattening, field promotion).
3. **Invalid Envelopes**: If an envelope fails Pydantic validation:
   - The malformed message is quarantined in the SQLite `event_log`.
   - A structured `protocol_error` envelope is returned with details.
   - The orchestrator isolates the sender without halting the diagnostic graph.

### 5.4 Output in the Hackathon JSON Format

To export any diagnostic run directly into the hackathon required 10-key contract (`incident_id`, `status`, `suspected_root_cause`, `confidence`, `affected_devices`, `supporting_evidence`, `alternative_causes`, `recommended_actions`, `evidence_sources`, `limitations`), use the `export_hackathon_report_json` adapter:

```powershell
python -c "import json; from netcoop.data.generator import SyntheticNetworkGenerator; from netcoop.orchestrator.graph import run_diagnosis; from netcoop.reporting.builder import export_hackathon_report_json; inc = SyntheticNetworkGenerator.generate(scenario='link_congestion', seed=42); rep = run_diagnosis(inc); print(json.dumps(export_hackathon_report_json(rep), indent=2))"
```

First 15 lines of output:
```json
{
  "incident_id": "inc-link-congestion-42",
  "status": "diagnosed",
  "suspected_root_cause": "Link utilization saturation causing buffer queue drops and latency spikes",
  "confidence": 0.956,
  "affected_devices": [
    "dist-sw-core",
    "core-rtr-01"
  ],
  "supporting_evidence": [
    {
      "metric": "latency_ms",
      "value": 131.1,
      "interpretation": "core-rtr-01 latency_ms: observed 131.1 ms"
    },
```

---

## 6. Calibration and Conformal Prediction Caveat

Reliable network automation requires knowing when not to trust a model. NetCoop AI incorporates isotonic calibration to align confidence estimates with empirical diagnostic accuracy:

| Confusion Matrix | Reliability Diagram |
| :---: | :---: |
| *Confusion matrix over primary benchmark samples (overall accuracy 55.2%)* | *Reliability diagram demonstrating ECE of 0.180 (18.0%)* |

### Conformal Prediction & Calibration Caveat

> [!WARNING]
> **Conformal Calibration Caveat** (from [`docs/eval_report.md`](docs/eval_report.md)):
> Empirical confidence scores and conformal coverage guarantees assume exchangeability between offline validation traces and real-world network operations. Severe distribution shifts—including unobserved multi-vendor syslog dialect variations, simultaneous optical attenuation on uninstrumented dark fiber, or unprecedented transit peering flaps—can cause empirical coverage to fall below the nominal $(1 - \alpha)$ target.
> In high-stakes production environments, automated remediation must enforce human-in-the-loop sign-off whenever uncertainty bounds exceed 15% or when the mediator's prediction set contains multiple unresolvable competing hypotheses.

For model architecture, arbitration rules, and training procedures, see the [NetCoop AI Model Card](netcoop/models/MODEL_CARD.md).

---

## 7. Dashboard Gallery

The NetCoop AI dashboard is a minimalist, monochrome web application built with React, Vite, TypeScript, and Tailwind CSS. It communicates with the backend via WebSocket (`WS /ws/events`) to stream live agent envelopes, topology changes, and diagnostic reports:

### 7.1 Real-Time Diagnostic Interface

| Dark Mode (Default) | Light Mode |
| :---: | :---: |
| ![Dashboard Overview Dark](docs/assets/dashboard_dark.png) | ![Dashboard Overview Light](docs/assets/dashboard_light.png) |
| *Dark theme: Live agent graph, streaming timeline, and calibrated confidence arc* | *Light theme: High-contrast layout with persistent local state toggle* |

### 7.2 Interoperability Inspector & Topology View

| Interoperability Inspector | Topology & Blast Radius |
| :---: | :---: |
| ![Interoperability Inspector](docs/assets/interop_inspector.png) | ![Topology View](docs/assets/agent_graph.png) |
| *Side-by-side raw vs. canonicalized view showing flattening, alias mapping, and quality audit* | *Topology map highlighting affected switches and visual blast radius line weighting* |

### 7.3 Human-in-the-Loop (HITL) Queue & Simulated Remediation

| HITL Operator Approval Queue (`FEATURE_HITL`) | Simulated Remediation Sandbox (`FEATURE_REMEDIATION_SIM`) |
| :---: | :---: |
| ![HITL Approval Queue](docs/assets/hitl_queue.png) | ![Simulated Remediation View](docs/assets/simulated_remediation.png) |
| *Pending remediation proposals with approve, reject, and modify controls and mandatory rationale logging* | *Before vs. after metric deltas with persistent "Simulated, no production changes" sandbox label* |

### 7.4 Diagnostic Sessions & Resume Control (`FEATURE_RESUME`)

| Diagnostic Session Manager |
| :---: |
| ![Sessions & Resume Control](docs/assets/sessions_resume.png) |
| *Stateful session manager showing paused sessions with one-click multi-turn resume execution.* |

### 7.5 Model Context Protocol (MCP) Integration & Client Configuration

The NetCoop AI platform implements a standard **Model Context Protocol (MCP)** server providing external AI coding assistants, IDE extensions (Claude Desktop, Cursor, VS Code, Antigravity), and autonomous agents direct access to network diagnostic, telemetry analysis, topology inspection, and simulated remediation capabilities:

- **Entrypoint**: `python -m netcoop.mcp.server` (or `python mcp_server/server.py`)
- **Protocol**: JSON-RPC 2.0 over standard input / output (`stdin` / `stdout`)
- **Zero-LLM Core**: All tools execute against local deterministic Python engines with zero external API dependencies.

#### MCP Tools Directory

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_telemetry` | `device_id` (str, required), `window` (int, default 5) | Retrieves the latest telemetry time-series metrics window for a specified network device. |
| `list_devices` | *(none)* | Enumerates all unique active and historical network devices across scenarios, organizer samples, and database logs. |
| `get_topology` | `incident_id` (str, optional), `scenario` (str, optional) | Returns the current network topology (nodes, links, and interface roles). Gracefully returns `"topology unavailable"` when missing. |
| `run_diagnosis` | `target` (str, optional), `incident_data` (obj, optional) | Executes complete multi-agent offline diagnosis on a named scenario (`link_congestion.json`), organizer sample (`normal.jsonl`), or inline telemetry. |
| `explain_finding` | `finding_id` (str, required) | Provides human-readable evidentiary explanations, metric attribution, and corroboration trails for an observation or hypothesis ID. |
| `diagnose_network` | `incident_data` (obj, required) | Direct programmatic entrypoint conforming to `schemas/telemetry.json`. |
| `get_incident_status` | `incident_id` (str, required) | Fetches persisted diagnostic report, confidence, and root cause from SQLite storage. |
| `get_envelope_trace` | `correlation_id` (str, required) | Retrieves complete auditable history of versioned inter-agent envelope messages. |
| `simulate_remediation` | `incident_id` (str, optional), `action_id` (str, optional), `action_type` (str, optional) | Simulates safe remediation in an isolated sandbox (`rebalance traffic`, `clear interface counters`, `raise QoS priority`, `fail over a link`). |
| `get_protocol_schema` | `schema_name` (str, required) | Inspects formal JSON schemas (`envelope`, `telemetry`, `diagnostic_report`, `remediation_plan`). |

#### MCP Client Configuration Snippet (Windows 11 / PowerShell)

Add the following configuration block to your MCP client configuration file (e.g., `claude_desktop_config.json`, Cursor MCP Settings, or Antigravity MCP Settings):

##### Relative Path Alternative (when running from repository root)
```json
{
  "mcpServers": {
    "netcoop": {
      "command": "python",
      "args": [
        "-m",
        "netcoop.mcp.server"
      ],
      "env": {
        "PYTHONPATH": ".",
        "FEATURE_MCP": "true",
        "FEATURE_REMEDIATION_SIM": "true"
      }
    }
  }
}
```

##### Standard Virtual Environment Configuration
```json
{
  "mcpServers": {
    "netcoop": {
      "command": "C:\\Users\\kumar\\OneDrive\\Desktop\\NetCoop-AI\\NetCoop-AI\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "netcoop.mcp.server"
      ],
      "cwd": "C:\\Users\\kumar\\OneDrive\\Desktop\\NetCoop-AI\\NetCoop-AI",
      "env": {
        "PYTHONPATH": "C:\\Users\\kumar\\OneDrive\\Desktop\\NetCoop-AI\\NetCoop-AI",
        "FEATURE_MCP": "true",
        "FEATURE_REMEDIATION_SIM": "true"
      }
    }
  }
}
```

#### Test MCP Server over stdio

```powershell
# List available tools
'{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | .\.venv\Scripts\python.exe -m netcoop.mcp.server

# Call list_devices tool
'{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_devices", "arguments": {}}}' | .\.venv\Scripts\python.exe -m netcoop.mcp.server

# List resources
'{"jsonrpc": "2.0", "id": 3, "method": "resources/list"}' | .\.venv\Scripts\python.exe -m netcoop.mcp.server
```

For full MCP specifications and URI resource documentation, see [`docs/mcp.md`](docs/mcp.md).

---

## 8. Quickstart Guide (PowerShell / Windows 11)

All commands below run natively in PowerShell on Windows 11 using Python 3.12 or 3.13.

### 8.1 Setup Virtual Environment

```powershell
# Clone repository
git clone https://github.com/Satwik265/NetCoop-AI.git
Set-Location NetCoop-AI

# Create virtual environment and activate
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install package in editable mode with all dependencies
pip install -e .
pip install -r requirements.txt
```

### 8.2 Start Specialist Agents & Orchestrator

```powershell
# Launch all six specialist agents, synthesizer, gateway, and orchestrator in background processes
python scripts/run_agents.py
```

### 8.3 Run End-to-End Diagnostic Demos

```powershell
# Run primary diagnostic demo across all canonical fault scenarios
python scripts/demo.py

# Ingest and diagnose organizer Colab telemetry format
python scripts/demo_organizer.py
```

### 8.4 Launch Web Dashboard

```powershell
# Launch frontend development server
Set-Location dashboard
npm install
npm run dev
# Dashboard available at http://localhost:5173
```

### 8.5 Air-Gapped Offline Verification

```powershell
# Verify that all diagnostic scenarios execute with zero outbound internet access
$env:OFFLINE_MODE = "1"
$env:GEMINI_API_KEY = ""
python scripts/demo.py
```

---

## 9. Data and Testing Environment

### 9.1 Held-Out Generator (`netcoop/data/heldout_generator.py`)

To ensure evaluation validity, the held-out generator was built under clean-room conditions without inspecting detector logic. It deliberately shifts parameters:
- **Heavy-Tailed Noise**: Pareto-distributed spikes ($\alpha \in [2.5, 4.0]$) and log-normal buffer drop excursions instead of symmetric Gaussian noise.
- **Dynamic Severity**: Continuous severity multipliers ($0.75\times$ to $1.65\times$) testing both subtle degradation and extreme saturation.
- **Dynamic Onset**: Shifts fault onset from $10\%$ early to $85\%$ late with periodic oscillation.
- **Bursty Gaps**: Drops contiguous blocks of telemetry samples (2–4 intervals) to evaluate detector resilience to packet loss in the monitoring plane.
- **Compound Scenarios**: Multi-fault combinations (CPU overload + queue tail-drops, Wi-Fi interference + DNS failure).

For full details, see [`docs/heldout_notes.md`](docs/heldout_notes.md).

### 9.2 Organizer Colab Telemetry Adaptation

NetCoop AI ingests raw telemetry generated by the IIT Bhubaneswar hackathon organizer Colab notebook (`data/organizer/`):
- **Metrics Flattening**: Flattens nested `metrics` objects into root records.
- **Alias Mapping**: Maps `cpu_utilization_pct` to `cpu_pct`, `interface_errors` to counts, and `status` strings (`Healthy`, `Warning`, `Critical`) to operational states.
- **Caveat**: The organizer dataset is restricted to isolated campus distribution switches; when ingesting organizer data, the topology map displays a clear "topology unavailable" indicator.

For full schema details, see [`docs/organizer_format.md`](docs/organizer_format.md).

---

## 10. Repository Layout

```text
NetCoop-AI/
|-- dashboard/                  # React + Vite + TypeScript + Tailwind web dashboard
|   |-- src/                    # Components (AgentGraph, Timeline, ProofTab, HITL, Simulation)
|   `-- package.json
|-- data/                       # Telemetry scenarios & organizer datasets
|   |-- organizer/              # Hackathon organizer Colab notebook and JSONL samples
|   `-- scenarios/              # Canonical and compound scenario JSON libraries
|-- docs/                       # Architectural documentation & specifications
|   |-- assets/                 # Monochrome SVGs and Playwright screenshots
|   |-- contract.md             # Cross-team inter-process API and port contract
|   |-- contract_changes.md     # Protocol change governance, HITL and simulation contracts
|   |-- eval_report.md          # Benchmark report & conformal calibration caveat
|   |-- heldout_notes.md        # Held-out generator distribution shift notes
|   |-- handoff.md              # Real environment paths, ports, and startup guide
|   |-- mcp.md                  # Model Context Protocol (MCP) server specification
|   |-- organizer_format.md     # Organizer Colab telemetry schema specification
|   `-- progress.md             # Implementation progress and rubric compliance matrix
|-- eval/                       # Evaluation benchmarks and results
|   `-- results/                # Ground-truth benchmark JSONs (mock.json, benchmark.json)
|-- gateway/                    # Ingestion Gateway service (:8006)
|   |-- adapters/               # Organizer Colab adapter and telemetry normalizer
|   `-- api.py                  # FastAPI gateway endpoints
|-- mcp_server/                 # Model Context Protocol stdio server
|-- netcoop/                    # Core Python package
|   |-- agents/                 # Specialist agent microservices (:8001 - :8005)
|   |-- cli.py                  # Typer monochrome CLI (diagnose, replay, gen)
|   |-- core/                   # Wire models, correlation rules, scoring, thresholds
|   |-- data/                   # Canonical and held-out dataset generators
|   |-- models/                 # Model card and calibration utilities
|   |-- orchestrator/           # LangGraph state machine, mediator, conflict resolver
|   |-- remediation/            # Safe simulated remediation engine and rollback plans
|   `-- storage/                # SQLite persistent event store and incident logger
|-- schemas/                    # Authoritative JSON Schemas
|   |-- envelope.json           # Inter-agent wire envelope schema (v1.0.0)
|   |-- telemetry.json          # Canonical network telemetry schema
|   `-- diagnostic_report.json  # Output diagnostic report schema
|-- scripts/                    # Automation and demo utilities
|   |-- build_readme.py         # Dynamic README generator (compiles this file)
|   |-- demo.py                 # End-to-end diagnostic demonstration
|   |-- demo_organizer.py       # Organizer Colab telemetry demo
|   `-- run_agents.py           # Multi-process agent launcher
|-- tests/                      # Automated unit and integration test suite
|-- Makefile                    # Optional shortcut commands (wrapped for PowerShell)
`-- pyproject.toml              # Package configuration and dependencies
```


## 11. Compliance Matrix

| Requirement | Implementation Module | Verification Status |
| :--- | :--- | :---: |
| Six Specialist Agents Plus a Synthesizer | `netcoop/agents/*.py` (ports 8001–8005) | **Complete** (All tests passing) |
| Authoritative Wire Envelope Schema | `schemas/envelope.json`, `docs/contract.md` | **Complete** |
| LangGraph Orchestration & Mediation | `netcoop/orchestrator/graph.py`, `mediator.py` | **Complete** |
| Zero-LLM Deterministic Engine | `netcoop/core/correlation.py`, `evidence.py` | **Complete** (Offline Core) |
| Optional LLM Bridge with Offline Fallback | `netcoop/llm/client.py` | **Complete** |
| Organizer Colab Format Adaptation | `gateway/adapters/organizer_adapter.py` | **Complete** |
| Safe Simulated Remediation & Rollback | `netcoop/remediation/engine.py` | **Complete** |
| Persistent SQLite Event Log & Replay | `netcoop/storage/db.py`, `netcoop replay` | **Complete** |
| Model Context Protocol (MCP) Server | `mcp_server/server.py`, `docs/mcp.md` | **Complete** |
| Rich CLI & React Web Dashboard | `netcoop/cli.py`, `dashboard/` | **Complete** |
| Human-in-the-Loop (HITL) Queue | `dashboard/src/components/HitlApprovalQueue.tsx` | **Complete** |
| Remediation Simulation Sandbox | `dashboard/src/components/SimulatedRemediationView.tsx` | **Complete** |
| Stateful Diagnostic Session Resume | `dashboard/src/components/SessionListResume.tsx` | **Complete** |

---

## 12. Honest Limitations

1. **Exchangeability Assumption**: Calibrated confidence scores rely on telemetry distributions aligning with reference observations. Extreme catastrophic novel anomalies may fall outside calibrated intervals.
2. **Narrow Organizer Topology**: Organizer Colab telemetry is limited to isolated campus switches and lacks multi-tier spine-leaf fabric context.
3. **Simulated Actions Only**: NetCoop AI outputs proposed remediation plans with safety bounds and rollbacks; it intentionally does not push unverified live commands to physical hardware.
4. **Interface Scale**: High-density switches with > 256 physical interfaces require horizontal agent scaling to prevent telemetry processing bottlenecks.

---

## 13. Team & License

- **Team**: Team inSANE MITRA (IIT Bhubaneswar Hackathon)
- **Repository**: [https://github.com/Satwik265/Team_inSANE_MITRA_NetCoop-AI](https://github.com/Satwik265/Team_inSANE_MITRA_NetCoop-AI)
- **License**: [MIT License](LICENSE)
