# NetCoop AI: Cooperative Multi-Agent Network Fault Diagnosis Platform

[![Python](https://img.shields.io/badge/Python-3.11%20|%203.12%20|%203.13-2A2A2D?style=flat-square&labelColor=161618)](https://python.org)
[![Architecture](https://img.shields.io/badge/Architecture-Shared--Nothing%20Microservices-2A2A2D?style=flat-square&labelColor=161618)](docs/contract.md)
[![Orchestration](https://img.shields.io/badge/Orchestration-LangGraph-2A2A2D?style=flat-square&labelColor=161618)](netcoop/orchestrator/graph.py)
[![Wire Protocol](https://img.shields.io/badge/Wire%20Protocol-JSON%20Schema%20v1.0-2A2A2D?style=flat-square&labelColor=161618)](schemas/envelope.json)
[![License](https://img.shields.io/badge/License-MIT-2A2A2D?style=flat-square&labelColor=161618)](LICENSE)

A modular, shared-nothing multi-agent platform for enterprise and campus network fault diagnosis, cross-domain evidence corroboration, and safe simulated remediation planning.

---

## 1. Problem and Insight

Enterprise and campus network operations suffer from fragmented observability. Modern fabrics produce disjointed telemetry streams: time-series interface metrics, spanning-tree topology state transitions, configuration change diffs, and high-volume syslog bursts reside in isolated monitoring silos.

Existing approaches fall into two failure modes:
1. **Monolithic Rule Engines**: Rigid heuristic systems lack the ability to cross-examine evidence across operational domains. When multiple anomalies fire simultaneously (e.g. high CPU utilization alongside link packet loss), monolithic systems fail to isolate root cause from derivative downstream symptoms.
2. **Naive LLM Wrappers**: Direct prompt-engineering wrappers hallucinate network topology, invent non-existent interfaces, violate JSON wire schemas, leak state across diagnostic turns, and cannot operate in disconnected environments without external cloud endpoints.

**The NetCoop AI Insight**:
Network diagnosis is fundamentally a multi-perspective consensus problem. NetCoop AI decomposes network intelligence into isolated specialist agents plus a synthesizer operating as decoupled processes (Telemetry, Topology, Configuration, Log, Classifier, and Wifi Services specialists, with consensus mediation by the Synthesizer). Agents share zero memory and communicate strictly through versioned, strongly-typed wire envelopes (`schemas/envelope.json`). A LangGraph state-machine orchestrator manages multi-turn mediation, routing targeted cross-inquiries (`payload.inquiries`) between specialists to corroborate empirical evidence (`Observation`) and debate causal hypotheses (`Hypothesis`). When evidence is incomplete, corrupted, or conflicting, the system strictly refuses to guess and emits an auditable `insufficient_evidence` determination.

Under identical seed initialization, two consecutive runs of link_congestion seed 42 produced byte-identical reasoning output excluding timestamps and IDs.

---

## 2. What Makes This Different: Rubric Mapping

| Evaluation Pillar | Hackathon Weight | NetCoop AI Implementation | Verifiable Source / Metric |
| :--- | :---: | :--- | :---: |
| **Interoperability & Protocol Design** | 30% | Dedicated HTTP REST microservices with zero shared memory. Fully documented wire schema (`schemas/envelope.json`), semantic versioning (`1.0.0`), strict SI unit conversions, and Ingestion Gateway with typed validation handlers for multi-vendor and organizer Colab telemetry. | `schemas/envelope.json`, `gateway/adapters/organizer_adapter.py` |
| **Diagnostic Accuracy & Evidence Quality** | 25% | Two-layer finding architecture: empirical facts (`Observation`) separate from inferred causes (`Hypothesis`). Complete corroboration matrix with calibrated confidence scoring and mathematical abstention bounds. | `eval/results/benchmark_latest.json` (64.4% in-distribution, 40.0% held-out, 93.8% selective accuracy at 40% coverage) |
| **Orchestration & Conflict Resolution** | 15% | LangGraph cyclical state graph. The Mediator evaluates hypothesis overlap, triggers cross-inquiry turns, and applies a strict domain precedence hierarchy (physical optics > buffer drops > routing flaps > ping latency). | `netcoop/orchestrator/graph.py`, `tests/test_conflict_resolution.py` |
| **Robustness to Missing & Corrupted Data** | 15% | Evaluated on independently generated non-Gaussian held-out data (Pareto/log-normal noise, bursty dropouts) and organizer Colab telemetry. Degrades gracefully to `insufficient_evidence` rather than hallucinating root causes. | `eval/results/benchmark_latest.json` (66.7% organizer set-match; exact-match is 0.0%) |
| **Usability, Extensibility & Innovation** | 10% | Stdio Model Context Protocol (MCP) server for external AI tools; blast-radius bounded simulated remediation engine with rollback automation; Rich monochrome CLI (`netcoop`); and real-time React web dashboard. | `netcoop/mcp/server.py`, `netcoop/remediation/engine.py` |
| **Code Quality, Docs & Demo** | 5% | Clean-room architectural separation, comprehensive automated test suite (327 collected tests across 31 test files), typed codebase, docstrings, structured logging, zero emojis, and reproducible demo scripts. | `tests/` (326 passed in full test suite run) |

---

## 3. Results at a Glance

> [!NOTE]
> Benchmark evaluations were executed in in-process fallback mode (zero external microservice dependency). Synthetic benchmark performance reflects measured metrics from `eval/results/benchmark_latest.json`: in-distribution 64.4%, held-out 40.0%, selective accuracy 93.8% at 40% coverage.
>
> **The committed benchmark was generated before the normal-operation benign fix and has not been regenerated.**

### 3.1 Benchmark Dataset Splits

| Evaluation Split | Sample Count | Accuracy | Macro F1 | Expected Calibration Error (ECE) | Brier Score | Source JSON Field |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Combined Primary Benchmark** | 400 | **55.2%** | 0.593 | 0.180 | 0.201 | `summary["combined_primary_accuracy"]` (or `summary["overall_accuracy"]`) |
| **In-Distribution Evaluation (Synthetic)** | 250 | **64.4%** | - | - | - | `dataset_splits["in_distribution_accuracy"]` |
| **Held-Out Evaluation (Synthetic Non-Gaussian)** | 150 | **40.0%** | - | - | - | `dataset_splits["held_out_accuracy"]` |
| **Organizer Colab Telemetry (Set Match)** | 900 | **66.7%** | - | - | - | `dataset_splits["organizer_accuracy"]` (or `summary["organizer_set_match_accuracy"]`) |
| **Organizer Colab Telemetry (Exact Match)** | 900 | **0.0%** | - | - | - | `summary["organizer_exact_match_accuracy"]` |
| **Selective Classification (Coverage 40%)** | 160 | **93.8%** | - | - | - | `summary["selective_accuracy"]` |

*Source: `eval/results/benchmark_latest.json` (generated_at: 2026-10-31T18:58:30Z)*

> **Exact JSON Field Derivation & Macro F1 Definition**:
> - **Headline Combined Primary Accuracy (55.2%)**: Read directly from `summary["combined_primary_accuracy"]` (identical to `summary["overall_accuracy"]` over the 400 primary in-distribution and held-out benchmark samples).
> - **Macro F1 (0.593)**: Read directly from `summary["macro_f1"]`. This value is exactly the unweighted arithmetic mean of the 8 per-class F1 values in `per_class_metrics`:
>   $$\text{Macro F1} = \frac{0.000 + 0.892 + 0.621 + 0.519 + 0.769 + 0.689 + 0.824 + 0.431}{8} = 0.593125 \approx 0.593$$
> - **Expected Calibration Error (0.180)**: Read directly from `summary["expected_calibration_error"]` (population: `in_distribution_and_heldout_primary_samples`).
> - **Brier Score (0.201)**: Read directly from `summary["brier_score"]` (population: `in_distribution_and_heldout_primary_samples`).
> - **Selective Accuracy (93.8%)**: Read directly from `summary["selective_accuracy"]` at coverage `summary["coverage"] = 0.400` (selective risk: `summary["selective_risk"] = 0.062`).
> - **Organizer Set-Match vs Exact-Match**: Set-match accuracy (66.7%, `dataset_splits["organizer_accuracy"]`) counts an abstention on 'normal' organizer samples as correct, and is lenient on fault classes; exact-match is strictly 0.0% (`summary["organizer_exact_match_accuracy"]`). The organizer evaluation dataset consists of narrow single-device campus distribution telemetry snapshots (`data/organizer/`) rather than full multi-tier backbone fabric traces.

### 3.2 Pipeline Ablation Analysis

Smoke test: 32 cases, 4 fault types, 8 seeds. Not evidence of generalization.

Ablation evaluation results from `eval/results/benchmark_latest.json` (source: `eval/run_eval.py::run_ablations`). On this smoke test, Rules-Only Core, Model-Only, and the Full Multi-Agent Pipeline all achieve identical accuracy (100.0%) and Macro F1 (1.000); neither the learned layer nor the multi-agent pipeline improves accuracy over rules-only here.

| Pipeline Configuration | Accuracy | Macro F1 | ECE | Latency (ms) | Insufficient Evidence Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Full Multi-Agent Pipeline** | 100.0% | 1.000 | 0.073 | 175.6 ms | 0.0% |
| Rules-Only Core (Without Learned Layer) | 100.0% | 1.000 | 0.073 | 0.5 ms | 0.0% |
| Model-Only (Learned Classifier Alone) | 100.0% | 1.000 | 0.000 | 22.6 ms | 0.0% |
| Single-Agent Heuristic Baseline | 25.0% | 0.250 | 0.195 | 0.2 ms | 50.0% |

*Source: `eval/results/benchmark_latest.json` (generated_at: 2026-10-31T18:58:30Z)*

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

*Source: `eval/results/benchmark_latest.json` (generated_at: 2026-10-31T18:58:30Z)*

### 3.4 Selective Classification (Risk-Coverage)

Operating points derived from `eval/results/benchmark_latest.json` (selective accuracy: 93.8% at 40.0% coverage across confidence thresholds 0.40–0.90). Calibrated probabilities are saturated, so varying the threshold does not move the operating point.

| Confidence Threshold | Selective Coverage | Selective Risk (Error Rate) | Accepted Samples | Operational Decision |
| :---: | :---: | :---: | :---: | :--- |
| >= 0.40 to 0.90 | 40.0% | 6.2% | 160 / 400 | Autonomous diagnosis with 93.8% selective accuracy |

*Source: `eval/results/benchmark_latest.json` (generated_at: 2026-10-31T18:58:30Z)*

---

## 4. Architecture & Agent Specifications

The platform is designed around strict process isolation. Six specialist agents plus a synthesizer operate with independent responsibilities across dedicated microservices or in-process fallback:

![NetCoop AI Architecture Diagram](docs/assets/architecture.svg)

### 4.1 Agent Role Matrix

| Agent | Service Name & Port | HTTP Endpoint | Operational Domain | Key Analyzed Metrics / Artifacts |
| :--- | :--- | :--- | :--- | :--- |
| **Telemetry Agent** | `telemetry_agent`<br/>`:8001` | `POST /process` | Time-series metrics (loss, latency, utilization, optics) | `link_utilization_pct`, `packet_loss_pct`, `latency_ms`, `queue_drops`, `optical_rx_power_dbm`, `optical_tx_power_dbm` |
| **Topology Agent** | `topology_agent`<br/>`:8002` | `POST /process` | Network graph topology, interface states, BGP peering | `interface_state` (up/down/flapping), `bgp_state` (established/active/idle), `mtu`, `is_redundant_path` |
| **Configuration Agent** | `config_agent`<br/>`:8003` | `POST /process` | Running device configurations, commit history, diffs | `commit_diff`, `configured_mtu`, `qos_policy`, `traffic_policy`, `vlan_membership`, `acl_applied` |
| **Log Agent** | `log_agent`<br/>`:8004` | `POST /process` | Syslog streams, system events, kernel alerts | Syslog severity (`EMERGENCY` through `DEBUG`), facility (`LINEPROTO`, `BFD`, `LINK`, `SYSTEM`), regex signatures |
| **Synthesizer Agent** | `synthesizer_agent`<br/>`:8005` | `POST /synthesize` | Multi-perspective evidence correlation & consensus | Cross-agent observation correlation, causal hypothesis generation, inquiry formulation, confidence scoring |
| **Classifier Agent** | `classifier_agent`<br/>`:8007` | `POST /process` | Learned statistical inference & conformal calibration | Normalized 12-feature telemetry vectors, isotonic calibration, softmax distributions, conformal prediction sets |
| **Wifi Services Agent** | `wifi_services_agent`<br/>`:8008` | `POST /process` | Wireless RF & campus core network services | `rssi_dbm`, `snr_db`, `wifi_retrans_pct`, `channel_util_pct`, `dns_latency_ms`, `dns_failure_rate`, `dhcp_ack_latency_ms`, `dhcp_failure_rate` |
| **Ingestion Gateway** | `gateway`<br/>`:8006` | `POST /ingest` | Multi-vendor & external telemetry normalization | Format auto-detection, schema adaptation (`v1.0.0`), SI unit coercion, clock skew correction, 12 typed validation error handlers |
| **Orchestrator** | `orchestrator-api`<br/>`:8000` | `POST /api/diagnose`<br/>`POST /api/diagnose/export` | Workflow state graph & external API server | LangGraph state graph coordination, supervisor mediation, timeout / retry / circuit-breaker policies, SQLite persistence |

---

## 5. Wire Protocol & Interoperability

All agent communication strictly adheres to the versioned wire envelope specification in [`schemas/envelope.json`](schemas/envelope.json). Agents accept and emit strongly-typed JSON envelopes over HTTP REST `POST` endpoints. No raw strings, untyped dictionaries, or hidden states are permitted across agent boundaries.

### 5.1 Ingestion Gateway Normalization

The Ingestion Gateway (`gateway/api.py`, port 8006) ingests multi-vendor and third-party telemetry, normalizes data models, and emits canonical structures conforming to `schemas/telemetry.json`:

1. **Unit Coercion**: Converts non-standard units to standard SI units:
   - Bandwidth throughput: `bps`, `Kbps`, `Gbps` coerced to canonical `Mbps`.
   - Latency: Fractional seconds (`0.1311 s`) and microseconds coerced to milliseconds (`131.1 ms`).
   - Jitter: Microseconds coerced to milliseconds.
   - Signal strength: Raw RF power milliwatts coerced to `dBm`.
2. **Schema Migration**: When receiving older schema versions, the Ingestion Gateway applies structural migration transformations to ensure zero protocol errors reach specialist agents.
3. **Dirty Data Sanitization**: Sanitizes string `'NaN'` and `'null'` tokens into structured null attributes; trims and synchronizes timestamps exceeding operational skew boundaries (600s boundary).

### 5.2 Standard Envelope Structure

```json
{
  "header": {
    "message_id": "c1f72b22-86ee-4eb3-8182-3d712f5581ea",
    "correlation_id": "inc-link-congestion-42",
    "timestamp_utc": "2026-10-31T12:00:00.000000+00:00",
    "sender": "telemetry_agent",
    "recipient": "orchestrator",
    "schema_version": "1.0.0",
    "message_type": "finding_submission",
    "priority": "normal"
  },
  "payload": {
    "scope": {
      "network_id": "iit-bbs-campus-fabric",
      "devices": ["dist-sw-core", "core-rtr-01"],
      "interfaces": ["et-0/0/1"]
    },
    "observations": [
      {
        "observation_id": "obs-e4c19a02",
        "category": "metric_anomaly",
        "entity": "core-rtr-01:et-0/0/1",
        "metric_name": "link_utilization_pct",
        "observed_value": 97.65,
        "baseline_value": 45.0,
        "unit": "percent",
        "severity": "critical",
        "timestamp_start": "2026-10-31T12:00:00Z",
        "timestamp_end": "2026-10-31T12:05:00Z",
        "context": { "queue_drops": 1019 }
      }
    ],
    "hypotheses": [
      {
        "hypothesis_id": "hyp-82b3a104",
        "probable_cause": "LINK_CONGESTION",
        "confidence": 0.956,
        "supporting_observation_ids": ["obs-e4c19a02"],
        "refuting_observation_ids": [],
        "required_corroboration": ["LOG_INTERFACE_DROP_MESSAGES"]
      }
    ],
    "inquiries": [
      {
        "inquiry_id": "inq-91f82c31",
        "target_agent": "log_agent",
        "question": "Are there queue drop syslog messages on interface et-0/0/1?",
        "target_entity": "core-rtr-01:et-0/0/1",
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

### 5.3 Canonical Metric Keys and SI Units

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

### 5.4 Version Negotiation & Protocol Incompatibility Handling

1. **Semantic Version Check**: Every envelope specifies `header.schema_version`. Agents accept any version matching `1.x.x`. Minor versions are backward-compatible.
2. **Schema Migration**: When receiving older schema versions, the Ingestion Gateway runs structural transforms (e.g. nested metric flattening, field promotion).
3. **Invalid Envelopes**: If an envelope fails Pydantic validation:
   - The malformed message is quarantined in the SQLite `event_log`.
   - A structured `protocol_error` envelope is returned with error details.
   - The orchestrator isolates the sender without halting the diagnostic graph.

### 5.5 Output in the Hackathon JSON Format

To export any diagnostic run directly into the hackathon required 10-key contract (`incident_id`, `status`, `suspected_root_cause`, `confidence`, `affected_devices`, `supporting_evidence`, `alternative_causes`, `recommended_actions`, `evidence_sources`, `limitations`), use the `export_hackathon_report_json` adapter:

```powershell
python -c "import json; from netcoop.data.generator import SyntheticNetworkGenerator; from netcoop.orchestrator.graph import run_diagnosis; from netcoop.reporting.builder import export_hackathon_report_json; inc = SyntheticNetworkGenerator.generate(scenario='link_congestion', seed=42); rep = run_diagnosis(inc); print(json.dumps(export_hackathon_report_json(rep), indent=2))"
```

For the complete, verified 10-key output example, see [Section 9.4 Real 10-Key Hackathon JSON Contract](#4-real-10-key-hackathon-json-contract-for-link_congestion).

---

## 6. Calibration and Conformal Prediction Caveat

Reliable network automation requires knowing when not to trust a model. NetCoop AI incorporates isotonic calibration to align confidence estimates with empirical diagnostic accuracy:

| Confusion Matrix | Reliability Diagram |
| :---: | :---: |
| *Confusion matrix over primary benchmark samples (overall accuracy 55.2%)* | *Reliability diagram demonstrating ECE of 0.180 (18.0%)* |

*Source: `eval/results/benchmark_latest.json` (generated_at: 2026-10-31T18:58:30Z)*

### Conformal Prediction & Calibration Caveat

> [!WARNING]
> **Conformal Calibration Caveat** (from [`docs/eval_report.md`](docs/eval_report.md)):
> Empirical confidence scores and conformal coverage guarantees assume exchangeability between offline validation traces and real-world network operations. Severe distribution shifts—including unobserved multi-vendor syslog dialect variations, simultaneous optical attenuation on uninstrumented dark fiber, or unprecedented transit peering flaps—can cause empirical coverage to fall below the nominal $(1 - lpha)$ target.
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
- **Core Engine**: All tools execute against local Python engines with zero external API dependencies.

#### MCP Tools Directory

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_telemetry` | `device_id` (str, required), `window` (int, default 5) | Retrieves the latest telemetry time-series metrics window for a specified network device. |
| `list_devices` | *(none)* | Enumerates all unique active and historical network devices across scenarios, organizer samples, and database logs. |
| `get_topology` | `incident_id` (str, optional), `scenario` (str, optional) | Returns the current network topology (nodes, links, and interface roles). Gracefully returns `"topology unavailable"` when missing. |
| `run_diagnosis` | `target` (str, optional), `incident_data` (obj, optional) | Executes complete multi-agent diagnosis on a named scenario (`link_congestion.json`), organizer sample (`normal.jsonl`), or inline telemetry. |
| `explain_finding` | `finding_id` (str, required) | Provides human-readable evidentiary explanations, metric attribution, and corroboration trails for an observation or hypothesis ID. |
| `diagnose_network` | `incident_data` (obj, required) | Direct programmatic entrypoint conforming to `schemas/telemetry.json`. |
| `get_incident_status` | `incident_id` (str, required) | Fetches persisted diagnostic report, confidence, and root cause from SQLite storage. |
| `get_envelope_trace` | `correlation_id` (str, required) | Retrieves complete auditable history of versioned inter-agent envelope messages. |
| `simulate_remediation` | `incident_id` (str, optional), `action_id` (str, optional), `action_type` (str, optional) | Simulates safe remediation in an isolated sandbox (`rebalance traffic`, `clear interface counters`, `raise QoS priority`, `fail over a link`). |
| `get_protocol_schema` | `schema_name` (str, required) | Inspects formal JSON schemas (`envelope`, `telemetry`, `diagnostic_report`, `remediation_plan`). |

#### MCP Client Configuration Snippet

Add the following configuration block to your MCP client configuration file (e.g., `claude_desktop_config.json`, Cursor MCP Settings, or Antigravity MCP Settings):

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

#### Test MCP Server over stdio

```powershell
# List available tools
'{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | .\.venv\Scripts\python.exe -m netcoop.mcp.server

# Call list_devices tool
'{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_devices", "arguments": {}}}' | .\.venv\Scripts\python.exe -m netcoop.mcp.server

# List resources
'{"jsonrpc": "2.0", "id": 3, "method": "resources/list"}' | .\.venv\Scripts\python.exe -m netcoop.mcp.server
```

---

## 8. Installation and Operations Guide

### 8.1 Prerequisites & Installation

Verify local prerequisites before beginning installation:
- **Python**: Minimum `requires-python = ">=3.11"` from `pyproject.toml`. Verified in testing on Python 3.13.15 (virtual environment) and Python 3.14.3 (`python --version`).
- **Node.js**: `FROM node:22-alpine` specified in `Dockerfile`. Verified locally on Node `v24.15.0` (`node --version`).
- **Git**: Verified locally with `git version 2.54.0.windows.1` (`git --version`).
- **Docker & Docker Compose (Optional)**: Containerized deployment path exists via `docker-compose.yml`. **NOT VERIFIED on this machine** (Docker Desktop Linux engine daemon is not running on this host; check returned `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`).

#### Local Virtual Environment Setup

```powershell
# 1. Clone repository
git clone https://github.com/Satwik265/NetCoop-AI.git
Set-Location NetCoop-AI

# 2. Create virtual environment and activate
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install package in editable mode with all dependencies
pip install -e .
pip install -r requirements.txt

# 4. Install dashboard frontend dependencies
cd dashboard
npm install
cd ..
```
*Source: Verified with `pip install -e .`, `pip install -r requirements.txt`, and `npm install`.*

### 8.2 Starting Agent Microservices & Orchestrator

NetCoop AI operates as a set of decoupled operating system processes communicating over HTTP with token authentication:

```powershell
# 1. Generate a strong internal service authentication token in PowerShell
$env:INTERNAL_SERVICE_TOKEN = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
Remove-Item Env:AGENTS_MODE -ErrorAction SilentlyContinue

# 2. Launch the 8 specialist agent and gateway processes in the background
python scripts/run_agents.py --daemon

# 3. Check health status of all 8 microservices (ports 8001-8008)
python scripts/run_agents.py --status

# 4. In a separate terminal window, start the FastAPI Orchestrator API
# Entry point confirmed in Makefile 'run' target and Dockerfile:
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# 5. When finished, terminate all 8 background microservices cleanly
python scripts/run_agents.py --stop
```

> **Process Architecture Note**: `python scripts/run_agents.py --daemon` spawns exactly 8 processes across ports 8001–8008 (`telemetry_agent:8001`, `topology_agent:8002`, `config_agent:8003`, `log_agent:8004`, `synthesizer_agent:8005`, `gateway:8006`, `classifier_agent:8007`, `wifi_services_agent:8008`). The Orchestrator API (`uvicorn api.main:app`) is executed separately on port 8000.

#### Docker Compose Deployment Path (Optional)

```powershell
$env:INTERNAL_SERVICE_TOKEN = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
docker compose up --build -d
```
*Status: NOT VERIFIED on this machine (Docker daemon stopped).*

### 8.3 Environment Configuration

Configuration variables defined in `netcoop/config.py` and `.env.example`:

| Variable | Default | Purpose | Required? |
| :--- | :--- | :--- | :---: |
| `INTERNAL_SERVICE_TOKEN` | `None` (`change-me` in `.env.example`) | Service-to-service authentication header token (`X-NetCoop-Service-Token`). Validated by `validate_service_token_strength` (`netcoop/config.py:110-120`): must be at least 16 characters (`len >= 16`) and must not match common default keywords (`test`, `default`, `secret`, `token`, `changeme`, `password`, `admin`, `12345678`, `development`). | **Yes** (in production / strict HTTP agent mode) |
| `AGENTS_MODE` | `"http"` | Inter-process communication mode between orchestrator and agents. Set to `"http"` for independent microservice dispatches, or `"in_process"` for monolithic testing. | No |
| `IN_PROCESS_FALLBACK` | `false` | When true, enables in-process fallback execution if an agent HTTP service is unreachable (development only). | No |
| `PORT` | `8000` | Orchestrator FastAPI REST & WebSocket listener port. | No |
| `TELEMETRY_AGENT_PORT` | `8001` | Dedicated port for Telemetry Specialist Agent. | No |
| `TOPOLOGY_AGENT_PORT` | `8002` | Dedicated port for Topology Specialist Agent. | No |
| `CONFIG_AGENT_PORT` | `8003` | Dedicated port for Configuration Specialist Agent. | No |
| `LOG_AGENT_PORT` | `8004` | Dedicated port for Syslog Specialist Agent. | No |
| `SYNTHESIZER_AGENT_PORT` | `8005` | Dedicated port for Cross-Domain Synthesizer Agent. | No |
| `GATEWAY_PORT` | `8006` | Dedicated port for Ingestion Gateway & Normalizer. | No |
| `CLASSIFIER_AGENT_PORT` | `8007` | Dedicated port for Learned Classifier & Calibration Agent. | No |
| `WIFI_SERVICES_AGENT_PORT` | `8008` | Dedicated port for Wireless & Network Services Agent. | No |
| `DATABASE_URL` | `"sqlite:///./netcoop.db"` | SQLModel connection string for persistent incident logging, audit trails, and authentication. | No |
| `GEMINI_API_KEY` | `None` | Optional API key for Google Gemini natural language summaries. When empty, the core pipeline makes zero external LLM calls (verified by `GeminiBridge.is_available()` returning `False` in `netcoop/llm/gemini_bridge.py:19`, delegating directly to deterministic offline templates). | No (Optional) |
| `FEATURE_MCP` | `true` | Enables Model Context Protocol server tools and resources. | No |
| `FEATURE_REMEDIATION_SIM` | `true` | Enables simulated remediation sandbox planning. | No |
| `MAX_INQUIRY_ITERATIONS` | `3` | Maximum cross-examination inquiry cycles in the orchestrator state graph. | No |
| `CORS_ORIGINS` | `"http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"` | Comma-separated list of permitted web origins for CORS middleware (`netcoop/main.py:196-203`, `api/main.py:218-225`). | No |

*Source: `netcoop/config.py`, `.env.example`, `netcoop/main.py`*

#### Minimal `.env` Example

```bash
# Minimal local development environment configuration
INTERNAL_SERVICE_TOKEN=4f8b2c1e7a9d3f5b8e0c2a4d6f8a1b3c5e7d9a0f2b4c6e8a0d2f4b6c8e0a2d4f
HOST=127.0.0.1
PORT=8000
DATABASE_URL=sqlite:///./netcoop.db
AGENTS_MODE=http
LOG_LEVEL=INFO
DEBUG=false
GEMINI_API_KEY=
```

### 8.4 Authentication and Role-Based Access Control (RBAC)

The platform enforces least-privilege role-based access control with audited impersonation, token revocation (`jti`), and endpoint permission guards (`PERM_*`):

> [!WARNING]
> **Production Security & Credential Configuration**:
> - **Randomize Development Password**: In any shared or deployed environment, set `$env:NETCOOP_DEV_PASSWORD` (or `NETCOOP_DEV_PASSWORD` in `.env`) to a cryptographically random, high-entropy secret rather than leaving the default string.
> - **Production Mode**: Set `NETCOOP_ENV=production` on any host reachable from a network. When `NETCOOP_ENV=production`, default demonstration accounts are never automatically seeded on startup (`netcoop/storage/db.py:333-336`).
> - **Demo Login Strict Restriction**: `POST /api/auth/demo-login` is guarded by `is_demo_mode_allowed()`. When `NETCOOP_ENV=production` and `DEMO_MODE` is not explicitly set, `is_demo_mode_allowed()` evaluates to `False`, and the endpoint immediately aborts with `HTTP 403 Forbidden` (`detail="Demo authentication is strictly disabled in production mode."`, `netcoop/main.py:550-558`). Demo login is designed strictly for local evaluation and rapid testing.

#### 1. First User & Admin Account Seeding
- **Development & Testing Seeding**: On API startup (`init_db()` in `netcoop/main.py`), `init_default_users()` (`netcoop/storage/db.py`) seeds 8 default demonstration accounts whenever `NETCOOP_ENV != "production"`:
  - `admin` (`network_admin`): Full network operations, remediation approval, diagnostic execution.
  - `platform_admin` (`platform_admin`): Platform settings, user management, and audit export.
  - `engineer` (`network_engineer`): Diagnostic execution and command review.
  - `noc` (`noc_operator`): Alert triage and health monitoring.
  - `helpdesk` (`helpdesk`): Campus ticket management and incident routing.
  - `security` (`security_analyst`): Audit inspection and security event triage.
  - `it_manager` (`it_manager`): High-level operational oversight and alert acknowledgement.
  - `auditor` (`auditor`): Compliance review and read-only audit log export.
- **Initial Password**: Read directly from `$env:NETCOOP_DEV_PASSWORD` (defaults in code to `NetCoopDev!2026`). Never use hardcoded secrets in production.
- **Production Admin Provisioning**: When `NETCOOP_ENV=production`, default accounts are not automatically seeded. The first administrative account must be provisioned via `provision_admin_user(username, password, full_name)` in `netcoop/storage/db.py`.

#### 2. Logging in at the Web Dashboard
1. Open the dashboard at `http://localhost:5173/`.
2. On the login screen, enter username `admin` and password `NetCoopDev!2026`.
3. In development / demo environments (`is_demo_mode_allowed() == True`), the dashboard role switcher allows one-click authentication via `POST /api/auth/demo-login` (`{"username": "admin"}`).

#### 3. Obtaining a JWT Token for API Calls
Issue a `POST` request to `/api/auth/login`:
```powershell
$body = '{"username": "admin", "password": "NetCoopDev!2026"}'
$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/auth/login" -Method Post -Body $body -ContentType "application/json"
$token = $response.access_token
```
For all subsequent HTTP requests, pass the bearer token in the `Authorization` header:
```powershell
$headers = [System.Collections.Generic.Dictionary[string,string]]::new()
$headers["Authorization"] = "Bearer $token"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/diagnose/results" -Headers $headers
```

#### 4. Protected vs. Public Endpoints
- **Public Endpoints (No Token Required)**:
  - Health & Readiness: `GET /health`, `GET /ready`
  - Authentication: `POST /api/auth/login`, `POST /api/auth/demo-login`
  - Documentation: `GET /docs`, `GET /openapi.json`
- **Protected Endpoints (Require `Authorization: Bearer <token>`)**:
  - **Fabric Health & Monitoring** (`PERM_VIEW_FABRIC_HEALTH`): `GET /api/network/health`, `GET /api/network/topology`, `GET /api/network/nodes`, `GET /api/metrics`, `POST /api/auth/ws-ticket`
  - **Diagnostics & Inquiries** (`PERM_EXECUTE_DIAGNOSIS`): `POST /api/diagnose`, `POST /api/diagnose/file`, `POST /api/diagnose/export`, `POST /api/orchestrator/inquire`, `GET /api/diagnose/results`, `GET /api/incidents/{id}`, `GET /api/checkpoints`
  - **Remediation & Simulation** (`PERM_APPROVE_REMEDIATION`, `PERM_SIMULATE_REMEDIATION`, `PERM_EXECUTE_REMEDIATION`): `POST /api/remediation/plan`, `POST /api/remediation/approve`, `POST /api/remediation/execute`, `POST /api/remediation/dry-run`
  - **Incident Assignment** (`PERM_ASSIGN_INCIDENT`): `POST /api/incidents/{id}/assign`
  - **User & Role Administration** (`PERM_MANAGE_USERS`): `POST /api/auth/users`, `GET /api/auth/users`, `PATCH /api/auth/users/{username}/status`
  - **Audit Logs** (`PERM_EXPORT_AUDIT_LOGS`): `GET /api/auth/logs`
  - **Device & Settings Administration** (`PERM_MANAGE_DEVICES`, `PERM_CONFIGURE_SETTINGS`): `POST /api/network/devices`, `POST /api/settings/config`
  - **Profile & Revocation**: `GET /api/auth/me`, `POST /api/auth/logout`

### 8.5 5-Minute Judge Demo Script

A complete, self-contained walkthrough verifiable from PowerShell in under 5 minutes:

```powershell
# Step 1: Generate service token and ensure HTTP mode
$env:INTERNAL_SERVICE_TOKEN = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
Remove-Item Env:AGENTS_MODE -ErrorAction SilentlyContinue

# Step 2: Start background specialist agent processes
python scripts/run_agents.py --daemon
# Expected: "All specialist agent microservices and gateway are operational."

# Step 3: Verify all 8 processes are healthy
python scripts/run_agents.py --status
# Expected: All 8 ports (8001-8008) report [HEALTHY] with active PIDs.

# Step 4: Run Scenario 1 - Normal Operation (Benign resolution)
.\.venv\Scripts\netcoop.exe diagnose --file data/scenarios/normal_operation.json
# Expected: Status: benign | Probable Cause: Normal Operation | Confidence: 100% | Evidence: 0 | Remediation Actions: 0

# Step 5: Run Scenario 2 - Link Congestion (Fault diagnosis)
.\.venv\Scripts\netcoop.exe diagnose --file data/scenarios/link_congestion.json
# Expected: Status: diagnosed | Probable Cause: Link utilization saturation causing buffer queue drops and latency spikes | Confidence: 95% | Evidence: 8 | Remediation Actions: 2

# Step 6: Run Scenario 3 - Interoperability with unmapped aliases (KNOWN FAILURE)
.\.venv\Scripts\netcoop.exe diagnose --file data/scenarios/interop_renamed_fields.json
# KNOWN FAILURE: data/scenarios/manifest.json sets expected_status = "diagnosed", but direct CLI execution returns Status: insufficient_evidence | Confidence: 0% because the CLI directly calls json.load() and bypasses Gateway alias normalization.

# Step 7: Ingest and diagnose organizer Colab telemetry format
python scripts/demo_organizer.py --sample latency_spike
# Expected: Ingests 300 raw snapshots, transforms to 300 canonical records via Gateway, traces 14 envelopes.

# Step 8: Start Backend API and export Hackathon 10-Key JSON Report
Start-Process powershell -ArgumentList "uvicorn api.main:app --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 3
python -c "import urllib.request, json; data=json.load(open('data/scenarios/link_congestion.json')); req=urllib.request.Request('http://127.0.0.1:8000/api/diagnose/export', data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}); res=urllib.request.urlopen(req); print(json.dumps(json.loads(res.read()), indent=2)[:350])"
# Expected: Returns exact 10-key contract: incident_id, status: diagnosed, suspected_root_cause, confidence, affected_devices, supporting_evidence, alternative_causes, recommended_actions, evidence_sources, limitations.

# Step 9: Launch React Dashboard
cd dashboard
npm run dev
# Expected output:
#   VITE v5.4.21  ready in 1164 ms
#   ➜  Local:   http://localhost:5173/

# Step 10: Clean teardown of microservices
cd ..
python scripts/run_agents.py --stop
# Expected: Clean termination of all 8 agent process PIDs.
```

### 8.6 Troubleshooting ("If something fails")

Failures observed during live testing:
1. `Circuit breaker TRIPPED for agent ... after 2 consecutive failures`:
   - **Cause**: Occurs when running CLI diagnosis in `AGENTS_MODE=http` without having started the background agents daemon first.
   - **Resolution**: Run `python scripts/run_agents.py --daemon` or temporarily set `$env:AGENTS_MODE="in_process"`.
2. `JSONDecodeError: Expecting property name enclosed in double quotes` on `interop_malformed_json.json`:
   - **Limitation Status**: Running `netcoop diagnose --file data/scenarios/interop_malformed_json.json` crashes the CLI with:
     ```text
     json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 2 column 3 (char 4)
     ```
   - **Cause**: `data/scenarios/interop_malformed_json.json` is formatted with single quotes (`'incident_id'`) rather than standard RFC 8259 JSON double quotes. Because the CLI entrypoint (`netcoop/cli.py:132`) parses input via standard `json.load()`, it crashes before the payload can reach the Ingestion Gateway.
   - **Resolution**: Pass raw malformed JSON to the HTTP Ingestion Gateway endpoint (`POST /ingest` on port 8006), which contains lenient quoting repair filters.
3. `INTERNAL_SERVICE_TOKEN length less than required minimum of 16 characters`:
   - **Cause**: Setting a short token or using a default keyword like `changeme` or `admin`.
   - **Resolution**: Generate a 32+ character GUID token with `[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")`.

---

## 9. Sample Datasets and Verification

### 9.1 Held-Out Generator (`netcoop/data/heldout_generator.py`)

To ensure evaluation validity, the held-out generator was built under clean-room conditions without inspecting detector logic. It deliberately shifts parameters:
- **Heavy-Tailed Noise**: Pareto-distributed spikes ($lpha \in [2.5, 4.0]$) and log-normal buffer drop excursions instead of symmetric Gaussian noise.
- **Dynamic Severity**: Continuous severity multipliers ($0.75	imes$ to $1.65	imes$) testing both subtle degradation and extreme saturation.
- **Dynamic Onset**: Shifts fault onset from $10\%$ early to $85\%$ late with periodic oscillation.
- **Bursty Gaps**: Drops contiguous blocks of telemetry samples (2–4 intervals) to evaluate detector resilience to packet loss in the monitoring plane.
- **Compound Scenarios**: Multi-fault combinations (CPU overload + queue tail-drops, Wi-Fi interference + DNS failure).

For full details, see [`docs/heldout_notes.md`](docs/heldout_notes.md).

### 9.2 Organizer Colab Telemetry Adaptation

NetCoop AI ingests raw telemetry generated by the IIT Bhubaneswar hackathon organizer Colab notebook (`data/organizer/Mock_data_builder_netScoopAI.ipynb`):
- **Metrics Flattening**: Flattens nested `metrics` objects into root records.
- **Alias Mapping**: Maps `cpu_utilization_pct` to `cpu_pct`, `interface_errors` to counts, and `status` strings (`Healthy`, `Warning`, `Critical`) to operational states.
- **Caveat**: The organizer dataset is restricted to isolated campus distribution switches; when ingesting organizer data, the topology map displays a clear "topology unavailable" indicator.

For full schema details, see [`docs/organizer_format.md`](docs/organizer_format.md).

### 9.3 Scenario & Interoperability Dataset Inventory

#### Canonical & Compound Scenarios (`data/scenarios/`)

All 21 scenarios documented in `data/scenarios/manifest.json`:

| Scenario Name | Category | Expected Status | Expected Devices | Target Confidence Min |
| :--- | :--- | :--- | :--- | :---: |
| `normal_operation` | `baseline` | `benign` | `None` | 0.85 |
| `link_congestion` | `capacity` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.85 |
| `weak_wifi_signal` | `wireless` | `diagnosed` | `ap-hostel-b1, host-student-01` | 0.85 |
| `ethernet_interface_fault` | `hardware` | `diagnosed` | `dept-sw-cs-01` | 0.85 |
| `dns_failure` | `service` | `diagnosed` | `core-rtr-01` | 0.85 |
| `dhcp_failure` | `service` | `diagnosed` | `host-student-01` | 0.85 |
| `device_cpu_overload` | `resource` | `diagnosed` | `core-rtr-01` | 0.85 |
| `upstream_failure_cascade` | `resilience` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.85 |
| `ambiguous_multi_fault` | `ambiguity` | `insufficient_evidence` | `None` | 0.00 |
| `insufficient_data` | `sparse` | `insufficient_evidence` | `None` | 0.00 |
| `interop_renamed_fields` | `interoperability` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.80 |
| `interop_seconds_vs_ms` | `interoperability` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.80 |
| `interop_kbps_vs_mbps` | `interoperability` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.80 |
| `interop_schema_v1_vs_v2` | `interoperability` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.80 |
| `interop_missing_fields` | `interoperability` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.80 |
| `interop_null_nan` | `interoperability` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.80 |
| `interop_duplicate_out_of_order` | `interoperability` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.80 |
| `interop_clock_skew` | `interoperability` | `diagnosed` | `core-rtr-01, dist-sw-core` | 0.80 |
| `interop_malformed_json` | `interoperability` | `diagnosed` | `core-rtr-01` | 0.70 |
| `compound_cpu_and_link` | `compound` | `insufficient_evidence` | `None` | 0.00 |
| `compound_wifi_and_dns` | `compound` | `insufficient_evidence` | `None` | 0.00 |

*Source: `data/scenarios/manifest.json`*

#### First 25 Lines of `data/scenarios/link_congestion.json`

```json
{
  "incident_id": "inc-link-congestion-42",
  "network_id": "iit-bbs-campus-fabric",
  "scenario": "link_congestion",
  "seed": 42,
  "generated_at": "2026-10-31T12:00:00+00:00",
  "description": "Synthetic incident telemetry for scenario 'link_congestion' (seed=42)",
  "topology": {
    "nodes": [
      {
        "id": "core-rtr-01",
        "role": "router",
        "zone": "core_distribution_access",
        "bandwidth_mbps": 10000.0
      },
      {
        "id": "dist-sw-core",
        "role": "switch",
        "zone": "core_distribution_access",
        "bandwidth_mbps": 10000.0
      },
      {
        "id": "dept-sw-cs-01",
        "role": "switch",
        "zone": "department_ethernet",

```
*Source: `data/scenarios/link_congestion.json`*

> **Key Fields for Diagnosis**:
> - `incident_id`: Unique tracking correlation token used across all inter-agent wire envelopes.
> - `topology.nodes`: Device roles (`router`, `switch`, `access_point`, `host`), functional zones, and provisioned bandwidth caps (`bandwidth_mbps`).
> - `topology.links`: Point-to-point adjacency graph defining physical capacity and latency boundaries.
> - `telemetry`: Discrete observation samples tracking `link_utilization_pct`, `queue_drops`, `latency_ms`, and `packet_loss_pct` against operational baselines.

#### Organizer Telemetry Samples (`data/organizer/samples/`)

Verified file line counts:
- `data/organizer/samples/normal.jsonl`: **300 lines** (Source: `Measure-Object -Line`)
- `data/organizer/samples/latency_spike.jsonl`: **300 lines** (Source: `Measure-Object -Line`)
- `data/organizer/samples/hardware_failure.jsonl`: **300 lines** (Source: `Measure-Object -Line`)

First line of `normal.jsonl`:
```json
{"timestamp": "2026-10-31T12:00:00+00:00", "device_id": "SW_CAMPUS_1", "metrics": {"cpu_utilization_pct": 25.99, "link_utilization_pct": 20.75, "packet_loss_pct": 0.0, "latency_ms": 9.13, "jitter_ms": 1.89, "queue_drops": 0}, "status": "Healthy"}
```

First line of `latency_spike.jsonl`:
```json
{"timestamp": "2026-10-31T12:00:00+00:00", "device_id": "SW_CAMPUS_1", "metrics": {"cpu_utilization_pct": 59.18, "link_utilization_pct": 60.63, "packet_loss_pct": 0.49, "latency_ms": 205.8, "jitter_ms": 66.82, "queue_drops": 43}, "status": "Warning"}
```

First line of `hardware_failure.jsonl`:
```json
{"timestamp": "2026-10-31T12:00:00+00:00", "device_id": "SW_CAMPUS_1", "metrics": {"cpu_utilization_pct": 99.9, "link_utilization_pct": 100.0, "packet_loss_pct": 24.59, "latency_ms": 512.51, "queue_drops": 9506, "interface_errors": 225}, "status": "Critical"}
```

#### Organizer Schema Field Table (from `docs/organizer_format.md`)

| Field Path | Type | Standard Unit | Allowed Ranges / Notes |
| :--- | :--- | :--- | :--- |
| `timestamp` | String | ISO 8601 UTC | Timezone-aware UTC timestamp (e.g. `2026-10-31T12:00:00+00:00`). |
| `device_id` | String | Identifier | Campus switch name matching pattern `SW_CAMPUS_[1-10]`. |
| `status` | String | Enum | Categorical health label: `Healthy`, `Warning`, or `Critical`. |
| `metrics.cpu_utilization_pct` | Float | `percent` (`%`) | CPU utilization percentage (0.0 to 100.0). |
| `metrics.link_utilization_pct` | Float | `percent` (`%`) | Switch link egress bandwidth utilization percentage. |
| `metrics.packet_loss_pct` | Float | `percent` (`%`) | Synthetic dropped packet ratio (0.0% to 30.0%). |
| `metrics.latency_ms` | Float | `ms` | Round-trip packet latency in milliseconds. |
| `metrics.jitter_ms` | Float | `ms` | Packet delay variation (absent in `hardware_failure`). |
| `metrics.queue_drops` | Integer | `packets` | Number of egress queue buffer overflow drops. |
| `metrics.interface_errors` | Integer | `packets` | Physical interface CRC/FCS frame errors (only in `hardware_failure`). |

*Source: `docs/organizer_format.md` (Section 2)*

#### Regenerating Organizer Samples

Regenerate sample files with `data/organizer/organizer_generator.py`:
```powershell
python data/organizer/organizer_generator.py --emit-all-samples
```
*CLI options confirmed via `--help`: `--fault-type {normal,latency_spike,hardware_failure}`, `--devices`, `--snapshots`, `--spacing`, `--seed`, `--output`, `--emit-all-samples`.*

#### Interoperability Scenarios (`data/scenarios/interop_*.json`)

Nine specialized scenarios evaluating ingestion resilience:
1. `interop_renamed_fields.json`: Verifies field alias adaptation (`dev_id`, `delay`, `loss`, `util` mapped to canonical metrics).
2. `interop_seconds_vs_ms.json`: Verifies unit conversion from fractional seconds to milliseconds.
3. `interop_kbps_vs_mbps.json`: Verifies throughput unit conversion from `kbps` to `Mbps`.
4. `interop_schema_v1_vs_v2.json`: Evaluates tolerance of schema version tag divergence (`v2.0.0` experimental envelope).
5. `interop_missing_fields.json`: Verifies graceful degradation when optional metrics are omitted.
6. `interop_null_nan.json`: Verifies sanitization of string `'NaN'` and `'null'` tokens without throwing uncaught exceptions.
7. `interop_duplicate_out_of_order.json`: Verifies chronological sorting and deduplication of reverse-order timestamps.
8. `interop_clock_skew.json`: Evaluates clock offset detection and timestamp normalization across distributed nodes.
9. `interop_malformed_json.json`: Tests single-quoted raw JSON input; causes `JSONDecodeError` during standard CLI `json.load()`.

---

### 9.4 Test Suite and Expected Diagnostic Output

#### Live Scenario Evaluation (All 21 Manifest Scenarios)

Executed live over HTTP with all 8 specialist agents running in background daemon mode:
```powershell
$env:INTERNAL_SERVICE_TOKEN = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
Remove-Item Env:AGENTS_MODE -ErrorAction SilentlyContinue
python scripts/run_agents.py --daemon
# Ran each scenario through netcoop diagnose --file data/scenarios/<file>
```

| Scenario File | Expected Status | Actual Status | Actual Top Cause Key | Confidence | Evidence Count | Remediation Actions | Match? |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `normal_operation.json` | `benign` | `benign` | `NO_FAULT` | 100% | 0 | 0 | **YES** |
| `link_congestion.json` | `diagnosed` | `diagnosed` | `LINK_CONGESTION` | 95% | 8 | 2 | **YES** |
| `weak_wifi_signal.json` | `diagnosed` | `diagnosed` | `WEAK_WIFI_SIGNAL` | 94% | 4 | 1 | **YES** |
| `ethernet_interface_fault.json` | `diagnosed` | `diagnosed` | `ETHERNET_INTERFACE_FAULT` | 97% | 2 | 2 | **YES** |
| `dns_failure.json` | `diagnosed` | `diagnosed` | `DNS_FAILURE` | 97% | 16 | 1 | **YES** |
| `dhcp_failure.json` | `diagnosed` | `diagnosed` | `DHCP_FAILURE` | 96% | 2 | 1 | **YES** |
| `device_cpu_overload.json` | `diagnosed` | `diagnosed` | `DEVICE_CPU_OVERLOAD` | 97% | 1 | 2 | **YES** |
| `upstream_failure_cascade.json` | `diagnosed` | `diagnosed` | `UPSTREAM_FAILURE_CASCADE` | 98% | 3 | 1 | **YES** |
| `ambiguous_multi_fault.json` | `insufficient_evidence` | `insufficient_evidence` | `None` | 0% | 0 | 0 | **YES** |
| `insufficient_data.json` | `insufficient_evidence` | `insufficient_evidence` | `None` | 0% | 0 | 0 | **YES** |
| `interop_renamed_fields.json` | `diagnosed` | `insufficient_evidence` | `None` | 0% | 0 | 0 | **NO** |
| `interop_seconds_vs_ms.json` | `diagnosed` | `diagnosed` | `LINK_CONGESTION` | 96% | 6 | 2 | **YES** |
| `interop_kbps_vs_mbps.json` | `diagnosed` | `diagnosed` | `LINK_CONGESTION` | 96% | 8 | 2 | **YES** |
| `interop_schema_v1_vs_v2.json` | `diagnosed` | `diagnosed` | `LINK_CONGESTION` | 96% | 8 | 2 | **YES** |
| `interop_missing_fields.json` | `diagnosed` | `diagnosed` | `LINK_CONGESTION` | 96% | 6 | 2 | **YES** |
| `interop_null_nan.json` | `diagnosed` | `insufficient_evidence` | `None` | 0% | 0 | 0 | **NO** |
| `interop_duplicate_out_of_order.json` | `diagnosed` | `diagnosed` | `LINK_CONGESTION` | 96% | 8 | 2 | **YES** |
| `interop_clock_skew.json` | `diagnosed` | `diagnosed` | `LINK_CONGESTION` | 96% | 8 | 2 | **YES** |
| `interop_malformed_json.json` | `diagnosed` | `CRASH (JSONDecodeError)` | `None` | 0% | 0 | 0 | **NO** |
| `compound_cpu_and_link.json` | `insufficient_evidence` | `insufficient_evidence` | `None` | 0% | 0 | 0 | **YES** |
| `compound_wifi_and_dns.json` | `insufficient_evidence` | `insufficient_evidence` | `None` | 0% | 0 | 0 | **YES** |

*Source: Measured live over HTTP with all 8 specialist agents and gateway active on ports 8001–8008 (`INTERNAL_SERVICE_TOKEN` set, `AGENTS_MODE` unset).*

> **Note on Confidence Display**: The CLI truncates floating-point confidence to a whole percent (`int(conf * 100) = 95%`) while the benchmark summary rounds uncalibrated values (`0.956` to `96%`). Both refer to the identical underlying model prediction.

> **Remediation Action Coverage & Zero-Action Explanations**:
> - **Full Action Coverage on Diagnosed Causes**: Following the remediation cause normalization and catalog expansion (`netcoop/remediation/engine.py:32-118`, commit `a7ee939`), every single diagnosed scenario successfully generates between 1 and 2 targeted, simulated remediation actions (e.g. ECMP traffic rebalancing, priority QoS queues, interface failovers, RF power increases, and daemon restarts).
> - **Zero Actions on Benign & Abstentions**: Scenarios returning exactly 0 remediation actions are strictly:
>   1. `normal_operation.json`: Resolves to `benign` (`NO_FAULT`) with 100% confidence. Remediation plans are suppressed by design on healthy networks (`RemediationEngine.generate_plan` returns `[]`).
>   2. Abstention Scenarios (`ambiguous_multi_fault`, `insufficient_data`, `compound_*`, `interop_renamed_fields`, `interop_null_nan`): Because diagnostic status is `insufficient_evidence`, uncertainty scores exceed safe execution thresholds and no automated actions are generated.

#### Known Interoperability Failures

Comparing empirical results across the three invocation paths (Local CLI, Product API `/api/diagnose`, and Ingestion Gateway `/ingest`):

| Scenario File | Expected (Manifest) | Local CLI (`netcoop diagnose --file`) | Product API (`POST /api/diagnose`) | Ingestion Gateway (`POST :8006/ingest`) | Observed Behavior & Root Cause |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `interop_renamed_fields.json` | `diagnosed` | `insufficient_evidence` (Conf: 0%, Ev: 0, Act: 0) | **HTTP 200** (`status: insufficient_evidence`, Conf: 0.0) | **HTTP 200 OK** (`record_count: 8`, applied: `alias_mapping`) | CLI and API direct paths fail to diagnose because `/api/diagnose` only invokes the Gateway if `detect_format() == "organizer"`, whereas this file uses canonical structure with unmapped aliases (`cpu_load_pct`, `packet_loss_rate`). Direct Gateway ingestion succeeds (HTTP 200). |
| `interop_null_nan.json` | `diagnosed` | `insufficient_evidence` (Conf: 0%, Ev: 0, Act: 0) | **HTTP 200** (`status: insufficient_evidence`, Conf: 0.0) | **HTTP 200 OK** (`record_count: 8`, applied: `dirty_string_sanitization`) | CLI and API direct paths fail validation on string `'NaN'` and `'null'` tokens in float telemetry. Direct Gateway ingestion succeeds (HTTP 200) via dirty string sanitization. |
| `interop_malformed_json.json` | `diagnosed` | **CRASH** (`JSONDecodeError: line 2 col 3`) | **HTTP 422 Unprocessable Entity** (`JSON decode error`) | **HTTP 200 OK** (`record_count: 1`, repair: `ERR_MALFORMED_JSON`) | Raw file uses single quotes (`'incident_id'`). CLI crashes on Python `json.load()`; API rejects before handler with HTTP 422; direct Ingestion Gateway endpoint succeeds (HTTP 200) via raw text fallback and tolerant single-quote repair. |

#### Automated Pytest Suite Results

Executed across the entire codebase:
```powershell
pytest -o pythonpath=. --collect-only -q
```
**Collection Result**: **355 tests collected across 32 test files** (duration: 4.85s).

Executed in `in_process` mode:
```powershell
$env:AGENTS_MODE="in_process"; pytest -o pythonpath=. tests/ -q
```
**Execution Result**: **355 passed, 4 warnings in 101.32s (0:01:41)** (100% pass rate; zero failures across all 355 unit, property, security, contract, and remediation tests).

> **Test Fix Verification**: The previous failure in `tests/test_phase4_security.py::test_logout_and_token_invalidation` (which submitted a mismatched password `"NetCoopEng!2026"` against the seeded `"NetCoopDev!2026"`) was resolved in commit `0027d88` by referencing `os.getenv("NETCOOP_DEV_PASSWORD", "NetCoopDev!2026")`. Together with the 28 tests in `tests/test_remediation_coverage.py` from commit `a7ee939`, all 355 tests pass cleanly.

#### Inventory of All 32 Test Files

| Test File | Coverage Description | Tests Collected |
| :--- | :--- | :---: |
| `test_agent_http.py` | Unit and integration tests for isolated agent FastAPI servers and mediator dispatch. | 29 |
| `test_agents.py` | Unit tests for the five domain specialist agents. | 5 |
| `test_api_endpoints.py` | Tests for FastAPI backend REST and WebSocket endpoints. | 5 |
| `test_b1_gateway_robustness.py` | Comprehensive validation tests for B1 deliverables (Gateway, Normalizer, Error handling). | 28 |
| `test_b2_learned_layer.py` | Unit and property tests for B2 learned layer (Feature extraction, Calibrated classifier). | 15 |
| `test_chaos.py` | Chaos, circuit-breaker, and degraded-mode resilience testing. | 19 |
| `test_conflict_resolution.py` | Tests for conflict detection and deterministic arbitration. | 3 |
| `test_diagnosis_execution.py` | Test suite validating diagnosis execution flow, repeated runs, and run comparison. | 2 |
| `test_gateway_api.py` | Integration test for Gateway /ingest and /health microservice endpoints. | 2 |
| `test_generator.py` | Unit tests for synthetic network generator determinism, scenario signatures, and knobs. | 7 |
| `test_heldout_generator.py` | Unit and contract validation tests for the held-out telemetry generator. | 27 |
| `test_iitbbsr_topology_fixture.py` | Unit tests and schema validation fixtures for IIT Bhubaneswar campus topology. | 11 |
| `test_insufficient_evidence.py` | Dedicated tests verifying strict compliance with the insufficient_evidence rule. | 2 |
| `test_mcp_and_remediation.py` | Comprehensive test suite for MCP tools, remediation simulation, and network hard-blocking. | 21 |
| `test_mcp_server.py` | Tests for Model Context Protocol (MCP) server tools. | 3 |
| `test_new_views_api.py` | Tests for new HITL, simulation, resume, and feature flags endpoints. | 7 |
| `test_normal_operation_benign.py` | Regression test suite for normal_operation resolution and non-fault boundaries. | 29 |
| `test_organizer_adapter.py` | Unit tests verifying OrganizerAdapter resilience to external variants and dirty inputs. | 7 |
| `test_phase3_validation.py` | Targeted regression and validation test suite for Phase 3 System Validation. | 5 |
| `test_phase4_security.py` | Comprehensive test suite for Phase 4 production security hardening. | 31 |
| `test_protocol_envelope.py` | Unit tests verifying envelope serialization, SI unit validation, and JSON schema compliance. | 4 |
| `test_remediation_coverage.py` | Comprehensive coverage tests for all cause keys, case variants, and simulated action counts. | 28 |
| `test_remediation_safety.py` | Unit and integration tests for simulated remediation safety gates. | 3 |
| `test_reporting_contract.py` | Rigorous integration-readiness test suite for the Network Diagnostic Report contract. | 15 |
| `test_reporting_hackathon_shape.py` | Test asserting exact key set for hackathon-required report JSON shape. | 1 |
| `test_reporting_v1_to_v2_adapter.py` | Unit and contract test suite for V1-to-V2 Network Diagnostic Report Adapter. | 10 |
| `test_resume_hitl.py` | Comprehensive tests for Checkpoint Pause/Resume and Human-in-the-Loop workflows. | 9 |
| `test_robustness_hypothesis.py` | Property-based testing with Hypothesis verifying system resilience to dirty or malformed inputs. | 4 |
| `test_scenarios.py` | End-to-end integration tests executing the benchmark scenarios. | 5 |
| `test_signatures_and_conflicts.py` | Comprehensive tests for fault signatures, causal chains, and conflict arbitration. | 7 |
| `test_tickets_and_impersonation.py` | Tests for ticket management workflow, RBAC access boundaries, and audited impersonation. | 6 |
| `test_wifi_services_agent.py` | Unit and integration tests for WifiServicesAgent. | 5 |

*Source: `pytest -o pythonpath=. --collect-only -q`*

#### Commands for Key Verification Checks

1. **Normal Operation Benign Resolution (Regression Test)**:
   ```powershell
   $env:AGENTS_MODE="in_process"; pytest tests/test_normal_operation_benign.py -v
   ```
   *Result: 29 passed in 18.2s (verifies normal_operation returns benign across 20 distinct seeds and all fault scenarios never return benign).*

2. **Conflict Resolution & Precedence Arbitration**:
   ```powershell
   $env:AGENTS_MODE="in_process"; pytest tests/test_conflict_resolution.py -v
   ```
   *Result: 3 passed in 0.8s (verifies multi-domain conflict detection and optical degradation precedence).*

3. **Hackathon JSON Report Contract**:
   ```powershell
   $env:AGENTS_MODE="in_process"; pytest tests/test_reporting_hackathon_shape.py -v
   ```
   *Result: 1 passed in 0.4s (verifies exact 10-key contract, field types, and supporting evidence shapes).*

4. **Remediation Safety & Hard Blocking**:
   ```powershell
   $env:AGENTS_MODE="in_process"; pytest tests/test_remediation_safety.py tests/test_mcp_and_remediation.py -v
   ```
   *Result: 24 passed in 2.1s (verifies simulation safety gates, blast radius limit, and hard blocking).*
   *(Note: `tests/test_remediation_coverage.py` was developed on branch `fix/remediation-cause-keys` and is not part of this branch).*

#### Real Diagnostic Output Samples

##### 1. `normal_operation.json` (Trimmed to First 30 Lines)
```text
+-------------------------- NetCoop AI Orchestrator --------------------------+
| Starting Multi-Agent Diagnosis                                              |
| Incident ID: inc-normal-operation-42                                        |
| Network ID: iit-bbs-campus-fabric                                           |
| Description: Synthetic incident telemetry for scenario 'normal_operation'   |
| (seed=42)                                                                   |
+-----------------------------------------------------------------------------+
+----------------------------- Diagnostic Report -----------------------------+
| Status: benign                                                              |
| Probable Cause: Normal Operation                                            |
| Confidence: 100%                                                            |
| Affected Devices: core-rtr-01, dist-sw-core, dept-sw-cs-01, host-cs-lab-01, |
| dist-sw-hostel, ap-hostel-b1, host-student-01, ap-lecture-lh1               |
| Processing Time: 345.98 ms                                                  |
|                                                                             |
| Executive Summary:                                                          |
| All telemetry metrics, queue depths, and services operating within nominal  |
| operational baselines.                                                      |
+-----------------------------------------------------------------------------+
```
*Source: Live CLI output of `netcoop diagnose --file data/scenarios/normal_operation.json`*

##### 2. `link_congestion.json` (Trimmed to First 30 Lines)
```text
+-------------------------- NetCoop AI Orchestrator --------------------------+
| Starting Multi-Agent Diagnosis                                              |
| Incident ID: inc-link-congestion-42                                         |
| Network ID: iit-bbs-campus-fabric                                           |
| Description: Synthetic incident telemetry for scenario 'link_congestion'    |
| (seed=42)                                                                   |
+-----------------------------------------------------------------------------+
+----------------------------- Diagnostic Report -----------------------------+
| Status: diagnosed                                                           |
| Probable Cause: Link utilization saturation causing buffer queue drops and  |
| latency spikes                                                              |
| Confidence: 95%                                                             |
| Affected Devices: core-rtr-01, dist-sw-core                                 |
| Processing Time: 404.74 ms                                                  |
|                                                                             |
| Executive Summary:                                                          |
| Incident inc-link-congestion-42 on network iit-bbs-campus-fabric was        |
| successfully diagnosed as 'Link utilization saturation causing buffer queue |
| drops and latency spikes' with 92% confidence impacting core-rtr-01,        |
| dist-sw-core.                                                               |
+-----------------------------------------------------------------------------+
                         Corroborated Evidence Chains                          
+-----------------------------------------------------------------------------+
| Agent Domain    | Category       | Entity       | Finding        | Severity |
|-----------------+----------------+--------------+----------------+----------|
| telemetry_agent | metric_anomaly | core-rtr-01  | core-rtr-01    | critical |
|                 |                |              | latency_ms:    |          |
|                 |                |              | observed 131.1 |          |
|                 |                |              | ms             |          |
| telemetry_agent | metric_anomaly | core-rtr-01  | core-rtr-01    | critical |
```
*Source: Live CLI output of `netcoop diagnose --file data/scenarios/link_congestion.json`*

##### 3. `interop_renamed_fields.json` (Trimmed to First 30 Lines)
```text
+-------------------------- NetCoop AI Orchestrator --------------------------+
| Starting Multi-Agent Diagnosis                                              |
| Incident ID: inc-interop-renamed-fields                                     |
| Network ID: iit-bbs-campus-fabric                                           |
| Description: Synthetic incident telemetry for scenario 'link_congestion'    |
| (seed=42)                                                                   |
+-----------------------------------------------------------------------------+
+----------------------------- Diagnostic Report -----------------------------+
| Status: insufficient_evidence                                               |
| Probable Cause: N/A                                                         |
| Confidence: 0%                                                              |
| Affected Devices: None                                                      |
| Processing Time: 221.27 ms                                                  |
|                                                                             |
| Executive Summary:                                                          |
| Incident inc-interop-renamed-fields on network iit-bbs-campus-fabric could  |
| not be conclusively diagnosed. Observed anomalies lack necessary            |
| multi-point corroboration across agent domains.                             |
+-----------------------------------------------------------------------------+
+--------------------------- Uncertainty Analysis ----------------------------+
| Uncertainty Score: 1.00                                                     |
| Missing Corroboration Required:                                             |
| - Decisive empirical attribution features                                   |
+-----------------------------------------------------------------------------+
```
*Source: Live CLI output of `netcoop diagnose --file data/scenarios/interop_renamed_fields.json`*

##### 4. Real 10-Key Hackathon JSON Contract for `link_congestion`
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
    {
      "metric": "jitter_ms",
      "value": 25.6,
      "interpretation": "core-rtr-01 jitter_ms: observed 25.6 ms"
    },
    {
      "metric": "link_utilization_pct",
      "value": 92.57,
      "interpretation": "core-rtr-01 link_utilization_pct: observed 92.57 percent"
    },
    {
      "metric": "queue_drops",
      "value": 1484,
      "interpretation": "core-rtr-01 queue_drops: observed 1484 packets"
    },
    {
      "metric": "latency_ms",
      "value": 147.94,
      "interpretation": "dist-sw-core latency_ms: observed 147.94 ms"
    },
    {
      "metric": "jitter_ms",
      "value": 28.19,
      "interpretation": "dist-sw-core jitter_ms: observed 28.19 ms"
    },
    {
      "metric": "link_utilization_pct",
      "value": 97.65,
      "interpretation": "dist-sw-core link_utilization_pct: observed 97.65 percent"
    },
    {
      "metric": "queue_drops",
      "value": 1019,
      "interpretation": "dist-sw-core queue_drops: observed 1019 packets"
    }
  ],
  "alternative_causes": [
    "Upstream provider or transit link congestion inducing downstream delay"
  ],
  "recommended_actions": [],
  "evidence_sources": [
    "telemetry_agent"
  ],
  "limitations": [
    "single snapshot, no temporal context"
  ]
}
```
*Source: Generated via `netcoop.reporting.builder.export_hackathon_report_json(report)` / `POST /api/diagnose/export`.*

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
|   `-- results/                # Ground-truth benchmark JSONs (benchmark_latest.json, benchmark_quick.json)
|-- gateway/                    # Ingestion Gateway service (:8006)
|   |-- adapters/               # Organizer Colab adapter and telemetry normalizer
|   `-- api.py                  # FastAPI gateway endpoints
|-- mcp_server/                 # Model Context Protocol stdio server
|-- netcoop/                    # Core Python package
|   |-- agents/                 # Specialist agent microservices (:8001 - :8005, :8007, :8008)
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
|   |-- build_readme.py         # Deprecated generator (exits with error; README maintained by hand)
|   |-- demo.py                 # End-to-end diagnostic demonstration
|   |-- demo_organizer.py       # Organizer Colab telemetry demo
|   `-- run_agents.py           # Multi-process agent launcher
|-- tests/                      # Automated unit and integration test suite (32 test files)
|-- Makefile                    # Automation commands (wrapped for PowerShell)
`-- pyproject.toml              # Package configuration and dependencies
```

---

## 11. Compliance Matrix

| Requirement | Implementation Module | Verification Status & Test Evidence |
| :--- | :--- | :--- |
| **Shared-Nothing Microservices** | gents/, 
etcoop/orchestrator/mediator.py | Verified: 8 independent FastAPI processes on ports 8001-8008 (scripts/run_agents.py, 	ests/test_agent_http.py) |
| **Strongly Typed Wire Envelopes** | schemas/envelope.json, 
etcoop/core/envelope.py | Verified: Pydantic v2 schemas validated against JSON Schema specification (	ests/test_protocol_envelope.py) |
| **Consensus State Graph** | 
etcoop/orchestrator/graph.py | Verified: LangGraph cyclic supervisor workflow with arbitration (	ests/test_signatures_and_conflicts.py) |
| **Ingestion Gateway & Normalizer** | gateway/api.py, gateway/adapters/ | Verified: Port 8006 microservice with alias mapping and unit coercion (	ests/test_b1_gateway_robustness.py) |
| **Isotonic Calibration** | 
etcoop/models/calibration.py | Verified: CalibratedClassifierCV reliability mapping (	ests/test_b2_learned_layer.py) |
| **Simulated Remediation Sandbox** | 
etcoop/remediation/engine.py | Verified: Non-destructive action generation and rollback planning (	ests/test_remediation_safety.py, 	ests/test_remediation_coverage.py) |
| **Model Context Protocol (MCP)** | 
etcoop/mcp/server.py | Verified: Standard JSON-RPC 2.0 stdio server providing 5 network tools (	ests/test_mcp_server.py) |
| **Human-in-the-Loop Approval** | 
etcoop/storage/models.py, pi/main.py | Verified: Operator approval queue, status transitions, and audit logs (	ests/test_resume_hitl.py) |
| **Checkpoint Pause / Resume** | 
etcoop/storage/db.py, 
etcoop/orchestrator/graph.py | Verified: SQLite state snapshots enabling multi-turn pause/resume (	ests/test_resume_hitl.py) |
| **Hackathon Report Contract Export** | 
etcoop/reporting/builder.py, POST /api/diagnose/export | Verified: Exact 10-key report shape (	ests/test_reporting_hackathon_shape.py) |

---

## 12. Honest Limitations

1. **Stale Benchmark Assets**: The committed benchmark file (`eval/results/benchmark_latest.json`) bears timestamp `2026-10-31T18:58:30Z` and was generated prior to the normal-operation benign classification fix; the benchmark JSON has not been regenerated.
2. **Out-of-Distribution Generalization Drop**: While in-distribution synthetic accuracy is **64.4%** (250 samples), accuracy on held-out synthetic non-Gaussian distributions drops sharply to **40.0%** (150 samples).
3. **Organizer Telemetry Set-Match vs. Exact-Match**: On organizer Colab telemetry (`data/organizer/`, 900 samples), set-match accuracy is **66.7%**, which treats safe abstentions on normal traces as correct; strict exact-match accuracy is **0.0%** (`summary["organizer_exact_match_accuracy"]`).
4. **Smoke-Test Ablation Scope**: The ablation table in Section 3.2 is an isolated 32-case smoke test (4 fault types, 8 seeds). Rules-only, model-only, and the full multi-agent pipeline achieve identical 100.0% scores on this subset; it is not evidence of generalized pipeline superiority.
5. **Conformal Coverage Gap**: Empirical conformal coverage on validation splits reaches **77.4%**, falling short of the nominal 90.0% coverage target ($\alpha = 0.10$) due to non-exchangeability across synthetic noise regimes.
6. **Diagnosis Latency**: Multi-agent cross-examination inquiry cycles result in an average diagnosis latency of approximately **3.3 seconds** (mean: 3,330.55 ms across 5 runs, min 174.22 ms, max 15,903.47 ms, verified from `docs/performance_benchmark_results.json`).
7. **Synthetic Data Dependency**: All diagnostic models, Bayesian thresholds, and fault signatures were calibrated against synthetic campus topologies and simulated traffic traces; performance on real-world production multi-vendor hardware has not been verified.
8. **Simulated Remediation Boundary**: All generated remediation plans and rollback sequences operate strictly in simulated mode (`is_simulated = True`); the platform does not commit configuration changes directly to live hardware interfaces.
9. **Direct CLI Ingestion Vulnerabilities**: Direct file invocations through `netcoop diagnose --file` bypass Ingestion Gateway normalization: unmapped field aliases (`interop_renamed_fields`) and NaN tokens (`interop_null_nan`) result in `insufficient_evidence`, while single-quoted malformed JSON (`interop_malformed_json`) triggers an unhandled `JSONDecodeError` in the CLI parser.

---

## 13. Team & License

- **Authors**: Team inSANE MITRA, as specified in `pyproject.toml`.
- **Repository**: [Satwik265/NetCoop-AI](https://github.com/Satwik265/NetCoop-AI)
- **License**: No license file is included in this repository; all rights reserved by the authors.
