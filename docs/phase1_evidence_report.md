# Phase 1 — Evidence Provenance, Multi-Agent Corroboration, and Diagnostic Integrity Report

**Repository:** `Team_inSANE_MITRA_NetCoop-AI`  
**Branch:** `fix/ps-readiness-p0`  
**Base Commit:** `77deb6034e5110c54cf7063fea63fc0c923d3409`  
**Date:** 2026-11-15  
**Author:** Principal Software Engineer (Team inSANE MITRA)  
**Status:** Completed & Verified (Gate 1 Ready)

---

## 1. Executive Summary & Problem Addressed

During the Phase 0 baseline audit, a critical integrity defect was identified in the diagnostic pipeline:
1. **Single-Agent Evidence Reporting:** In benchmark scenarios such as `link_congestion.json`, even though multiple specialist agents were dispatched (e.g., `telemetry_agent`, `topology_agent`), the generated diagnostic report attributed evidence solely to `["telemetry_agent"]`.
2. **Missing Observation Lineage:** `EvidenceItem` models lacked traceability to the underlying agent messages, envelopes, and specific observation IDs (`observation_id`, `message_id`, `correlation_id`).
3. **Hardcoded Domain Lists:** Fault checkers inside `OfflineCorrelationEngine` hardcoded static lists like `required_evidence_domains=["telemetry_agent"]` and `provided_evidence_domains=["telemetry_agent"]`, rather than deriving them dynamically from verified observations.
4. **Phantom Contributor Bug:** In `_check_optical_degradation`, `config_agent` was injected into `provided_evidence_domains` simply if *no* config diff was found, even if `config_agent` had never been dispatched or produced zero observations.
5. **Fixed Rule Confidence:** Diagnostic confidence was hardcoded to fixed static floats (e.g. 0.90) upon rule match, rather than computed from metric severity, evidence depth, and corroboration bonuses.

### Key Outcomes of Phase 1
- **Genuine Multi-Agent Corroboration:** In `link_congestion.json`, the diagnosis is now independently corroborated by `telemetry_agent` (8 metric observations: latency, jitter, utilization, queue drops) and `topology_agent` (1 transit link adjacency observation identifying the saturated core-to-distribution trunk). Both are reported in `evidence_sources: ["telemetry_agent", "topology_agent"]`.
- **End-to-End Observation Traceability:** Every evidence item in the report carries `observation_id`, `message_id`, `correlation_id`, and `provenance`.
- **Zero Phantom Sources:** Agents that are silent, erroring, timed out, or dispatched without contributing observations are strictly excluded from `evidence_sources`.
- **Explicit Abstention:** Scenarios lacking mandatory multi-domain evidence fail closed with `status="insufficient_evidence"`, `confidence=0.0`, `probable_cause=None`, and `remediation_actions=[]`.
- **Contract Preservation:** 100% compliance with `schemas/diagnostic_report.json`, the 10-key `export_hackathon_report_json` contract, and executive/technical report formats.
- **Verification:** All 9 Phase 1 acceptance tests pass; full 73-test regression suite passes.

---

## 2. Architectural Design & Source Files Modified

### 2.1 Modifications Summary

| File | Changes Made |
| :--- | :--- |
| `netcoop/core/evidence.py` | Added `observation_id: Optional[str]`, `message_id: Optional[str]`, `correlation_id: Optional[str]`, and `provenance: Optional[Dict[str, Any]]` to `EvidenceItem`. |
| `netcoop/agents/telemetry_agent.py` | Stamped `correlation_id`, `message_id`, and `agent_domain` onto all generated observations and their `provenance` metadata. |
| `netcoop/agents/topology_agent.py` | Analyzed transit graph links against incident telemetry; when both endpoints of an adjacency show congestion/degradation, emits a genuine `transit_link_adjacency` observation preserving envelope lineage. |
| `netcoop/core/correlation.py` | Overhauled all 12 fault checkers: derived `provided_evidence_domains` strictly from supporting evidence; computed dynamic confidence; added multi-domain corroboration bonus (+0.20); removed phantom `config_agent` source; extracted lineage into `EvidenceItem`. |
| `netcoop/orchestrator/graph.py` | Updated `_deduplicate_observations` to preserve lineage and record cross-agent corroborating sources in `provenance["corroborating_sources"]`; secured node specialists against `NoneType` dictionary access. |
| `tests/test_evidence_provenance_and_corroboration.py` | Created comprehensive 9-test suite verifying multi-domain corroboration, lineage preservation, duplicate handling, competing hypotheses, abstention, and contract validity. |

### 2.2 Corroboration & Lineage Architecture

