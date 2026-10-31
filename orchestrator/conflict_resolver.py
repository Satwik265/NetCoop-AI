"""Conflict resolver facade mirroring netcoop.orchestrator.conflict_resolver."""

import sys
import netcoop.orchestrator.conflict_resolver

sys.modules[__name__] = netcoop.orchestrator.conflict_resolver
from netcoop.orchestrator.conflict_resolver import ConflictResolver
