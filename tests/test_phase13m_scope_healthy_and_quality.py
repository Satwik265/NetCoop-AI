"""Unit tests for Phase 13M: Scope-aware healthy confirmation and data-quality score."""

import pytest
from netcoop.orchestrator.graph import run_diagnosis
from gateway.adapters.organizer_adapter import OrganizerAdapter


def test_scope_aware_healthy_without_wifi_or_services():
    """Topology with only switches/routers and hosts (no APs, no DNS/DHCP services).

    Healthy nominal telemetry lacking Wi-Fi and DNS/DHCP metrics must be confirmed benign.
    Provenance must record checked vs out-of-scope domains.
    """
    payload = {
        "incident_id": "test-scope-healthy-01",
        "network_id": "lab-net",
        "topology": {
            "nodes": [
                {"id": "r1", "role": "router"},
                {"id": "sw1", "role": "switch"},
                {"id": "h1", "role": "host"},
                {"id": "h2", "role": "host"},
            ],
            "links": [
                {"source": "r1", "target": "sw1"},
                {"source": "sw1", "target": "h1"},
                {"source": "sw1", "target": "h2"},
            ],
        },
        "telemetry": [
            {
                "timestamp": "2026-11-17T10:00:00Z",
                "device_id": "r1",
                "device_type": "router",
                "device_status": "online",
                "cpu_pct": 12.0,
                "packet_loss_pct": 0.0,
                "latency_ms": 1.2,
                "link_utilization_pct": 8.5,
            },
            {
                "timestamp": "2026-11-17T10:00:00Z",
                "device_id": "sw1",
                "device_type": "switch",
                "device_status": "online",
                "cpu_pct": 15.0,
                "packet_loss_pct": 0.0,
                "latency_ms": 0.8,
                "link_utilization_pct": 12.0,
            },
            {
                "timestamp": "2026-11-17T10:00:00Z",
                "device_id": "h1",
                "device_type": "host",
                "device_status": "online",
                "cpu_pct": 5.0,
                "packet_loss_pct": 0.0,
                "latency_ms": 1.5,
            },
            {
                "timestamp": "2026-11-17T10:00:00Z",
                "device_id": "h2",
                "device_type": "host",
                "device_status": "online",
                "cpu_pct": 4.5,
                "packet_loss_pct": 0.0,
                "latency_ms": 1.6,
            },
        ],
        "logs": [],
        "configurations": [],
    }

    report = run_diagnosis(payload)
    assert report.status == "benign", f"Expected benign, got {report.status}"
    assert report.probable_cause is not None
    assert "normal" in str(report.probable_cause).lower()

    # Scope domain tracking in provenance
    prov = report.provenance or {}
    checked = prov.get("checked_domains", [])
    out_of_scope = prov.get("out_of_scope_domains", [])

    assert "traffic_performance" in checked
    assert "switching_fabric" in checked
    assert "host_endpoints" in checked
    assert "wireless_rf" in out_of_scope
    assert "network_services" in out_of_scope


def test_data_quality_no_penalty_for_optional_and_out_of_scope_metrics():
    """Telemetry without optional fault counters (drops, errors, flaps) must not be penalized."""
    raw = {
        "telemetry": [
            {
                "timestamp": "2026-11-17T10:00:00Z",
                "device_id": "node-1",
                "device_type": "router",
                "status": "online",
                "cpu_utilization_pct": 20.0,
                "latency_ms": 2.5,
                "packet_loss_pct": 0.0,
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    dq = adapted.get("data_quality", {})
    score = dq.get("overall_score")
    assert score is not None
    assert score >= 0.90, f"Expected high quality score for valid telemetry, got {score}"


def test_data_quality_score_floor_at_040():
    """Even highly degraded or anomalous payloads must not drop below the 0.40 quality floor."""
    raw = {
        "telemetry": [
            {
                "timestamp": "2026-11-17T10:00:00Z",
                "device_id": "node-bad",
                "device_type": "unknown",
                "status": "bad_status_value",
                "cpu_pct": -999,  # negative value -> error
                "latency_ms": "not_a_number",  # wrong type
                "packet_loss_pct": 500.0,  # out of range
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    dq = adapted.get("data_quality", {})
    score = dq.get("overall_score", 0.0)
    assert score >= 0.40, f"Expected quality score >= 0.40 floor, got {score}"
