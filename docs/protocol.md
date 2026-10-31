# NetCoop AI Inter-Agent Protocol Specification (v1.0.0)

## 1. Overview and Design Principles

NetCoop AI employs a message-envelope architecture where agents communicate exclusively via serialized JSON payloads conforming to `schemas/envelope.json`. Agents never share Python memory, maintain shared global variables, or call internal methods of other agents.

### Core Principles
1. **Zero Shared State**: Agents are isolated computation units. State transitions occur exclusively via message passing mediated by the LangGraph orchestrator.
2. **Strict Field Typing and Units**: Every quantitative observation carries an explicit SI unit. Unspecified or ambiguous units are rejected during validation.
3. **Traceability**: Every diagnostic incident carries a unique `correlation_id` propagated across all agent message exchanges.
4. **Deterministic Validation**: Incoming messages are validated via Pydantic v2 and JSON Schema. Validation failures immediately generate a `protocol_error` envelope.
5. **No Hallucination / Insufficient Evidence**: Agents are strictly forbidden from guessing a root cause when supporting observations are incomplete. If prerequisite corroboration is absent, the agent must return an inquiry or report `insufficient_evidence`.

---

## 2. Message Envelope Architecture

The envelope consists of three top-level objects:
- `header`: Routing metadata, priority, timestamps, and message classification.
- `payload`: Domain data containing scope, observations, hypotheses, inquiries, or errors.
- `context`: Execution metadata such as iteration round and simulation flags.

### 2.1 Header Fields

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `message_id` | String | UUIDv4 format | Unique identifier for each individual envelope. |
| `correlation_id` | String | Non-empty string | Incident identifier uniting all messages for a single diagnosis. |
| `timestamp_utc` | String | ISO 8601 (UTC) | Creation timestamp (e.g. `2026-10-31T12:00:00.000Z`). |
| `sender` | String | Enum | One of: `orchestrator`, `telemetry_agent`, `topology_agent`, `config_agent`, `log_agent`, `synthesizer_agent`, `human_operator`. |
| `recipient` | String | Enum | One of: `orchestrator`, `telemetry_agent`, `topology_agent`, `config_agent`, `log_agent`, `synthesizer_agent`, `broadcast`. |
| `schema_version` | String | SemVer (`1.x.x`) | Protocol version identifier (current: `1.0.0`). |
| `message_type` | String | Enum | Purpose of message (see Section 2.2). |
| `priority` | String | Enum | One of: `low`, `normal`, `high`, `urgent`. Default: `normal`. |

### 2.2 Message Types

- `telemetry_dispatch`: Broadcast from orchestrator distributing raw telemetry, topology, configs, or logs to specialist agents.
- `finding_submission`: Sent by specialist agents to orchestrator with parsed observations and preliminary hypotheses.
- `inquiry_request`: Directed query from one agent (routed via orchestrator) requesting specific data or validation from a peer agent.
- `inquiry_response`: Targeted reply satisfying an `inquiry_request`.
- `conflict_notification`: Emitted by orchestrator when two or more agents propose mutually exclusive root causes.
- `synthesis_submission`: Final synthesis report produced by `synthesizer_agent`.
- `protocol_error`: Error envelope emitted on schema mismatch, unknown fields, or unparseable payloads.

---

## 3. Payload Semantics and Field Meanings

### 3.1 Scope Object
Defines the network boundary of the incident:
- `network_id` (string): Distinct network fabric or datacenter identifier (e.g., `fabric-dc-01`).
- `devices` (array of strings): List of device hostnames in scope (e.g., `["spine-01", "leaf-02"]`).
- `interfaces` (array of strings, optional): Specific interfaces involved (e.g., `["leaf-02:et-0/0/1"]`).

### 3.2 Observation Object
Represents an empirical, verified finding extracted from network data.

| Field | Type | Description |
| :--- | :--- | :--- |
| `observation_id` | String | Unique finding key (e.g., `obs-telemetry-001`). |
| `category` | Enum | `metric_anomaly`, `topology_change`, `config_diff`, `log_pattern`, `state_transition`. |
| `entity` | String | Fully-qualified target device or interface (e.g., `spine-01:et-0/0/2`). |
| `metric_name` | String | Specific metric key (e.g., `egress_drops`, `fcs_errors`, `rx_power_dbm`, `mtu`). |
| `observed_value` | Any | Number, string, or boolean measured value. |
| `baseline_value` | Any | Expected normal baseline (nullable). |
| `unit` | String | Standard unit string (see Section 4). |
| `severity` | Enum | `info`, `warning`, `critical`. |
| `timestamp_start`| String | Start of anomaly window (ISO 8601 UTC). |
| `timestamp_end` | String | End of anomaly window (ISO 8601 UTC). |
| `context` | Object | Optional key-value pairs providing additional metadata. |

