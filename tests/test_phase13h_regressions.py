"""Phase 13H Regression Tests.

Verifies:
1. Enum device_status bug regression (DeviceStatus.DEGRADED object never bypassed).
2. Healthy guard comprehensive regression (metric bounds, switch unobserved check, nominal confirmation).
3. Pipeline determinism multi-seed regression across scenarios.
"""

import copy
import os
import pytest

os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"
from netcoop.config import settings
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from netcoop.data.generator import DeviceStatus, DeviceType
from netcoop.data.generator import SyntheticNetworkGenerator, SeverityLevel, NoiseShape
from orchestrator.graph import run_diagnosis


def test_regression_enum_device_status_prevents_false_normal() -> None:
    """Regression test: DeviceStatus.DEGRADED enum object must trigger unhealthy guard, never benign."""
    # Create an incident with nominal metrics but one device marked as DeviceStatus.DEGRADED
    incident = {
        "incident_id": "test-inc-enum-regression",
        "network_id": "test-net",
        "topology": {
            "nodes": [
                {"id": "core-rtr-01", "type": "router"},
                {"id": "dept-sw-cs-01", "type": "switch"},
            ],
            "links": [
                {"source": "core-rtr-01", "target": "dept-sw-cs-01"}
            ]
        },
        "telemetry": [
            {
                "timestamp": "2026-11-16T12:00:00Z",
                "device_id": "core-rtr-01",
                "device_type": DeviceType.ROUTER,
                "device_status": DeviceStatus.ONLINE,
                "packet_loss_pct": 0.0,
                "latency_ms": 2.1,
                "link_utilization_pct": 20.0,
                "cpu_pct": 25.0,
                "queue_drops": 0,
                "interface_errors": 0,
                "link_flaps": 0,
            },
            {
                "timestamp": "2026-11-16T12:00:00Z",
                "device_id": "dept-sw-cs-01",
                "device_type": DeviceType.SWITCH,
                # Crucial: pass the Enum object directly, not a string
                "device_status": DeviceStatus.DEGRADED,
                "packet_loss_pct": 0.0,
                "latency_ms": 2.5,
                "link_utilization_pct": 22.0,
                "cpu_pct": 28.0,
                "queue_drops": 0,
                "interface_errors": 0,
                "link_flaps": 0,
            },
        ],
        "logs": [],
        "config_diffs": [],
    }

    report = run_diagnosis(incident)
    # The report MUST NEVER be benign when a device is DEGRADED
    assert report.status != "benign", f"Enum DeviceStatus.DEGRADED was incorrectly classified as benign!"
    assert report.status in ("diagnosed", "insufficient_evidence", "inconclusive")


@pytest.mark.parametrize("bad_field,bad_value", [
    ("packet_loss_pct", 5.0),
    ("queue_drops", 20),
    ("latency_ms", 65.0),
    ("cpu_pct", 92.0),
    ("link_utilization_pct", 88.0),
    ("interface_errors", 12),
    ("link_flaps", 3),
    ("dns_failure_pct", 25.0),
    ("dhcp_failure_pct", 30.0),
])
def test_regression_healthy_guard_catches_all_metric_deviations(bad_field: str, bad_value: float) -> None:
    """Regression test: Any anomalous metric above nominal bounds triggers unhealthy guard."""
    incident = {
        "incident_id": f"test-inc-metric-{bad_field}",
        "network_id": "test-net",
        "topology": {
            "nodes": [
                {"id": "rtr-01", "type": "router"},
                {"id": "sw-01", "type": "switch"},
            ],
            "links": [{"source": "rtr-01", "target": "sw-01"}]
        },
        "telemetry": [
            {
                "timestamp": "2026-11-16T12:00:00Z",
                "device_id": "rtr-01",
                "device_type": "router",
                "device_status": "online",
                "packet_loss_pct": 0.0,
                "latency_ms": 2.0,
                "link_utilization_pct": 20.0,
                "cpu_pct": 20.0,
                "queue_drops": 0,
                "interface_errors": 0,
                "link_flaps": 0,
            },
            {
                "timestamp": "2026-11-16T12:00:00Z",
                "device_id": "sw-01",
                "device_type": "switch",
                "device_status": "online",
                "packet_loss_pct": 0.0,
                "latency_ms": 2.0,
                "link_utilization_pct": 20.0,
                "cpu_pct": 20.0,
                "queue_drops": 0,
                "interface_errors": 0,
                "link_flaps": 0,
                bad_field: bad_value,
            },
        ],
        "logs": [],
        "config_diffs": [],
    }

    report = run_diagnosis(incident)
    assert report.status != "benign", f"Metric deviation {bad_field}={bad_value} was erroneously called benign!"


