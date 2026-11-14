"""Phase 2 Acceptance Tests: Canonical Ingestion, Normalization Path, and Interoperability.

Verifies:
1. Canonical input through CLI, API and Gateway.
2. Renamed field aliases.
3. Seconds/milliseconds and throughput unit conversions.
4. Missing optional fields (preserved as None, zero never invented).
5. Missing required fields (structured ERR_MISSING_REQUIRED_FIELD).
6. Null and NaN strings sanitization.
7. Invalid numeric values and out-of-range values.
8. Unknown units (ERR_UNKNOWN_UNIT).
9. Unsupported schema versions (ERR_UNSUPPORTED_SCHEMA_VERSION).
10. Malformed JSON (tolerant recovery vs unrecoverable 400 rejection).
11. Out-of-order timestamps and timezone offsets.
12. Clock skew (>600s flagged with ERR_STALE_TIMESTAMP).
13. Duplicate/repeated ingestion deduplicated.
14. Normalization idempotency (adapt(adapt(x)) == adapt(x), no double unit conversion).
15. Gate 2: exact equivalent normalized output across CLI, API, and Gateway.
"""

from __future__ import annotations

import json
from typing import Any, Dict
import pytest
from fastapi.testclient import TestClient

from api.main import app as api_app
from gateway.api import app as gateway_app
from gateway.adapters.organizer_adapter import OrganizerAdapter, TypedValidationError
from netcoop.core.normalizer import TelemetryNormalizer


@pytest.fixture
def sample_logical_input() -> Dict[str, Any]:
    """A realistic logical incident payload with aliases and mixed units."""
    return {
        "incident_id": "inc-phase2-matrix-01",
        "network_id": "campus-fabric-01",
        "schema_version": "1.0.0",
        "telemetry": [
            {
                "dev": "core-rtr-01",
                "role": "router",
                "state": "degraded",
                "delay": 45.2,
                "throughput_kbps": 85000.0,
                "loss": 2.5,
                "timestamp": "2026-10-31T17:30:00+05:30",
            }
        ],
    }


# -----------------------------------------------------------------------------
# 1. Canonical Input Through CLI, API, and Gateway
# -----------------------------------------------------------------------------
def test_1_canonical_input_through_gateway_api_cli() -> None:
    """Canonical schema input successfully accepted and normalized across all entry points."""
    canonical = {
        "incident_id": "inc-canon-01",
        "network_id": "campus-net",
        "schema_version": "1.0.0",
        "telemetry": [
            {
                "device_id": "core-rtr-01",
                "device_type": "router",
                "device_status": "online",
                "latency_ms": 12.5,
                "packet_loss_pct": 0.1,
                "throughput_mbps": 500.0,
                "timestamp": "2026-10-31T12:00:00Z",
            }
        ],
    }
    # Gateway
    gw_client = TestClient(gateway_app)
    gw_res = gw_client.post("/ingest", json=canonical)
    assert gw_res.status_code == 200
    gw_data = gw_res.json()

    # API
    api_client = TestClient(api_app)
    api_res = api_client.post("/api/ingest", json=canonical)
    assert api_res.status_code == 200
    api_data = api_res.json()

    # CLI / Direct Adapter
    cli_data = OrganizerAdapter.adapt_dataset(canonical)

    assert gw_data["telemetry"][0]["device_id"] == "core-rtr-01"
    assert gw_data["telemetry"][0]["latency_ms"] == 12.5
    assert api_data["telemetry"][0]["latency_ms"] == 12.5
    assert cli_data["telemetry"][0]["latency_ms"] == 12.5


