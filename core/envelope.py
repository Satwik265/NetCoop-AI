"""Protocol envelope models and definitions for NetCoop AI."""

import sys
import netcoop.core.envelope

# Ensure module singleton identity across both core.envelope and netcoop.core.envelope
sys.modules[__name__] = netcoop.core.envelope
