"""Comprehensive validation tests for B1 deliverables:
- Scenario signatures (12 scenarios including compound faults)
- Typed error catalog & degraded-mode recovery
- Corrupted organizer variants (renamed fields, latency in seconds, missing metrics, null status, mixed records)
- Per-source data quality score and transformations report
"""

import json
from datetime import datetime, timezone
import pytest

from netcoop.data.generator import SyntheticNetworkGenerator, SeverityLevel, NoiseShape
from gateway.adapters.organizer_adapter import OrganizerAdapter, TypedValidationError
from orchestrator.graph import run_diagnosis


# -----------------------------------------------------------------------------
# 1. Scenario Signatures Tests
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("scenario, expected_status", [
    ("normal_operation", "insufficient_evidence"),  # benign / no fault detected
    ("link_congestion", "diagnosed"),
    ("weak_wifi_signal", "diagnosed"),
    ("ethernet_interface_fault", "diagnosed"),
    ("dns_failure", "diagnosed"),
    ("dhcp_failure", "diagnosed"),
    ("device_cpu_overload", "diagnosed"),
    ("upstream_failure_cascade", "diagnosed"),
    ("ambiguous_multi_fault", "insufficient_evidence"),
    ("insufficient_data", "insufficient_evidence"),
    ("compound_cpu_and_link", "insufficient_evidence"),
    ("compound_wifi_and_dns", "insufficient_evidence"),
])
def test_scenario_signature_generation_and_diagnosis(scenario: str, expected_status: str) -> None:
    """Verify all 12 scenario signatures generate valid payloads and diagnose according to ground truth."""
    dataset = SyntheticNetworkGenerator.generate(
        scenario=scenario,
        seed=123,
        severity=SeverityLevel.HIGH,
    )
    assert dataset["scenario"] == scenario
    assert len(dataset["telemetry"]) > 0

    adapted = OrganizerAdapter.adapt_dataset(dataset)
    report = run_diagnosis(adapted)

    if expected_status == "diagnosed":
        assert report.status == "diagnosed"
        assert report.confidence >= 0.80
        assert report.probable_cause is not None
    else:
        assert report.status in ("insufficient_evidence", "benign")


# -----------------------------------------------------------------------------
# 2. Typed Errors & Degraded Mode Tests
# -----------------------------------------------------------------------------

def test_typed_error_malformed_json() -> None:
    """ERR_MALFORMED_JSON: handles unquoted/single-quoted syntax with degraded continuation."""
    raw = "{'telemetry': [{'device_id': 'sw-1', 'metrics': {'cpu_utilization_pct': 55.0}}]}"
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_MALFORMED_JSON" in codes
    assert len(adapted["telemetry"]) == 1
    assert adapted["telemetry"][0]["cpu_pct"] == 55.0


def test_typed_error_empty_file() -> None:
    """ERR_EMPTY_FILE: handles empty payload without crash."""
    adapted = OrganizerAdapter.adapt_dataset("")
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_EMPTY_FILE" in codes
    assert adapted["telemetry"] == []


def test_typed_error_unknown_device() -> None:
    """ERR_UNKNOWN_DEVICE: flags null or empty device IDs and falls back."""
    raw = {"telemetry": [{"device_id": None, "latency_ms": 15.0}]}
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_UNKNOWN_DEVICE" in codes
    assert adapted["telemetry"][0]["device_id"] == "unknown_device"


def test_typed_error_wrong_type() -> None:
    """ERR_WRONG_TYPE: flags unparseable strings for numeric metrics."""
    raw = {"telemetry": [{"device_id": "r1", "latency_ms": "not_a_number"}]}
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_WRONG_TYPE" in codes
    assert adapted["telemetry"][0]["latency_ms"] is None


def test_typed_error_nan_inf() -> None:
    """ERR_NAN_INF: sanitizes NaN and Inf floats."""
    raw = {"telemetry": [{"device_id": "r1", "packet_loss_pct": float("nan")}]}
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_NAN_INF" in codes
    assert adapted["telemetry"][0]["packet_loss_pct"] is None


def test_typed_error_negative_value() -> None:
    """ERR_NEGATIVE_VALUE: clamps negative metric values to 0.0 and flags error."""
    raw = {"telemetry": [{"device_id": "r1", "queue_drops": -42, "latency_ms": -10.0}]}
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_NEGATIVE_VALUE" in codes
    assert adapted["telemetry"][0]["queue_drops"] == 0
    assert adapted["telemetry"][0]["latency_ms"] == 0.0


def test_typed_error_out_of_range_percentage() -> None:
    """ERR_OUT_OF_RANGE_PERCENT: clamps percentages > 100 to 100.0 and flags error."""
    raw = {"telemetry": [{"device_id": "r1", "link_utilization_pct": 145.0}]}
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_OUT_OF_RANGE_PERCENT" in codes
    assert adapted["telemetry"][0]["link_utilization_pct"] == 100.0


