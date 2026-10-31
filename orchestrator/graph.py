"""Orchestrator graph facade mirroring netcoop.orchestrator.graph."""

import sys
import netcoop.orchestrator.graph

sys.modules[__name__] = netcoop.orchestrator.graph
from netcoop.orchestrator.graph import (
    GraphState,
    build_diagnostic_graph,
    compiled_diagnostic_graph,
    pause_diagnosis,
    resume_diagnosis,
    run_diagnosis,
)
