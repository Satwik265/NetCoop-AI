"""Configuration facade mirroring netcoop.config."""

import sys
import netcoop.config

sys.modules[__name__] = netcoop.config
from netcoop.config import Settings, settings, FEATURE_MCP, FEATURE_REMEDIATION_SIM, FEATURE_RESUME, FEATURE_HITL, is_demo_mode_allowed