```
                  ┌───────────────────────────────┐
                  │   Incident Data & Topology    │
                  └──────────────┬────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
     ┌───────────────────────┐       ┌───────────────────────┐
     │    TelemetryAgent     │       │     TopologyAgent     │
     │  (Utilization, Queue  │       │ (Transit Graph Link   │
     │   Drops, Latency)     │       │  Adjacency Congested) │
     └───────────┬───────────┘       └───────────┬───────────┘
                 │ (msg-1, obs-1..8)             │ (msg-2, obs-9)
                 └───────────────┬───────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │   node_specialists    │
                     │  Lineage Preservation │
                     └───────────┬───────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ OfflineCorrelation    │
                     │  - Domain Extraction  │
                     │  - Cross-Corroboration│
                     │  - Dynamic Scoring    │
                     └───────────┬───────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ UnifiedDiagnosticRep. │
                     │  evidence_sources:    │
                     │  ["telemetry_agent",  │
                     │   "topology_agent"]   │
                     └───────────────────────┘
```

---

## 3. Scenario Trace: Link Congestion (Before vs. After)

### 3.1 Before Phase 1 (Baseline)
- `evidence_sources`: `["telemetry_agent"]` (only a single source, despite topology agent being dispatched).
- `evidence` items: lacked `observation_id`, `message_id`, `correlation_id`.
- `confidence`: fixed float `0.92`.
- `provided_evidence_domains`: hardcoded string `["telemetry_agent"]`.

### 3.2 After Phase 1 (Verified Output)

#### 10-Key Hackathon Contract JSON (`export_hackathon_report_json`):
```json
{
  "incident_id": "inc-link-congestion-42",
  "status": "diagnosed",
  "suspected_root_cause": "Link utilization saturation causing buffer queue drops and latency spikes",
  "confidence": 0.969,
  "affected_devices": [
    "core-rtr-01",
    "dist-sw-core"
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
    },
    {
      "metric": "transit_link_adjacency",
      "value": "congested_transit_trunk_10.0gbps",
      "interpretation": "core-rtr-01:eth0<->dist-sw-core:eth0 transit_link_adjacency: observed congested_transit_trunk_10.0gbps text"
    }
  ],
  "alternative_causes": [
    "Upstream provider or transit link congestion inducing downstream delay"
  ],
  "recommended_actions": [
    "Re-weight hash buckets to steer egress flows across parallel paths and relieve congestion.",
    "Prioritize delay-sensitive flows and allocate strict priority queue bandwidth."
  ],
  "evidence_sources": [
    "telemetry_agent",
    "topology_agent"
  ],
  "limitations": [
    "single snapshot, no temporal context"
  ]
}
```

### 3.3 Complete Traceability Table: Observations to Evidence Items

| # | Observation ID | Message ID | Correlation ID | Source Agent | Entity | Metric | Value | Unit | Severity |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `obs-e2262235` | `da327da9-1ac9-4dd6-a7f3-62fd06814039` | `inc-link-congestion-42` | `telemetry_agent` | `core-rtr-01` | `latency_ms` | 131.1 | ms | critical |
| 2 | `obs-a1084d59` | `da327da9-1ac9-4dd6-a7f3-62fd06814039` | `inc-link-congestion-42` | `telemetry_agent` | `core-rtr-01` | `jitter_ms` | 25.6 | ms | critical |
| 3 | `obs-3298a698` | `da327da9-1ac9-4dd6-a7f3-62fd06814039` | `inc-link-congestion-42` | `telemetry_agent` | `core-rtr-01` | `link_utilization_pct` | 92.57 | % | critical |
| 4 | `obs-24817478` | `da327da9-1ac9-4dd6-a7f3-62fd06814039` | `inc-link-congestion-42` | `telemetry_agent` | `core-rtr-01` | `queue_drops` | 1484 | packets | critical |
| 5 | `obs-4ad33092` | `da327da9-1ac9-4dd6-a7f3-62fd06814039` | `inc-link-congestion-42` | `telemetry_agent` | `dist-sw-core` | `latency_ms` | 147.94 | ms | critical |
| 6 | `obs-5aa796ea` | `da327da9-1ac9-4dd6-a7f3-62fd06814039` | `inc-link-congestion-42` | `telemetry_agent` | `dist-sw-core` | `jitter_ms` | 28.19 | ms | critical |
| 7 | `obs-e91b5c3e` | `da327da9-1ac9-4dd6-a7f3-62fd06814039` | `inc-link-congestion-42` | `telemetry_agent` | `dist-sw-core` | `link_utilization_pct` | 97.65 | % | critical |
| 8 | `obs-79caeb58` | `da327da9-1ac9-4dd6-a7f3-62fd06814039` | `inc-link-congestion-42` | `telemetry_agent` | `dist-sw-core` | `queue_drops` | 1019 | packets | critical |
| 9 | `obs-d332198d` | `3dc2cd07-3c7a-49de-ac12-da91bf353fcd` | `inc-link-congestion-42` | `topology_agent` | `core-rtr-01:eth0<->dist-sw-core:eth0` | `transit_link_adjacency` | `congested_transit_trunk_10.0gbps` | text | critical |

