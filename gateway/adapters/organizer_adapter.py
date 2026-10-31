"""Adapter mapping arbitrary hackathon organizer telemetry and Colab outputs into standard schema."""

import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from core.normalizer import TelemetryNormalizer


class OrganizerAdapter:
    """Translates external, variant, or legacy telemetry schemas into NetCoop standard formats."""

    # Field alias lookup dictionary
    FIELD_ALIASES: Dict[str, str] = {
        # Device identity & classification
        "dev": "device_id",
        "dev_id": "device_id",
        "node": "device_id",
        "node_id": "device_id",
        "hostname": "device_id",
        "device": "device_id",
        "role": "device_type",
        "type": "device_type",
        "state": "device_status",
        "status": "device_status",
        # Performance metrics
        "rtt": "latency_ms",
        "delay": "latency_ms",
        "delay_ms": "latency_ms",
        "latency": "latency_ms",
        "latency_s": "latency_s",  # special handling
        "jitter": "jitter_ms",
        "loss": "packet_loss_pct",
        "loss_pct": "packet_loss_pct",
        "packet_loss": "packet_loss_pct",
        "drop_rate": "packet_loss_pct",
        "tput": "throughput_mbps",
        "throughput": "throughput_mbps",
        "throughput_kbps": "throughput_kbps",
        "bw": "bandwidth_mbps",
        "bandwidth": "bandwidth_mbps",
        "bandwidth_kbps": "bandwidth_kbps",
        "util": "link_utilization_pct",
        "utilization": "link_utilization_pct",
        "link_util": "link_utilization_pct",
        "cpu": "cpu_pct",
        "mem": "memory_pct",
        "memory": "memory_pct",
        # Error and drop counters
        "drops": "queue_drops",
        "packet_drops": "queue_drops",
        "errors": "interface_errors",
        "crc_errors": "interface_errors",
        "fcs_errors": "interface_errors",
        "flaps": "link_flaps",
        "transitions": "link_flaps",
        # Wireless & Application
        "rssi": "wifi_rssi_dbm",
        "signal_dbm": "wifi_rssi_dbm",
        "retx": "wifi_retransmission_pct",
        "retransmissions": "wifi_retransmission_pct",
        "dns_ms": "dns_resolution_ms",
        "dns_latency": "dns_resolution_ms",
        "dns_rtt": "dns_resolution_ms",
        "dns_fail": "dns_failure_pct",
        "dhcp_fail": "dhcp_failure_pct",
    }

    @classmethod
    def clean_numeric_value(cls, val: Any) -> Optional[float]:
        """Convert messy or NaN/null numbers to clean float or None."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            if math.isnan(val) or math.isinf(val):
                return None
            return float(val)
        if isinstance(val, str):
            cleaned = val.strip().lower()
            if cleaned in ("nan", "null", "none", "", "n/a", "undefined"):
                return None
            try:
                num = float(cleaned)
                if math.isnan(num) or math.isinf(num):
                    return None
                return num
            except ValueError:
                return None
        return None

    @classmethod
    def adapt_record(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single arbitrary record into standard field schema."""
        mapped: Dict[str, Any] = {}

        # 1. Map aliases
        for k, v in raw.items():
            norm_key = cls.FIELD_ALIASES.get(k.lower().strip(), k)
            mapped[norm_key] = v

        # 2. Extract or infer device_id and device_type
        device_id = str(mapped.get("device_id") or "unknown_device")
        dev_type = str(mapped.get("device_type") or "host").lower()
        if dev_type not in ("router", "switch", "access_point", "host"):
            dev_type = "host"

        device_status = str(mapped.get("device_status") or "online").lower()
        if device_status not in ("online", "degraded", "offline"):
            device_status = "online"

        # 3. Handle seconds vs ms for latency
        lat = cls.clean_numeric_value(mapped.get("latency_ms"))
        if lat is None and "latency_s" in mapped:
            lat_s = cls.clean_numeric_value(mapped.get("latency_s"))
            if lat_s is not None:
                lat = round(lat_s * 1000.0, 2)
        elif lat is not None and lat < 1.0 and "latency" in raw and not str(raw.get("latency")).endswith("ms"):
            # If latency was e.g. 0.045 with no unit, treat as seconds -> 45ms
            lat = round(lat * 1000.0, 2)
        if lat is None:
            lat = 5.0

        # 4. Handle kbps vs Mbps for throughput
        tput = cls.clean_numeric_value(mapped.get("throughput_mbps"))
        if tput is None and "throughput_kbps" in mapped:
            tput_k = cls.clean_numeric_value(mapped.get("throughput_kbps"))
            if tput_k is not None:
                tput = round(tput_k / 1000.0, 2)
        if tput is None:
            tput = 100.0

        bw = cls.clean_numeric_value(mapped.get("bandwidth_mbps"))
        if bw is None and "bandwidth_kbps" in mapped:
            bw_k = cls.clean_numeric_value(mapped.get("bandwidth_kbps"))
            if bw_k is not None:
                bw = round(bw_k / 1000.0, 2)
        if bw is None:
            bw = 1000.0

        # Timestamp alignment
        raw_ts = mapped.get("timestamp") or mapped.get("timestamp_utc") or mapped.get("time")
        parsed_dt = TelemetryNormalizer.parse_iso_timestamp(str(raw_ts) if raw_ts else None)
        if not parsed_dt:
            parsed_dt = datetime.now(timezone.utc)
        timestamp_str = parsed_dt.isoformat()

        # Build clean record
        record = {
            "timestamp": timestamp_str,
            "device_id": device_id,
            "device_type": dev_type,
            "device_status": device_status,
            "latency_ms": lat,
            "jitter_ms": cls.clean_numeric_value(mapped.get("jitter_ms")) or 1.0,
            "packet_loss_pct": cls.clean_numeric_value(mapped.get("packet_loss_pct")) or 0.0,
            "throughput_mbps": tput,
            "bandwidth_mbps": bw,
            "link_utilization_pct": cls.clean_numeric_value(mapped.get("link_utilization_pct")) or 20.0,
            "cpu_pct": cls.clean_numeric_value(mapped.get("cpu_pct")) or 25.0,
            "memory_pct": cls.clean_numeric_value(mapped.get("memory_pct")) or 35.0,
            "queue_drops": int(cls.clean_numeric_value(mapped.get("queue_drops")) or 0),
            "interface_errors": int(cls.clean_numeric_value(mapped.get("interface_errors")) or 0),
            "link_flaps": int(cls.clean_numeric_value(mapped.get("link_flaps")) or 0),
            "wifi_rssi_dbm": cls.clean_numeric_value(mapped.get("wifi_rssi_dbm")),
            "wifi_retransmission_pct": cls.clean_numeric_value(mapped.get("wifi_retransmission_pct")),
            "dns_resolution_ms": cls.clean_numeric_value(mapped.get("dns_resolution_ms")),
            "dns_failure_pct": cls.clean_numeric_value(mapped.get("dns_failure_pct")),
            "dhcp_failure_pct": cls.clean_numeric_value(mapped.get("dhcp_failure_pct")),
        }
        return record

    @classmethod
    def adapt_dataset(cls, raw_data: Union[str, Dict[str, Any], List[Any]]) -> Dict[str, Any]:
        """Adapt a full incident or telemetry dataset into NetCoop format.

        Handles:
          - Raw JSON strings (with malformed tolerance)
          - Bare lists of records
          - Dictionaries with differing envelope conventions
          - Deduplication and chronological sorting
        """
        # Parse JSON string if needed
        data: Any = raw_data
        if isinstance(raw_data, str):
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                # Attempt tolerant regex parse for single quotes or unquoted keys
                sanitized = re.sub(r"'", '"', raw_data)
                try:
                    data = json.loads(sanitized)
                except Exception:
                    data = {"telemetry": []}

        # Extract telemetry array
        raw_telemetry: List[Any] = []
        if isinstance(data, list):
            raw_telemetry = data
            container = {}
        elif isinstance(data, dict):
            raw_telemetry = data.get("telemetry") or data.get("records") or data.get("events") or []
            container = data
        else:
            raw_telemetry = []
            container = {}

        adapted_records: List[Dict[str, Any]] = []
        for item in raw_telemetry:
            if isinstance(item, dict):
                adapted_records.append(cls.adapt_record(item))

        # Deduplicate and sort chronologically
        seen_keys = set()
        unique_records = []
        for r in adapted_records:
            key = (r["device_id"], r["timestamp"])
            if key not in seen_keys:
                seen_keys.add(key)
                unique_records.append(r)

        unique_records.sort(key=lambda x: x["timestamp"])

        # Detect clock skew
        clock_skew_flag = False
        if len(unique_records) > 1:
            try:
                t0 = datetime.fromisoformat(unique_records[0]["timestamp"])
                t1 = datetime.fromisoformat(unique_records[-1]["timestamp"])
                if abs((t1 - t0).total_seconds()) > 600.0:  # >10 min difference
                    clock_skew_flag = True
            except Exception:
                pass

        # Preserve or construct topology
        topology = container.get("topology") or {
            "nodes": [
                {"id": r["device_id"], "role": r["device_type"], "zone": "campus"}
                for r in unique_records
            ],
            "links": [],
        }

        incident_id = container.get("incident_id") or "inc-adapted-001"
        network_id = container.get("network_id") or "adapted-network"

        return {
            "incident_id": incident_id,
            "network_id": network_id,
            "schema_version": "1.0.0",
            "clock_skew_detected": clock_skew_flag,
            "topology": topology,
            "telemetry": unique_records,
            "configurations": container.get("configurations", []),
            "logs": container.get("logs", []),
        }
