"""Configuration facade mirroring netcoop.config."""

import sys
import netcoop.config

sys.modules[__name__] = netcoop.config
from netcoop.config import Settings, settings
