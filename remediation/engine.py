"""Simulated remediation execution engine facade mirroring netcoop.remediation.engine."""

import sys
import netcoop.remediation.engine

sys.modules[__name__] = netcoop.remediation.engine
from netcoop.remediation.engine import (
    NetworkCallBlockedError,
    RemediationEngine,
    network_sandbox_guard,
)

__all__ = [
    "NetworkCallBlockedError",
    "RemediationEngine",
    "network_sandbox_guard",
]
