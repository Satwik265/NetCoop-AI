"""Unit tests for synthetic network generator determinism, scenario signatures, and knobs."""

import json
from data.generator import DeviceStatus, DeviceType, SyntheticNetworkGenerator


def test_generator_determinism() -> None:
    """Verify that identical seeds produce byte-for-byte identical telemetry."""
    run1 = SyntheticNetworkGenerator.generate(scenario="link_congestion", seed=42)
    run2 = SyntheticNetworkGenerator.generate(scenario="link_congestion", seed=42)

    str1 = json.dumps(run1, sort_keys=True)
    str2 = json.dumps(run2, sort_keys=True)
    assert str1 == str2


def test_generator_different_seeds_produce_variance() -> None:
    """Verify that different seeds produce statistically different metric streams."""
    run_a = SyntheticNetworkGenerator.generate(scenario="normal_operation", seed=42)
    run_b = SyntheticNetworkGenerator.generate(scenario="normal_operation", seed=999)

    lat_a = [r["latency_ms"] for r in run_a["telemetry"]]
    lat_b = [r["latency_ms"] for r in run_b["telemetry"]]
    assert lat_a != lat_b


def test_scenario_signature_link_congestion() -> None:
    """Verify link_congestion triggers high utilization and queue drops on core."""
    data = SyntheticNetworkGenerator.generate(scenario="link_congestion", seed=42)
    core_records = [r for r in data["telemetry"] if r["device_id"] in ("core-rtr-01", "dist-sw-core")]

    assert len(core_records) == 2
    for r in core_records:
        assert r["link_utilization_pct"] > 90.0
        assert r["queue_drops"] > 400
        assert r["device_status"] == DeviceStatus.DEGRADED.value


def test_scenario_signature_weak_wifi() -> None:
    """Verify weak_wifi_signal triggers poor RSSI and high retransmissions on AP."""
    data = SyntheticNetworkGenerator.generate(scenario="weak_wifi_signal", seed=42)
    ap_records = [r for r in data["telemetry"] if r["device_id"] in ("ap-hostel-b1", "host-student-01")]

    assert len(ap_records) == 2
    for r in ap_records:
        assert r["wifi_rssi_dbm"] is not None
        assert r["wifi_rssi_dbm"] < -80.0
        assert r["wifi_retransmission_pct"] is not None
        assert r["wifi_retransmission_pct"] > 25.0


def test_scenario_signature_dns_failure() -> None:
    """Verify dns_failure triggers extreme resolution latency and failure rates."""
    data = SyntheticNetworkGenerator.generate(scenario="dns_failure", seed=42)
    for r in data["telemetry"]:
        assert r["dns_resolution_ms"] is not None
        assert r["dns_resolution_ms"] > 2000.0
        assert r["dns_failure_pct"] is not None
        assert r["dns_failure_pct"] > 80.0


def test_knobs_missing_sample_rate() -> None:
    """Verify missing sample rate knob introduces None values across records."""
    data_full = SyntheticNetworkGenerator.generate(scenario="normal_operation", seed=42, missing_sample_rate=0.0)
    data_dropped = SyntheticNetworkGenerator.generate(scenario="normal_operation", seed=42, missing_sample_rate=0.4)

    null_count_full = sum(
        1 for r in data_full["telemetry"] for v in r.values() if v is None
    )
    null_count_dropped = sum(
        1 for r in data_dropped["telemetry"] for v in r.values() if v is None
    )
    assert null_count_dropped > null_count_full


def test_knobs_staleness_seconds() -> None:
    """Verify staleness knob offsets timestamps backwards."""
    fresh = SyntheticNetworkGenerator.generate(scenario="normal_operation", seed=42, staleness_seconds=0.0)
    stale = SyntheticNetworkGenerator.generate(scenario="normal_operation", seed=42, staleness_seconds=3600.0)

    ts_fresh = fresh["telemetry"][0]["timestamp"]
    ts_stale = stale["telemetry"][0]["timestamp"]
    assert ts_fresh != ts_stale
    assert "11:00:00" in ts_stale  # 1 hour prior to 12:00:00

