# NetCoop AI — Diagnostic Quality & V2 Report Adapter Handoff

This document details the architectural integration, contract invariants, and usage specifications for the Version 2 Network Diagnostic Report (`NetworkDiagnosticReport`) adapter, delivered on branch `feat/diagnostic-quality-report-v2`.

---

## 1. Adapter Entry Point

The V1-to-V2 transformation is encapsulated within `DiagnosticReportBuilder.from_unified_report()` in module `netcoop.reporting.builder`:

```python
from netcoop.reporting.builder import DiagnosticReportBuilder
from netcoop.reporting.models import NetworkDiagnosticReport, RecoveryStatus

report_v2: NetworkDiagnosticReport = DiagnosticReportBuilder.from_unified_report(
    unified_report=v1_report,               # UnifiedDiagnosticReport (Required)
    campus_topology=campus_topology_dict,   # Optional IITBBSR topology dict
    incident_data=incident_data_dict,       # Optional raw incident dict
    envelopes=envelope_list,                 # Optional List[AgentEnvelope] for execution trace
    recovery_status=RecoveryStatus.PENDING_VERIFICATION, # Optional recovery state override
    report_id="rep-custom-001",              # Optional deterministic report ID
    missing_metric_names=["loss_pct"],       # Optional uncollected telemetry names
)
```

---

## 2. Core Invariant Rules

To preserve evaluation and diagnostic integrity across frontend and backend boundaries, the adapter strictly enforces the following guarantees:

1. **No Evidence or Provenance Fabrication:**
   - Evidence records retain their genuine upstream `evidence_id`, source agent, and collector provenance.
   - If an entity or metric was uncollected or missing from the telemetry stream, it is recorded in `key_observations` with `is_available=False`, `value=None`, and provenance `{"status": "not_reported_by_telemetry_source"}`. Fictitious poller timestamps or synthetic device MACs are never injected.

2. **Strict Advisory & Simulation Boundaries on Remediation:**
   - Every generated `RecommendedAction` is stamped with `is_simulated=True`, `is_advisory=True`, and an advisory warning.
   - NetCoop AI produces diagnostic and mitigation proposals only. No direct network mutation commands are dispatched without operator approval.

3. **Decoupled Recovery Verification:**
   - Operational recovery is strictly independent of diagnostic synthesis completion.
   - Diagnosed faults default to `RecoveryStatus.PENDING_VERIFICATION` unless an explicit telemetry post-check verifies restoration.
   - Benign health reports default to `RecoveryStatus.NOT_APPLICABLE`. Real recovery is never claimed merely because an analysis finished.

4. **Campus Topology Separation (`site_id` vs `site_name`):**
   - The adapter resolves topology against the validated IIT Bhubaneswar campus model (`data/campus/iitbbsr_demo_topology.json`).
   - Identifiers (`site_id`, e.g., `site_admin`, `zone_academic`) and human-readable names (`site_name`, e.g., `Administrative Building`, `Academic zone`) are strictly segregated in `affected_site_ids` and `affected_site_names`.

5. **Statistical Calibration & Conformal Abstention Integrity:**
   - Conformal prediction sets and empirical probability intervals are passed through transparently from the ML inference layer (`ClassifierAgent`).
   - When confidence is uncalibrated heuristic scoring, `is_confidence_calibrated` is set to `False` and `confidence_type="uncalibrated_heuristic"`.
   - If conformal coverage is violated or multiple fault hypotheses tie, status is set to `DiagnosticStatus.ABSTAINED` and `probable_root_cause=None`.

---

## 3. V1-to-V2 Field and Section Mapping

| UnifiedDiagnosticReport (V1) Field | NetworkDiagnosticReport (V2) Location | Semantics & Transformation |
| :--- | :--- | :--- |
| `incident_id` | `report.incident_id`, `executive.incident_id` | Preserved verbatim |
| `network_id` | `report.network_id` | Campus or subnet scope |
| `status` | `executive.diagnostic_status` | Mapped to enum: `diagnosed`, `benign`, `insufficient_evidence`, `abstained` |
| `probable_cause` | `executive.probable_root_cause` | Preserved for diagnosed/benign; null for abstained/insufficient evidence |
| `confidence` | `executive.confidence` | Prefers `calibrated_confidence` if available; otherwise raw heuristic score |
| `confidence_breakdown` | `technical.sections["confidence_calibration"]` | Full rules, model, blended scores, and conformal nonconformity bounds |
| `conformal_prediction_set` | `technical.sections["confidence_calibration"]` | List of accepted fault categories meeting statistical coverage $\ge 1 - \alpha$ |
| `affected_devices` | `executive.affected_devices` | Validated device IDs |
| `evidence` | `executive.key_observations`, `technical.sections["evidence_records"]` | Normalized records with category, entity, metric, value, unit, severity, weight |
| `uncertainty` | `technical.sections["hypotheses_evaluation"]`, `technical.sections["recovery_limitations"]` | Score, ambiguity reasons, alternative hypotheses, and missing evidence domains |
| `remediation_actions` | `executive.recommended_actions`, `technical.sections["remediation_plan"]` | Actions converted to advisory items with blast radius and rollback commands |
| `limitations` | `executive.limitations`, `technical.sections["recovery_limitations"]` | Operational boundary notes and disclaimers |
| `provenance` | `executive.data_provenance` | Ingestion metadata, pipeline version, and collector traces |

---

## 4. Integration Snippet for API & Orchestration (Satwik & Anjali)

### Backend API Integration (`api/main.py` or diagnostic endpoints)

```python
from fastapi import APIRouter, HTTPException
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.reporting.builder import DiagnosticReportBuilder
from netcoop.reporting.models import NetworkDiagnosticReport

router = APIRouter()

@router.post("/diagnose/v2", response_model=NetworkDiagnosticReport)
async def diagnose_incident_v2(payload: dict) -> NetworkDiagnosticReport:
    # 1. Execute diagnostic orchestration
    v1_report = run_diagnosis(payload)
    if not v1_report:
        raise HTTPException(status_code=500, detail="Diagnostic pipeline failed to synthesize report.")

    # 2. Convert to versioned V2 contract with topology resolution
    v2_report = DiagnosticReportBuilder.from_unified_report(
        unified_report=v1_report,
        incident_data=payload,
    )
    return v2_report
```

### Frontend Integration (`dashboard/` / UI Consumers)

The generated report exposes both Level 1 (Executive) and Level 2 (Technical) data models directly compatible with TypeScript interfaces:

```typescript
// Example response consumption in React / Next.js
interface NetworkDiagnosticReportV2 {
  schema_version: string;
  report_id: string;
  incident_id: string;
  executive: {
    diagnostic_status: "diagnosed" | "benign" | "insufficient_evidence" | "abstained";
    probable_root_cause: string | null;
    severity: "info" | "warning" | "critical" | "unknown";
    confidence: number | null;
    is_confidence_calibrated: boolean;
    affected_devices: string[];
    affected_site_ids: string[];
    affected_site_names: string[];
    recommended_actions: Array<{
      action_id: string;
      title: string;
      description: string;
      is_simulated: boolean;
      status: string;
    }>;
  };
  technical: {
    sections: Array<{
      section_id: string;
      title: string;
      order: number;
      is_available: boolean;
      data: Record<string, any>;
    }>;
  };
}
```

