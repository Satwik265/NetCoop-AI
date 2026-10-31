"""Thresholds facade mirroring netcoop.core.thresholds."""

import sys
import netcoop.core.thresholds

sys.modules[__name__] = netcoop.core.thresholds