# -----------------------------------------------------------------------------
# 2. Renamed Field Aliases
# -----------------------------------------------------------------------------
def test_2_renamed_field_aliases() -> None:
    """Documented field aliases map to canonical field names."""
    raw = {
        "telemetry": [
            {
                "node_id": "dist-sw-01",
                "type": "switch",
                "status": "warning",
                "rtt": 55.4,
                "tput": 920.0,
                "util": 89.5,
                "drops": 450,
                "rssi": -82.0,
                "retx": 28.5,
                "timestamp": "2026-10-31T12:00:00Z",
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]
    assert rec["device_id"] == "dist-sw-01"
    assert rec["device_type"] == "switch"
    assert rec["device_status"] == "degraded"  # 'warning' maps to canonical 'degraded'
    assert rec["latency_ms"] == 55.4
    assert rec["link_utilization_pct"] == 89.5
    assert rec["queue_drops"] == 450
    assert rec["wifi_rssi_dbm"] == -82.0
    assert rec["wifi_retransmission_pct"] == 28.5


# -----------------------------------------------------------------------------
# 3. Seconds/Milliseconds & Throughput Unit Conversions
# -----------------------------------------------------------------------------
def test_3_unit_conversions_seconds_and_throughput() -> None:
    """Verify fractional seconds -> ms and kbps -> Mbps conversions."""
    raw = {
        "telemetry": [
            {
                "device_id": "rtr-border",
                "latency_s": 0.0452,
                "throughput_kbps": 125000.0,
                "bandwidth_kbps": 1000000.0,
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]
    assert rec["latency_ms"] == 45.2
    assert rec["throughput_mbps"] == 125.0
    assert rec["bandwidth_mbps"] == 1000.0


# -----------------------------------------------------------------------------
# 4. Missing Optional Fields (Preserves None, No Invented Zero)
# -----------------------------------------------------------------------------
def test_4_missing_optional_fields_preserves_none_no_invented_zero() -> None:
    """Verify missing optional fields remain None; zero or dummy values are never invented."""
    raw = {
        "telemetry": [
            {
                "device_id": "sw-access-01",
                "cpu_pct": 45.0,
                # latency, jitter, throughput, bandwidth, queue_drops, wifi, dns omitted
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]
    assert rec["cpu_pct"] == 45.0
    assert rec["latency_ms"] is None, "Missing latency must not become invented default"
    assert rec["jitter_ms"] is None, "Missing jitter must not become invented default"
    assert rec["throughput_mbps"] is None, "Missing throughput must not become invented default"
    assert rec["bandwidth_mbps"] is None, "Missing bandwidth must not become invented default"
    assert rec["queue_drops"] is None, "Missing queue drops must not become invented zero"
    assert rec["packet_loss_pct"] is None, "Missing packet loss must not become invented zero"


# -----------------------------------------------------------------------------
# 5. Missing Required Fields
# -----------------------------------------------------------------------------
def test_5_missing_required_fields_reported_in_validation_errors() -> None:
    """Verify missing incident_id and network_id generate structured ERR_MISSING_REQUIRED_FIELD."""
    raw = {
        # incident_id and network_id omitted
        "telemetry": [
            {"device_id": "r1", "latency_ms": 10.0}
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errors = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errors]
    fields = [e.get("field") for e in errors]
    assert "ERR_MISSING_REQUIRED_FIELD" in codes
    assert "incident_id" in fields
    assert "network_id" in fields


# -----------------------------------------------------------------------------
# 6. Null and NaN Strings Sanitization
# -----------------------------------------------------------------------------
def test_6_null_and_nan_strings_sanitized_safely() -> None:
    """Verify string sentinels ('NaN', 'null', 'None') sanitize to None without crash."""
    raw = {
        "telemetry": [
            {
                "device_id": "core-rtr-01",
                "wifi_rssi_dbm": "NaN",
                "jitter_ms": "null",
                "dns_failure_pct": "None",
                "packet_loss_pct": float("nan"),
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]
    assert rec["wifi_rssi_dbm"] is None
    assert rec["jitter_ms"] is None
    assert rec["dns_failure_pct"] is None
    assert rec["packet_loss_pct"] is None
    codes = [e["code"] for e in adapted["data_quality"]["validation_errors"]]
    assert "ERR_NAN_INF" in codes


# -----------------------------------------------------------------------------
# 7. Invalid Numeric Values & Out-of-Range Clamping
# -----------------------------------------------------------------------------
def test_7_invalid_numeric_and_out_of_range_values() -> None:
    """Verify non-numeric string, negative counters, and out-of-range percentages."""
    raw = {
        "telemetry": [
            {
                "device_id": "rtr-edge",
                "latency_ms": "not_a_valid_number",
                "queue_drops": -50,
                "link_utilization_pct": 135.0,
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    rec = adapted["telemetry"][0]
    assert rec["latency_ms"] is None  # unparseable string rejected safely
    assert rec["queue_drops"] == 0  # clamped non-negative
    assert rec["link_utilization_pct"] == 100.0  # clamped percentage
    codes = [e["code"] for e in adapted["data_quality"]["validation_errors"]]
    assert "ERR_WRONG_TYPE" in codes
    assert "ERR_NEGATIVE_VALUE" in codes
    assert "ERR_OUT_OF_RANGE_PERCENT" in codes


# -----------------------------------------------------------------------------
# 8. Unknown Units Explicitly Flagged
# -----------------------------------------------------------------------------
def test_8_unknown_units_explicitly_flagged() -> None:
    """Verify unrecognized units are not silently discarded or guessed; flagged explicitly."""
    raw = {
        "telemetry": [
            {
                "device_id": "sw-1",
                "latency_ms": 10.0,
                "unit": "furlongs_per_fortnight",
            }
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errors = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errors]
    assert "ERR_UNKNOWN_UNIT" in codes


# -----------------------------------------------------------------------------
# 9. Unsupported Schema Versions Explicitly Flagged
# -----------------------------------------------------------------------------
def test_9_unsupported_schema_versions_explicitly_flagged() -> None:
    """Verify schema versions outside 1.x are flagged with ERR_UNSUPPORTED_SCHEMA_VERSION."""
    raw = {
        "schema_version": "2.4.0",
        "telemetry": [{"device_id": "rtr-1", "latency_ms": 15.0}],
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    errors = adapted["data_quality"]["validation_errors"]
    codes = [e["code"] for e in errors]
    assert "ERR_UNSUPPORTED_SCHEMA_VERSION" in codes


# -----------------------------------------------------------------------------
# 10. Malformed JSON (Tolerant Single-Quotes vs. Unrecoverable 400)
# -----------------------------------------------------------------------------
def test_10_malformed_json_handling_and_rejection() -> None:
    """Tolerant single-quoted python exports are accepted with warning; unrecoverable syntax returns 400."""
    # A. Tolerant single-quoted string
    single_quoted = "{'telemetry': [{'device_id': 'ap-1', 'metrics': {'cpu_utilization_pct': 60.0}}]}"
    adapted = OrganizerAdapter.adapt_dataset(single_quoted)
    assert len(adapted["telemetry"]) == 1
    assert adapted["telemetry"][0]["cpu_pct"] == 60.0
    codes = [e["code"] for e in adapted["data_quality"]["validation_errors"]]
    assert "ERR_MALFORMED_JSON" in codes

    # B. Unrecoverable garbage rejected by Gateway with HTTP 400
    gw_client = TestClient(gateway_app)
    unrecoverable = "{this is completely broken json"
    resp = gw_client.post("/ingest", content=unrecoverable, headers={"Content-Type": "application/json"})
    assert resp.status_code == 400


# -----------------------------------------------------------------------------
# 11. Out-of-Order Timestamps & Timezone Offsets
# -----------------------------------------------------------------------------
def test_11_out_of_order_timestamps_and_timezone_offsets() -> None:
    """Verify timezone offsets normalized to UTC and out-of-order records sorted chronologically."""
    raw = {
        "telemetry": [
            {"device_id": "r1", "timestamp": "2026-10-31T17:35:00+05:30", "latency_ms": 20.0},
            {"device_id": "r1", "timestamp": "2026-10-31T17:30:00+05:30", "latency_ms": 15.0},
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    records = adapted["telemetry"]
    assert len(records) == 2
    # Verify chronological sort
    assert records[0]["timestamp"] < records[1]["timestamp"]
    # Verify UTC conversion: 17:30 +05:30 -> 12:00:00 UTC
    assert "12:00:00" in records[0]["timestamp"]
    assert "12:05:00" in records[1]["timestamp"]
    # Verify raw timestamp preserved for provenance
    assert records[0]["raw_timestamp"] == "2026-10-31T17:30:00+05:30"
    codes = [e["code"] for e in adapted["data_quality"]["validation_errors"]]
    assert "ERR_OUT_OF_ORDER_TIMESTAMP" in codes


# -----------------------------------------------------------------------------
# 12. Clock Skew Flagged
# -----------------------------------------------------------------------------
def test_12_clock_skew_flagged() -> None:
    """Verify time difference > 600s sets clock_skew_detected: True and ERR_STALE_TIMESTAMP."""
    raw = {
        "telemetry": [
            {"device_id": "r1", "timestamp": "2026-10-31T12:00:00Z"},
            {"device_id": "r2", "timestamp": "2026-10-31T12:35:00Z"},  # 35 min skew
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    assert adapted["clock_skew_detected"] is True
    codes = [e["code"] for e in adapted["data_quality"]["validation_errors"]]
    assert "ERR_STALE_TIMESTAMP" in codes


# -----------------------------------------------------------------------------
# 13. Duplicate Repeated Ingestion Deduplication
# -----------------------------------------------------------------------------
def test_13_duplicate_repeated_ingestion_deduplicated() -> None:
    """Verify duplicate observations for same device and timestamp are pruned."""
    raw = {
        "telemetry": [
            {"device_id": "r1", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 10.0},
            {"device_id": "r1", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 10.0},  # duplicate
            {"device_id": "r1", "timestamp": "2026-10-31T12:01:00Z", "latency_ms": 12.0},
        ]
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    assert len(adapted["telemetry"]) == 2
    codes = [e["code"] for e in adapted["data_quality"]["validation_errors"]]
    assert "ERR_DUPLICATE_TIMESTAMP" in codes


# -----------------------------------------------------------------------------
# 14. Normalization Idempotency (Zero Double Unit Conversion)
# -----------------------------------------------------------------------------
def test_14_normalization_idempotency_no_double_conversion(sample_logical_input: Dict[str, Any]) -> None:
    """Mathematical idempotency: adapt_dataset(adapt_dataset(x)) == adapt_dataset(x).

    Guarantees throughput and latency are never multiplied or divided a second time.
    """
    pass1 = OrganizerAdapter.adapt_dataset(sample_logical_input)
    pass2 = OrganizerAdapter.adapt_dataset(pass1)

    assert pass1 == pass2, "Normalization must be strictly idempotent"
    assert pass1["telemetry"][0]["latency_ms"] == pass2["telemetry"][0]["latency_ms"]
    assert pass1["telemetry"][0]["throughput_mbps"] == pass2["telemetry"][0]["throughput_mbps"]
    assert pass1["telemetry"][0]["latency_ms"] == 45.2
    assert pass1["telemetry"][0]["throughput_mbps"] == 85.0


# -----------------------------------------------------------------------------
# 15. Gate 2: Exact Agreement Across CLI, API, and Gateway
# -----------------------------------------------------------------------------
def test_15_gate2_identical_normalized_output_across_cli_api_gateway(sample_logical_input: Dict[str, Any]) -> None:
    """Gate 2 Verification: CLI, API, and Gateway agree on values, units, missingness, and quality score."""
    gw_client = TestClient(gateway_app)
    api_client = TestClient(api_app)

    gw_res = gw_client.post("/ingest", json=sample_logical_input).json()
    api_res = api_client.post("/api/ingest", json=sample_logical_input).json()
    cli_res = OrganizerAdapter.adapt_dataset(sample_logical_input)

    # Values, units, missingness, validation status must agree exactly
    assert gw_res == api_res, "Gateway and API must produce identical normalized JSON"
    assert gw_res == cli_res, "Gateway and CLI must produce identical normalized JSON"
    assert api_res == cli_res, "API and CLI must produce identical normalized JSON"

    rec = gw_res["telemetry"][0]
    assert rec["device_id"] == "core-rtr-01"
    assert rec["latency_ms"] == 45.2
    assert rec["throughput_mbps"] == 85.0
    assert rec["packet_loss_pct"] == 2.5
    assert rec["jitter_ms"] is None, "Missing field must remain None across all entry points"
    assert rec["bandwidth_mbps"] is None, "Missing field must remain None across all entry points"
    assert rec["queue_drops"] is None, "Missing field must remain None across all entry points"
    assert gw_res["data_quality"]["overall_score"] == api_res["data_quality"]["overall_score"]
    assert gw_res["data_quality"]["validation_errors"] == cli_res["data_quality"]["validation_errors"]
