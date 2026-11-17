"""Comprehensive Phase 4 test suite for UnifiedDiagnosticReport contract, operator explainability, and PS compliance.

Tests:
1. Valid diagnosed report.
2. Normal/benign report.
3. Insufficient-evidence report.
4. Input validation failure.
5. Missing affected devices / topology.
6. Multiple evidence sources with provenance.
7. No recommendations justified.
8. Alternative hypotheses and conflicts.
9. Backward compatibility and version migration.
10. JSON serialization and exact required field/type contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import jsonschema
import pytest

from netcoop.core.evidence import DiagnosticHypothesis, EvidenceItem, UncertaintyEvaluation
from netcoop.core.report import (
    DiagnosticReportStatus,
    RemediationActionItem,
    ReportBuilder,
    UnifiedDiagnosticReport,
)
from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.reporting.builder import export_hackathon_report_json

SCHEMA_PATH = Path("schemas/diagnostic_report.json")


@pytest.fixture(scope="module")
def report_schema() -> Dict[str, Any]:
    assert SCHEMA_PATH.is_file(), f"Report schema missing at {SCHEMA_PATH}"
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------------------------------------------------------
# 1. Valid Diagnosed Report
# -----------------------------------------------------------------------------

def test_valid_diagnosed_report(report_schema: Dict[str, Any]) -> None:
    """Verify a complete, valid diagnosed report satisfies JSON schema, Hackathon PS contract, and Markdown consistency."""
    gen = SyntheticNetworkGenerator()
    inc = gen.generate(scenario="link_congestion", seed=101)
    report = run_diagnosis(inc)

    # 1. Report Status and Attributes
    assert report.status == "diagnosed"
    assert report.probable_cause is not None
    assert report.confidence > 0.70
    assert len(report.affected_devices) > 0
    assert len(report.evidence) > 0
    assert len(report.remediation_actions) > 0
    assert len(report.evidence_sources) > 0

    # 2. JSON Schema Validation
    rep_json = json.loads(report.to_json())
    jsonschema.validate(instance=rep_json, schema=report_schema)

    # 3. Hackathon 10-Key Export Contract
    h_export = export_hackathon_report_json(report)
    expected_10_keys = {
        "incident_id",
        "status",
        "suspected_root_cause",
        "confidence",
        "affected_devices",
        "supporting_evidence",
        "alternative_causes",
        "recommended_actions",
        "evidence_sources",
        "limitations",
    }
    assert set(h_export.keys()) == expected_10_keys
    assert h_export["status"] == "diagnosed"
    assert h_export["suspected_root_cause"] == report.probable_cause
    assert h_export["confidence"] == report.confidence
    assert len(h_export["supporting_evidence"]) == len(report.evidence)
    assert len(h_export["recommended_actions"]) > 0

    # 4. Markdown Consistency
    md = report.to_markdown()
    assert report.incident_id in md
    assert report.network_id in md
    assert "DIAGNOSED" in md
    assert report.probable_cause in md
    for dev in report.affected_devices:
        assert dev in md
    assert "## 9. Simulated Remediation Plan" in md
    assert "Safety Guarantee: Remediation actions are advisory and simulated only" in md


# -----------------------------------------------------------------------------
# 2. Normal / Benign Report
# -----------------------------------------------------------------------------

def test_normal_benign_report(report_schema: Dict[str, Any]) -> None:
    """Verify healthy fabric evaluation emits benign status, zero remediation actions, and valid schema."""
    gen = SyntheticNetworkGenerator()
    inc = gen.generate(scenario="normal_operation", seed=102)
    report = run_diagnosis(inc)

    assert report.status == "benign"
    assert report.probable_cause in ("Normal Operation", "Normal Operation (No Fault Detected)")
    assert report.confidence >= 0.0

    # No remediation actions should ever be recommended for healthy networks
    assert len(report.remediation_actions) == 0

    # JSON Schema Validation
    rep_json = json.loads(report.to_json())
    jsonschema.validate(instance=rep_json, schema=report_schema)

    # Hackathon 10-Key Export Contract
    h_export = export_hackathon_report_json(report)
    assert h_export["status"] == "benign"
    assert len(h_export["recommended_actions"]) == 0

    # Markdown Consistency: explicitly states no remediation actions justified
    md = report.to_markdown()
    assert "BENIGN" in md
    assert "No justified remediation actions" in md
    assert "Remediation is withheld because the incident is either benign" in md


# -----------------------------------------------------------------------------
# 3. Insufficient Evidence Report
# -----------------------------------------------------------------------------

def test_insufficient_evidence_report(report_schema: Dict[str, Any]) -> None:
    """Verify uncorroborated or sparse telemetry triggers disciplined abstention with zero confidence and no remediation."""
    with open("data/scenarios/05_insufficient_evidence_sparse.json", "r", encoding="utf-8") as f:
        inc = json.load(f)
    report = run_diagnosis(inc)

    assert report.status == "insufficient_evidence"
    assert report.probable_cause is None
    assert report.confidence == 0.0
    assert report.uncertainty.score == 1.0
    assert len(report.remediation_actions) == 0
    assert len(report.uncertainty.missing_evidence) > 0

    # JSON Schema Validation
    rep_json = json.loads(report.to_json())
    jsonschema.validate(instance=rep_json, schema=report_schema)

    # Hackathon 10-Key Export Contract
    h_export = export_hackathon_report_json(report)
    assert h_export["status"] == "insufficient_evidence"
    assert h_export["suspected_root_cause"] is None
    assert h_export["confidence"] == 0.0
    assert len(h_export["recommended_actions"]) == 0

    # Markdown Consistency
    md = report.to_markdown()
    assert "INSUFFICIENT_EVIDENCE" in md
    assert "None (Insufficient evidence to isolate root cause)" in md
    assert "No justified remediation actions" in md


# -----------------------------------------------------------------------------
# 4. Input Validation Failure Report
# -----------------------------------------------------------------------------

def test_input_validation_failure_report(report_schema: Dict[str, Any]) -> None:
    """Verify input validation failures produce a structured 'invalid' report without conflating processing errors with uncertainty."""
    errs = [
        "ERR_MISSING_REQUIRED_FIELD: incident_id missing",
        "ERR_MALFORMED_JSON: unclosed quote at byte 42",
        "ERR_UNKNOWN_UNIT: 'flurbo' is not a recognized telemetry unit",
    ]
    report = ReportBuilder.build_invalid_report(
        incident_id="inc-invalid-400",
        network_id="unknown-fabric",
        errors=errs,
        limitations=["Input payload failed validation gate 2"],
    )

    assert report.status == "invalid"
    assert report.probable_cause is None
    assert report.confidence == 0.0
    assert report.uncertainty.score == 1.0
    assert len(report.remediation_actions) == 0
    assert any("ERR_MISSING_REQUIRED_FIELD" in lim for lim in report.limitations)
    assert any("ERR_MALFORMED_JSON" in lim for lim in report.limitations)

    # JSON Schema Validation
    rep_json = json.loads(report.to_json())
    jsonschema.validate(instance=rep_json, schema=report_schema)

    # Hackathon 10-Key Export Contract
    h_export = export_hackathon_report_json(report)
    assert h_export["status"] == "invalid"
    assert h_export["suspected_root_cause"] is None
    assert h_export["confidence"] == 0.0
    assert len(h_export["recommended_actions"]) == 0
    assert len(h_export["limitations"]) >= 3

    # Markdown Consistency
    md = report.to_markdown()
    assert "INVALID" in md
    assert "None (Input validation failure)" in md
    assert "No justified remediation actions" in md


# -----------------------------------------------------------------------------
# 5. Missing Affected Devices / Topology
# -----------------------------------------------------------------------------

def test_missing_affected_devices_and_topology(report_schema: Dict[str, Any]) -> None:
    """Verify that reports missing device or topology references render cleanly without crashing or displaying ambiguous empty strings."""
    report = ReportBuilder.build_report(
        incident_id="inc-no-topo-001",
        network_id="unmapped-fabric",
        status="insufficient_evidence",
        hypothesis=None,
        uncertainty=UncertaintyEvaluation(
            score=1.0,
            reasons=["Topology graph unavailable for path tracing"],
            missing_evidence=["topology_service_peering_graph"],
        ),
        remediation_actions=[],
        limitations=["topology unavailable; upstream transit inference uncorroborated"],
    )

    assert report.affected_devices == []
    assert report.affected_interfaces == []

    # JSON Schema Validation
    rep_json = json.loads(report.to_json())
    jsonschema.validate(instance=rep_json, schema=report_schema)

    # Markdown Consistency: displays explicit "None identified (or unknown)"
    md = report.to_markdown()
    assert "- **Affected Devices**: None identified (or unknown)" in md
    assert "- **Affected Interfaces**: None identified (or unknown)" in md
    assert "topology unavailable; upstream transit inference uncorroborated" in md


# -----------------------------------------------------------------------------
# 6. Multiple Evidence Sources with Provenance
# -----------------------------------------------------------------------------

def test_multiple_evidence_sources_with_provenance(report_schema: Dict[str, Any]) -> None:
    """Verify evidence items preserve stable IDs, domain agent attribution, observations, timestamps, and provenance."""
    ev_items = [
        EvidenceItem(
            source_agent="telemetry_agent",
            category="metric_anomaly",
            finding="Link utilization 98.2% exceeds threshold",
            entity="core-rtr-01:HundredGigE0/0/0/1",
            metric_name="link_utilization_pct",
            value=98.2,
            unit="percent",
            severity="critical",
            timestamp="2026-11-15T02:00:00Z",
            observation_id="obs-tel-001",
            provenance={"collector": "snmp_interface_poller"},
        ),
        EvidenceItem(
            source_agent="log_agent",
            category="syslog_alert",
            finding="LINK-3-UPDOWN syslog event flaps 14 times",
            entity="core-rtr-01:HundredGigE0/0/0/1",
            metric_name="flap_count",
            value=14,
            unit="count",
            severity="warning",
            timestamp="2026-11-15T02:00:05Z",
            observation_id="obs-log-002",
            provenance={"facility": "LINEPROTO", "severity": 3},
        ),
        EvidenceItem(
            source_agent="config_agent",
            category="config_diff",
            finding="MTU mismatch configured: expected 9216, found 1500",
            entity="core-rtr-01:HundredGigE0/0/0/1",
            metric_name="configured_mtu",
            value=1500,
            unit="bytes",
            severity="critical",
            timestamp="2026-11-15T01:58:00Z",
            observation_id="obs-cfg-003",
            provenance={"commit_hash": "a1b2c3d4", "author": "admin"},
        ),
    ]

    hyp = DiagnosticHypothesis(
        cause_key="MTU_MISMATCH_BLACKHOLE",
        title="MTU Mismatch Blackhole",
        description="MTU discrepancy causing jumbo packet drops",
        affected_devices=["core-rtr-01"],
        affected_interfaces=["HundredGigE0/0/0/1"],
        supporting_evidence=ev_items,
        raw_score=0.92,
        final_confidence=0.92,
        is_sufficient=True,
    )

    action = RemediationActionItem(
        action_id="act-mtu-fix-01",
        title="Normalize Interface MTU to 9216",
        description="Set MTU to 9216 on core-rtr-01 HundredGigE0/0/0/1",
        device="core-rtr-01",
        commands=["set interfaces HundredGigE0/0/0/1 mtu 9216"],
        rollback_commands=["set interfaces HundredGigE0/0/0/1 mtu 1500"],
        risk_level="low",
    )

    report = ReportBuilder.build_report(
        incident_id="inc-multi-domain-001",
        network_id="campus-core",
        status="diagnosed",
        hypothesis=hyp,
        uncertainty=UncertaintyEvaluation(score=0.08, reasons=[], missing_evidence=[]),
        remediation_actions=[action],
    )

    # 1. Evidence Sources Derived
    assert set(report.evidence_sources) == {"telemetry_agent", "log_agent", "config_agent"}

    # 2. Stable Evidence Identifiers and Metric Aliases
    assert len(report.evidence) == 3
    for ev in report.evidence:
        assert ev["evidence_id"].startswith("evi-")
        assert ev["metric"] == ev["metric_name"]
        assert ev["interpretation"] == ev["finding"]
        assert ev["observation_id"] is not None

    # 3. JSON Schema Validation
    rep_json = json.loads(report.to_json())
    jsonschema.validate(instance=rep_json, schema=report_schema)

    # 4. Hackathon 10-Key Export Contract
    h_export = export_hackathon_report_json(report)
    assert set(h_export["evidence_sources"]) == {"config_agent", "log_agent", "telemetry_agent"}
    for item in h_export["supporting_evidence"]:
        assert set(item.keys()) == {"metric", "value", "interpretation"}

    # 5. Markdown Consistency
    md = report.to_markdown()
    assert "telemetry_agent, log_agent, config_agent" in md or "config_agent" in md
    assert "`evi-obs-tel-001`" in md
    assert "`obs-cfg-003`" in md


# -----------------------------------------------------------------------------
# 7. No Recommendations Justified
# -----------------------------------------------------------------------------

def test_no_recommendations_justified() -> None:
    """Verify that when an incident is benign or insufficient evidence, no remediation actions are output, and the report explains why."""
    report = ReportBuilder.build_report(
        incident_id="inc-no-remed-001",
        network_id="lab-fabric",
        status="insufficient_evidence",
        hypothesis=None,
        uncertainty=UncertaintyEvaluation(
            score=1.0,
            reasons=["Uncorroborated single-point metric drop"],
            missing_evidence=["syslog_records"],
        ),
        remediation_actions=[],
    )

    assert len(report.remediation_actions) == 0

    h_export = export_hackathon_report_json(report)
    assert h_export["recommended_actions"] == []

    md = report.to_markdown()
    assert "No justified remediation actions." in md
    assert "Remediation is withheld because the incident is either benign" in md


# -----------------------------------------------------------------------------
# 8. Alternative Hypotheses and Conflicts
# -----------------------------------------------------------------------------

def test_alternative_hypotheses_and_conflicts(report_schema: Dict[str, Any]) -> None:
    """Verify competing hypotheses, discriminating tests, and conflict arbitration records are accurately captured."""
    alt_hyps = [
        {
            "cause": "Upstream Transit Congestion",
            "confidence": 0.58,
            "discriminating_test": "Query transit router egress queues",
            "supporting_evidence_ids": ["evi-tel-001"],
            "refuting_evidence_ids": [],
        },
        {
            "cause": "Interface Hardware Attenuation",
            "confidence": 0.32,
            "discriminating_test": "Inspect optical transceiver DOM Rx/Tx power levels",
            "supporting_evidence_ids": [],
            "refuting_evidence_ids": ["evi-dom-002"],
        },
    ]

    conflicts = [
        {
            "iteration": 1,
            "competing_agents": ["telemetry_agent", "wifi_services_agent"],
            "rationale": "Resolved in favor of physical layer queue drops over RF channel utilization per domain precedence hierarchy.",
        }
    ]

    report = ReportBuilder.build_report(
        incident_id="inc-alt-001",
        network_id="core-transit",
        status="diagnosed",
        hypothesis=DiagnosticHypothesis(
            cause_key="LINK_CONGESTION",
            title="Link Congestion",
            description="Core egress link saturated",
            affected_devices=["core-rtr-01"],
            raw_score=0.88,
            final_confidence=0.88,
            is_sufficient=True,
        ),
        uncertainty=UncertaintyEvaluation(
            score=0.12,
            reasons=[],
            missing_evidence=[],
            alternative_hypotheses=alt_hyps,
        ),
        conflicts_resolved=conflicts,
    )

    # 1. Alternative Hypotheses & Conflict Attributes
    assert len(report.uncertainty.alternative_hypotheses) == 2
    assert report.conflicts_resolved[0]["iteration"] == 1

    # 2. JSON Schema Validation
    rep_json = json.loads(report.to_json())
    jsonschema.validate(instance=rep_json, schema=report_schema)

    # 3. Hackathon 10-Key Export Contract
    h_export = export_hackathon_report_json(report)
    assert set(h_export["alternative_causes"]) == {"Upstream Transit Congestion", "Interface Hardware Attenuation"}

    # 4. Markdown Consistency
    md = report.to_markdown()
    assert "Upstream Transit Congestion" in md
    assert "Query transit router egress queues" in md
    assert "Resolved in favor of physical layer queue drops" in md


# -----------------------------------------------------------------------------
# 9. Backward Compatibility and Version Migration
# -----------------------------------------------------------------------------

def test_backward_compatibility_and_version_migration(report_schema: Dict[str, Any]) -> None:
    """Verify that a legacy report payload missing Phase 4 fields deserializes cleanly and populates defaults without errors."""
    legacy_json_dict = {
        "incident_id": "legacy-inc-20261031-01",
        "network_id": "campus-old",
        "timestamp_utc": "2026-10-31T12:00:00Z",
        "status": "diagnosed",
        "probable_cause": "Weak Wifi Signal",
        "confidence": 0.85,
        "affected_devices": ["ap-west-01"],
        "affected_interfaces": ["wlan0"],
        "evidence": [
            {
                "source_agent": "wifi_services_agent",
                "category": "rf_anomaly",
                "finding": "ap-west-01 rssi: observed -84.0 dBm",
                "entity": "ap-west-01:wlan0",
                "metric_name": "rssi_dbm",
                "value": -84.0,
                "unit": "dbm",
                "severity": "critical",
                "timestamp": "2026-10-31T12:00:00Z",
            }
        ],
        "uncertainty": {
            "score": 0.15,
            "reasons": [],
            "missing_evidence": [],
            "alternative_hypotheses": [],
        },
        "remediation_actions": [
            {
                "action_id": "act-wifi-01",
                "title": "Increase Transmit Power",
                "description": "Increase Tx power to 20 dBm",
                "device": "ap-west-01",
                "commands": ["set wlan0 txpower 20"],
                "rollback_commands": ["set wlan0 txpower 14"],
                "risk_level": "low",
                "blast_radius_devices": ["ap-west-01"],
                "is_simulated": True,
                "status": "recommended",
            }
        ],
        "summary": "Diagnosed Weak Wifi Signal with 85% confidence.",
        "processing_time_ms": 94.2,
    }

    # Deserializing legacy payload
    report = UnifiedDiagnosticReport(**legacy_json_dict)

    # Assert automatically migrated/derived Phase 4 fields
    assert report.suspected_root_cause == "Weak Wifi Signal"
    assert report.evidence_sources == ["wifi_services_agent"]
    assert report.is_confidence_calibrated is False
    assert report.confidence_type == "uncalibrated_heuristic"

    # JSON Schema Validation
    rep_json = json.loads(report.to_json())
    jsonschema.validate(instance=rep_json, schema=report_schema)

    # Hackathon 10-Key Export Contract
    h_export = export_hackathon_report_json(report)
    assert h_export["suspected_root_cause"] == "Weak Wifi Signal"
    assert h_export["evidence_sources"] == ["wifi_services_agent"]


# -----------------------------------------------------------------------------
# 10. JSON Serialization and Exact Field/Type Contract
# -----------------------------------------------------------------------------

def test_json_serialization_and_exact_field_type_contract(report_schema: Dict[str, Any]) -> None:
    """Verify exact JSON field presence, typing, null-value rendering as 'unknown', and zero string fabrication."""
    # Evidence with None / unknown value
    ev_unknown = EvidenceItem(
        source_agent="topology_agent",
        category="topology_anomaly",
        finding="BGP peering state indeterminate due to lost keepalive",
        entity="dist-sw-01:bgp",
        metric_name="bgp_state",
        value=None,  # Missing metric value
        unit=None,
        severity="warning",
        timestamp="2026-11-15T02:00:00Z",
    )

    report = ReportBuilder.build_report(
        incident_id="inc-type-check-001",
        network_id="datacenter-spine",
        status="insufficient_evidence",
        hypothesis=None,
        uncertainty=UncertaintyEvaluation(
            score=1.0,
            reasons=["BGP session state unknown"],
            missing_evidence=["bgp_keepalive_telemetry"],
        ),
        remediation_actions=[],
    )
    # Manually append unknown-value evidence
    report.evidence.append(ev_unknown.model_dump())

    # 1. JSON Schema Validation
    rep_json = json.loads(report.to_json())
    jsonschema.validate(instance=rep_json, schema=report_schema)

    # 2. Strict Type Contract on Hackathon 10 Keys
    h_export = export_hackathon_report_json(report)
    assert isinstance(h_export["incident_id"], str)
    assert isinstance(h_export["status"], str)
    assert h_export["suspected_root_cause"] is None or isinstance(h_export["suspected_root_cause"], str)
    assert isinstance(h_export["confidence"], (float, int))
    assert isinstance(h_export["affected_devices"], list)
    assert isinstance(h_export["supporting_evidence"], list)
    assert isinstance(h_export["alternative_causes"], list)
    assert isinstance(h_export["recommended_actions"], list)
    assert isinstance(h_export["evidence_sources"], list)
    assert isinstance(h_export["limitations"], list)

    # 3. Value check: None preserved as None in JSON, NOT converted to 0
    unknown_item = h_export["supporting_evidence"][0]
    assert unknown_item["value"] is None

    # 4. Markdown check: renders "unknown", not "0" or "None None"
    md = report.to_markdown()
    assert "unknown" in md
    assert "None None" not in md
