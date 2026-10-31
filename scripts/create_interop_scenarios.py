"""Script to generate all interoperability failure variants and append to manifest."""

import json
from pathlib import Path
from data.generator import SyntheticNetworkGenerator

scenarios_dir = Path("data/scenarios")
base = SyntheticNetworkGenerator.generate("link_congestion", seed=42)

# 1. Renamed fields
renamed = json.loads(json.dumps(base))
renamed["incident_id"] = "inc-interop-renamed-fields"
for r in renamed["telemetry"]:
    r["dev_id"] = r.pop("device_id")
    r["delay"] = r.pop("latency_ms")
    r["loss"] = r.pop("packet_loss_pct")
    r["util"] = r.pop("link_utilization_pct")
with open(scenarios_dir / "interop_renamed_fields.json", "w", encoding="utf-8") as f:
    json.dump(renamed, f, indent=2)

# 2. Seconds vs ms
sec_data = json.loads(json.dumps(base))
sec_data["incident_id"] = "inc-interop-seconds-vs-ms"
for r in sec_data["telemetry"]:
    r["latency_s"] = round(r.pop("latency_ms") / 1000.0, 4)
with open(scenarios_dir / "interop_seconds_vs_ms.json", "w", encoding="utf-8") as f:
    json.dump(sec_data, f, indent=2)

# 3. kbps vs Mbps
kbps_data = json.loads(json.dumps(base))
kbps_data["incident_id"] = "inc-interop-kbps-vs-mbps"
for r in kbps_data["telemetry"]:
    r["throughput_kbps"] = round(r.pop("throughput_mbps") * 1000.0, 1)
    r["bandwidth_kbps"] = round(r.pop("bandwidth_mbps") * 1000.0, 1)
with open(scenarios_dir / "interop_kbps_vs_mbps.json", "w", encoding="utf-8") as f:
    json.dump(kbps_data, f, indent=2)

# 4. Schema v1 vs v2
v2_data = json.loads(json.dumps(base))
v2_data["incident_id"] = "inc-interop-schema-v2"
v2_data["schema_version"] = "2.0.0-experimental"
with open(scenarios_dir / "interop_schema_v1_vs_v2.json", "w", encoding="utf-8") as f:
    json.dump(v2_data, f, indent=2)

# 5. Missing fields
miss_data = json.loads(json.dumps(base))
miss_data["incident_id"] = "inc-interop-missing-fields"
for r in miss_data["telemetry"]:
    r.pop("jitter_ms", None)
    r.pop("cpu_pct", None)
    r.pop("memory_pct", None)
with open(scenarios_dir / "interop_missing_fields.json", "w", encoding="utf-8") as f:
    json.dump(miss_data, f, indent=2)

# 6. Null and NaN
null_data = json.loads(json.dumps(base))
null_data["incident_id"] = "inc-interop-null-nan"
for r in null_data["telemetry"]:
    r["jitter_ms"] = "NaN"
    r["wifi_rssi_dbm"] = "null"
with open(scenarios_dir / "interop_null_nan.json", "w", encoding="utf-8") as f:
    json.dump(null_data, f, indent=2)

# 7. Duplicate and out-of-order timestamps
order_data = json.loads(json.dumps(base))
order_data["incident_id"] = "inc-interop-dup-out-of-order"
if len(order_data["telemetry"]) >= 2:
    order_data["telemetry"].append(dict(order_data["telemetry"][0]))  # duplicate
    order_data["telemetry"].reverse()  # out of order
with open(scenarios_dir / "interop_duplicate_out_of_order.json", "w", encoding="utf-8") as f:
    json.dump(order_data, f, indent=2)

# 8. Clock skew
skew_data = json.loads(json.dumps(base))
skew_data["incident_id"] = "inc-interop-clock-skew"
if len(skew_data["telemetry"]) >= 2:
    skew_data["telemetry"][0]["timestamp"] = "2026-10-31T12:00:00Z"
    skew_data["telemetry"][1]["timestamp"] = "2026-10-31T12:45:00Z"  # 45 min skew
with open(scenarios_dir / "interop_clock_skew.json", "w", encoding="utf-8") as f:
    json.dump(skew_data, f, indent=2)

# 9. Malformed JSON representation
malformed_raw = """{
  'incident_id': 'inc-interop-malformed-json',
  'network_id': 'iit-bbs-campus-fabric',
  'telemetry': [
    {'device': 'core-rtr-01', 'delay': 140.5, 'loss': 5.2, 'util': 95.0, 'drops': 850}
  ]
}"""
with open(scenarios_dir / "interop_malformed_json.json", "w", encoding="utf-8") as f:
    f.write(malformed_raw)

# Update manifest
with open(scenarios_dir / "manifest.json", "r", encoding="utf-8") as f:
    manifest = json.load(f)

interop_entries = [
    {
        "name": "interop_renamed_fields",
        "file": "interop_renamed_fields.json",
        "category": "interoperability",
        "ground_truth": "Field alias adaptation (dev_id, delay, loss, util)",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "target_confidence_min": 0.80,
        "description": "Telemetry keys renamed to test adapter mapping."
    },
    {
        "name": "interop_seconds_vs_ms",
        "file": "interop_seconds_vs_ms.json",
        "category": "interoperability",
        "ground_truth": "Time unit conversion from seconds to milliseconds",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "target_confidence_min": 0.80,
        "description": "Latency metric provided in fractional seconds."
    },
    {
        "name": "interop_kbps_vs_mbps",
        "file": "interop_kbps_vs_mbps.json",
        "category": "interoperability",
        "ground_truth": "Rate conversion from kbps to Mbps",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "target_confidence_min": 0.80,
        "description": "Throughput provided in kbps."
    },
    {
        "name": "interop_schema_v1_vs_v2",
        "file": "interop_schema_v1_vs_v2.json",
        "category": "interoperability",
        "ground_truth": "Schema version tag divergence tolerance",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "target_confidence_min": 0.80,
        "description": "Schema version 2.0.0 experimental envelope."
    },
    {
        "name": "interop_missing_fields",
        "file": "interop_missing_fields.json",
        "category": "interoperability",
        "ground_truth": "Graceful degradation under missing optional metrics",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "target_confidence_min": 0.80,
        "description": "Optional fields omitted entirely."
    },
    {
        "name": "interop_null_nan",
        "file": "interop_null_nan.json",
        "category": "interoperability",
        "ground_truth": "Sanitization of string 'NaN' and 'null' values",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "target_confidence_min": 0.80,
        "description": "Unsanitized null strings present in telemetry."
    },
    {
        "name": "interop_duplicate_out_of_order",
        "file": "interop_duplicate_out_of_order.json",
        "category": "interoperability",
        "ground_truth": "Chronological sorting and deduplication",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "target_confidence_min": 0.80,
        "description": "Duplicate records and reverse timestamp order."
    },
    {
        "name": "interop_clock_skew",
        "file": "interop_clock_skew.json",
        "category": "interoperability",
        "ground_truth": "Clock skew detection and time window normalization",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "target_confidence_min": 0.80,
        "description": "Extreme clock offset between records."
    },
    {
        "name": "interop_malformed_json",
        "file": "interop_malformed_json.json",
        "category": "interoperability",
        "ground_truth": "Lenient parsing of single-quoted / unformatted JSON",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01"],
        "target_confidence_min": 0.70,
        "description": "Single-quoted raw JSON input."
    }
]

manifest["scenarios"].extend(interop_entries)
with open(scenarios_dir / "manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Successfully generated {len(interop_entries)} interop variants and updated manifest.")