def test_typed_error_duplicate_and_out_of_order() -> None:
    """ERR_DUPLICATE_TIMESTAMP & ERR_OUT_OF_ORDER_TIMESTAMP."""
    raw = {
        "telemetry": [
            {"device_id": "r1", "timestamp": "2026-10-31T12:05:00Z", "latency_ms": 10.0},
            {"device_id": "r1", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 5.0},
            {"device_id": "r1", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 5.0},
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_DUPLICATE_TIMESTAMP" in codes
    assert "ERR_OUT_OF_ORDER_TIMESTAMP" in codes
    assert len(adapted["telemetry"]) == 2
    # Verify sorted chronologically
    assert adapted["telemetry"][0]["timestamp"] < adapted["telemetry"][1]["timestamp"]


def test_typed_error_stale_timestamp_and_clock_skew() -> None:
    """ERR_STALE_TIMESTAMP: flags clock skew > 600s."""
    raw = {
        "telemetry": [
            {"device_id": "r1", "timestamp": "2026-10-31T12:00:00Z"},
            {"device_id": "r2", "timestamp": "2026-10-31T12:45:00Z"},
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    assert adapted["clock_skew_detected"] is True
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_STALE_TIMESTAMP" in codes


def test_typed_error_unsupported_schema_version() -> None:
    """ERR_UNSUPPORTED_SCHEMA_VERSION: flags version divergence."""
    raw = {
        "schema_version": "9.9.0",
        "telemetry": [{"device_id": "sw-1", "latency_ms": 10.0}],
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_UNSUPPORTED_SCHEMA_VERSION" in codes


# -----------------------------------------------------------------------------
# 3. Corrupted Organizer Variants Tests
# -----------------------------------------------------------------------------

def test_organizer_renamed_fields() -> None:
    """Corrupted organizer variant: renamed fields and nested metrics."""
    raw = {
        "timestamp": "2026-10-14T07:05:49.619Z",
        "device_id": "SW_CAMPUS_4",
        "metrics": {
            "cpu_utilization_pct": 98.5,
            "loss_pct": 12.0,
            "util": 95.0,
            "rtt": 150.0,
        },
        "status": "Critical",
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]
    assert rec["device_id"] == "SW_CAMPUS_4"
    assert rec["device_type"] == "switch"
    assert rec["device_status"] == "degraded"
    assert rec["cpu_pct"] == 98.5
    assert rec["packet_loss_pct"] == 12.0
    assert rec["link_utilization_pct"] == 95.0
    assert rec["latency_ms"] == 150.0


def test_organizer_latency_in_seconds() -> None:
    """Corrupted organizer variant: latency provided in fractional seconds."""
    raw = {
        "device_id": "SW_CAMPUS_2",
        "metrics": {
            "latency_s": 0.085,
        },
        "status": "Warning",
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]
    assert rec["latency_ms"] == 85.0
    assert rec["device_status"] == "degraded"


def test_organizer_missing_metrics_object() -> None:
    """Corrupted organizer variant: metrics key is missing or null."""
    raw = {
        "timestamp": "2026-10-14T07:05:49Z",
        "device_id": "SW_CAMPUS_7",
        "metrics": None,
        "status": "Healthy",
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_MISSING_FIELD" in codes
    rec = adapted["telemetry"][0]
    assert rec["device_id"] == "SW_CAMPUS_7"
    assert rec["device_status"] == "online"
    # Absent metrics remain absent (None)
    assert rec["cpu_pct"] is None
    assert rec["queue_drops"] is None


def test_organizer_null_status() -> None:
    """Corrupted organizer variant: status is null."""
    raw = {
        "device_id": "SW_CAMPUS_3",
        "metrics": {
            "cpu_utilization_pct": 45.0,
        },
        "status": None,
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]
    assert rec["device_status"] == "online"
    errs = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errs]
    assert "ERR_MISSING_FIELD" in codes


def test_mix_of_organizer_and_canonical_records() -> None:
    """Mix of organizer format records and canonical records in single ingestion."""
    raw = {
        "telemetry": [
            # Organizer record
            {
                "timestamp": "2026-10-31T12:00:00Z",
                "device_id": "SW_CAMPUS_1",
                "metrics": {
                    "cpu_utilization_pct": 88.0,
                    "latency_ms": 40.0,
                },
                "status": "Warning",
            },
            # Canonical record
            {
                "timestamp": "2026-10-31T12:01:00Z",
                "device_id": "core-rtr-01",
                "device_type": "router",
                "device_status": "online",
                "cpu_pct": 22.0,
                "latency_ms": 5.0,
            },
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    assert len(adapted["telemetry"]) == 2
    r0 = adapted["telemetry"][0]
    r1 = adapted["telemetry"][1]

    assert r0["device_id"] == "SW_CAMPUS_1"
    assert r0["device_type"] == "switch"
    assert r0["device_status"] == "degraded"
    assert r0["cpu_pct"] == 88.0

    assert r1["device_id"] == "core-rtr-01"
    assert r1["device_type"] == "router"
    assert r1["device_status"] == "online"
    assert r1["cpu_pct"] == 22.0


# -----------------------------------------------------------------------------
# 4. Data Quality & Transformations Report Tests
# -----------------------------------------------------------------------------

def test_data_quality_report_structure() -> None:
    """Verify data_quality report returns per-source scores and transformation audit trail."""
    raw = {
        "telemetry": [
            {
                "timestamp": "2026-10-14T07:05:49Z",
                "device_id": "SW_CAMPUS_9",
                "metrics": {
                    "cpu_utilization_pct": 99.0,
                    "latency_s": 0.12,
                },
                "status": "Critical",
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    dq = adapted["data_quality"]

    assert "overall_score" in dq
    assert 0.0 <= dq["overall_score"] <= 1.0
    assert "transformations_applied" in dq
    assert "flattening" in dq["transformations_applied"]
    assert "status_mapping" in dq["transformations_applied"]
    assert "unit_conversion" in dq["transformations_applied"]

    per_source = dq["per_source"]
    assert "SW_CAMPUS_9" in per_source
    src_info = per_source["SW_CAMPUS_9"]
    assert src_info["record_count"] == 1
    assert "flattening" in src_info["transformations_applied"]
    assert isinstance(src_info["missing_fields"], list)
