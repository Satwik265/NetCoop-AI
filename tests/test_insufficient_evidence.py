"""Dedicated tests verifying strict compliance with the insufficient_evidence rule."""

from netcoop.orchestrator.graph import run_diagnosis


def test_empty_incident_returns_insufficient_evidence() -> None:
    """Verify that an incident with empty telemetry and logs returns insufficient_evidence."""
    empty_data = {
        "incident_id": "inc-empty-test",
        "network_id": "test-net",
        "topology": {"nodes": [], "links": []},
        "telemetry": [],
        "configurations": [],
        "logs": [],
    }
    report = run_diagnosis(empty_data)

    assert report.status == "insufficient_evidence"
    assert report.probable_cause is None
    assert report.confidence == 0.0
    assert report.uncertainty.score == 1.0
    assert len(report.remediation_actions) == 0


def test_isolated_single_counter_anomaly_refuses_to_guess() -> None:
    """Verify that a single isolated counter spike without corroboration returns insufficient_evidence."""
    data = {
        "incident_id": "inc-single-spike",
        "network_id": "isolated-net",
        "topology": {"nodes": [{"id": "sw-9", "role": "switch"}], "links": []},
        "telemetry": [
            {
                "device": "sw-9",
                "interface": "et-0/0/1",
                "metric": "egress_queue_drops",
                "value": 50,
                "unit": "packets",
                "timestamp_utc": "2026-10-31T12:00:00.000Z",
            }
        ],
        "configurations": [],
        "logs": [],
    }
    report = run_diagnosis(data)

    assert report.status == "insufficient_evidence"
    assert report.probable_cause is None
    assert report.confidence == 0.0
    assert "missing" in str(report.uncertainty.missing_evidence).lower() or len(report.uncertainty.missing_evidence) > 0
