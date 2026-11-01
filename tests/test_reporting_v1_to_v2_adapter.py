"""Unit and contract test suite for V1-to-V2 Network Diagnostic Report Adapter.

Covers the 10 core integration requirements:
1. Complete V1 report converting to a valid V2 report (NetworkDiagnosticReport).
2. Missing optional fields (null probable_cause, empty evidence, empty remediation_actions).
3. Unknown or unavailable provenance (preserving limitations without inventing sources).
4. Multiple findings and affected devices (verifying evidence and topology mappings).
5. Empty findings or insufficient evidence (DiagnosticStatus.INSUFFICIENT_EVIDENCE).
6. Low-confidence diagnosis and abstention (DiagnosticStatus.ABSTAINED).
7. Simulated remediation vs verified recovery (is_simulated=True, pending_verification or NOT_APPLICABLE).
8. Serialization and deserialization of the V2 result (model_dump_json and model_validate_json).
9. Deterministic conversion for identical input.
10. Invalid source data producing clear validation errors rather than fabricated output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from netcoop.core.evidence import UncertaintyEvaluation
from netcoop.core.report import RemediationActionItem, UnifiedDiagnosticReport
from netcoop.remediation.actions import RemediationCatalog
from netcoop.reporting.builder import DiagnosticReportBuilder
from netcoop.reporting.models import (
    DiagnosticStatus,
    NetworkDiagnosticReport,
    RecoveryStatus,
    RemediationState,
    ReportSeverity,
    RootCauseStatus,
)

TOPOLOGY_PATH = Path("data/campus/iitbbsr_demo_topology.json")


@pytest.fixture(scope="module")
def campus_topology() -> Dict[str, Any]:
    if TOPOLOGY_PATH.is_file():
        with open(TOPOLOGY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def create_base_unified_report(
    incident_id: str = "inc-v1-test-001",
    status: str = "diagnosed",
    probable_cause: str | None = "Link Congestion and Queue Drops",
    confidence: float = 0.92,
    calibrated_confidence: float | None = 0.89,
    affected_devices: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    remediation_actions: list[RemediationActionItem] | None = None,
    limitations: list[str] | None = None,
    provenance: dict[str, Any] | None = None,
) -> UnifiedDiagnosticReport:
    """Helper to build consistent UnifiedDiagnosticReport fixtures."""
    actions = remediation_actions if remediation_actions is not None else [
        RemediationCatalog.create_rebalance_traffic_action(
            device="IITBBSR-CORE-RTR-01",
            interface="HundredGigE0/0/0/1",
        )
    ]
    ev_list = evidence if evidence is not None else [
        {
            "evidence_id": "evi-cong-001",
            "source_agent": "telemetry_agent",
            "category": "metric_anomaly",
            "finding": "Egress link utilization reached 94.2% exceeding saturation threshold",
            "entity": "IITBBSR-CORE-RTR-01:HundredGigE0/0/0/1",
            "metric_name": "interface_utilization_pct",
            "value": 94.2,
            "unit": "percent",
            "severity": "critical",
            "timestamp": "2026-11-01T02:00:00Z",
            "provenance": {"collector": "snmp_interface_poller", "poll_interval_s": 10},
            "weight": 1.0,
        }
    ]
    cb: dict[str, Any] = {"rules_score": confidence}
    if calibrated_confidence is not None:
        cb["calibrated_confidence"] = calibrated_confidence
        cb["model_score"] = 0.90
        cb["blended_score"] = 0.91

    return UnifiedDiagnosticReport(
        incident_id=incident_id,
        network_id="iitbbsr_argul_campus",
        status=status,
        probable_cause=probable_cause,
        confidence=confidence,
        confidence_breakdown=cb,
        confidence_category="high" if confidence >= 0.85 else "medium",
        conformal_prediction_set=["link_congestion"],
        affected_devices=affected_devices or ["IITBBSR-CORE-RTR-01"],
        affected_interfaces=["HundredGigE0/0/0/1"],
        evidence=ev_list,
        remediation_actions=actions,
        uncertainty=UncertaintyEvaluation(
            score=0.10,
            reasons=["Strong corroborated queue drops and latency increase."],
        ),
        limitations=limitations if limitations is not None else ["Advisory simulation only."],
        provenance=provenance if provenance is not None else {"pipeline": "netcoop_eval", "version": "2.0.0"},
    )


# -----------------------------------------------------------------------------
# 1. Complete V1 Report Conversion
# -----------------------------------------------------------------------------

def test_1_complete_v1_report_conversion(campus_topology: Dict[str, Any]) -> None:
    """Requirement 1: Complete V1 report converts to a valid V2 NetworkDiagnosticReport."""
    v1_rep = create_base_unified_report()
    v2_rep = DiagnosticReportBuilder.from_unified_report(
        unified_report=v1_rep,
        campus_topology=campus_topology,
        report_id="rep-complete-001",
    )

    assert isinstance(v2_rep, NetworkDiagnosticReport)
    assert v2_rep.report_id == "rep-complete-001"
    assert v2_rep.incident_id == "inc-v1-test-001"
    assert v2_rep.schema_version == "2.0.0"

    exec_rep = v2_rep.executive
    assert exec_rep.diagnostic_status == DiagnosticStatus.DIAGNOSED
    assert exec_rep.probable_root_cause == "Link Congestion and Queue Drops"
    assert exec_rep.root_cause_status == RootCauseStatus.PROBABLE
    assert exec_rep.severity == ReportSeverity.CRITICAL
    assert exec_rep.is_confidence_calibrated is True
    assert exec_rep.confidence == 0.89  # uses calibrated confidence
    assert exec_rep.affected_devices == ["IITBBSR-CORE-RTR-01"]
    assert len(exec_rep.key_observations) == 1
    assert exec_rep.key_observations[0].metric_name == "interface_utilization_pct"
    assert exec_rep.key_observations[0].value == 94.2
    assert len(exec_rep.recommended_actions) == 1
    assert exec_rep.recommended_actions[0].is_simulated is True

    tech_rep = v2_rep.technical
    assert len(tech_rep.sections) == 12
    assert tech_rep.get_section("incident_context") is not None
    assert tech_rep.get_section("root_cause_analysis") is not None or tech_rep.get_section("hypotheses_evaluation") is not None
    assert tech_rep.get_section("evidence_records") is not None
    assert tech_rep.get_section("confidence_calibration") is not None
    assert tech_rep.get_section("recovery_limitations") is not None


# -----------------------------------------------------------------------------
# 2. Missing Optional Fields Handling
# -----------------------------------------------------------------------------

def test_2_missing_optional_fields() -> None:
    """Requirement 2: Missing optional fields (null probable_cause, empty evidence/actions) convert cleanly."""
    v1_rep = UnifiedDiagnosticReport(
        incident_id="inc-minimal-002",
        network_id="iitbbsr_test",
        status="insufficient_evidence",
        probable_cause=None,
        confidence=0.0,
        confidence_breakdown={},
        affected_devices=[],
        affected_interfaces=[],
        evidence=[],
        remediation_actions=[],
        uncertainty=UncertaintyEvaluation(score=1.0, reasons=["No anomalous telemetry detected."]),
        limitations=[],
        provenance={},
    )
    v2_rep = DiagnosticReportBuilder.from_unified_report(unified_report=v1_rep)

    assert isinstance(v2_rep, NetworkDiagnosticReport)
    assert v2_rep.executive.diagnostic_status == DiagnosticStatus.INSUFFICIENT_EVIDENCE
    assert v2_rep.executive.probable_root_cause is None
    assert v2_rep.executive.confidence is None
    assert v2_rep.executive.key_observations == []
    assert v2_rep.executive.recommended_actions == []
    assert v2_rep.executive.affected_devices == []
    assert v2_rep.executive.affected_site_ids == []
    assert v2_rep.executive.affected_site_names == []


# -----------------------------------------------------------------------------
# 3. Unknown or Unavailable Provenance Preservation
# -----------------------------------------------------------------------------

def test_3_unknown_or_unavailable_provenance() -> None:
    """Requirement 3: Unknown or unavailable provenance preserves limitations without inventing sources."""
    evidence_with_empty_prov = [
        {
            "evidence_id": "evi-unknown-001",
            "source_agent": "telemetry_agent",
            "category": "metric_anomaly",
            "finding": "Telemetry jitter detected without hardware poller timestamp",
            "entity": "device-unknown",
            "metric_name": "jitter_ms",
            "value": 15.4,
            "unit": "ms",
            "severity": "warning",
            "timestamp": None,
            "provenance": {},  # Missing live collector provenance
            "weight": 0.5,
        }
    ]
    v1_rep = create_base_unified_report(
        incident_id="inc-prov-003",
        evidence=evidence_with_empty_prov,
        provenance={},
    )
    missing_metrics = ["packet_drop_rate", "optical_rx_power_dbm"]
    v2_rep = DiagnosticReportBuilder.from_unified_report(
        unified_report=v1_rep,
        missing_metric_names=missing_metrics,
    )

    # Validate provenance is not fabricated
    obs = v2_rep.executive.key_observations
    avail_obs = [o for o in obs if o.is_available]
    unavail_obs = [o for o in obs if not o.is_available]

    assert len(avail_obs) == 1
    assert avail_obs[0].provenance == {}  # Empty dict preserved, no fictitious source injected

    assert len(unavail_obs) == 2
    for unavail in unavail_obs:
        assert unavail.value is None
        assert unavail.is_available is False
        assert unavail.provenance == {"status": "not_reported_by_telemetry_source"}


# -----------------------------------------------------------------------------
# 4. Multiple Findings and Affected Devices Mapping
# -----------------------------------------------------------------------------

def test_4_multiple_findings_and_affected_devices(campus_topology: Dict[str, Any]) -> None:
    """Requirement 4: Multiple findings across distinct devices map evidence and topology sites properly."""
    multi_evidence = [
        {
            "evidence_id": "evi-core-01",
            "source_agent": "telemetry_agent",
            "category": "metric_anomaly",
            "finding": "Core router buffer starvation",
            "entity": "IITBBSR-CORE-RTR-01",
            "metric_name": "buffer_drop_count",
            "value": 1250,
            "unit": "pkts",
            "severity": "critical",
            "timestamp": "2026-11-01T03:00:00Z",
            "provenance": {"source": "interface_stats"},
        },
        {
            "evidence_id": "evi-agg-01",
            "source_agent": "log_agent",
            "category": "log_pattern",
            "finding": "Agg switch OSPF state down notification",
            "entity": "IITBBSR-AGG-ACAD-01",
            "metric_name": "syslog_event",
            "value": "OSPF_NBR_DOWN",
            "unit": None,
            "severity": "warning",
            "timestamp": "2026-11-01T03:00:01Z",
            "provenance": {"source": "syslog_listener"},
        },
    ]

    v1_rep = create_base_unified_report(
        incident_id="inc-multi-004",
        affected_devices=["IITBBSR-CORE-RTR-01", "IITBBSR-AGG-ACAD-01"],
        evidence=multi_evidence,
    )
    v2_rep = DiagnosticReportBuilder.from_unified_report(
        unified_report=v1_rep,
        campus_topology=campus_topology,
    )

    exec_rep = v2_rep.executive
    assert len(exec_rep.affected_devices) == 2
    # Verify strict site_id and site_name separation
    assert "site_admin" in exec_rep.affected_site_ids
    assert "Administrative Building" in exec_rep.affected_site_names
    assert len(exec_rep.key_observations) == 2
    agents_present = {ev.source for ev in exec_rep.key_observations}
    assert agents_present == {"telemetry_agent", "log_agent"}


# -----------------------------------------------------------------------------
# 5. Empty Findings and Insufficient Evidence
# -----------------------------------------------------------------------------

def test_5_empty_findings_insufficient_evidence() -> None:
    """Requirement 5: Empty findings or insufficient evidence maps to INSUFFICIENT_EVIDENCE."""
    v1_rep = UnifiedDiagnosticReport(
        incident_id="inc-insuff-005",
        network_id="iitbbsr_campus",
        status="insufficient_evidence",
        probable_cause=None,
        confidence=0.0,
        confidence_breakdown={},
        affected_devices=[],
        evidence=[],
        remediation_actions=[],
        uncertainty=UncertaintyEvaluation(
            score=1.0,
            reasons=["All telemetry within normal bounds", "Zero anomalous cross-domain observations"],
        ),
        limitations=[],
        provenance={},
    )
    v2_rep = DiagnosticReportBuilder.from_unified_report(unified_report=v1_rep)

    assert v2_rep.executive.diagnostic_status == DiagnosticStatus.INSUFFICIENT_EVIDENCE
    assert v2_rep.executive.probable_root_cause is None
    assert v2_rep.executive.root_cause_status == RootCauseStatus.INCONCLUSIVE
    assert v2_rep.executive.confidence is None
    assert v2_rep.executive.key_observations == []


# -----------------------------------------------------------------------------
# 6. Low-Confidence Diagnosis and Abstention
# -----------------------------------------------------------------------------

def test_6_low_confidence_diagnosis_and_abstention() -> None:
    """Requirement 6: Low-confidence diagnosis and conformal abstention maps to ABSTAINED."""
    v1_rep = UnifiedDiagnosticReport(
        incident_id="inc-abstain-006",
        network_id="iitbbsr_campus",
        status="abstained",
        probable_cause=None,
        confidence=0.0,
        confidence_breakdown={
            "rules_score": 0.35,
            "model_score": 0.40,
        },
        conformal_prediction_set=[],
        affected_devices=["IITBBSR-CORE-RTR-01"],
        evidence=[],
        remediation_actions=[],
        uncertainty=UncertaintyEvaluation(
            score=0.95,
            reasons=["Conformal prediction set is empty; coverage guarantees violated."],
        ),
        limitations=[],
        provenance={},
    )
    v2_rep = DiagnosticReportBuilder.from_unified_report(unified_report=v1_rep)

    assert v2_rep.executive.diagnostic_status == DiagnosticStatus.ABSTAINED
    assert v2_rep.executive.probable_root_cause is None
    assert v2_rep.executive.root_cause_status == RootCauseStatus.ABSTAINED
    assert v2_rep.executive.confidence is None
    calib_section = v2_rep.technical.get_section("confidence_calibration")
    assert calib_section is not None
    assert calib_section.data["conformal_prediction_set"] == []


# -----------------------------------------------------------------------------
# 7. Simulated Remediation vs Verified Recovery
# -----------------------------------------------------------------------------

def test_7_simulated_remediation_vs_verified_recovery() -> None:
    """Requirement 7: Remediation is explicitly marked advisory/simulated and recovery is independent."""
    # 7a: Fault scenario with simulated action
    v1_fault = create_base_unified_report(
        incident_id="inc-fault-007a",
        status="diagnosed",
        remediation_actions=[
            RemediationCatalog.create_clear_flap_damping_action(
                device="IITBBSR-CORE-RTR-01",
                peer_ip="10.200.0.2",
            )
        ],
    )
    v2_fault = DiagnosticReportBuilder.from_unified_report(unified_report=v1_fault)

    assert len(v2_fault.executive.recommended_actions) == 1
    action = v2_fault.executive.recommended_actions[0]
    assert action.is_simulated is True
    assert action.is_advisory is True
    assert action.status == RemediationState.APPROVED  # "pending_approval" maps to APPROVED
    assert "advisory and simulated only" in action.advisory_notice.lower()
    # Recovery must NOT be claimed as completed or verified
    assert v2_fault.executive.recovery_verification_status == RecoveryStatus.PENDING_VERIFICATION

    # 7b: Benign scenario should have NOT_APPLICABLE recovery status
    v1_benign = UnifiedDiagnosticReport(
        incident_id="inc-benign-007b",
        network_id="iitbbsr_campus",
        status="benign",
        probable_cause="Normal Operation",
        confidence=1.0,
        affected_devices=[],
        evidence=[],
        remediation_actions=[],
        uncertainty=UncertaintyEvaluation(score=0.0, reasons=["All nominal"]),
        limitations=[],
        provenance={},
    )
    v2_benign = DiagnosticReportBuilder.from_unified_report(unified_report=v1_benign)
    assert v2_benign.executive.diagnostic_status == DiagnosticStatus.BENIGN
    assert v2_benign.executive.recovery_verification_status == RecoveryStatus.NOT_APPLICABLE


# -----------------------------------------------------------------------------
# 8. Serialization and Deserialization Round-trip
# -----------------------------------------------------------------------------

def test_8_serialization_and_deserialization_roundtrip(campus_topology: Dict[str, Any]) -> None:
    """Requirement 8: Serialization to JSON and deserialization via Pydantic matches perfectly."""
    v1_rep = create_base_unified_report(incident_id="inc-ser-008")
    v2_rep = DiagnosticReportBuilder.from_unified_report(
        unified_report=v1_rep,
        campus_topology=campus_topology,
        report_id="rep-ser-roundtrip",
    )

    json_str = v2_rep.model_dump_json(indent=2)
    assert isinstance(json_str, str)
    assert len(json_str) > 0

    # Ensure it parses as valid JSON dictionary
    parsed_dict = json.loads(json_str)
    assert parsed_dict["report_id"] == "rep-ser-roundtrip"
    assert parsed_dict["executive"]["diagnostic_status"] == "diagnosed"

    # Re-instantiate model from JSON
    reconstructed = NetworkDiagnosticReport.model_validate_json(json_str)
    assert reconstructed.report_id == v2_rep.report_id
    assert reconstructed.incident_id == v2_rep.incident_id
    assert reconstructed.executive.diagnostic_status == v2_rep.executive.diagnostic_status
    assert reconstructed.executive.confidence == v2_rep.executive.confidence
    assert reconstructed.executive.affected_devices == v2_rep.executive.affected_devices
    assert len(reconstructed.technical.sections) == len(v2_rep.technical.sections)


# -----------------------------------------------------------------------------
# 9. Deterministic Conversion
# -----------------------------------------------------------------------------

def test_9_deterministic_conversion(campus_topology: Dict[str, Any]) -> None:
    """Requirement 9: Identical V1 input produces identical V2 reports."""
    v1_rep = create_base_unified_report(incident_id="inc-determ-009")

    rep1 = DiagnosticReportBuilder.from_unified_report(
        unified_report=v1_rep,
        campus_topology=campus_topology,
        report_id="rep-fixed-deterministic",
    )
    rep2 = DiagnosticReportBuilder.from_unified_report(
        unified_report=v1_rep,
        campus_topology=campus_topology,
        report_id="rep-fixed-deterministic",
    )

    # Comparing dumped JSON strings (excluding runtime timestamp)
    d1 = rep1.model_dump()
    d2 = rep2.model_dump()

    # Align generated_timestamp and created_at to verify purely algorithmic determinism
    d1["created_at"] = "2026-11-01T00:00:00Z"
    d2["created_at"] = "2026-11-01T00:00:00Z"
    d1["executive"]["generated_timestamp"] = "2026-11-01T00:00:00Z"
    d2["executive"]["generated_timestamp"] = "2026-11-01T00:00:00Z"

    assert d1 == d2


# -----------------------------------------------------------------------------
# 10. Invalid Source Data Produces Clear Validation Errors
# -----------------------------------------------------------------------------

def test_10_invalid_source_data_produces_clear_validation_error() -> None:
    """Requirement 10: Invalid source data triggers validation errors rather than fabricating output."""
    # Invalid confidence value > 1.0 on UnifiedDiagnosticReport
    with pytest.raises(ValidationError):
        UnifiedDiagnosticReport(
            incident_id="inc-invalid-010",
            network_id="iitbbsr",
            status="diagnosed",
            confidence=1.5,  # Exceeds maximum 1.0
            uncertainty=UncertaintyEvaluation(score=0.1, reasons=[]),
        )

    # Missing mandatory uncertainty
    with pytest.raises(ValidationError):
        UnifiedDiagnosticReport(
            incident_id="inc-invalid-010",
            network_id="iitbbsr",
            status="diagnosed",
            confidence=0.8,
            # uncertainty omitted
        )
