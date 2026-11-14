# Phase 4 Deliverable: Unified Diagnostic Report Contract & Operator Explainability Report

**Project:** NetCoop AI — Cooperative Multi-Agent Network Fault Diagnosis Platform  
**Team:** inSANE MITRA  
**Phase:** Phase 4 — Report Contract and Explainability  
**Target Branch:** `fix/ps-readiness-p0`  
**Date:** November 15, 2026  
**Status:** **PASSED GATE 4** (Fully Verified & Schema-Compliant)

---

## 1. Executive Summary

Phase 4 standardizes the unified diagnostic report models, JSON schemas, human-readable markdown outputs, and dashboard mappings across NetCoop AI. Prior to this phase:
- Incomplete diagnostic runs occasionally represented missing metrics with ambiguous zeros (`0` or `0.0`) or empty strings (`""`), obscuring true telemetry gaps.
- Diagnostic uncertainty (`insufficient_evidence`) was conflated with input validation rejections and pipeline execution crashes.
- The 10-key Hackathon Problem Statement (PS) export lacked top-level representation in the core `UnifiedDiagnosticReport` model, forcing divergent serialization routines.
- Confidence values were occasionally described in markdown prose as "calibrated probabilities" even when derived from uncalibrated heuristic corroboration rules.
- When an incident lacked justified remediation actions (such as benign or ambiguous scenarios), human-readable markdown outputs silently omitted the section rather than explicitly stating why remediation was withheld.

