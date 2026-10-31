"""Data normalization, unit conversion, and clock skew alignment engine."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union


class TelemetryNormalizer:
    """Normalizes raw network metrics, converts units, and aligns timestamps."""

    # Unit conversion lookup table mapping (source_unit -> (standard_unit, multiplier))
    UNIT_CONVERSIONS: Dict[str, Tuple[str, float]] = {
        # Bandwidth to bps
        "bps": ("bps", 1.0),
        "kbps": ("bps", 1_000.0),
        "mbps": ("bps", 1_000_000.0),
        "gbps": ("bps", 1_000_000_000.0),
        # Memory/Storage to bytes
        "b": ("bytes", 1.0),
        "bytes": ("bytes", 1.0),
        "octets": ("bytes", 1.0),
        "kb": ("bytes", 1024.0),
        "mb": ("bytes", 1024.0**2),
        "gb": ("bytes", 1024.0**3),
        # Packets / Frames
        "packets": ("packets", 1.0),
        "pkts": ("packets", 1.0),
        "frames": ("packets", 1.0),
        "count": ("packets", 1.0),
        # Time to milliseconds
        "ms": ("ms", 1.0),
        "s": ("ms", 1000.0),
        "sec": ("ms", 1000.0),
        "seconds": ("ms", 1000.0),
        "us": ("ms", 0.001),
        "microseconds": ("ms", 0.001),
        "ns": ("ms", 0.000001),
        # Power
        "dbm": ("dbm", 1.0),
        # Percentage
        "percent": ("percent", 1.0),
        "ratio": ("percent", 100.0),
        # Flaps
        "flaps_per_minute": ("flaps_per_minute", 1.0),
        "flaps_per_second": ("flaps_per_minute", 60.0),
    }

    @classmethod
    def normalize_metric(
        cls, value: Union[float, int, str], raw_unit: str
    ) -> Tuple[float, str]:
        """Convert a numerical metric and raw unit into standardized SI unit.

        Returns:
            Tuple of (converted_value, standardized_unit_name)
        """
        unit_key = str(raw_unit).strip().lower()
        if unit_key not in cls.UNIT_CONVERSIONS:
            try:
                numeric_val = float(value)
                return numeric_val, unit_key
            except (ValueError, TypeError):
                return 0.0, unit_key

        standard_unit, multiplier = cls.UNIT_CONVERSIONS[unit_key]
        try:
            numeric_val = float(value)
            return round(numeric_val * multiplier, 4), standard_unit
        except (ValueError, TypeError):
            return 0.0, standard_unit

    @classmethod
    def parse_iso_timestamp(cls, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Safely parse ISO 8601 timestamps with multiple fallback formats."""
        if not timestamp_str or not isinstance(timestamp_str, str):
            return None
        cleaned = timestamp_str.strip()
        # Handle 'Z' suffix
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            pass

        # Try common fallback patterns
        patterns = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y %b %d %H:%M:%S",
        ]
        for pattern in patterns:
            try:
                dt = datetime.strptime(cleaned, pattern)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    @classmethod
    def align_timestamps(
        cls,
        events: List[Dict[str, Any]],
        timestamp_key: str = "timestamp_utc",
        max_skew_seconds: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """Sort and detect clock skews across distributed device records."""
        parsed_events = []
        for event in events:
            raw_ts = event.get(timestamp_key)
            dt = cls.parse_iso_timestamp(raw_ts)
            if dt is None:
                # Use current UTC if completely unparseable
                dt = datetime.now(timezone.utc)
            item = dict(event)
            item["_parsed_dt"] = dt
            item[timestamp_key] = dt.isoformat()
            parsed_events.append(item)

        # Sort chronologically
        parsed_events.sort(key=lambda x: x["_parsed_dt"])

        # Check for extreme clock skew
        if len(parsed_events) > 1:
            first_ts = parsed_events[0]["_parsed_dt"]
            last_ts = parsed_events[-1]["_parsed_dt"]
            total_duration = (last_ts - first_ts).total_seconds()
            for item in parsed_events:
                item["_skew_flag"] = total_duration > max_skew_seconds

        for item in parsed_events:
            item.pop("_parsed_dt", None)

        return parsed_events

    @classmethod
    def standardize_interface_name(cls, if_name: str) -> str:
        """Standardize interface abbreviations (e.g. Gi0/1 -> GigabitEthernet0/1, et-0/0/0 -> et-0/0/0)."""
        if not if_name or not isinstance(if_name, str):
            return "unknown"
        cleaned = if_name.strip()
        # Normalization map for common Cisco / Juniper / Arista abbreviations
        mappings = [
            (r"^gi([0-9/]+)$", r"GigabitEthernet\1"),
            (r"^te([0-9/]+)$", r"TenGigabitEthernet\1"),
            (r"^fa([0-9/]+)$", r"FastEthernet\1"),
            (r"^eth([0-9/]+)$", r"Ethernet\1"),
        ]
        for pattern, repl in mappings:
            cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
        return cleaned.lower()
