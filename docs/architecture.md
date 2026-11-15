# NetCoop AI: Technical Architecture and System Design

## 1. Architectural Philosophy

NetCoop AI is designed from first principles around offline determinism, strict interoperability, and verifiable multi-point evidence.

Modern networks frequently suffer from cascaded failure modes: a physical fiber degradation triggers Frame Check Sequence (FCS) errors, causing TCP retransmissions, which drive buffer queue drops, which may trigger BFD timeout and BGP route flap damping. Traditional single-agent or monolithic diagnostic tools easily confuse downstream symptoms with root causes.

NetCoop AI solves this by deploying 7 specialist agents plus gateway and orchestrator that examine disjoint slices of the network state (telemetry, topology, configuration, event logs, learned classification, and wireless/services) and collaborate via a versioned envelope protocol.

---

## 2. 7 Specialist Agents Plus Gateway and Orchestrator

Agents maintain zero shared state and zero direct in-memory communication. All interactions pass through the LangGraph mediator as validated JSON envelopes (`schemas/envelope.json`).

### 2.1 Telemetry Agent (`telemetry_agent:8001`)
- **Domain**: Time-series counters and metrics.
- **Analyzed Signals**:
  - `egress_queue_drops`, `large_packet_drops`
  - `rx_power_dbm`, `optical_rx_power`
  - `fcs_errors`, `crc_errors`
  - `cpu_utilization_pct`, `broadcast_pps`, `mac_flaps`
- **Output**: Generates empirical `metric_anomaly` observations with normalized SI units.

### 2.2 Topology Agent (`topology_agent:8002`)
- **Domain**: Graph connectivity, adjacency states, and loop prevention.
- **Analyzed Signals**:
  - BGP peering states (`Established`, `Active`, `Idle`, flap penalties)
  - Spanning Tree states (root bridge identity, blocked ports, BPDU filter anomalies)
  - Physical and transit link adjacencies
- **Output**: Generates `state_transition` and `topology_change` observations.

### 2.3 Configuration Agent (`config_agent:8003`)
- **Domain**: Running configurations, commit diffs, and security policies.
- **Analyzed Signals**:
  - Candidate commit diffs (`+ interface et-0/0/1 mtu 9000`)
  - Interface MTU parameter discrepancies across interconnected links
  - BPDU filter configurations on trunk links
- **Output**: Generates `config_diff` observations with exact delta text.

### 2.4 Log Agent (`log_agent:8004`)
- **Domain**: RFC 5424 syslog streams and event bursts.
- **Analyzed Signals**:
  - BFD neighbor down transitions
  - Route flap dampening suppressions
  - Optical DOM warning and alarm thresholds
  - MAC address port flapping alarms
- **Output**: Generates `log_pattern` observations with severity classification.

### 2.5 Synthesizer Agent (`synthesizer_agent:8005`)
- **Domain**: Multi-agent evidence synthesis and sufficiency validation.
- **Role**: Combines empirical observations across all specialist agents, checks prerequisite cross-domain corroboration, evaluates composite confidence, and enforces the strict rule: returns `status: "insufficient_evidence"` if evidence is incomplete or uncorroborated.

### 2.6 Classifier Agent (`classifier_agent:8007`)
- **Domain**: Learned classification, feature extraction, and calibration.
- **Role**: Extracts normalized numerical feature vectors from telemetry and topology observations, evaluates calibrated class probabilities via per-class IsotonicRegression, and computes conformal uncertainty sets.

### 2.7 Wireless & Services Agent (`wifi_services_agent:8008`)
- **Domain**: 802.11 wireless links, AP infrastructure, and network services.
- **Analyzed Signals**:
  - Wi-Fi RSSI degradation, SNR margins, client retries, and AP channel saturation
  - DNS resolution latency, timeout spikes, and server unresponsiveness
  - DHCP pool exhaustion, DORA exchange timeouts, and lease failures
- **Output**: Generates `metric_anomaly` and `service_anomaly` observations.

### 2.8 Ingestion Gateway (`gateway:8006`)
- **Domain**: Edge data ingestion, protocol normalization, and resilience.
- **Role**: Normalizes external telemetry dialects (e.g. `dev_id` -> `device_id`), coerces units (seconds to ms, kbps to Mbps), sanitizes dirty string tokens (`'NaN'`, `'null'`), and performs single-quote JSON repair.

