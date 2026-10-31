"""Mediator routing envelopes between specialist agents and orchestrator."""

from typing import Dict, List, Optional
from netcoop.agents.base import BaseAgent
from netcoop.agents.config_agent import ConfigAgent
from netcoop.agents.log_agent import LogAgent
from netcoop.agents.synthesizer_agent import SynthesizerAgent
from netcoop.agents.telemetry_agent import TelemetryAgent
from netcoop.agents.topology_agent import TopologyAgent
from netcoop.core.envelope import AgentEnvelope, AgentRole
from netcoop.storage.db import log_envelope


class AgentMediator:
    """Dispatches envelopes to specialist agents and preserves message audit traces."""

    def __init__(self) -> None:
        self.agents: Dict[AgentRole, BaseAgent] = {
            AgentRole.TELEMETRY_AGENT: TelemetryAgent(),
            AgentRole.TOPOLOGY_AGENT: TopologyAgent(),
            AgentRole.CONFIG_AGENT: ConfigAgent(),
            AgentRole.LOG_AGENT: LogAgent(),
            AgentRole.SYNTHESIZER_AGENT: SynthesizerAgent(),
        }

    def dispatch(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Route envelope to the designated recipient agent and record in audit log."""
        log_envelope(envelope)
        target_role = envelope.header.recipient

        agent = self.agents.get(target_role)
        if not agent:
            # Generate protocol error response if recipient is unknown
            error_resp = AgentEnvelope.create_error_response(
                original=envelope,
                error_code="UNKNOWN_RECIPIENT",
                message=f"No agent registered for role {target_role.value}",
            )
            log_envelope(error_resp)
            return error_resp

        response_envelope = agent.handle_envelope(envelope)
        log_envelope(response_envelope)
        return response_envelope

