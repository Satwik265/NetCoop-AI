# NetCoop AI Cross-Team System Contract (v1.1.0)

This contract defines the authoritative inter-process boundaries, network endpoints, wire schemas, field names, units, and responsibilities for all NetCoop AI subsystems. It reverse-engineers the actual running implementation and provides a formal reference for Member A (Integrator), Member B (Specialist Agents & Gateway), and Member C (UI & Testing).

---

## 1. System Topology and Subsystem Allocation

| Team Member | Subsystem Ownership | Git Branch | Core Responsibilities |
| :--- | :--- | :--- | :--- |
| **Member A** (Integrator & Lead) | Orchestrator, Core Protocols, LangGraph Engine, Storage, CI/CD | `main` | Graph orchestration, mediator loop, conflict resolution, SQLite event log, `netcoop replay`, merge gatekeeper |
| **Member B** (Specialist Agents) | Specialist Domain Agents, Gateway Ingestion, Adapters | `feat/gateway`, `feat/agents` | Telemetry, Topology, Config, Log, and Synthesizer agents; Colab/organizer adapters; `/ingest` pipeline |
| **Member C** (UI & Testing) | Web Dashboard, WebSocket Stream, Replay, Test Harness | `feat/ui` | React monochrome dashboard, real-time envelope stream consumer, E2E demo runner, CLI commands |

---

## 2. Process Architecture and Port Allocations

All agents run as independent OS processes with dedicated Python interpreters. Agents never share memory, threads, or global state; communication occurs strictly over HTTP REST endpoints using versioned envelopes.

| Subsystem / Agent Role | Process Name | Host Binding | HTTP Port | Endpoints | Health Probe |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **Orchestrator & API** | `orchestrator` | `127.0.0.1` | **8000** | `POST /api/diagnose`<br/>`POST /api/ingest`<br/>`GET /api/incidents`<br/>`WS /ws/events`<br/>`WS /ws/envelopes` | `GET /api/health` |
| **Telemetry Agent** | `telemetry_agent` | `127.0.0.1` | **8001** | `POST /process` | `GET /health` |
| **Topology Agent** | `topology_agent` | `127.0.0.1` | **8002** | `POST /process` | `GET /health` |
| **Config Agent** | `config_agent` | `127.0.0.1` | **8003** | `POST /process` | `GET /health` |
| **Log Agent** | `log_agent` | `127.0.0.1` | **8004** | `POST /process` | `GET /health` |
| **Synthesizer Agent** | `synthesizer_agent` | `127.0.0.1` | **8005** | `POST /process` | `GET /health` |
| **Ingestion Gateway** | `gateway` | `127.0.0.1` | **8006** | `POST /ingest` | `GET /health` |

---

## 3. Wire Protocol: Standard Agent Envelope (`schemas/envelope.json`)

