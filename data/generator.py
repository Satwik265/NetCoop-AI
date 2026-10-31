"""Deterministic, seeded synthetic network telemetry and topology generator.

Delegates to netcoop.data.generator to preserve full backward compatibility.
"""

import sys
from netcoop.data.generator import (
    DeviceType,
    DeviceStatus,
    CampusZone,
    SeverityLevel,
    NoiseShape,
    TelemetryRecord,
    SyntheticNetworkGenerator,
)

__all__ = [
    "DeviceType",
    "DeviceStatus",
    "CampusZone",
    "SeverityLevel",
    "NoiseShape",
    "TelemetryRecord",
    "SyntheticNetworkGenerator",
]
