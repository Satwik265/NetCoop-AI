"""Mediator routing envelopes between specialist agents and orchestrator via HTTP microservices."""

import logging
from typing import Callable, Dict, List, Optional
import httpx

from core.config import settings
from core.envelope import AgentEnvelope, AgentRole
from agents.base import BaseAgent
from agents.config_agent import ConfigAgent
from agents.log_agent import LogAgent
from agents.synthesizer_agent import SynthesizerAgent
from agents.telemetry_agent import TelemetryAgent
from agents.topology_agent import TopologyAgent
from storage.db import log_envelope

logger = logging.getLogger(__name__)

# Global registry of envelope listeners (e.g. WebSocket streamers)
_envelope_listeners: List[Callable[[AgentEnvelope], None]] = []


def register_envelope_listener(callback: Callable[[AgentEnvelope], None]) -> None:
    """Register an asynchronous or synchronous listener for dispatched envelopes."""
    if callback not in _envelope_listeners:
        _envelope_listeners.append(callback)


def unregister_envelope_listener(callback: Callable[[AgentEnvelope], None]) -> None:
    """Unregister an envelope listener."""
    if callback in _envelope_listeners:
        _envelope_listeners.remove(callback)


def notify_envelope_listeners(envelope: AgentEnvelope) -> None:
    """Broadcast an envelope to all registered listeners."""
    for listener in _envelope_listeners:
        try:
            listener(envelope)
        except Exception as e:
            logger.debug(f"Envelope listener notification error: {e}")


class AgentMediator:
    """Dispatches envelopes to specialist agents over HTTP and preserves message audit traces."""

    def __init__(self, mode: Optional[str] = None) -> None:
        self.mode = mode or settings.agents_mode
        self._in_process_agents: Dict[AgentRole, BaseAgent] = {
            AgentRole.TELEMETRY_AGENT: TelemetryAgent(),
            AgentRole.TOPOLOGY_AGENT: TopologyAgent(),
            AgentRole.CONFIG_AGENT: ConfigAgent(),
            AgentRole.LOG_AGENT: LogAgent(),
            AgentRole.SYNTHESIZER_AGENT: SynthesizerAgent(),
        }

    def dispatch(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Route envelope to the designated recipient agent and record in audit log."""
        # 1. Log outbound envelope to SQLite and notify listeners (WebSocket stream)
        log_envelope(envelope)
        notify_envelope_listeners(envelope)

        target_role = envelope.header.recipient

        # 2. Dispatch via HTTP if mode is 'http'
        if self.mode == "http":
            try:
                url = settings.get_agent_url(target_role)
                payload_data = envelope.model_dump(mode="json")

                with httpx.Client(timeout=settings.agent_timeout_seconds) as client:
                    response = client.post(url, json=payload_data)

                if response.status_code == 200:
                    resp_data = response.json()
                    response_envelope = AgentEnvelope.model_validate(resp_data)
                    log_envelope(response_envelope)
                    notify_envelope_listeners(response_envelope)
                    return response_envelope
                else:
                    logger.warning(
                        f"Agent {target_role.value} returned status {response.status_code}: {response.text}"
                    )
            except (httpx.ConnectError, httpx.TimeoutException, Exception) as exc:
                logger.warning(
                    f"HTTP dispatch to {target_role.value} failed ({exc}). "
                    f"Fallback enabled: {settings.in_process_fallback}"
                )
                if not settings.in_process_fallback:
                    error_resp = AgentEnvelope.create_error_response(
                        original=envelope,
                        error_code="AGENT_UNAVAILABLE",
                        message=f"Agent process for {target_role.value} unavailable over HTTP: {str(exc)}",
                    )
                    log_envelope(error_resp)
                    notify_envelope_listeners(error_resp)
                    return error_resp

        # 3. In-process fallback or direct execution
        agent = self._in_process_agents.get(target_role)
        if not agent:
            error_resp = AgentEnvelope.create_error_response(
                original=envelope,
                error_code="UNKNOWN_RECIPIENT",
                message=f"No agent registered for role {target_role.value}",
            )
            log_envelope(error_resp)
            notify_envelope_listeners(error_resp)
            return error_resp

        response_envelope = agent.handle_envelope(envelope)
        log_envelope(response_envelope)
        notify_envelope_listeners(response_envelope)
        return response_envelope