All inter-agent communication (requests, responses, cross-inquiries, synthesis submissions) is wrapped in the standard `AgentEnvelope`.

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
    "observations": [ ... ],
    "hypotheses": [ ... ],
    "inquiries": [ ... ],
    "raw_data": null,
    "error": null
  },
  "context": {
    "iteration": 0,
    "environment": "simulation"
  }
}
```

### 3.1 Header Fields (`ProtocolHeader`)

- `message_id` (*string, UUID*): Unique identifier per message.
- `correlation_id` (*string*): Identifier tracking this diagnostic incident across turns.
- `timestamp_utc` (*string, ISO8601 UTC*): Generation timestamp (e.g., `2026-10-31T12:00:00.000Z`).
- `sender` (*string, enum*): `orchestrator`, `telemetry_agent`, `topology_agent`, `config_agent`, `log_agent`, `synthesizer_agent`, `human_operator`.
- `recipient` (*string, enum*): Same as sender enum plus `broadcast`.
- `schema_version` (*string*): Enforces semantic versioning matching `1.x.x` (default `1.0.0`).
- `message_type` (*string, enum*):
  - `telemetry_dispatch`: Orchestrator dispatching raw incident data to specialists.
  - `finding_submission`: Specialist agent returning observations and domain hypotheses.
  - `inquiry_request`: Targeted corroboration query sent to another agent.
  - `inquiry_response`: Answering agent returning corroborating/refuting evidence.
  - `conflict_notification`: Mediator notifying agents of competing hypotheses.
  - `synthesis_submission`: Synthesizer returning unified root-cause assessment.
  - `protocol_error`: Structured error return for schema or handling violations.
- `priority` (*string, enum*): `low`, `normal`, `high`, `urgent`.

### 3.2 Concept Mapping

The codebase maps standard multi-agent debate concepts directly to the envelope payload:

| Problem Statement Concept | Codebase Model & Field | Purpose |
| :--- | :--- | :--- |
| **Evidence Query** | `payload.inquiries` (`Inquiry` model) | Targeted questions routed between agents for cross-domain corroboration |
| **Findings** | `payload.observations` + `payload.hypotheses` | Empirical anomalies (`Observation`) and proposed root causes (`Hypothesis`) |
| **Debate / Conflict Rounds** | `context.iteration` | Round counter managed by the Mediator and Conflict Resolver |

---

## 4. Finding and Evidence Models

Specialist agents emit two complementary finding structures inside `payload`:

### 4.1 Observations (`Observation`)
Empirical telemetry facts, anomalies, or configuration changes directly measured:

```json
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
```

- **Categories**: `metric_anomaly`, `topology_change`, `config_diff`, `log_pattern`, `state_transition`.
- **Severities**: `info`, `warning`, `critical`.

### 4.2 Hypotheses (`Hypothesis`)
Inferred domain causes proposed by specialist agents:

```json
{
  "hypothesis_id": "hyp-82b3a104",
  "probable_cause": "INTERFACE_SATURATION_QUEUE_OVERFLOW",
  "confidence": 0.88,
  "supporting_observation_ids": ["obs-e4c19a02"],
  "refuting_observation_ids": [],
  "required_corroboration": ["LOG_INTERFACE_DROP_MESSAGES", "TOPOLOGY_ALTERNATE_PATH"]
}
```

### 4.3 Inquiries (`Inquiry`)
Targeted cross-agent queries for missing corroboration:

```json
{
  "inquiry_id": "inq-91f82c31",
  "target_agent": "log_agent",
  "question": "Are there CRC or queue drop syslog messages on interface GigabitEthernet0/1?",
  "target_entity": "dist-sw-01:GigabitEthernet0/1",
  "parameters": { "window_minutes": 15 },
  "answer": null
}
```

---

## 5. Canonical Metric Names and Units

The Ingestion Gateway and Specialist Agents normalize all raw metrics to the following canonical keys and SI units:

| Canonical Metric Key | Description | Standard Unit | Valid Aliases Normalizable by Gateway |
| :--- | :--- | :--- | :--- |
| `latency_ms` | One-way or round-trip delay | `ms` | `latency`, `rtt`, `ping_ms`, `delay_ms` |
| `jitter_ms` | Packet delay variation | `ms` | `jitter`, `delay_variation` |
| `packet_loss_pct` | Packet loss percentage | `percent` | `loss`, `packet_loss`, `drop_rate` |
| `throughput_mbps` | Observed data rate | `mbps` | `throughput`, `traffic_rate`, `tx_rate` |
| `bandwidth_mbps` | Link capacity | `mbps` | `speed`, `link_speed`, `capacity` |
| `link_utilization_pct` | Relative bandwidth consumption | `percent` | `util`, `utilization`, `load_pct` |
| `cpu_pct` | Processor utilization | `percent` | `cpu`, `cpu_usage`, `processor_pct` |
| `memory_pct` | Memory allocation | `percent` | `memory`, `mem_pct`, `ram_usage` |
| `queue_drops` | Egress buffer drops | `count` | `drops`, `buffer_drops`, `queue_overflows` |
| `interface_errors` | CRC / frame / physical errors | `count` | `crc_errors`, `input_errors`, `phy_errors` |
| `link_flaps` | State transition flap count | `flaps_per_minute` | `flaps`, `carrier_transitions` |
| `wifi_rssi_dbm` | Wireless received signal power | `dbm` | `rssi`, `signal_strength_dbm`, `wifi_signal` |
| `wifi_retransmission_pct` | 802.11 frame retries | `percent` | `wifi_retries`, `retrans_pct` |
| `dns_resolution_ms` | DNS query response latency | `ms` | `dns_latency`, `query_time_ms` |
| `dns_failure_pct` | DNS resolution failure rate | `percent` | `dns_errors`, `dns_drop_pct` |
| `dhcp_failure_pct` | DHCP lease allocation failure | `percent` | `dhcp_errors`, `lease_timeout_pct` |

### Unit Conversion Table (`TelemetryNormalizer`)

- **Bandwidth**: `bps` (1x), `kbps` (1,000x), `mbps` (1,000,000x), `gbps` (1,000,000,000x).
- **Time**: `ms` (1x), `s` / `sec` / `seconds` (1,000x), `us` / `microseconds` (0.001x), `ns` (0.000001x).
- **Memory**: `bytes` / `b` (1x), `kb` (1024x), `mb` (1048576x), `gb` (1073741824x).
- **Counts / Packets**: `packets`, `pkts`, `frames`, `count` (1x).
- **Ratios**: `percent` (1x), `ratio` (100x).

---

## 6. Unified Diagnostic Report (`schemas/diagnostic_report.json`)

The final output emitted by `node_report` and returned by `/api/diagnose`:

```json
{
  "incident_id": "inc-20261031-001",
  "network_id": "campus-core",
  "timestamp_utc": "2026-10-31T12:05:00.000000+00:00",
  "status": "diagnosed",
  "probable_cause": "MTU_MISMATCH_BLACKHOLE",
  "confidence": 0.92,
  "affected_devices": ["spine-01", "leaf-02"],
  "affected_interfaces": ["et-0/0/1"],
  "evidence": [
    {
      "source_agent": "telemetry_agent",
      "category": "metric_anomaly",
      "finding": "Drop rate exceeded threshold on spine-01:et-0/0/1",
      "entity": "spine-01:et-0/0/1",
      "metric_name": "packet_loss_pct",
      "value": 14.8,
      "unit": "percent",
      "severity": "critical",
      "weight": 1.0
    }
  ],
  "uncertainty": {
    "score": 0.08,
    "reasons": [],
    "missing_evidence": [],
    "alternative_hypotheses": []
  },
  "remediation_actions": [
    {
      "action_id": "rem-mtu-spine-01",
      "title": "Harmonize MTU Configuration",
      "description": "Align MTU on spine-01:et-0/0/1 to standard jumbo frame size 9000",
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
      "blast_radius_devices": ["spine-01", "leaf-02"],
      "is_simulated": true,
      "status": "recommended"
    }
  ],
  "summary": "Diagnosed MTU Mismatch Blackhole with 92% confidence affecting spine-01.",
  "processing_time_ms": 142.5
}
```

---

## 7. Problem Statement Gap Analysis & Compatibility Map

The IIT Bhubaneswar problem statement specifies target report fields. The table below documents how the codebase currently represents these fields, and how they map with 100% backward compatibility:

| Hackathon Spec Field | Codebase Field (`UnifiedDiagnosticReport`) | Compatibility Status | Notes / Resolution |
| :--- | :--- | :--- | :--- |
| `incident_id` | `incident_id` | Identical | Primary correlation key |
| `status` | `status` | Identical | Values: `diagnosed`, `insufficient_evidence`, `inconclusive`, `benign` |
| `suspected_root_cause` | `probable_cause` | Aliased / Compatible | The code uses `probable_cause`. Downstream consumers may accept both interchangeably. |
| `confidence` | `confidence` | Identical | Normalized float between `0.0` and `1.0` |
| `affected_devices` | `affected_devices` | Identical | Array of affected device ID strings |
| `supporting_evidence` | `evidence` / `hypothesis.supporting_evidence` | Fully Compatible | Structured list of evidence items including `source_agent`, `metric_name`, `value`, `unit` |
| `alternative_causes` | `uncertainty.alternative_hypotheses` | Fully Compatible | Contained within the `uncertainty` block to capture discarded or competing hypotheses |
| `recommended_actions`| `remediation_actions` | Fully Compatible | Extends plain text actions with structured simulated commands, rollback, and blast radius |
| `evidence_sources` | Derived from `evidence[*].source_agent` | Fully Compatible | Available per evidence datum; optionally aggregated as unique list |
| `limitations` | `uncertainty.reasons` + `uncertainty.missing_evidence` | Fully Compatible | Explicitly enumerates missing corroborations and telemetry gaps |

> [!IMPORTANT]
> **Additive Change Policy**: Any future changes to `UnifiedDiagnosticReport` or `AgentEnvelope` MUST be strictly additive. Existing fields and paths must never be removed or renamed.

---

## 8. WebSocket Event Streaming (`WS /ws/events` and `WS /ws/envelopes`)

The Orchestrator streams real-time state transitions and raw envelopes over WebSocket.

- **Endpoints**:
  - `ws://127.0.0.1:8000/ws/events`: Broadcasts diagnostic progress events.
  - `ws://127.0.0.1:8000/ws/envelopes`: Streams complete raw `AgentEnvelope` objects as they are logged.