In Phase 4, NetCoop AI establishes a unified, additive, and strictly typed report contract conforming to [`schemas/diagnostic_report.json`](file:///d:/NetCoop-AI/Team_inSANE_MITRA_NetCoop-AI/schemas/diagnostic_report.json), [`netcoop/core/report.py`](file:///d:/NetCoop-AI/Team_inSANE_MITRA_NetCoop-AI/netcoop/core/report.py), and [`dashboard/src/types/protocol.ts`](file:///d:/NetCoop-AI/Team_inSANE_MITRA_NetCoop-AI/dashboard/src/types/protocol.ts).

---

## 2. Core Diagnostic Status Semantics

To eliminate conflation between processing errors, schema violations, and empirical network uncertainty, NetCoop AI defines six mutually exclusive status states (`DiagnosticReportStatus` in `netcoop/core/report.py` and enum in `schemas/diagnostic_report.json`):

| Diagnostic Status | Semantics & Operational Meaning | Probable Cause Field | Confidence | Remediation Actions | Recommended Action |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `diagnosed` | Fault positively isolated with corroborated cross-agent evidence meeting domain precedence rules. | Populated (String) | $> 0.0$ to $1.0$ | Populated | Autonomous or engineer-approved simulated remediation. |
| `benign` | Normal network operation confirmed across all monitored parameters; fabric is healthy. | `"Normal Operation"` | $\ge 0.0$ | Empty (`[]`) | None. Monitoring continues; remediation is withheld. |
| `insufficient_evidence` | Empirical diagnostic uncertainty: telemetry is sparse, ambiguous, or lacks required multi-domain corroboration. | `None` (`null`) | `0.0` | Empty (`[]`) | None. Safe abstention; dispatch active probes or escalate to engineer. |
| `inconclusive` | Conflicting hypotheses between domain specialists that could not be arbitrated by deterministic precedence. | `None` (`null`) | `0.0` | Empty (`[]`) | None. Escalate competing hypotheses to NOC lead. |
| `invalid` | Inbound telemetry payload failed structural, schema, or unit validation (malformed JSON, missing container keys). | `None` (`null`) | `0.0` | Empty (`[]`) | None. Reject payload at gateway with detailed error log in `limitations`. |
| `failed` | Diagnostic pipeline execution error, agent timeout, or unhandled exception during synthesis. | `None` (`null`) | `0.0` | Empty (`[]`) | None. Fast-fail via circuit breaker; alert operations team. |

> [!IMPORTANT]
> **Anti-Conflation Invariant:** A malformed payload or failed service call NEVER results in `insufficient_evidence`. Validation errors emit `invalid`, execution crashes emit `failed`, and network ambiguity emits `insufficient_evidence`.

---

## 3. Report Model Specifications & Additive Fields

The canonical Python model is `UnifiedDiagnosticReport` (`netcoop/core/report.py`), validated against JSON Schema Draft 2020-12 in `schemas/diagnostic_report.json`.

### 3.1 Field-by-Field Contract

| JSON Key | Python Type | JSON Schema Type | Required | Description / Provenance |
| :--- | :--- | :--- | :---: | :--- |
| `incident_id` | `str` | `string` | **Yes** | Primary incident correlation identifier. |
| `network_id` | `str` | `string` | **Yes** | Target network fabric identifier (e.g. `campus-core`, `iitbbsr_argul_campus`). |
| `timestamp_utc` | `str` | `string` (date-time) | **Yes** | ISO-8601 UTC report generation timestamp. |
| `status` | `str` | `string` (enum) | **Yes** | One of: `diagnosed`, `benign`, `insufficient_evidence`, `inconclusive`, `invalid`, `failed`. |
| `probable_cause` | `str \| None` | `string \| null` | **Yes** | Deterministic root cause explanation; `null` if not diagnosed. |
| `suspected_root_cause` | `str \| None` | `string \| null` | No | Compatibility alias for Hackathon Problem Statement consumers. |
| `confidence` | `float` | `number` [0.0, 1.0] | **Yes** | Composite confidence score across corroborated agent findings. |
| `is_confidence_calibrated`| `bool` | `boolean` | No | `true` if calibrated via isotonic/conformal pipeline; `false` if heuristic. |
| `confidence_type` | `str` | `string` | No | `"calibrated_probability"`, `"uncalibrated_heuristic"`, or `"abstain"`. |
| `affected_devices` | `List[str]` | `array` of strings | **Yes** | Isolated network device hostnames; `[]` if unknown or unmapped. |
| `affected_interfaces` | `List[str]` | `array` of strings | No | Interface names experiencing anomalous telemetry. |
| `evidence` | `List[Dict]` | `array` of objects | **Yes** | Complete empirical observations with provenance and stable IDs. |
| `evidence_sources` | `List[str]` | `array` of strings | No | Unique specialist agent domains contributing verified evidence. |
| `uncertainty` | `UncertaintyEvaluation` | `object` | **Yes** | Quantitative ambiguity score, reasons, missing evidence, and alternatives. |
| `remediation_actions` | `List[RemediationActionItem]` | `array` of objects | **Yes** | Advisory simulated actions; strictly empty for non-diagnosed incidents. |
| `summary` | `str` | `string` | No | Executive plain-text summary of incident and operational status. |
| `processing_time_ms` | `float` | `number` | No | Total end-to-end multi-agent orchestration duration in milliseconds. |
| `causal_chain` | `List[str]` | `array` of strings | No | Ordered step-by-step causal reasoning sequence. |
| `conflicts_resolved` | `List[Dict]` | `array` of objects | No | Contradictions arbitrated during mediator consensus iterations. |
| `limitations` | `List[str]` | `array` of strings | No | Operational caveats (e.g. single-snapshot, missing topology). |
| `confidence_breakdown` | `Dict[str, float] \| None`| `object \| null` | No | Hybrid decomposition: `rules_score`, `model_score`, `blended_score`, `calibrated_confidence`. |
| `conformal_prediction_set`| `List[str]` | `array` of strings | No | Split-conformal prediction set guarantees (alpha=0.10). |
| `confidence_category` | `str \| None` | `string \| null` | No | Empirical operational tier: `"high"`, `"medium"`, `"low"`, `"abstain"`. |

---

## 4. Evidence Traceability & Stable Identifiers

Every evidence item conforms to `EvidenceItem` (`netcoop/core/evidence.py`):

```json
{
  "evidence_id": "evi-obs-e4c19a02",
  "source_agent": "telemetry_agent",
  "category": "metric_anomaly",
  "finding": "core-rtr-01:HundredGigE0/0/0/1 link_utilization_pct: observed 98.2 percent",
  "interpretation": "core-rtr-01:HundredGigE0/0/0/1 link_utilization_pct: observed 98.2 percent",
  "entity": "core-rtr-01:HundredGigE0/0/0/1",
  "metric_name": "link_utilization_pct",
  "metric": "link_utilization_pct",
  "value": 98.2,
  "unit": "percent",
  "severity": "critical",
  "timestamp": "2026-11-15T02:00:00Z",
  "timestamp_window": "2026-11-15T01:55:00Z to 2026-11-15T02:00:00Z",
  "observation_id": "obs-e4c19a02",
  "message_id": "msg-tel-101",
  "correlation_id": "inc-link-congestion-42",
  "provenance": {
    "collector": "snmp_interface_poller",
    "sample_rate_s": 10
  }
}
```

### Traceability Rules
1. **Stable Identifiers:** `evidence_id` is guaranteed stable and prefixed with `evi-`. UI links (`#evidence-${evidence_id}`) navigate directly to the underlying raw envelope log.
2. **Dual-Key Aliasing:** Both `metric_name` and `metric`, as well as `finding` and `interpretation`, are symmetrically populated to guarantee 100% compatibility across legacy and modern callers.
3. **Null Representation:** If a metric value is absent or indeterminate (such as lost keepalives), `value` is explicitly `null` in JSON and `"unknown"` in Markdown—never `0`, `0.0`, or `""`.

---

## 5. Distinction: Facts vs. Hypotheses vs. Recommendations vs. Actions

NetCoop AI strictly delineates operational concepts:

```
[Raw Telemetry Envelopes]
         │
         ▼
 1. FACTS (Evidence)
    - Verified empirical measurements (e.g. latency: 131.1 ms, queue drops: 1484).
    - Immutable, time-stamped, and attributed to a specific collector/agent.
         │
         ▼
 2. HYPOTHESES (Diagnostic Reasoning)
    - Synthesized candidate explanations (e.g. "Link Congestion", "Optical Transceiver Degradation").
    - Evaluated with confidence scores, required corroboration rules, and discriminating tests.
         │
         ▼
 3. RECOMMENDATIONS & ACTIONS (Simulated Advisory)
    - Specific, scoped remediation steps (e.g. "Re-weight hash buckets", "Normalize MTU").
    - Explicitly tagged with `is_simulated: true`, `risk_level`, and reversible rollback commands.
    - STRICT RULE: Withheld entirely if the incident is benign or uncorroborated.
```

---

## 6. Hackathon Problem Statement 10-Key Contract

The authoritative adapter `export_hackathon_report_json()` (`netcoop/reporting/builder.py`) maps the full `UnifiedDiagnosticReport` into the required 10-key contract:

```json
{
  "incident_id": "inc-link-congestion-42",
  "status": "diagnosed",
  "suspected_root_cause": "Link utilization saturation causing buffer queue drops and latency spikes",
  "confidence": 0.956,
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
      "metric": "link_utilization_pct",
      "value": 92.57,
      "interpretation": "core-rtr-01 link_utilization_pct: observed 92.57 percent"
    }
  ],
  "alternative_causes": [
    "Upstream provider or transit link congestion inducing downstream delay"
  ],
  "recommended_actions": [
    "Re-weight hash buckets to steer egress flows across parallel paths and relieve congestion."
  ],
  "evidence_sources": [
    "telemetry_agent"
  ],
  "limitations": [
    "single snapshot, no temporal context"
  ]
}
```

### Invariants:
1. `supporting_evidence` items strictly contain the exact 3 keys: `metric`, `value`, `interpretation`.
2. `recommended_actions` is strictly a list of strings (`List[str]`).
3. For `insufficient_evidence`, `benign`, `invalid`, or `failed` reports:
   - `suspected_root_cause`: `null`
   - `confidence`: `0.0`
   - `recommended_actions`: `[]`

---

## 7. Sample Outputs from Actual Test Fixtures

### Sample A: Positively Diagnosed Report (`link_congestion`)

```json
{
  "incident_id": "inc-synth-link_congestion-101",
  "network_id": "iitbbsr-campus-fabric",
  "timestamp_utc": "2026-11-15T02:00:00Z",
  "status": "diagnosed",
  "probable_cause": "Link Congestion",
  "suspected_root_cause": "Link Congestion",
  "confidence": 0.95,
  "is_confidence_calibrated": false,
  "confidence_type": "uncalibrated_heuristic",
  "affected_devices": ["core-rtr-01", "dist-sw-core"],
  "affected_interfaces": ["et-0/0/1"],
  "evidence": [
    {
      "evidence_id": "evi-obs-001",
      "source_agent": "telemetry_agent",
      "category": "metric_anomaly",
      "finding": "core-rtr-01:et-0/0/1 link_utilization_pct: observed 98.4 percent",
      "interpretation": "core-rtr-01:et-0/0/1 link_utilization_pct: observed 98.4 percent",
      "entity": "core-rtr-01:et-0/0/1",
      "metric_name": "link_utilization_pct",
      "metric": "link_utilization_pct",
      "value": 98.4,
      "unit": "percent",
      "severity": "critical",
      "timestamp": "2026-11-15T02:00:00Z"
    }
  ],
  "evidence_sources": ["telemetry_agent"],
  "uncertainty": {
    "score": 0.05,
    "reasons": [],
    "missing_evidence": [],
    "alternative_hypotheses": [
      {
        "cause": "Upstream provider or transit link congestion inducing downstream delay",
        "confidence": 0.55,
        "discriminating_test": "Query egress queue drops on upstream transit hops"
      }
    ]
  },
  "remediation_actions": [
    {
      "action_id": "act-cong-01",
      "title": "Re-weight hash buckets to steer egress flows across parallel trunks",
      "description": "Adjust ECMP multipath weights to balance traffic away from saturated et-0/0/1",
      "device": "core-rtr-01",
      "commands": ["set load-balancing ecmp-weight et-0/0/1 20 et-0/0/2 80"],
      "rollback_commands": ["set load-balancing ecmp-weight et-0/0/1 50 et-0/0/2 50"],
      "risk_level": "medium",
      "blast_radius_devices": ["dist-sw-core"],
      "is_simulated": true,
      "status": "recommended"
    }
  ],
  "summary": "Diagnosed Link Congestion with 95% confidence. Affecting devices: core-rtr-01, dist-sw-core.",
  "processing_time_ms": 112.4
}
```

### Sample B: Normal Operation Report (`benign`)

```json
{
  "incident_id": "inc-synth-normal_operation-102",
  "network_id": "iitbbsr-campus-fabric",
  "timestamp_utc": "2026-11-15T02:00:00Z",
  "status": "benign",
  "probable_cause": "Normal Operation",
  "suspected_root_cause": "Normal Operation",
  "confidence": 0.92,
  "is_confidence_calibrated": false,
  "confidence_type": "uncalibrated_heuristic",
  "affected_devices": [],
  "affected_interfaces": [],
  "evidence": [],
  "evidence_sources": [],
  "uncertainty": {
    "score": 0.0,
    "reasons": [],
    "missing_evidence": [],
    "alternative_hypotheses": []
  },
  "remediation_actions": [],
  "summary": "Normal operation verified: all telemetry metrics within nominal baseline boundaries.",
  "processing_time_ms": 84.1
}
```

### Sample C: Input Validation Failure (`invalid`)

```json
{
  "incident_id": "inc-invalid-400",
  "network_id": "unknown-fabric",
  "timestamp_utc": "2026-11-15T02:00:00Z",
  "status": "invalid",
  "probable_cause": null,
  "suspected_root_cause": null,
  "confidence": 0.0,
  "is_confidence_calibrated": false,
  "confidence_type": "abstain",
  "affected_devices": [],
  "affected_interfaces": [],
  "evidence": [],
  "evidence_sources": [],
  "uncertainty": {
    "score": 1.0,
    "reasons": [
      "ERR_MISSING_REQUIRED_FIELD: incident_id missing",
      "ERR_MALFORMED_JSON: unclosed quote at byte 42"
    ],
    "missing_evidence": ["valid_canonical_telemetry_payload"],
    "alternative_hypotheses": []
  },
  "remediation_actions": [],
  "summary": "Input validation failure: ERR_MISSING_REQUIRED_FIELD: incident_id missing; ERR_MALFORMED_JSON: unclosed quote at byte 42",
  "limitations": [
    "ERR_MISSING_REQUIRED_FIELD: incident_id missing",
    "ERR_MALFORMED_JSON: unclosed quote at byte 42"
  ]
}
```

---

## 8. Verification & Acceptance Test Suite

The Phase 4 test suite [`tests/test_phase4_report_contract.py`](file:///d:/NetCoop-AI/Team_inSANE_MITRA_NetCoop-AI/tests/test_phase4_report_contract.py) passed all 10 acceptance criteria:

```
tests/test_phase4_report_contract.py::test_valid_diagnosed_report PASSED [ 10%]
tests/test_phase4_report_contract.py::test_normal_benign_report PASSED   [ 20%]
tests/test_phase4_report_contract.py::test_insufficient_evidence_report PASSED [ 30%]
tests/test_phase4_report_contract.py::test_input_validation_failure_report PASSED [ 40%]
tests/test_phase4_report_contract.py::test_missing_affected_devices_and_topology PASSED [ 50%]
tests/test_phase4_report_contract.py::test_multiple_evidence_sources_with_provenance PASSED [ 60%]
tests/test_phase4_report_contract.py::test_no_recommendations_justified PASSED [ 70%]
tests/test_phase4_report_contract.py::test_alternative_hypotheses_and_conflicts PASSED [ 80%]
tests/test_phase4_report_contract.py::test_backward_compatibility_and_version_migration PASSED [ 90%]
tests/test_phase4_report_contract.py::test_json_serialization_and_exact_field_type_contract PASSED [100%]
============================= 10 passed in 8.92s ==============================
```

### Full Regression Suite:
- **71/71 tests passed** across all test suites (`test_phase4_report_contract.py`, `test_phase3_evaluation.py`, `test_phase2_canonical_ingestion.py`, `test_evidence_provenance_and_corroboration.py`, `test_scenarios.py`, `test_organizer_adapter.py`, `test_gateway_api.py`, `test_reporting_contract.py`, `test_reporting_hackathon_shape.py`).
- **Dashboard Type Check & Build:** Passed cleanly (`tsc && vite build`, 228 modules transformed, zero TypeScript errors).

---

## 9. Gate 4 Sign-Off Checklist

| Requirement | Status | Verification Reference |
| :--- | :---: | :--- |
| PS-required concepts preserved | **PASSED** | Validated in `test_valid_diagnosed_report` & `test_8_report_schema_contract`. |
| Field names and types stable | **PASSED** | 100% backward compatible; strictly additive fields. |
| Status semantics defined without conflation | **PASSED** | Formal enum: `diagnosed`, `benign`, `insufficient_evidence`, `inconclusive`, `invalid`, `failed`. |
| Complete evidence item details & provenance | **PASSED** | Metric, entity, value, unit, timestamp, severity, interpretation, and source references verified. |
| Missing values rendered as unknown | **PASSED** | Verified in `test_json_serialization_and_exact_field_type_contract`. |
| Separation of facts, hypotheses, actions | **PASSED** | Separate sections in JSON schema, Markdown, and Dashboard types. |
| Confidence semantics explicit | **PASSED** | Distinguishes heuristic scores from calibrated probabilities. |
| Alternative hypotheses with discriminating tests | **PASSED** | Verified in `test_alternative_hypotheses_and_conflicts`. |
| Remediation actions justified & safe | **PASSED** | Remediation actions strictly empty for non-diagnosed incidents; simulated only. |
| Data limitations tracked | **PASSED** | Enforces temporal and topology limitation reporting. |
| Stable identifiers for UI navigation | **PASSED** | Stable `evidence_id` (`evi-...`) across all evidence items. |
| JSON and Markdown output consistency | **PASSED** | Exact field-by-field mirror verified in all test fixtures. |
| Zero Git push/pull/fetch/remote branch changes | **PASSED** | Strictly committed locally on `fix/ps-readiness-p0`. |
