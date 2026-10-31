"""Abstract base class for all specialist NetCoop AI domain agents."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    EnvelopePayload,
    MessageType,
    NetworkScope,
    ProtocolHeader,
)


class BaseAgent(ABC):
    """BaseAgent enforces isolated envelope-only input/output contracts."""

    def __init__(self, role: AgentRole, name: str) -> None:
        self.role = role
        self.name = name

    @abstractmethod
    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Process an incoming envelope and return a response envelope."""
        pass

    def create_response_envelope(
        self,
        original: AgentEnvelope,
        message_type: MessageType = MessageType.FINDING_SUBMISSION,
    ) -> AgentEnvelope:
        """Create a boilerplate envelope response addressing the orchestrator."""
        return AgentEnvelope(
            header=ProtocolHeader(
                correlation_id=original.header.correlation_id,
                sender=self.role,
                recipient=AgentRole.ORCHESTRATOR,
                schema_version=original.header.schema_version,
                message_type=message_type,
            ),
            payload=EnvelopePayload(
                scope=original.payload.scope,
                observations=[],
                hypotheses=[],
                inquiries=[],
            ),
            context={"iteration": original.context.get("iteration", 0)},
        )