### Event Format (`WS /ws/events`)

```json
{
  "event_type": "envelope_logged",
  "correlation_id": "inc-20261031-001",
  "timestamp_utc": "2026-10-31T12:00:01.000Z",
  "sender": "telemetry_agent",
  "recipient": "orchestrator",
  "message_type": "finding_submission",
  "summary": "Reported 2 observations, 1 hypothesis (confidence: 0.88)",
  "envelope": { ... }
}
```

### Supported `event_type` Values
- `diagnosis_started`: Pipeline execution initiated.
- `envelope_logged`: Inter-agent envelope logged to SQLite event store.
- `conflict_detected`: ConflictResolver detected competing hypotheses.
- `inquiry_turn`: Targeted cross-inquiry sent to resolve ambiguity.
- `diagnosis_completed`: Synthesis finished, report compiled.
- `remediation_simulated`: Simulated remediation plan evaluated against safety gates.

---

## 9. Zero Hallucination and Evidence Standard

1. **No Guessing**: A root cause hypothesis may only be accepted when supporting observations satisfy domain correlation rules.
2. **Ambiguity / Missing Telemetry**: If prerequisite corroboration is absent or uncertainty is high, status must be `insufficient_evidence`.
3. **Simulated Remediation Only**: All remediation commands are simulated and sandboxed; real network hardware is never contacted.

---

## 10. Additive and Backward-Compatible Extensions

All envelope extensions must be strictly **additive** without renaming or deleting existing fields:
- `schema_version`: Maintained in header as `"1.0.0"` (or `"1.x.y"`).
- `units`: Enforced via canonical unit dictionary in `Observation.validate_unit` with alias support.
- `provenance`: Optional metadata dictionary tracing agent origin, data source, or transformation history.
- `data_quality`: Optional quality rating (0.0 to 1.0) and anomaly trace per observation or payload.
- `confidence`: Calibrated float bounded in `[0.0, 1.0]` across hypotheses and diagnostic conclusions.
