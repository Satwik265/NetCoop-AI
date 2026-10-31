"""End-to-end integration tests executing the 5 benchmark scenarios."""

import json
from pathlib import Path
import pytest

from netcoop.orchestrator.graph import run_diagnosis
from netcoop.storage.db import get_envelope_logs, get_incident

SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


def load_scenario(filename: str) -> dict:
    """Load scenario JSON file."""
    path = SCENARIOS_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_scenario_1_mtu_mismatch_blackhole() -> None:
    """Verify diagnosis of MTU mismatch with jumbo frame packet drops."""
    data = load_scenario("01_mtu_mismatch_blackhole.json")
    report = run_diagnosis(data)

    assert report.status == "diagnosed"
    assert report.confidence >= 0.85
    assert report.probable_cause is not None
    assert "MTU" in report.probable_cause
    assert len(report.remediation_actions) > 0
    assert report.remediation_actions[0].is_simulated is True

    # Verify persistent state and envelope logs
    incident = get_incident(data["incident_id"])
    assert incident is not None
    assert incident.status == "diagnosed"

    logs = get_envelope_logs(data["incident_id"])
    assert len(logs) >= 5  # At least 4 agent dispatches + response envelopes


def test_scenario_2_bgp_route_flap_damping() -> None:
    """Verify diagnosis of BGP route flap damping from carrier transitions."""
    data = load_scenario("02_bgp_route_flap_damping.json")
    report = run_diagnosis(data)

    assert report.status == "diagnosed"
    assert report.confidence >= 0.85
    assert report.probable_cause is not None
    assert "BGP" in report.probable_cause or "Flap" in report.probable_cause


def test_scenario_3_optical_crc_degradation() -> None:
    """Verify diagnosis of physical layer optical attenuation and CRC errors."""
    data = load_scenario("03_optical_crc_degradation.json")
    report = run_diagnosis(data)

    assert report.status == "diagnosed"
    assert report.confidence >= 0.85
    assert report.probable_cause is not None
    assert "Optical" in report.probable_cause or "Signal" in report.probable_cause


def test_scenario_4_stp_split_brain_loop() -> None:
    """Verify diagnosis of Spanning Tree loop from BPDU filter configuration."""
    data = load_scenario("04_stp_split_brain_loop.json")
    report = run_diagnosis(data)

    assert report.status == "diagnosed"
    assert report.confidence >= 0.85
    assert report.probable_cause is not None
    assert "Spanning Tree" in report.probable_cause or "Loop" in report.probable_cause


def test_scenario_5_insufficient_evidence_sparse() -> None:
    """Verify hard rule: sparse telemetry MUST return insufficient_evidence."""
    data = load_scenario("05_insufficient_evidence_sparse.json")
    report = run_diagnosis(data)

    assert report.status == "insufficient_evidence"
    assert report.probable_cause is None
    assert report.confidence == 0.0
    assert report.uncertainty.score > 0.50
    assert len(report.uncertainty.missing_evidence) > 0
    assert len(report.remediation_actions) == 0