### 2.9 Central Orchestrator (`orchestrator:8000`)
- **Domain**: Workflow state machine, mediation, conflict arbitration, and API.
- **Role**: Implements a LangGraph cyclic state machine coordinating multi-turn specialist dispatch, manages Human-in-the-Loop (HITL) approval gates, hosts WebSocket telemetry feeds, and serves the REST API.

---

## 3. Deterministic Conflict Resolution Matrix

When agents propose competing hypotheses, the Conflict Resolution Engine applies strict deterministic arbitration rules:

1. **Physical Layer Primacy**: If optical power is below physical receiver sensitivity (-15 dBm) AND CRC errors are confirmed without config changes, physical fiber attenuation overrides soft queue hypotheses.
2. **Path MTU Specificity**: If packet drops correlate specifically with large frames (MTU mismatch), it takes precedence over generic buffer starvation.
3. **Loop Detection**: BPDU filtering on cross-connects with broadcast storms and CPU spikes arbitrates as a Spanning Tree loop.
4. **Tie-Breaker Rule**: If competing hypotheses remain within a 0.10 confidence margin without decisive rules, NetCoop AI declines to speculate and returns `status: "insufficient_evidence"` with dual candidates reported under `uncertainty.alternative_hypotheses`.

---

## 4. Remediation Safety Sandbox

NetCoop AI strictly enforces the safety invariant: **never touch real hardware**.

All remediation actions adhere to:
1. `is_simulated: true` invariant.
2. Pre-flight blast radius assessment: action rejected if blast radius exceeds 60% of network nodes.
3. Automated rollback command generation for every medium and high-risk action.
4. Human-in-the-Loop gate requiring operator approval before simulation execution.
5. Persistent logging of simulated commands in `remediation_logs` SQLite table.

---

## 5. Operational Boundaries & Architecture Disclosures

To ensure absolute transparency and engineering trustworthiness, NetCoop AI explicitly documents its physical architectural boundaries:

1. **Independent vs. Derived Corroboration**:
   - `telemetry_agent` and `topology_agent` operate as separate OS processes and evaluate disjoint aspects of the network. However, in synthetic single-snapshot files where topology links are synthesized from the same incident generator, their evidence is logically complementary rather than physically out-of-band. The synthesizer scores confidence based on multi-agent corroboration, but operators should note when evidence domains originate from a common telemetry collector snapshot.

2. **In-Memory Rate Limiting Boundary**:
   - Rate limiting on API endpoints (`SlowAPIMiddleware` / in-memory sliding window) executes inside a single Python process memory space. In a multi-worker production deployment (`gunicorn -w 4` or multiple Kubernetes pods) without a centralized Redis instance, rate limits are enforced per-worker rather than globally aggregated.

3. **SQLite Persistence Boundary**:
   - Incident records, checkpoints, audit trails, and HITL states persist to a local SQLite database (`netcoop.db`) running in Write-Ahead Logging (`WAL`) mode with synchronous writes. SQLite is single-node and non-distributed; concurrent multi-process writes are managed via SQLite busy timeouts. Production high-availability deployments require migrating connection strings to PostgreSQL.

4. **Plaintext Internal Microservice HTTP**:
   - Inter-process communication between the central Orchestrator (port 8000), Gateway (port 8006), and the 7 specialist agents (ports 8001-8008) uses standard unencrypted HTTP/1.1 over loopback (`127.0.0.1`), authenticated via the `X-NetCoop-Service-Token` header. Inter-service TLS (mTLS) is not enabled on loopback; in multi-host production topologies, services must run within a service mesh (e.g. Istio / Envoy) or wireguard network overlay.

5. **Simulation-Only Remediation Guarantee**:
   - All remediation actions emitted by NetCoop AI are strictly simulated (`is_simulated: true`). The platform explicitly rejects real hardware execution attempts with HTTP 403 Forbidden. Safe operational boundary tests enforce that no network interfaces, routing tables, or hardware daemons are ever modified on the host machine.

6. **Sample and Offline Data Labelling in UI**:
   - The React operator dashboard explicitly labels all non-production feeds with visual status indicators, including an `OFFLINE BENCHMARK REPLAY` badge, synthetic dataset indicators, and simulation watermarks on the Remediation and Proof panels to prevent operator confusion during triage.


