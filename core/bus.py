"""Inter-agent message bus for routing versioned envelopes."""

from collections import defaultdict
from typing import Callable, Dict, List, Optional
from core.envelope import AgentEnvelope, AgentRole
from storage.db import log_envelope


class MessageBus:
    """Publish-subscribe and point-to-point message bus for agent envelopes."""

    def __init__(self) -> None:
        self._subscribers: Dict[AgentRole, List[Callable[[AgentEnvelope], Optional[AgentEnvelope]]]] = defaultdict(list)
        self._audit_log: List[AgentEnvelope] = []

    def subscribe(
        self, role: AgentRole, handler: Callable[[AgentEnvelope], Optional[AgentEnvelope]]
    ) -> None:
        """Register a handler callback for envelopes addressed to role."""
        self._subscribers[role].append(handler)

    def publish(self, envelope: AgentEnvelope) -> List[AgentEnvelope]:
        """Publish an envelope to its designated recipient or broadcast."""
        self._audit_log.append(envelope)
        try:
            log_envelope(envelope)
        except Exception:
            pass

        recipient = envelope.header.recipient
        responses: List[AgentEnvelope] = []

        if recipient == AgentRole.BROADCAST:
            for role, handlers in self._subscribers.items():
                if role != envelope.header.sender:
                    for h in handlers:
                        resp = h(envelope)
                        if resp:
                            self._audit_log.append(resp)
                            responses.append(resp)
        else:
            handlers = self._subscribers.get(recipient, [])
            for h in handlers:
                resp = h(envelope)
                if resp:
                    self._audit_log.append(resp)
                    responses.append(resp)

        return responses

    def get_audit_trail(self, correlation_id: Optional[str] = None) -> List[AgentEnvelope]:
        """Retrieve recorded envelope messages, optionally filtered by correlation ID."""
        if correlation_id:
            return [e for e in self._audit_log if e.header.correlation_id == correlation_id]
        return list(self._audit_log)

    def clear(self) -> None:
        """Clear in-memory audit log and subscribers."""
        self._subscribers.clear()
        self._audit_log.clear()


# Default global bus instance
bus = MessageBus()
