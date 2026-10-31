"""Adapter mapping arbitrary hackathon organizer telemetry and Colab outputs into standard schema."""

import json
import math
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from core.normalizer import TelemetryNormalizer


class TypedValidationError(BaseModel):
    """Typed error for schema validation anomalies."""

    code: str
    field: Optional[str] = None
    explanation: str
    suggested_fix: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "field": self.field,
            "explanation": self.explanation,
            "suggested_fix": self.suggested_fix,
        }


class OrganizerAdapter:
    """Translates external, organizer Colab, and legacy telemetry schemas into NetCoop standard formats."""

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
        "latency_s": "latency_s",
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
        "cpu_utilization_pct": "cpu_pct",
        "cpu_utilization": "cpu_pct",
        "cpu_util": "cpu_pct",
        "cpu": "cpu_pct",
        "mem": "memory_pct",
        "memory": "memory_pct",
        "memory_utilization_pct": "memory_pct",
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

    CANONICAL_FIELDS = [
        "timestamp",
        "device_id",
        "device_type",
        "device_status",
        "latency_ms",
        "jitter_ms",
        "packet_loss_pct",
        "throughput_mbps",
        "bandwidth_mbps",
        "link_utilization_pct",
        "cpu_pct",
        "memory_pct",
        "queue_drops",
        "interface_errors",
        "link_flaps",
        "wifi_rssi_dbm",
        "wifi_retransmission_pct",
        "dns_resolution_ms",
        "dns_failure_pct",
        "dhcp_failure_pct",
    ]

    STATUS_MAP: Dict[str, str] = {
        "healthy": "online",
        "warning": "degraded",
        "critical": "degraded",
        "online": "online",
        "degraded": "degraded",
        "offline": "offline",
    }

    @classmethod
    def clean_numeric_value(
        cls,
        val: Any,
        field_name: str = "",
        errors: Optional[List[TypedValidationError]] = None,
        quarantined: Optional[List[str]] = None,
        allow_negative: bool = False,
        is_percentage: bool = False,
    ) -> Optional[float]:
        """Convert messy or NaN/null numbers to clean float or None with typed error tracking."""
        if val is None:
            return None
        
        num: Optional[float] = None
        if isinstance(val, (int, float)):
            if math.isnan(val) or math.isinf(val):
                if errors is not None:
                    errors.append(
                        TypedValidationError(
                            code="ERR_NAN_INF",
                            field=field_name,
                            explanation=f"Field '{field_name}' contains NaN or infinite value: {val}",
                            suggested_fix="Sanitize metric collectors to emit null or finite floating points.",
                        )
                    )
                if quarantined is not None and field_name:
                    quarantined.append(field_name)
                return None
            num = float(val)
        elif isinstance(val, str):
            cleaned = val.strip().lower()
            if cleaned in ("nan", "null", "none", "", "n/a", "undefined"):
                if cleaned in ("nan", "null") and errors is not None:
                    errors.append(
                        TypedValidationError(
                            code="ERR_NAN_INF" if cleaned == "nan" else "ERR_WRONG_TYPE",
                            field=field_name,
                            explanation=f"Field '{field_name}' received unparsed string representation: '{val}'",
                            suggested_fix="Send numeric floats or null primitives instead of string sentinels.",
                        )
                    )
                return None
            try:
                parsed = float(cleaned)
                if math.isnan(parsed) or math.isinf(parsed):
                    if errors is not None:
                        errors.append(
                            TypedValidationError(
                                code="ERR_NAN_INF",
                                field=field_name,
                                explanation=f"Field '{field_name}' parsed to NaN or Inf.",
                                suggested_fix="Ensure valid finite float values.",
                            )
                        )
                    if quarantined is not None and field_name:
                        quarantined.append(field_name)
                    return None
                num = parsed
            except ValueError:
                if errors is not None:
                    errors.append(
                        TypedValidationError(
                            code="ERR_WRONG_TYPE",
                            field=field_name,
                            explanation=f"Field '{field_name}' expects numeric value but received non-numeric string: '{val}'",
                            suggested_fix="Ensure metric values are numerical numbers.",
                        )
                    )
                if quarantined is not None and field_name:
                    quarantined.append(field_name)
                return None
        else:
            if errors is not None:
                errors.append(
                    TypedValidationError(
                        code="ERR_WRONG_TYPE",
                        field=field_name,
                        explanation=f"Field '{field_name}' received unexpected type: {type(val).__name__}",
                        suggested_fix="Provide integer or float numeric types.",
                    )
                )
            if quarantined is not None and field_name:
                quarantined.append(field_name)
            return None

        # Check negative constraint
        if num is not None and not allow_negative and num < 0.0:
            if errors is not None:
                errors.append(
                    TypedValidationError(
                        code="ERR_NEGATIVE_VALUE",
                        field=field_name,
                        explanation=f"Field '{field_name}' must be non-negative, received: {num}",
                        suggested_fix="Clamp counters or check collection offset.",
                    )
                )
            num = 0.0

        # Check percentage bounds
        if num is not None and is_percentage and (num < 0.0 or num > 100.0):
            if errors is not None:
                errors.append(
                    TypedValidationError(
                        code="ERR_OUT_OF_RANGE_PERCENT",
                        field=field_name,
                        explanation=f"Percentage field '{field_name}' out of bounds [0.0, 100.0]: {num}",
                        suggested_fix="Normalize percentage values to scale [0.0, 100.0].",
                    )
                )
            num = max(0.0, min(100.0, num))

        return num

    @classmethod
    def adapt_record(
        cls,
        raw: Dict[str, Any],
        source_errors: Optional[List[TypedValidationError]] = None,
        source_transformations: Optional[List[str]] = None,
        quarantined_fields: Optional[List[str]] = None,
        is_organizer_format: bool = False,
    ) -> Dict[str, Any]:
        """Normalize a single arbitrary or organizer-format record into canonical schema."""
        mapped: Dict[str, Any] = {}
        transformations: List[str] = source_transformations if source_transformations is not None else []
        errors: List[TypedValidationError] = source_errors if source_errors is not None else []
        quarantined: List[str] = quarantined_fields if quarantined_fields is not None else []

        # 1. Flatten nested metrics object if present (Organizer Format)
        merged_raw: Dict[str, Any] = {}
        if "metrics" in raw and isinstance(raw["metrics"], dict):
            if "flattening" not in transformations:
                transformations.append("flattening")
            for mk, mv in raw["metrics"].items():
                merged_raw[mk] = mv
            for rk, rv in raw.items():
                if rk != "metrics":
                    merged_raw[rk] = rv
        elif "metrics" in raw and raw["metrics"] is None:
            errors.append(
                TypedValidationError(
                    code="ERR_MISSING_FIELD",
                    field="metrics",
                    explanation="Nested metrics object was null or missing.",
                    suggested_fix="Supply dictionary under 'metrics' key in organizer format.",
                )
            )
            for rk, rv in raw.items():
                if rk != "metrics":
                    merged_raw[rk] = rv
        else:
            merged_raw = dict(raw)

        # 2. Map aliases through alias table
        for k, v in merged_raw.items():
            k_clean = str(k).lower().strip()
            if k_clean in cls.FIELD_ALIASES:
                norm_key = cls.FIELD_ALIASES[k_clean]
                if norm_key != k_clean and "alias_mapping" not in transformations:
                    transformations.append("alias_mapping")
                mapped[norm_key] = v
            else:
                mapped[k] = v

        # 3. Extract or infer device_id
        raw_dev = mapped.get("device_id")
        if not raw_dev or str(raw_dev).strip() == "" or str(raw_dev).lower() in ("null", "none"):
            device_id = "unknown_device"
            errors.append(
                TypedValidationError(
                    code="ERR_UNKNOWN_DEVICE",
                    field="device_id",
                    explanation="Device identifier missing or null.",
                    suggested_fix="Specify a non-empty string device_id.",
                )
            )
        else:
            device_id = str(raw_dev).strip()

        # 4. Infer device_type (switches for SW_CAMPUS_n)
        dev_type = str(mapped.get("device_type") or "").lower().strip()
        if not dev_type or dev_type not in ("router", "switch", "access_point", "host"):
            if re.match(r"^sw_campus.*", device_id.lower()) or "sw" in device_id.lower():
                dev_type = "switch"
            elif re.match(r"^ap.*", device_id.lower()) or "wifi" in device_id.lower():
                dev_type = "access_point"
            elif re.match(r"^rtr.*", device_id.lower()) or "core" in device_id.lower() or "router" in device_id.lower():
                dev_type = "router"
            else:
                dev_type = "host"

        # 5. Map device status
        raw_status = mapped.get("device_status")
        if raw_status is None:
            device_status = "online"
            errors.append(
                TypedValidationError(
                    code="ERR_MISSING_FIELD",
                    field="device_status",
                    explanation="Status was null or omitted.",
                    suggested_fix="Provide status: Healthy, Warning, or Critical.",
                )
            )
        else:
            st_clean = str(raw_status).lower().strip()
            if st_clean in cls.STATUS_MAP:
                device_status = cls.STATUS_MAP[st_clean]
                if "status_mapping" not in transformations:
                    transformations.append("status_mapping")
            else:
                device_status = "online"

        # 6. Parse and normalize timestamp (UTC)
        raw_ts = mapped.get("timestamp") or mapped.get("timestamp_utc") or mapped.get("time")
        parsed_dt = None
        if raw_ts:
            parsed_dt = TelemetryNormalizer.parse_iso_timestamp(str(raw_ts))
            if parsed_dt:
                if "timestamp_parsing" not in transformations:
                    transformations.append("timestamp_parsing")
            else:
                errors.append(
                    TypedValidationError(
                        code="ERR_WRONG_TYPE",
                        field="timestamp",
                        explanation=f"Could not parse timestamp format: '{raw_ts}'",
                        suggested_fix="Use ISO 8601 UTC format (e.g. 2026-10-31T12:00:00Z).",
                    )
                )
        if not parsed_dt:
            parsed_dt = datetime.now(timezone.utc)
            if not raw_ts:
                errors.append(
                    TypedValidationError(
                        code="ERR_MISSING_FIELD",
                        field="timestamp",
                        explanation="Timestamp field was absent.",
                        suggested_fix="Include timestamp in ISO 8601 UTC.",
                    )
                )
        timestamp_str = parsed_dt.isoformat()

        # 7. Latency: seconds vs ms
        lat = None
        if "latency_s" in mapped:
            lat_s = cls.clean_numeric_value(
                mapped.get("latency_s"), "latency_s", errors, quarantined, allow_negative=False
            )
            if lat_s is not None:
                lat = round(lat_s * 1000.0, 2)
                if "unit_conversion" not in transformations:
                    transformations.append("unit_conversion")
        elif "latency_ms" in mapped:
            lat = cls.clean_numeric_value(
                mapped.get("latency_ms"), "latency_ms", errors, quarantined, allow_negative=False
            )
            if lat is not None and lat < 1.0 and "latency" in merged_raw and not str(merged_raw.get("latency")).endswith("ms"):
                lat = round(lat * 1000.0, 2)
                if "unit_conversion" not in transformations:
                    transformations.append("unit_conversion")
        elif not is_organizer_format:
            lat = 5.0

        # 8. Throughput & Bandwidth: kbps vs Mbps
        tput = None
        if "throughput_kbps" in mapped:
            tput_k = cls.clean_numeric_value(
                mapped.get("throughput_kbps"), "throughput_kbps", errors, quarantined, allow_negative=False
            )
            if tput_k is not None:
                tput = round(tput_k / 1000.0, 2)
                if "unit_conversion" not in transformations:
                    transformations.append("unit_conversion")
        elif "throughput_mbps" in mapped:
            tput = cls.clean_numeric_value(
                mapped.get("throughput_mbps"), "throughput_mbps", errors, quarantined, allow_negative=False
            )
        elif not is_organizer_format:
            tput = 100.0

        bw = None
        if "bandwidth_kbps" in mapped:
            bw_k = cls.clean_numeric_value(
                mapped.get("bandwidth_kbps"), "bandwidth_kbps", errors, quarantined, allow_negative=False
            )
            if bw_k is not None:
                bw = round(bw_k / 1000.0, 2)
                if "unit_conversion" not in transformations:
                    transformations.append("unit_conversion")
        elif "bandwidth_mbps" in mapped:
            bw = cls.clean_numeric_value(
                mapped.get("bandwidth_mbps"), "bandwidth_mbps", errors, quarantined, allow_negative=False
            )
        elif not is_organizer_format:
            bw = 1000.0

        # Other metrics: if absent in raw, leave absent (None)
        jit = None
        if "jitter_ms" in mapped:
            jit = cls.clean_numeric_value(
                mapped.get("jitter_ms"), "jitter_ms", errors, quarantined, allow_negative=False
            )
            if jit is None and not is_organizer_format:
                jit = 1.0

        loss = None
        if "packet_loss_pct" in mapped:
            loss = cls.clean_numeric_value(
                mapped.get("packet_loss_pct"), "packet_loss_pct", errors, quarantined, allow_negative=False, is_percentage=True
            )

        util = None
        if "link_utilization_pct" in mapped:
            util = cls.clean_numeric_value(
                mapped.get("link_utilization_pct"), "link_utilization_pct", errors, quarantined, allow_negative=False, is_percentage=True
            )

        cpu = None
        if "cpu_pct" in mapped:
            cpu = cls.clean_numeric_value(
                mapped.get("cpu_pct"), "cpu_pct", errors, quarantined, allow_negative=False, is_percentage=True
            )

        mem = None
        if "memory_pct" in mapped:
            mem = cls.clean_numeric_value(
                mapped.get("memory_pct"), "memory_pct", errors, quarantined, allow_negative=False, is_percentage=True
            )

        q_drops = None
        if "queue_drops" in mapped:
            raw_q = cls.clean_numeric_value(
                mapped.get("queue_drops"), "queue_drops", errors, quarantined, allow_negative=False
            )
            q_drops = int(raw_q) if raw_q is not None else None

        if_errs = None
        if "interface_errors" in mapped:
            raw_errs = cls.clean_numeric_value(
                mapped.get("interface_errors"), "interface_errors", errors, quarantined, allow_negative=False
            )
            if_errs = int(raw_errs) if raw_errs is not None else None

        flaps = None
        if "link_flaps" in mapped:
            raw_flaps = cls.clean_numeric_value(
                mapped.get("link_flaps"), "link_flaps", errors, quarantined, allow_negative=False
            )
            flaps = int(raw_flaps) if raw_flaps is not None else None

        rssi = cls.clean_numeric_value(
            mapped.get("wifi_rssi_dbm"), "wifi_rssi_dbm", errors, quarantined, allow_negative=True
        ) if "wifi_rssi_dbm" in mapped else None

        wifi_retx = cls.clean_numeric_value(
            mapped.get("wifi_retransmission_pct"), "wifi_retransmission_pct", errors, quarantined, allow_negative=False, is_percentage=True
        ) if "wifi_retransmission_pct" in mapped else None

        dns_res = cls.clean_numeric_value(
            mapped.get("dns_resolution_ms"), "dns_resolution_ms", errors, quarantined, allow_negative=False
        ) if "dns_resolution_ms" in mapped else None

        dns_fail = cls.clean_numeric_value(
            mapped.get("dns_failure_pct"), "dns_failure_pct", errors, quarantined, allow_negative=False, is_percentage=True
        ) if "dns_failure_pct" in mapped else None

        dhcp_fail = cls.clean_numeric_value(
            mapped.get("dhcp_failure_pct"), "dhcp_failure_pct", errors, quarantined, allow_negative=False, is_percentage=True
        ) if "dhcp_failure_pct" in mapped else None

        record: Dict[str, Any] = {
            "timestamp": timestamp_str,
            "device_id": device_id,
            "device_type": dev_type,
            "device_status": device_status,
            "latency_ms": lat,
            "jitter_ms": jit,
            "packet_loss_pct": loss,
            "throughput_mbps": tput,
            "bandwidth_mbps": bw,
            "link_utilization_pct": util,
            "cpu_pct": cpu,
            "memory_pct": mem,
            "queue_drops": q_drops,
            "interface_errors": if_errs,
            "link_flaps": flaps,
            "wifi_rssi_dbm": rssi,
            "wifi_retransmission_pct": wifi_retx,
            "dns_resolution_ms": dns_res,
            "dns_failure_pct": dns_fail,
            "dhcp_failure_pct": dhcp_fail,
        }
        return record

    @classmethod
    def detect_format(cls, raw: Any) -> str:
        """Auto-detect whether input data conforms to organizer format, canonical, or unknown."""
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return cls.detect_format(parsed)
            except Exception:
                if "'" in raw and "metrics" in raw:
                    return "organizer"
                return "unknown"

        if isinstance(raw, dict):
            if "metrics" in raw or ("status" in raw and raw["status"] in ("Healthy", "Warning", "Critical")):
                return "organizer"
            if "telemetry" in raw and isinstance(raw["telemetry"], list):
                if raw["telemetry"] and any("metrics" in item for item in raw["telemetry"] if isinstance(item, dict)):
                    return "organizer"
                return "canonical"
            if "incident_id" in raw and "topology" in raw:
                return "canonical"

        if isinstance(raw, list):
            if any(isinstance(x, dict) and ("metrics" in x or x.get("status") in ("Healthy", "Warning", "Critical")) for x in raw):
                return "organizer"
            return "canonical"

        return "unknown"

    @classmethod
    def adapt_dataset(cls, raw_data: Union[str, Dict[str, Any], List[Any]]) -> Dict[str, Any]:
        """Adapt a full incident or telemetry dataset into NetCoop format with data quality scoring."""
        all_validation_errors: List[TypedValidationError] = []
        global_transformations: List[str] = []

        # 1. Parse JSON if string
        data: Any = raw_data
        if isinstance(raw_data, str):
            clean_str = raw_data.strip()
            if not clean_str:
                all_validation_errors.append(
                    TypedValidationError(
                        code="ERR_EMPTY_FILE",
                        explanation="Input payload was an empty string.",
                        suggested_fix="Provide valid JSON telemetry content.",
                    )
                )
                data = {"telemetry": []}
            else:
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    # Attempt tolerant parse for single quotes or Python syntax
                    all_validation_errors.append(
                        TypedValidationError(
                            code="ERR_MALFORMED_JSON",
                            explanation="Raw JSON parsing failed, attempting tolerant single-quote sanitization.",
                            suggested_fix="Validate JSON formatting with RFC 8259 compliance.",
                        )
                    )
                    sanitized = re.sub(r"'", '"', raw_data)
                    sanitized = re.sub(r"\bNone\b", "null", sanitized)
                    sanitized = re.sub(r"\bTrue\b", "true", sanitized)
                    sanitized = re.sub(r"\bFalse\b", "false", sanitized)
                    try:
                        data = json.loads(sanitized)
                    except Exception as err:
                        all_validation_errors.append(
                            TypedValidationError(
                                code="ERR_MALFORMED_JSON",
                                explanation=f"Unrecoverable JSON syntax error: {str(err)}",
                                suggested_fix="Check brackets and quotes in input payload.",
                            )
                        )
                        data = {"telemetry": []}

        # 2. Check empty structures
        if isinstance(data, (dict, list)) and len(data) == 0:
            all_validation_errors.append(
                TypedValidationError(
                    code="ERR_EMPTY_FILE",
                    explanation="Input container is empty.",
                    suggested_fix="Provide telemetry records or incident object.",
                )
            )

        # 3. Detect format
        format_detected = cls.detect_format(data)
        is_organizer = (format_detected == "organizer")

        # 4. Extract raw telemetry records
        raw_telemetry: List[Any] = []
        container: Dict[str, Any] = {}
        if isinstance(data, list):
            raw_telemetry = data
        elif isinstance(data, dict):
            raw_telemetry = data.get("telemetry") or data.get("records") or data.get("events") or []
            if not raw_telemetry and ("metrics" in data or "device_id" in data or "status" in data):
                # Single snapshot organizer record at the root
                raw_telemetry = [data]
            container = data
        else:
            raw_telemetry = []

        # 5. Schema version check
        schema_version = str(container.get("schema_version", "1.0.0"))
        if not schema_version.startswith("1."):
            all_validation_errors.append(
                TypedValidationError(
                    code="ERR_UNSUPPORTED_SCHEMA_VERSION",
                    field="schema_version",
                    explanation=f"Schema version '{schema_version}' diverges from expected 1.x.x.",
                    suggested_fix="Migrate schema to 1.0.0 standard.",
                )
            )

        # 6. Adapt each record and track per-source quality
        adapted_records: List[Dict[str, Any]] = []
        per_source_quality: Dict[str, Dict[str, Any]] = {}

        for item in raw_telemetry:
            if not isinstance(item, dict):
                all_validation_errors.append(
                    TypedValidationError(
                        code="ERR_WRONG_TYPE",
                        explanation=f"Expected telemetry record dictionary, received: {type(item).__name__}",
                        suggested_fix="Format each record as a JSON object.",
                    )
                )
                continue

            rec_errors: List[TypedValidationError] = []
            rec_transformations: List[str] = []
            rec_quarantined: List[str] = []

            adapted = cls.adapt_record(
                item,
                source_errors=rec_errors,
                source_transformations=rec_transformations,
                quarantined_fields=rec_quarantined,
                is_organizer_format=is_organizer,
            )
            adapted_records.append(adapted)

            # Record per-source stats
            src = adapted["device_id"]
            if src not in per_source_quality:
                per_source_quality[src] = {
                    "record_count": 0,
                    "transformations_applied": set(),
                    "quarantined_fields": set(),
                    "dropped_fields": set(),
                    "missing_fields": set(),
                    "error_count": 0,
                }
            per_source_quality[src]["record_count"] += 1
            per_source_quality[src]["transformations_applied"].update(rec_transformations)
            per_source_quality[src]["quarantined_fields"].update(rec_quarantined)
            per_source_quality[src]["error_count"] += len(rec_errors)

            # Check absent canonical metrics
            for cf in cls.CANONICAL_FIELDS:
                if adapted.get(cf) is None and cf not in ("wifi_rssi_dbm", "wifi_retransmission_pct", "dns_resolution_ms", "dns_failure_pct", "dhcp_failure_pct"):
                    per_source_quality[src]["missing_fields"].add(cf)

            for t in rec_transformations:
                if t not in global_transformations:
                    global_transformations.append(t)
            all_validation_errors.extend(rec_errors)

        # 7. Deduplicate and detect out-of-order timestamps
        seen_keys = set()
        unique_records = []
        out_of_order_flag = False
        duplicate_count = 0
        last_ts = None

        for r in adapted_records:
            key = (r["device_id"], r["timestamp"])
            if key in seen_keys:
                duplicate_count += 1
                all_validation_errors.append(
                    TypedValidationError(
                        code="ERR_DUPLICATE_TIMESTAMP",
                        field="timestamp",
                        explanation=f"Duplicate observation for device '{r['device_id']}' at timestamp '{r['timestamp']}'.",
                        suggested_fix="Ensure deduplicated stream ingestion.",
                    )
                )
                continue
            seen_keys.add(key)

            if last_ts and r["timestamp"] < last_ts:
                out_of_order_flag = True
            last_ts = r["timestamp"]
            unique_records.append(r)

        if out_of_order_flag:
            all_validation_errors.append(
                TypedValidationError(
                    code="ERR_OUT_OF_ORDER_TIMESTAMP",
                    field="timestamp",
                    explanation="Telemetry records were received out of chronological order.",
                    suggested_fix="Sort records by UTC timestamp prior to dispatch.",
                )
            )

        unique_records.sort(key=lambda x: x["timestamp"])

        # 8. Check clock skew & stale timestamps
        clock_skew_flag = False
        if len(unique_records) > 1:
            try:
                t0 = datetime.fromisoformat(unique_records[0]["timestamp"])
                t1 = datetime.fromisoformat(unique_records[-1]["timestamp"])
                skew_sec = abs((t1 - t0).total_seconds())
                if skew_sec > 600.0:  # > 10 min
                    clock_skew_flag = True
                    all_validation_errors.append(
                        TypedValidationError(
                            code="ERR_STALE_TIMESTAMP",
                            field="timestamp",
                            explanation=f"Clock skew of {skew_sec:.1f}s exceeds allowable 600s boundary.",
                            suggested_fix="Synchronize device clocks with NTP.",
                        )
                    )
            except Exception:
                pass

        # 9. Compute per-source and overall data quality score
        per_source_final: Dict[str, Any] = {}
        total_source_score = 0.0
        num_sources = max(1, len(per_source_quality))

        for src, sq in per_source_quality.items():
            # Scoring logic: 1.0 baseline - penalties
            penalty = 0.0
            penalty += len(sq["quarantined_fields"]) * 0.1
            penalty += len(sq["missing_fields"]) * 0.05
            penalty += sq["error_count"] * 0.05
            if clock_skew_flag:
                penalty += 0.1
            src_score = round(max(0.0, min(1.0, 1.0 - penalty)), 3)
            total_source_score += src_score

            per_source_final[src] = {
                "score": src_score,
                "record_count": sq["record_count"],
                "transformations_applied": sorted(list(sq["transformations_applied"])),
                "quarantined_fields": sorted(list(sq["quarantined_fields"])),
                "dropped_fields": sorted(list(sq["dropped_fields"])),
                "missing_fields": sorted(list(sq["missing_fields"])),
            }

        overall_quality_score = round(total_source_score / num_sources, 3)

        # 10. Group single snapshots into per-device windows when multiple points exist
        device_windows: Dict[str, List[Dict[str, Any]]] = {}
        for r in unique_records:
            d_id = r["device_id"]
            if d_id not in device_windows:
                device_windows[d_id] = []
            device_windows[d_id].append(r)

        # 11. Preserve or construct topology
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
            "detected_format": format_detected,
            "clock_skew_detected": clock_skew_flag,
            "record_count": len(unique_records),
            "data_quality": {
                "overall_score": overall_quality_score,
                "transformations_applied": sorted(global_transformations),
                "validation_errors": [e.to_dict() for e in all_validation_errors],
                "per_source": per_source_final,
            },
            "windows": {k: len(v) for k, v in device_windows.items()},
            "topology": topology,
            "telemetry": unique_records,
            "configurations": container.get("configurations", []),
            "logs": container.get("logs", []),
        }
