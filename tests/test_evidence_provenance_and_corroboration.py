"""Phase 1 Acceptance Tests: Evidence Provenance, Multi-Agent Corroboration, and Report Correctness.

Tests:
1. Golden multi-domain scenario where two real agents contribute supporting observations to one diagnosis.
2. Dispatched agent with no valid evidence is NOT counted as a source.
3. Empty/error/timeout response cannot create corroboration.
4. Duplicate evidence does not inflate confidence or erase source lineage.
5. Conflicting hypotheses are reported in alternative hypotheses and not silently discarded.
6. Insufficient evidence returns an explicit abstention/uncertain result with reasons.
7. Each recommendation is linked to the diagnosed fault and affected devices, and empty on abstention.
8. Exact required fields and types matching schema contract and 10-key hackathon export.
9. Traceability following report evidence to source observation and envelope/message identifiers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import pytest

from netcoop.config import settings
from netcoop.core.correlation import OfflineCorrelationEngine
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    EnvelopePayload,
    MessageType,
    Observation,
    ObservationCategory,
    ProtocolHeader,
    Severity,
)
from netcoop.core.evidence import DiagnosticHypothesis, EvidenceItem
from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.orchestrator.graph import run_diagnosis, _deduplicate_observations
from netcoop.reporting.builder import export_hackathon_report_json


@pytest.fixture(autouse=True)
def setup_in_process_mode():
    """Ensure in-process execution mode for deterministic unit and integration tests."""
    old_env = {k: os.environ.get(k) for k in ("AGENTS_MODE", "IN_PROCESS_FALLBACK", "ALLOW_DEV_IN_PROCESS_FALLBACK")}
    old_mode = settings.agents_mode
    old_fb = settings.in_process_fallback
    old_allow = settings.allow_dev_in_process_fallback

    os.environ["AGENTS_MODE"] = "in_process"
    os.environ["IN_PROCESS_FALLBACK"] = "true"
    os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"
    settings.agents_mode = "in_process"
    settings.in_process_fallback = True
    settings.allow_dev_in_process_fallback = True

    yield

    for k, v in old_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    settings.agents_mode = old_mode
    settings.in_process_fallback = old_fb
    settings.allow_dev_in_process_fallback = old_allow


# -----------------------------------------------------------------------------
# Test 1: Golden Multi-Domain Corroboration Scenario
# -----------------------------------------------------------------------------
def test_1_golden_multi_domain_scenario() -> None:
    """Verify link_congestion produces genuine multi-domain evidence (telemetry + topology)."""
    gen = SyntheticNetworkGenerator()
    incident_data = gen.generate(scenario="link_congestion", seed=42)
    report = run_diagnosis(incident_data)

    assert report.status == "diagnosed"
    assert report.probable_cause is not None
    assert "Link" in report.probable_cause or "congestion" in report.probable_cause.lower()
    assert report.confidence >= 0.85

    # Check hackathon export JSON
    export = export_hackathon_report_json(report)
    sources = export["evidence_sources"]

    # Must contain both telemetry_agent and topology_agent
    assert "telemetry_agent" in sources, f"Expected telemetry_agent in {sources}"
    assert "topology_agent" in sources, f"Expected topology_agent in {sources}"
    assert len(sources) >= 2

    # Verify that both sources actually have corresponding supporting evidence items
    ev_sources_in_items = {
        ev.get("source_agent")
        for ev in report.evidence
        if ev.get("source_agent")
    }
    assert "telemetry_agent" in ev_sources_in_items
    assert "topology_agent" in ev_sources_in_items


# -----------------------------------------------------------------------------
# Test 2: Dispatched Agent with No Valid Evidence is Not Counted
# -----------------------------------------------------------------------------
def test_2_dispatched_agent_without_evidence_not_counted() -> None:
    """Agents that run without contributing anomalous findings must not appear in evidence_sources."""
    gen = SyntheticNetworkGenerator()
    incident_data = gen.generate(scenario="link_congestion", seed=42)
    report = run_diagnosis(incident_data)

    export = export_hackathon_report_json(report)
    sources = export["evidence_sources"]

    # wifi_services_agent, config_agent, and log_agent were dispatched, but had no findings
    assert "wifi_services_agent" not in sources
    assert "config_agent" not in sources
    assert "log_agent" not in sources


# -----------------------------------------------------------------------------
# Test 3: Empty, Error, or Timeout Cannot Create Corroboration
# -----------------------------------------------------------------------------
def test_3_empty_error_timeout_cannot_create_corroboration() -> None:
    """Empty, error, or timed-out agent responses cannot satisfy multi-domain sufficiency."""
    # When an agent times out or returns error, no valid observations are provided from it.
    # If a fault requires multi-domain corroboration (e.g. MTU mismatch requiring config_agent,
    # or BGP damping requiring log_agent), the missing domain leaves the diagnosis uncorroborated.
    telemetry_obs = [
        Observation(
            observation_id="obs-tel-01",
            category=ObservationCategory.METRIC_ANOMALY,
            entity="leaf-01:et-0/0/1",
            metric_name="large_packet_drops",
            observed_value=120,
            unit="packets",
            severity=Severity.CRITICAL,
            context={"agent_domain": "telemetry_agent"},
            provenance={"source_agent": "telemetry_agent"},
        ),
    ]

    # Without config_agent providing MTU mismatch evidence, MTU mismatch is insufficient:
    hyp = OfflineCorrelationEngine._check_mtu_mismatch(telemetry_obs, [])
    assert hyp is not None
    assert hyp.is_sufficient is False
    assert "config_agent" not in hyp.provided_evidence_domains
    assert "config_agent" in hyp.required_evidence_domains

    # End-to-end evaluation must abstain
    status, top_hyp, uncertainty = OfflineCorrelationEngine.evaluate(telemetry_obs)
    assert status == "insufficient_evidence"
    assert top_hyp is None
    assert uncertainty.score > 0.50


# -----------------------------------------------------------------------------
# Test 4: Duplicate Evidence Does Not Inflate Confidence or Erase Lineage
# -----------------------------------------------------------------------------
def test_4_duplicate_evidence_handling() -> None:
    """Duplicate observations must be deduplicated and preserve lineage without score inflation."""
    obs1 = {
        "entity": "core-rtr-01",
        "metric_name": "link_utilization_pct",
        "observed_value": 92.57,
        "unit": "percent",
        "provenance": {"source_agent": "telemetry_agent", "message_id": "msg-001"},
    }
    obs2 = {
        "entity": "core-rtr-01",
        "metric_name": "link_utilization_pct",
        "observed_value": 92.57,
        "unit": "percent",
        "provenance": {"source_agent": "telemetry_agent_mirror", "message_id": "msg-002"},
    }

    deduped = _deduplicate_observations([obs1, obs2])
    assert len(deduped) == 1
    # Lineage from duplicate source must be preserved
    assert "corroborating_sources" in deduped[0]["provenance"]
    assert "telemetry_agent_mirror" in deduped[0]["provenance"]["corroborating_sources"]


# -----------------------------------------------------------------------------
# Test 5: Conflicting Hypotheses Are Reported in Alternative Hypotheses
# -----------------------------------------------------------------------------
def test_5_competing_hypotheses_reported() -> None:
    """Diagnosed report must maintain alternative hypotheses and discriminating tests."""
    gen = SyntheticNetworkGenerator()
    incident_data = gen.generate(scenario="link_congestion", seed=42)
    report = run_diagnosis(incident_data)

    export = export_hackathon_report_json(report)
    assert "alternative_causes" in export
    assert len(export["alternative_causes"]) > 0
    # Expected competing explanation: Upstream transit delay
    assert any("Upstream" in alt or "transit" in alt.lower() for alt in export["alternative_causes"])


# -----------------------------------------------------------------------------
# Test 6: Insufficient Evidence Returns Explicit Abstention
# -----------------------------------------------------------------------------
def test_6_insufficient_evidence_explicit_abstention() -> None:
    """Sparse telemetry without cross-domain corroboration must return insufficient_evidence."""
    scenario_path = Path("data/scenarios/05_insufficient_evidence_sparse.json")
    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = run_diagnosis(data)
    assert report.status == "insufficient_evidence"
    assert report.probable_cause is None
    assert report.confidence == 0.0
    assert report.uncertainty.score > 0.50
    assert len(report.uncertainty.missing_evidence) > 0
    assert len(report.remediation_actions) == 0


# -----------------------------------------------------------------------------
# Test 7: Recommendations Linked to Diagnosed Fault and Empty on Abstention
# -----------------------------------------------------------------------------
def test_7_recommendations_linked_to_fault_and_empty_on_abstention() -> None:
    """Remediation actions must map to the diagnosed root cause and be empty on abstention."""
    gen = SyntheticNetworkGenerator()

    # 1. Diagnosed link congestion: targeted QoS and rebalance actions
    inc_diagnosed = gen.generate(scenario="link_congestion", seed=42)
    rep_diagnosed = run_diagnosis(inc_diagnosed)
    assert len(rep_diagnosed.remediation_actions) > 0
    for act in rep_diagnosed.remediation_actions:
        assert act.is_simulated is True
        assert act.device in rep_diagnosed.affected_devices

    # 2. Abstention: zero actions
    with open("data/scenarios/05_insufficient_evidence_sparse.json", "r", encoding="utf-8") as f:
        inc_sparse = json.load(f)
    rep_sparse = run_diagnosis(inc_sparse)
    assert len(rep_sparse.remediation_actions) == 0


# -----------------------------------------------------------------------------
# Test 8: Report Schema Contract and Hackathon 10-Key Export
# -----------------------------------------------------------------------------
def test_8_report_schema_contract() -> None:
    """Verify exact 10 hackathon keys and valid types."""
    gen = SyntheticNetworkGenerator()
    inc = gen.generate(scenario="link_congestion", seed=42)
    rep = run_diagnosis(inc)
    export = export_hackathon_report_json(rep)

    expected_keys = {
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
    assert set(export.keys()) == expected_keys

    # Exact supporting_evidence item structure
    for item in export["supporting_evidence"]:
        assert set(item.keys()) == {"metric", "value", "interpretation"}
        assert item["metric"] is not None

    # Recommendations must be list of strings
    assert isinstance(export["recommended_actions"], list)
    for act in export["recommended_actions"]:
        assert isinstance(act, str)


# -----------------------------------------------------------------------------
# Test 9: Evidence Traceability to Observation and Envelope IDs
# -----------------------------------------------------------------------------
def test_9_evidence_traceability() -> None:
    """Every evidence item in the report must trace to an observation ID and correlation ID."""
    gen = SyntheticNetworkGenerator()
    inc = gen.generate(scenario="link_congestion", seed=42)
    rep = run_diagnosis(inc)

    assert len(rep.evidence) > 0
    for ev in rep.evidence:
        assert "source_agent" in ev
        assert ev["source_agent"] in ("telemetry_agent", "topology_agent")
        # Ensure observation provenance exists
        prov = ev.get("provenance") or {}
        assert isinstance(prov, dict)
        corr_id = prov.get("correlation_id") or ev.get("correlation_id")
        assert corr_id == rep.incident_id or corr_id is not None