### 3.3 Hypothesis Object
Represents an inferred fault hypothesis formulated by an agent.

| Field | Type | Description |
| :--- | :--- | :--- |
| `hypothesis_id` | String | Unique hypothesis key (e.g., `hyp-mtu-01`). |
| `probable_cause` | String | Clear technical description of suspected root cause. |
| `confidence` | Float (0.0 - 1.0) | Numerical certainty based on supporting observations. |
| `supporting_observation_ids` | Array of strings | IDs of observations that back this hypothesis. |
| `refuting_observation_ids` | Array of strings | IDs of observations that contradict alternate causes. |
| `required_corroboration` | Array of strings | Identifiers of evidence required from other agents to confirm (e.g., `["config_agent:mtu_diff"]`). |

### 3.4 Inquiry Object
Allows agents to pose questions to cross-examine evidence:
- `inquiry_id` (string): Unique identifier for the question.
- `target_agent` (string): Specialist agent being queried.
- `question` (string): Technical query statement.
- `target_entity` (string): Device or interface in question.
- `parameters` (object): Specific parameters (e.g., `{"window_seconds": 60}`).
- `answer` (nullable): Filled by target agent during response turn.

---

## 4. Standard Measurement Units

To prevent unit-mismatch errors across agent communications, all numerical values must use the following SI/standard units:

| Category | Standard Unit String | Accepted Raw Variations (Auto-converted) | Conversion Factor to Standard |
| :--- | :--- | :--- | :--- |
| **Bandwidth / Throughput** | `bps` | `Kbps`, `Mbps`, `Gbps` | $10^3$, $10^6$, $10^9$ |
| **Data Volume / Memory** | `bytes` | `KB`, `MB`, `GB`, `octets` | $1024$, $1024^2$, $1024^3$, $1$ |
| **Packet / Frame Counters** | `packets` | `pkts`, `frames`, `count` | $1$ |
| **Time Duration** | `ms` | `s`, `sec`, `us`, `ns` | $1000$, $1000$, $10^{-3}$, $10^{-6}$ |
| **Optical Power** | `dBm` | `dbm` | None (logarithmic ratio to 1 mW) |
| **Ratio / Percentage** | `percent` | `ratio` (0.0-1.0) | Multiplied by 100 for percent |
| **Frequency / Rate** | `flaps_per_minute` | `flaps_per_second` | Multiplied by 60 |

---

## 5. Interaction Patterns

### 5.1 Telemetry Broadcast & Parallel Analysis
```text
Orchestrator -> (telemetry_dispatch) -> Telemetry Agent
Orchestrator -> (telemetry_dispatch) -> Topology Agent
Orchestrator -> (telemetry_dispatch) -> Config Agent
Orchestrator -> (telemetry_dispatch) -> Log Agent
```

### 5.2 Finding Submissions
```text
Telemetry Agent -> (finding_submission) -> Orchestrator
Topology Agent  -> (finding_submission) -> Orchestrator
Config Agent    -> (finding_submission) -> Orchestrator
Log Agent       -> (finding_submission) -> Orchestrator
```

### 5.3 Conflict Resolution / Cross-Inquiry Turn
If Telemetry Agent asserts "Fiber Physical Degradation" while Config Agent asserts "MTU Mismatch":
```text
Orchestrator -> (inquiry_request) -> Telemetry Agent (question: "Are packet drops payload-size dependent?")
Telemetry Agent -> (inquiry_response) -> Orchestrator (answer: "Drops occur only on packets > 1500 bytes.")
Orchestrator -> resolves in favor of MTU mismatch.
```

### 5.4 Root Cause Synthesis
```text
Orchestrator -> (synthesis_submission request) -> Synthesizer Agent
Synthesizer Agent -> (synthesis_submission) -> Orchestrator (UnifiedDiagnosticReport)
```

---

## 6. Error Handling and Protocol Fault Isolation

1. **Schema Validation Error**:
   If an agent receives an envelope failing Pydantic v2 validation, it immediately rejects the message and transmits a `protocol_error` envelope back to the sender containing:
   - `error_code`: `SCHEMA_VALIDATION_FAILED`
   - `message`: Specific schema violation detail
   - `field_path`: Dot-delimited location of invalid attribute
2. **Missing Evidence Protocol**:
   If an agent cannot establish a link between observations and a known fault pattern, it emits:
   - `hypotheses`: empty list `[]`
   - `inquiries`: containing list of missing telemetry keys required
3. **Timeout / Unresponsive Agent**:
   The orchestrator applies a 5.0-second timeout per agent turn. If an agent fails to respond, the orchestrator logs an agent timeout and marks the agent's domain as `unresponsive_domain` in the uncertainty section of the final report.
