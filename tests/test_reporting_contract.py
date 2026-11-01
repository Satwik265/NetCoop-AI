"""Rigorous integration-readiness test suite for the two-level Network Diagnostic Report contract.

Validates the 15 core hardening requirements:
1. Real upstream UnifiedDiagnosticReport conversion.
2. Realistic orchestrator-result conversion (from run_diagnosis pipeline).
3. Raw versus calibrated confidence integrity.
4. Conformal abstention preservation.
5. Multiple-agent evidence attribution.
6. Conflicting hypotheses and arbitration records.
7. Failed and skipped agent states.
8. Site ID versus site name correctness.
9. Invalid topology references handling.
10. Missing audit records truthfulness.
11. Advisory remediation without executed commands.
12. Pending recovery verification independence.
13. All 12 technical report sections integrity.
14. Partial and degraded report serialization.
15. JSON Schema and Pydantic model consistency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import jsonschema
import pytest

from netcoop.core.evidence import UncertaintyEvaluation
from netcoop.core.report import RemediationActionItem, UnifiedDiagnosticReport
from netcoop.remediation.actions import RemediationCatalog
from netcoop.reporting.builder import DiagnosticReportBuilder
from netcoop.reporting.models import (
    AgentInvestigationRecord,
    AgentState,
    AuditReference,
    DiagnosticStatus,
    NetworkDiagnosticReport,
    RecoveryStatus,
    RemediationState,
    ReportSeverity,
    RootCauseStatus,
)

SCHEMA_PATH = Path("schemas/network_diagnostic_report.schema.json")
TOPOLOGY_PATH = Path("data/campus/iitbbsr_demo_topology.json")
FIXTURE_PATH = Path("data/fixtures/synthetic_diagnostic_report.json")


@pytest.fixture(scope="module")
def report_schema() -> Dict[str, Any]:
    assert SCHEMA_PATH.is_file(), f"Report schema missing at {SCHEMA_PATH}"
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def campus_topology() -> Dict[str, Any]:
    assert TOPOLOGY_PATH.is_file(), f"Campus topology missing at {TOPOLOGY_PATH}"
    with open(TOPOLOGY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_unified_report() -> UnifiedDiagnosticReport:
    action = RemediationCatalog.create_drain_optical_link_action(
        device="IITBBSR-CORE-RTR-01",
        interface="HundredGigE0/0/0/0",
        peer_device="IITBBSR-AGG-ACAD-01",
    )
    return UnifiedDiagnosticReport(
        incident_id="inc-test-001",
        network_id="iitbbsr_argul_campus",
        status="diagnosed",
        probable_cause="Optical Transceiver Degradation",
        confidence=0.884,
        affected_devices=["IITBBSR-CORE-RTR-01", "IITBBSR-AGG-ACAD-01"],
        affected_interfaces=["HundredGigE0/0/0/0"],
        evidence=[
            {
                "evidence_id": "evi-opt-001",
                "source_agent": "telemetry_agent",
                "category": "metric_anomaly",
                "finding": "Laser Tx optical power dropped below -12.5 dBm warning threshold",
                "entity": "IITBBSR-CORE-RTR-01:HundredGigE0/0/0/0",
                "metric_name": "optical_tx_power_dbm",
                "value": -13.2,
                "unit": "dbm",
                "severity": "critical",
                "timestamp": "2026-11-01T00:30:00Z",
                "provenance": {"collector": "snmp_dom_poller"},
                "weight": 1.0,
            },
            {
                "evidence_id": "evi-opt-002",
                "source_agent": "telemetry_agent",
                "category": "metric_anomaly",
                "finding": "Physical FCS cyclic redundancy check error rate spiked to 420 pkts/s",
                "entity": "IITBBSR-CORE-RTR-01:HundredGigE0/0/0/0",
                "metric_name": "fcs_error_rate",
                "value": 420.0,
                "unit": "frames",
                "severity": "warning",
                "timestamp": "2026-11-01T00:30:15Z",
                "provenance": {"collector": "interface_counter_poller"},
                "weight": 0.8,
            },
        ],
        uncertainty=UncertaintyEvaluation(
            score=0.116,
            reasons=["Optical attenuation confirmed on local transceiver interface."],
            missing_evidence=["OTDR physical fiber trace"],
            alternative_hypotheses=[{"cause": "Dirty Fiber Connector", "confidence": 0.28}],
        ),
        remediation_actions=[action],
        summary="Diagnosed Optical Transceiver Degradation on HundredGigE0/0/0/0.",
        processing_time_ms=145.2,
        causal_chain=[
            "Laser diode degradation",
            "Tx power attenuation below receiver threshold",
            "CRC error escalation",
        ],
        conflicts_resolved=[],
        limitations=["Remediation actions are simulated only."],
        provenance={"source": "test_runner"},
        confidence_breakdown={
            "rules_score": 0.890,
            "model_score": 0.875,
            "blended_score": 0.884,
            "calibrated_confidence": 0.884,
        },
        conformal_prediction_set=["optical_transceiver_degradation"],
        confidence_category="high",
    )


# 1. Real upstream UnifiedDiagnosticReport conversion
def test_valid_report_construction(
    sample_unified_report: UnifiedDiagnosticReport,
    campus_topology: Dict[str, Any],
    report_schema: Dict[str, Any],
):
    report = DiagnosticReportBuilder.from_unified_report(
        unified_report=sample_unified_report,
        campus_topology=campus_topology,
    )
    assert isinstance(report, NetworkDiagnosticReport)
    assert report.schema_version == "2.0.0"
    assert report.incident_id == "inc-test-001"
    assert report.executive.diagnostic_status == DiagnosticStatus.DIAGNOSED
    assert report.executive.probable_root_cause == "Optical Transceiver Degradation"
    assert report.executive.confidence == 0.884
    assert len(report.technical.sections) == 12

    # Validate against JSON schema
    report_dict = json.loads(report.to_json())
    jsonschema.validate(instance=report_dict, schema=report_schema)


# 2. Realistic orchestrator-result conversion (from run_diagnosis pipeline)
def test_realistic_orchestrator_pipeline_conversion(campus_topology: Dict[str, Any]):
    from netcoop.orchestrator.graph import run_diagnosis

    synthetic_incident = {
        "incident_id": "inc-orch-test-002",
        "network_id": "iitbbsr_argul_campus",
        "telemetry": [
            {
                "device_id": "IITBBSR-CORE-RTR-01",
                "interface": "HundredGigE0/0/0/0",
                "timestamp": "2026-11-01T00:30:00Z",
                "optical_tx_power_dbm": -14.5,
                "fcs_error_rate": 650.0,
                "carrier_transitions": 18,
            }
        ],
        "topology": campus_topology,
    }

    u_report = run_diagnosis(synthetic_incident)
    assert isinstance(u_report, UnifiedDiagnosticReport)

    report = DiagnosticReportBuilder.from_unified_report(
        unified_report=u_report,
        campus_topology=campus_topology,
    )

    assert report.incident_id == "inc-orch-test-002"
    assert report.executive.diagnostic_status in (
        DiagnosticStatus.DIAGNOSED,
        DiagnosticStatus.INSUFFICIENT_EVIDENCE,
    )
    assert report.technical.get_section("incident_context") is not None


# 3. Raw versus calibrated confidence integrity
def test_raw_versus_calibrated_confidence(campus_topology: Dict[str, Any]):
    # Scenario A: Calibrated report
    calibrated_report = UnifiedDiagnosticReport(
        incident_id="inc-calib-001",
        network_id="iitbbsr_argul_campus",
        status="diagnosed",
        probable_cause="Optical Transceiver Degradation",
        confidence=0.884,
        confidence_breakdown={
            "rules_score": 0.890,
            "model_score": 0.875,
            "blended_score": 0.884,
            "calibrated_confidence": 0.884,
        },
        conformal_prediction_set=["optical_transceiver_degradation"],
        confidence_category="high",
        uncertainty=UncertaintyEvaluation(score=0.116, reasons=[], missing_evidence=[]),
    )
    rep_a = DiagnosticReportBuilder.from_unified_report(calibrated_report, campus_topology=campus_topology)
    assert rep_a.executive.is_confidence_calibrated is True
    assert rep_a.executive.confidence_type == "calibrated_probability"
    assert rep_a.executive.confidence == 0.884

    # Scenario B: Purely heuristic uncalibrated report
    uncalibrated_report = UnifiedDiagnosticReport(
        incident_id="inc-uncalib-002",
        network_id="iitbbsr_argul_campus",
        status="diagnosed",
        probable_cause="MTU Mismatch Blackhole",
        confidence=0.75,
        confidence_breakdown=None,  # No calibration breakdown
        conformal_prediction_set=[],
        uncertainty=UncertaintyEvaluation(score=0.25, reasons=[], missing_evidence=[]),
    )
    rep_b = DiagnosticReportBuilder.from_unified_report(uncalibrated_report, campus_topology=campus_topology)
    assert rep_b.executive.is_confidence_calibrated is False
    assert rep_b.executive.confidence_type == "uncalibrated_heuristic"
    assert rep_b.executive.confidence == 0.75

    calib_sec = rep_b.technical.get_section("confidence_calibration")
    assert calib_sec is not None
    assert calib_sec.is_available is False  # Explicitly communicates uncalibrated state
    assert calib_sec.data["calibrated_confidence"] is None, "Must not fabricate calibrated score from raw heuristic"


# 4. Conformal abstention preservation
def test_conformal_abstention_preservation():
    abstained_unified = UnifiedDiagnosticReport(
        incident_id="inc-abstain-003",
        network_id="iitbbsr_argul_campus",
        status="abstained",
        probable_cause=None,
        confidence=0.0,
        affected_devices=["IITBBSR-CORE-RTR-01"],
        evidence=[],
        uncertainty=UncertaintyEvaluation(
            score=0.95,
            reasons=["Conformal prediction set is empty; nonconformity exceeds threshold."],
            missing_evidence=["Packet loss telemetry"],
            alternative_hypotheses=[],
        ),
        conformal_prediction_set=[],
        confidence_category="abstain",
        remediation_actions=[],
    )

    report = DiagnosticReportBuilder.from_unified_report(unified_report=abstained_unified)

    assert report.executive.diagnostic_status == DiagnosticStatus.ABSTAINED
    assert report.executive.probable_root_cause is None, "Must not force root cause label when abstained"
    assert report.executive.confidence is None, "Confidence must be None when abstained"
    assert report.executive.root_cause_status == RootCauseStatus.ABSTAINED
    assert report.executive.confidence_type is None
    assert "abstained" in report.executive.executive_summary.lower()


# 5. Multiple-agent evidence attribution
def test_multiple_agent_evidence_attribution(campus_topology: Dict[str, Any]):
    multi_agent_report = UnifiedDiagnosticReport(
        incident_id="inc-multi-001",
        network_id="iitbbsr_argul_campus",
        status="diagnosed",
        probable_cause="Optical Transceiver Degradation",
        confidence=0.91,
        affected_devices=["IITBBSR-CORE-RTR-01"],
        evidence=[
            {
                "evidence_id": "evi-tel-01",
                "source_agent": "telemetry_agent",
                "category": "metric_anomaly",
                "finding": "Rx power drop",
                "entity": "IITBBSR-CORE-RTR-01",
                "metric_name": "rx_power",
                "value": -18.2,
                "unit": "dbm",
                "severity": "critical",
            },
            {
                "evidence_id": "evi-log-02",
                "source_agent": "log_agent",
                "category": "log_pattern",
                "finding": "Optics alarm in syslog",
                "entity": "IITBBSR-CORE-RTR-01",
                "metric_name": "syslog_count",
                "value": 5,
                "unit": "count",
                "severity": "warning",
            },
            {
                "evidence_id": "evi-top-03",
                "source_agent": "topology_agent",
                "category": "topology_change",
                "finding": "BGP adjacency flap on trunk",
                "entity": "IITBBSR-CORE-RTR-01",
                "metric_name": "flap_count",
                "value": 3,
                "unit": "count",
                "severity": "warning",
            },
        ],
        uncertainty=UncertaintyEvaluation(score=0.09, reasons=[], missing_evidence=[]),
    )

    report = DiagnosticReportBuilder.from_unified_report(multi_agent_report, campus_topology=campus_topology)
    ev_sec = report.technical.get_section("evidence_records")
    assert ev_sec is not None
    records = ev_sec.data.get("records", [])
    assert len(records) == 3

    sources = {r["source_agent"] for r in records}
    assert sources == {"telemetry_agent", "log_agent", "topology_agent"}

    agent_status_roles = {a.agent_role for a in report.executive.agent_investigation_status if a.status == AgentState.COMPLETED}
    assert "telemetry_agent" in agent_status_roles
    assert "log_agent" in agent_status_roles
    assert "topology_agent" in agent_status_roles


# 6. Conflicting hypotheses and arbitration records
def test_conflicting_hypotheses_and_arbitration():
    conflict_report = UnifiedDiagnosticReport(
        incident_id="inc-conf-001",
        network_id="iitbbsr_argul_campus",
        status="diagnosed",
        probable_cause="Optical Transceiver Degradation",
        confidence=0.88,
        conflicts_resolved=[
            {
                "iteration": 1,
                "conflicting_causes": ["Link Congestion", "Optical Transceiver Degradation"],
                "arbitrated_winner": "Optical Transceiver Degradation",
                "rationale": "Direct DOM transceiver telemetry overrides downstream traffic congestion inference.",
            }
        ],
        uncertainty=UncertaintyEvaluation(score=0.12, reasons=[], missing_evidence=[]),
    )

    report = DiagnosticReportBuilder.from_unified_report(conflict_report)
    arb_sec = report.technical.get_section("arbitration")
    assert arb_sec is not None
    assert arb_sec.is_available is True
    assert len(arb_sec.data["conflicts_resolved"]) == 1
    assert "Direct Telemetry > Correlated Telemetry > Topology Inference" in arb_sec.data["arbitration_rule"]


# 7. Failed and skipped agent states
def test_failed_and_skipped_agent_states():
    agent_records = [
        AgentInvestigationRecord(
            agent_role="telemetry_agent",
            agent_name="Telemetry Specialist",
            status=AgentState.COMPLETED,
            observations_count=4,
            findings_summary="Completed telemetry scan.",
        ),
        AgentInvestigationRecord(
            agent_role="wifi_services_agent",
            agent_name="WiFi Specialist",
            status=AgentState.FAILED,
            observations_count=0,
            findings_summary="Agent exception during AP telemetry polling.",
            error_message="Connection timeout to AP controller.",
        ),
        AgentInvestigationRecord(
            agent_role="config_agent",
            agent_name="Configuration Specialist",
            status=AgentState.SKIPPED,
            observations_count=0,
            findings_summary="Skipped; no configuration changes within incident window.",
        ),
    ]

    minimal_report = UnifiedDiagnosticReport(
        incident_id="inc-fail-001",
        network_id="iitbbsr_argul_campus",
        status="diagnosed",
        probable_cause="Optical Transceiver Degradation",
        confidence=0.85,
        uncertainty=UncertaintyEvaluation(score=0.15, reasons=[], missing_evidence=[]),
    )

    report = DiagnosticReportBuilder.from_unified_report(
        minimal_report,
        agent_records=agent_records,
    )

    statuses = {a.agent_role: a.status for a in report.executive.agent_investigation_status}
    assert statuses["telemetry_agent"] == AgentState.COMPLETED
    assert statuses["wifi_services_agent"] == AgentState.FAILED
    assert statuses["config_agent"] == AgentState.SKIPPED


# 8. Site ID versus site name correctness
def test_site_id_versus_site_name_correctness(campus_topology: Dict[str, Any]):
    u_report = UnifiedDiagnosticReport(
        incident_id="inc-topo-001",
        network_id="iitbbsr_argul_campus",
        status="diagnosed",
        probable_cause="Link Congestion",
        confidence=0.90,
        affected_devices=["IITBBSR-CORE-RTR-01", "IITBBSR-DIST-SBS-01"],
        uncertainty=UncertaintyEvaluation(score=0.10, reasons=[], missing_evidence=[]),
    )

    report = DiagnosticReportBuilder.from_unified_report(u_report, campus_topology=campus_topology)
    topo = report.topology_reference
    assert topo is not None

    # Strict separation: site_ids must contain stable IDs, not names
    assert "site_admin" in topo.affected_site_ids
    assert "site_sbs" in topo.affected_site_ids
    assert "Administrative Building" not in topo.affected_site_ids, "site_ids must not contain human names"

    # Strict separation: site_names must contain human-readable names
    assert "Administrative Building" in topo.affected_site_names
    assert "School of Basic Sciences" in topo.affected_site_names
    assert "site_admin" not in topo.affected_site_names, "site_names must not contain machine IDs"

    # Executive report has both
    assert "site_admin" in report.executive.affected_site_ids
    assert "Administrative Building" in report.executive.affected_site_names


# 9. Invalid topology references handling
def test_invalid_topology_references_handling(campus_topology: Dict[str, Any]):
    u_report = UnifiedDiagnosticReport(
        incident_id="inc-unmapped-001",
        network_id="unknown_external_net",
        status="diagnosed",
        probable_cause="Device Hardware Overload",
        confidence=0.80,
        affected_devices=["UNKNOWN-ROUTER-999"],
        uncertainty=UncertaintyEvaluation(score=0.20, reasons=[], missing_evidence=[]),
    )

    # Building report with non-matching devices should not crash or hallucinate
    report = DiagnosticReportBuilder.from_unified_report(u_report, campus_topology=campus_topology)
    topo = report.topology_reference
    assert topo is not None
    assert topo.affected_node_ids == ["UNKNOWN-ROUTER-999"]
    assert topo.affected_site_ids == []
    assert topo.affected_site_names == []
    assert topo.affected_path_ids == []


# 10. Missing audit records truthfulness
def test_missing_audit_records_truthfulness():
    u_report = UnifiedDiagnosticReport(
        incident_id="inc-no-audit-999",
        network_id="test-net",
        status="insufficient_evidence",
        probable_cause=None,
        confidence=0.0,
        uncertainty=UncertaintyEvaluation(score=1.0, reasons=[], missing_evidence=[]),
    )

    report = DiagnosticReportBuilder.from_unified_report(u_report, audit_metadata=None)
    assert report.audit is not None
    # For a newly synthesized ID with no DB entries, audit_logged must be False
    assert report.audit.audit_logged is False
    assert "no persistent storage records" in report.audit.notes.lower()

    audit_sec = report.technical.get_section("audit_replay")
    assert audit_sec is not None
    assert audit_sec.is_available is False


# 11. Advisory remediation without executed commands
def test_advisory_remediation_without_executed_commands():
    action = RemediationCatalog.create_mtu_harmonization_action(
        device="IITBBSR-CORE-RTR-01", interface="et-0/0/1", target_mtu=9000
    )
    u_report = UnifiedDiagnosticReport(
        incident_id="inc-rem-001",
        network_id="iitbbsr_argul_campus",
        status="diagnosed",
        probable_cause="MTU Mismatch Blackhole",
        confidence=0.85,
        remediation_actions=[action],
        uncertainty=UncertaintyEvaluation(score=0.15, reasons=[], missing_evidence=[]),
    )

    report = DiagnosticReportBuilder.from_unified_report(u_report)
    assert len(report.executive.recommended_actions) == 1
    act = report.executive.recommended_actions[0]

    assert act.is_simulated is True
    assert act.is_advisory is True
    assert "no production network change has occurred" in act.advisory_notice.lower()
    assert act.status == RemediationState.APPROVED or act.status == RemediationState.PROPOSED


# 12. Pending recovery verification independence
def test_pending_recovery_verification_independence(sample_unified_report: UnifiedDiagnosticReport):
    # Diagnostic status is completed (diagnosed), but recovery is explicitly pending
    report = DiagnosticReportBuilder.from_unified_report(
        sample_unified_report,
        recovery_status=RecoveryStatus.PENDING_VERIFICATION,
    )
    assert report.executive.diagnostic_status == DiagnosticStatus.DIAGNOSED
    assert report.executive.recovery_verification_status == RecoveryStatus.PENDING_VERIFICATION

    # Diagnostic status is completed, but recovery failed
    report_failed = DiagnosticReportBuilder.from_unified_report(
        sample_unified_report,
        recovery_status=RecoveryStatus.NOT_RECOVERED,
    )
    assert report_failed.executive.diagnostic_status == DiagnosticStatus.DIAGNOSED
    assert report_failed.executive.recovery_verification_status == RecoveryStatus.NOT_RECOVERED


# 13. All 12 technical report sections integrity
def test_all_12_technical_report_sections_integrity(sample_unified_report: UnifiedDiagnosticReport):
    report = DiagnosticReportBuilder.from_unified_report(sample_unified_report)
    sections = report.technical.sections
    assert len(sections) == 12

    expected_section_ids = [
        "incident_context",
        "input_telemetry",
        "topology_and_paths",
        "anomaly_detection",
        "hypotheses_evaluation",
        "evidence_records",
        "specialist_findings",
        "arbitration",
        "confidence_calibration",
        "remediation_plan",
        "audit_replay",
        "recovery_limitations",
    ]

    actual_section_ids = [s.section_id for s in sections]
    assert actual_section_ids == expected_section_ids

    # Validate ordering
    for idx, sec in enumerate(sections):
        assert sec.order == idx + 1
        assert isinstance(sec.is_available, bool)
        assert sec.data is not None


# 14. Partial and degraded report serialization
def test_partial_and_degraded_report_serialization():
    minimal_report = UnifiedDiagnosticReport(
        incident_id="inc-degraded-999",
        network_id="unreachable-network",
        status="inconclusive",
        probable_cause=None,
        confidence=0.0,
        evidence=[],
        uncertainty=UncertaintyEvaluation(score=1.0, reasons=["Complete telemetry timeout."], missing_evidence=[]),
    )

    report = DiagnosticReportBuilder.from_unified_report(minimal_report)
    json_str = report.to_json()
    assert json_str is not None

    md_str = report.to_markdown()
    assert "# Network Diagnostic Report: inc-degraded-999" in md_str
    assert "Level 1: Executive Summary" in md_str
    assert "Level 2: Technical Diagnostic Details" in md_str

    parsed = NetworkDiagnosticReport.model_validate_json(json_str)
    assert parsed.incident_id == "inc-degraded-999"
    assert parsed.executive.diagnostic_status == DiagnosticStatus.INSUFFICIENT_EVIDENCE


# 15. JSON Schema and Pydantic model consistency
def test_json_schema_and_pydantic_consistency(
    sample_unified_report: UnifiedDiagnosticReport,
    campus_topology: Dict[str, Any],
    report_schema: Dict[str, Any],
):
    report = DiagnosticReportBuilder.from_unified_report(
        sample_unified_report,
        campus_topology=campus_topology,
        audit_metadata={
            "audit_logged": True,
            "storage_engine": "sqlite",
            "incident_record_id": "inc-test-001",
            "envelope_count": 5,
        },
    )

    dumped = json.loads(report.to_json())
    jsonschema.validate(instance=dumped, schema=report_schema)

    # Fixture consistency check
    assert FIXTURE_PATH.is_file()
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixture_json = json.load(f)
    jsonschema.validate(instance=fixture_json, schema=report_schema)
