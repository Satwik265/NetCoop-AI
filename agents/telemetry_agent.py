"""Telemetry agent facade mirroring netcoop.agents.telemetry_agent."""

import sys
import netcoop.agents.telemetry_agent

sys.modules[__name__] = netcoop.agents.telemetry_agent
from netcoop.agents.telemetry_agent import TelemetryAgent
