"""Mediator facade mirroring netcoop.orchestrator.mediator."""

import sys
import netcoop.orchestrator.mediator

sys.modules[__name__] = netcoop.orchestrator.mediator
from netcoop.orchestrator.mediator import (
    AgentMediator,
    AgentRegistry,
    CircuitBreaker,
    notify_envelope_listeners,
    register_envelope_listener,
    unregister_envelope_listener,
)
