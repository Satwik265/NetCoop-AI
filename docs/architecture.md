# NetCoop AI: Technical Architecture and System Design

## 1. Architectural Philosophy

NetCoop AI is designed from first principles around offline determinism, strict interoperability, and verifiable multi-point evidence.

Modern networks frequently suffer from cascaded failure modes: a physical fiber degradation triggers Frame Check Sequence (FCS) errors, causing TCP retransmissions, which drive buffer queue drops, which may trigger BFD timeout and BGP route flap damping. Traditional single-agent or monolithic diagnostic tools easily confuse downstream symptoms with root causes.

NetCoop AI solves this by deploying five specialist domain agents that examine disjoint slices of the network state (telemetry, topology, configuration, and event logs) and collaborate via a versioned envelope protocol.

---

## 2. The Five Specialist Agents

Agents maintain zero shared state and zero direct in-memory communication. All interactions pass through the LangGraph mediator as validated JSON envelopes.

### 2.1 Telemetry Agent (`telemetry_agent`)
- **Domain**: Time-series counters and metrics.
- **Analyzed Signals**:
  - `egress_queue_drops`, `large_packet_drops`
  - `rx_power_dbm`, `optical_rx_power`
  - `fcs_errors`, `crc_errors`
  - `cpu_utilization_pct`, `broadcast_pps`, `mac_flaps`
- **Output**: Generates empirical `metric_anomaly` observations with normalized SI units.

### 2.2 Topology Agent (`topology_agent`)
- **Domain**: Graph connectivity, adjacency states, and loop prevention.
- **Analyzed Signals**:
  - BGP peering states (`Established`, `Active`, `Idle`, flap penalties)
  - Spanning Tree states (root bridge identity, blocked ports, BPDU filter anomalies)
- **Output**: Generates `state_transition` and `topology_change` observations.

### 2.3 Configuration Agent (`config_agent`)
- **Domain**: Running configurations, commit diffs, and security policies.
- **Analyzed Signals**:
  - Candidate commit diffs (`+ interface et-0/0/1 mtu 9000`)
  - Interface MTU parameter discrepancies across interconnected links
  - BPDU filter configurations on trunk links
- **Output**: Generates `config_diff` observations with exact delta text.

### 2.4 Log Agent (`log_agent`)
- **Domain**: RFC 5424 syslog streams and event bursts.
- **Analyzed Signals**:
  - BFD neighbor down transitions
  - Route flap dampening suppressions
  - Optical DOM warning and alarm thresholds
  - MAC address port flapping alarms
- **Output**: Generates `log_pattern` observations with severity classification.

### 2.5 Synthesizer Agent (`synthesizer_agent`)
- **Domain**: Multi-agent evidence synthesis and sufficiency validation.
- **Role**: Combines all empirical observations across agents 1-4, checks prerequisite cross-domain corroboration, evaluates composite confidence, and enforces the strict rule: returns `status: "insufficient_evidence"` if evidence is incomplete.

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

