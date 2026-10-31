"""Correlation facade mirroring netcoop.core.correlation."""

import sys
import netcoop.core.correlation

sys.modules[__name__] = netcoop.core.correlation
from netcoop.core.correlation import OfflineCorrelationEngine