def test_regression_healthy_guard_unobserved_switch() -> None:
    """Regression test: Critical switch with completely unobserved interface health triggers guard."""
    incident = {
        "incident_id": "test-inc-unobserved-switch",
        "network_id": "test-net",
        "topology": {
            "nodes": [
                {"id": "core-rtr-01", "type": "router"},
                {"id": "dept-sw-cs-01", "type": "switch"},
            ],
            "links": [{"source": "core-rtr-01", "target": "dept-sw-cs-01"}]
        },
        "telemetry": [
            {
                "timestamp": "2026-11-16T12:00:00Z",
                "device_id": "core-rtr-01",
                "device_type": "router",
                "device_status": "online",
                "packet_loss_pct": 0.0,
                "latency_ms": 2.0,
                "link_utilization_pct": 20.0,
                "cpu_pct": 20.0,
                "queue_drops": 0,
                "interface_errors": 0,
                "link_flaps": 0,
            },
            {
                "timestamp": "2026-11-16T12:00:00Z",
                "device_id": "dept-sw-cs-01",
                "device_type": "switch",
                # Unobserved switch: status is None, errors/flaps/loss are None
                "device_status": None,
                "packet_loss_pct": None,
                "latency_ms": None,
                "link_utilization_pct": None,
                "cpu_pct": None,
                "queue_drops": None,
                "interface_errors": None,
                "link_flaps": None,
            },
        ],
        "logs": [],
        "config_diffs": [],
    }

    report = run_diagnosis(incident)
    assert report.status != "benign", "Unobserved switch must not be classified as benign!"


def test_regression_pipeline_determinism_multi_seed() -> None:
    """Regression test: Diagnostic pipeline produces 100% identical outputs on repeated runs across seeds."""
    test_cases = [
        ("normal_operation", 255),
        ("link_congestion", 256),
        ("weak_wifi_signal", 257),
        ("device_cpu_overload", 258),
    ]

    for scenario, seed in test_cases:
        inc = SyntheticNetworkGenerator.generate(
            scenario=scenario,
            seed=seed,
            severity=SeverityLevel.HIGH,
            noise_level=0.1,
            noise_shape=NoiseShape.GAUSSIAN,
            missing_sample_rate=0.1,
            onset_offset_seconds=60.0,
        )

        rep1 = run_diagnosis(copy.deepcopy(inc))
        rep2 = run_diagnosis(copy.deepcopy(inc))

        assert rep1.status == rep2.status, f"Non-deterministic status on {scenario}-{seed}: {rep1.status} vs {rep2.status}"
        assert rep1.probable_cause == rep2.probable_cause, f"Non-deterministic probable_cause on {scenario}-{seed}"
        assert rep1.confidence == rep2.confidence, f"Non-deterministic confidence on {scenario}-{seed}"
        assert rep1.conformal_prediction_set == rep2.conformal_prediction_set, f"Non-deterministic conformal_set on {scenario}-{seed}"
        assert rep1.affected_devices == rep2.affected_devices, f"Non-deterministic affected_devices on {scenario}-{seed}"
