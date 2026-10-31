"""Signatures facade mirroring netcoop.core.signatures."""

import sys
import netcoop.core.signatures

sys.modules[__name__] = netcoop.core.signatures