---

## 4. Test Execution & Verification Results

### 4.1 Phase 1 Acceptance Suite (`tests/test_evidence_provenance_and_corroboration.py`)

| Test Name | Verification Focus | Result |
| :--- | :--- | :--- |
| `test_1_golden_multi_domain_scenario` | Confirms `link_congestion` produces genuine multi-domain evidence (`telemetry_agent` + `topology_agent`). | **PASSED** |
| `test_2_dispatched_agent_without_evidence_not_counted` | Confirms healthy/dispatched agent without relevant observations is NOT included in `evidence_sources`. | **PASSED** |
| `test_3_empty_error_timeout_cannot_create_corroboration` | Confirms failed/timed-out agent responses cannot satisfy sufficiency; engine abstains. | **PASSED** |
| `test_4_duplicate_evidence_handling` | Confirms deduplication merges identical observations without double-counting confidence or losing lineage. | **PASSED** |
| `test_5_competing_hypotheses_reported` | Confirms non-top hypotheses (e.g. upstream provider congestion) are retained in `alternative_causes`. | **PASSED** |
| `test_6_insufficient_evidence_explicit_abstention` | Confirms missing required domain triggers explicit abstention (`status="insufficient_evidence"`). | **PASSED** |
| `test_7_recommendations_linked_to_fault_and_empty_on_abstention` | Confirms remediation actions exist only for diagnosed causes, and are strictly empty on abstention. | **PASSED** |
| `test_8_report_schema_contract` | Confirms exact compliance with 10-key hackathon export contract and `schemas/diagnostic_report.json`. | **PASSED** |
| `test_9_evidence_traceability` | Validates end-to-end lineage (`observation_id`, `message_id`, `correlation_id`) across all evidence items. | **PASSED** |

**Execution Time:** 9 passed in 34.09s.

### 4.2 Full Regression Test Suite

All 73 unit, integration, and scenario tests pass with zero regressions:
```bash
.venv\Scripts\python -m pytest tests/test_scenarios.py tests/test_reporting_contract.py tests/test_reporting_hackathon_shape.py tests/test_conflict_resolution.py tests/test_protocol_envelope.py tests/test_agents.py tests/test_normal_operation_benign.py tests/test_insufficient_evidence.py tests/test_evidence_provenance_and_corroboration.py
```
**Result:** **73 passed** in 38.54s (100% pass rate).

---

## 5. Public Contract Compliance

1. **`schemas/diagnostic_report.json`:** Fully compliant. All extra evidence attributes (`observation_id`, `message_id`, `correlation_id`, `provenance`) are valid under JSON Schema and Pydantic validation rules.
2. **`export_hackathon_report_json`:** The 10 canonical keys are strictly preserved:
   - `incident_id`: `str`
   - `status`: `"diagnosed" | "insufficient_evidence"`
   - `suspected_root_cause`: `str | None`
   - `confidence`: `float`
   - `affected_devices`: `List[str]`
   - `supporting_evidence`: `List[Dict[str, Any]]`
   - `alternative_causes`: `List[str]`
   - `recommended_actions`: `List[str]`
   - `evidence_sources`: `List[str]` (strictly derived from `supporting_evidence`)
   - `limitations`: `List[str]`
3. **Dual Executive & Technical Reports:** `ExecutiveReport` and `TechnicalReport` structures generated by `build_two_level_reports` continue to operate as expected.

---

## 6. Residual Limitations & Boundary Conditions

1. **In-Process vs. Distributed Agent Mode:** When running without background HTTP agent daemons on ports 8001–8007, `AGENTS_MODE="in_process"` is used. In distributed mode, circuit breakers gracefully fall back if an agent is unreachable.
2. **Temporal Windowing:** The current `link_congestion.json` scenario operates over a single time-slice snapshot. Temporal trend analysis across multiple historical snapshots remains an opportunity for Phase 2/3 enhancements.
3. **Simulated Remediation:** As mandated by system safety rules, all recommended remediations are strictly simulated; no production network devices are mutated.
