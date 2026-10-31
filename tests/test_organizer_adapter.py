"""Unit tests verifying OrganizerAdapter resilience to external variants and dirty inputs."""

import json
from pathlib import Path
from gateway.adapters.organizer_adapter import OrganizerAdapter

SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


def test_adapter_renamed_fields() -> None:
    """Verify adapter correctly normalizes renamed alias keys."""
    raw = {
        "telemetry": [
            {
                "dev_id": "rtr-99",
                "role": "router",
                "state": "online",
                "delay": 45.2,
                "loss": 3.1,
                "util": 88.0,
                "tput": 880.0,
                "drops": 120,
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]

    assert rec["device_id"] == "rtr-99"
    assert rec["device_type"] == "router"
    assert rec["latency_ms"] == 45.2
    assert rec["packet_loss_pct"] == 3.1
    assert rec["link_utilization_pct"] == 88.0
    assert rec["queue_drops"] == 120


def test_adapter_seconds_to_ms_conversion() -> None:
    """Verify latency provided in seconds (e.g. 0.052) is converted to milliseconds."""
    raw = {
        "telemetry": [
            {
                "device_id": "sw-1",
                "latency_s": 0.052,
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    assert adapted["telemetry"][0]["latency_ms"] == 52.0


def test_adapter_kbps_to_mbps_conversion() -> None:
    """Verify throughput provided in kbps (e.g. 75000) is converted to Mbps."""
    raw = {
        "telemetry": [
            {
                "device_id": "sw-1",
                "throughput_kbps": 75000.0,
                "bandwidth_kbps": 100000.0,
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    assert adapted["telemetry"][0]["throughput_mbps"] == 75.0
    assert adapted["telemetry"][0]["bandwidth_mbps"] == 100.0


def test_adapter_sanitizes_nan_and_null_strings() -> None:
    """Verify string 'NaN' and 'null' values are sanitized to None."""
    raw = {
        "telemetry": [
            {
                "device_id": "ap-1",
                "wifi_rssi_dbm": "NaN",
                "jitter_ms": "null",
                "dns_failure_pct": "None",
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]
    assert rec["wifi_rssi_dbm"] is None
    assert rec["jitter_ms"] == 1.0  # fallback applied
    assert rec["dns_failure_pct"] is None


def test_adapter_deduplicates_and_sorts_timestamps() -> None:
    """Verify duplicate records are pruned and timestamps are sorted chronologically."""
    raw = {
        "telemetry": [
            {"device_id": "r1", "timestamp": "2026-10-31T12:05:00Z", "latency_ms": 10.0},
            {"device_id": "r1", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 8.0},
            {"device_id": "r1", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 8.0},  # duplicate
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    records = adapted["telemetry"]
    assert len(records) == 2
    assert "12:00:00" in records[0]["timestamp"]
    assert "12:05:00" in records[1]["timestamp"]


def test_adapter_detects_clock_skew() -> None:
    """Verify clock skew is flagged when records span extreme time gaps."""
    raw = {
        "telemetry": [
            {"device_id": "r1", "timestamp": "2026-10-31T12:00:00Z"},
            {"device_id": "r2", "timestamp": "2026-10-31T12:45:00Z"},
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    assert adapted["clock_skew_detected"] is True


def test_adapter_handles_malformed_json_string() -> None:
    """Verify single-quoted JSON string is parsed without fatal crash."""
    malformed = "{'telemetry': [{'device': 'sw-10', 'delay': 35.0, 'loss': 1.0}]}"
    adapted = OrganizerAdapter.adapt_dataset(malformed)
    assert len(adapted["telemetry"]) == 1
    assert adapted["telemetry"][0]["device_id"] == "sw-10"
    assert adapted["telemetry"][0]["latency_ms"] == 35.0

