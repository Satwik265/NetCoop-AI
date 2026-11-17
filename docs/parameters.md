# NetCoop AI Operational Parameters & Thresholds Catalog

| Parameter Name | Value | Unit | Type | Category | Evidence / Rationale |
|:---|:---:|:---:|:---:|:---:|:---|
| `acceptance_confidence_threshold` | `0.7` | `confidence` | **hard safety** | `decision_gating` | Minimum blended confidence cutoff for declaring a diagnosis rather than abstaining with insufficient_evidence. |
| `agent_timeout_seconds` | `3.0` | `seconds` | **hard safety** | `orchestration` | Per-agent HTTP request timeout before failing fast and recording degraded mode limitations. |
| `circuit_breaker_failure_threshold` | `2` | `failures` | **hard safety** | `orchestration` | Consecutive specialist agent failures before circuit breaker trips open to protect overall system response time. |
| `circuit_breaker_recovery_timeout_s` | `30.0` | `seconds` | **hard safety** | `orchestration` | Cooldown duration before probing a tripped agent in half-open state. |
| `conformal_alpha` | `0.1` | `ratio` | **hard safety** | `conformal_and_uncertainty` | Split conformal error budget targeting nominal 90% finite-sample prediction set coverage (1 - alpha = 0.90). |
| `conformal_q_hat` | `0.6786` | `nonconformity_score` | **fitted** | `conformal_and_uncertainty` | Calibrated 90th percentile nonconformity score on CONFORMAL_CALIB partition (seeds 151-175). |
| `cpu_overload_pct` | `85.0` | `percent` | **heuristic** | `fault_signatures` | Device control plane CPU utilization threshold triggering process inspection and control plane protection. |
| `dq_floor` | `0.4` | `quality_score` | **hard safety** | `data_quality` | Minimum data quality floor ensuring structurally valid telemetry with intact timestamps and device identities remains evaluable. |
| `dq_threshold` | `0.7` | `quality_score` | **hard safety** | `data_quality` | Minimum required data quality score to prevent garbage-in-garbage-out hallucinations on corrupted payloads. |
| `ethernet_error_packet_threshold` | `100` | `packets` | **heuristic** | `fault_signatures` | FCS/CRC error count indicating physical layer cable degradation or transceiver defect. |
| `ethernet_flap_threshold` | `3` | `flaps` | **heuristic** | `fault_signatures` | Carrier state transition count indicating link instability or faulty auto-negotiation. |
| `high_confidence_threshold` | `0.85` | `confidence` | **heuristic** | `decision_gating` | High-assurance threshold for automated remediation dispatch without mandatory HITL confirmation. |
| `latency_spike_threshold_ms` | `25.0` | `milliseconds` | **heuristic** | `fault_signatures` | Round-trip delay or jitter elevation indicative of queueing delay or transit impairment. |
| `link_utilization_congestion_pct` | `55.0` | `percent` | **heuristic** | `fault_signatures` | Utilization threshold above which sustained egress queue drops indicate active link congestion. |
| `link_utilization_critical_pct` | `85.0` | `percent` | **heuristic** | `fault_signatures` | Severe saturation threshold where buffer overflow induces packet loss and latency spikes. |
| `max_inquiry_iterations` | `3` | `iterations` | **hard safety** | `orchestration` | Hard cap on cross-examination inquiry iterations between orchestrator and specialist agents to prevent infinite loops. |
| `medium_confidence_threshold` | `0.7` | `confidence` | **heuristic** | `decision_gating` | Medium confidence threshold presenting diagnosed root cause with required HITL operator confirmation. |
| `min_independent_domains` | `2` | `domain_count` | **hard safety** | `multi_agent_corroboration` | Multi-agent corroboration requirement; high-impact diagnoses must derive from >= 2 independent direct evidence domains or are marked limited. |
| `normal_operation_prob` | `0.8` | `probability` | **fitted** | `conformal_and_uncertainty` | Calibrated threshold for normal benign confirmation when all specialist agents observe zero metric anomalies. |
| `ood_mahalanobis_threshold` | `12.2` | `mahalanobis_distance` | **fitted** | `ood_gating` | 99th percentile * 1.35 multiplier fitted on PCA-reduced multi-topology training features. |
| `optical_rx_power_crit_dbm` | `-18.0` | `dBm` | **hard safety** | `fault_signatures` | Critical optical power threshold indicating dirty connectors, macro-bends, or dying lasers. |
| `optical_rx_power_warn_dbm` | `-14.0` | `dBm` | **hard safety** | `fault_signatures` | SFP/QSFP transceiver warning threshold indicating optical degradation before complete loss of signal. |
| `packet_loss_critical_pct` | `0.5` | `percent` | **heuristic** | `fault_signatures` | Active packet loss threshold signifying path impairment or congestion discard. |
| `queue_drops_threshold` | `5` | `packets` | **heuristic** | `fault_signatures` | Interface egress buffer drop count indicating persistent queue saturation. |
| `weights_model` | `0.45` | `weight` | **fitted** | `decision_blending` | Validation split optimization (weights.json); calibrated multi-class gradient-boosted probability weight. |
| `weights_rules` | `0.55` | `weight` | **fitted** | `decision_blending` | Validation split optimization (weights.json); rules provide conservative baseline against unseen topologies. |
| `wifi_retransmission_critical_pct` | `20.0` | `percent` | **heuristic** | `fault_signatures` | 802.11 frame retry rate indicating severe RF contention, interference, or coverage gap. |
| `wifi_rssi_weak_dbm` | `-78.0` | `dBm` | **heuristic** | `fault_signatures` | 802.11 signal power threshold below which modulation drops and packet retransmissions escalate. |

## Data Quality Scoring & Acceptance Logic (Phase 13M)

### Data Quality Score Calculation
The data quality engine evaluates telemetry integrity on a scale from `0.40` (minimum evaluable floor) to `1.00` (nominal).

1. **Required vs. Optional Metrics**:
   - **Core Required Fields**: `timestamp`, `device_id`, and at least one primary performance metric (`latency_ms`, `packet_loss_pct`, `link_utilization_pct`, `cpu_pct`, or `throughput_mbps`).
   - **Optional / Out-of-Scope Metrics**: `wifi_*` (wireless RF), `dns_*` / `dhcp_*` (network services), `queue_drops`, `interface_errors`, and `link_flaps` are event- or topology-contingent. Their absence during normal operation or on wired/non-server nodes is **never penalized**.
2. **Quality Penalties**:
   - Quarantined fields: `-0.10` per field.
   - Missing required fields: `-0.05` per field.
   - Validation errors: `-0.05` per error.
   - Unmitigated clock skew (> 600s): `-0.10`.
3. **The 0.40 Score Floor**:
   - `src_score = round(max(0.40, min(1.0, 1.0 - penalty)), 3)`
   - The `0.40` floor guarantees that any structurally valid telemetry with intact device IDs and timestamps remains evaluable by specialist agents and deterministic domain rules rather than being unconditionally rejected.
4. **Acceptance Threshold (`dq_threshold = 0.70`)**:
   - Normal/healthy confirmation requires `dq_score >= 0.70`. Payloads with data quality below `0.70` are gated to prevent false-negative normal calls on severely corrupted or missing telemetry.
   - Diagnosed fault hypotheses apply a proportional data-quality penalty to calibrated confidence: `gap_penalty = (1.0 - dq_score) * 0.50`, with a confidence floor of `0.40`. If calibrated confidence drops below `acceptance_confidence_threshold = 0.70`, the system abstains with `status = "insufficient_evidence"`.
