"""Mediator routing envelopes between specialist agents and orchestrator via HTTP microservices.

Includes dynamic agent discovery from registry, circuit breaker, retry with backoff,
and degraded-mode continuation recording dead agents in limitations.
"""

import logging
import time
from typing import Callable, Dict, List, Optional, Set
import httpx

from netcoop.config import settings
from netcoop.core.envelope import AgentEnvelope, AgentRole, MessageType, Priority, ProtocolErrorDetail, ProtocolHeader
from netcoop.agents.base import BaseAgent
from netcoop.agents.config_agent import ConfigAgent
from netcoop.agents.log_agent import LogAgent
from netcoop.agents.synthesizer_agent import SynthesizerAgent
from netcoop.agents.telemetry_agent import TelemetryAgent
from netcoop.agents.topology_agent import ConnectivityAgent, TopologyAgent
from netcoop.agents.wifi_services_agent import WifiServicesAgent
try:
    from netcoop.agents.classifier import ClassifierAgent
except ImportError:
    ClassifierAgent = None

from netcoop.storage.db import log_envelope

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


class CircuitBreaker:
    """Tracks per-agent microservice health and fast-fails persistently dead agents."""

    def __init__(self, failure_threshold: int = 2, recovery_timeout_s: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self._failures: Dict[AgentRole, int] = {}
        self._last_failure_time: Dict[AgentRole, float] = {}
        self._open_circuits: Set[AgentRole] = set()

    def is_open(self, role: AgentRole) -> bool:
        """Check if circuit is open (agent unreachable)."""
        if role in self._open_circuits:
            # Check if recovery timeout expired (half-open check)
            if time.time() - self._last_failure_time.get(role, 0) > self.recovery_timeout_s:
                self._open_circuits.remove(role)
                self._failures[role] = 0
                return False
            return True
        return False

    def record_success(self, role: AgentRole) -> None:
        """Reset failure tracking upon successful response."""
        self._failures[role] = 0
        self._open_circuits.discard(role)

    def record_failure(self, role: AgentRole) -> None:
        """Record an agent communication failure and trip circuit if threshold reached."""
        count = self._failures.get(role, 0) + 1
        self._failures[role] = count
        self._last_failure_time[role] = time.time()
        if count >= self.failure_threshold:
            self._open_circuits.add(role)
            logger.warning(
                f"Circuit breaker TRIPPED for agent {role.value} after {count} consecutive failures. Fast-failing future calls."
            )


class AgentRegistry:
    """Dynamic registry discovering available specialist agents and their operational status."""

    def __init__(self) -> None:
        self.registered_roles: List[AgentRole] = [
            AgentRole.TELEMETRY_AGENT,
            AgentRole.TOPOLOGY_AGENT,
            AgentRole.CONFIG_AGENT,
            AgentRole.LOG_AGENT,
            AgentRole.WIFI_SERVICES_AGENT,
        ]
        if ClassifierAgent is not None:
            self.registered_roles.append(AgentRole.CLASSIFIER_AGENT)

    def discover_live_agents(self, host: Optional[str] = None) -> Dict[AgentRole, bool]:
        """Poll health check endpoints to assess live microservice status."""
        status_map: Dict[AgentRole, bool] = {}
        for role in self.registered_roles:
            url = settings.get_agent_health_url(role)
            try:
                with httpx.Client(timeout=1.0) as client:
                    resp = client.get(url)
                    status_map[role] = (resp.status_code == 200)
            except Exception:
                status_map[role] = False
        return status_map


class AgentMediator:
    """Dispatches envelopes to specialist agents over HTTP and preserves message audit traces."""

    def __init__(self, mode: Optional[str] = None) -> None:
        self.mode = mode or settings.agents_mode
        self.registry = AgentRegistry()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold
        )
        self.dead_agents: Set[str] = set()

        self._in_process_agents: Dict[AgentRole, BaseAgent] = {
            AgentRole.TELEMETRY_AGENT: TelemetryAgent(),
            AgentRole.TOPOLOGY_AGENT: TopologyAgent(),
            AgentRole.CONNECTIVITY_AGENT: ConnectivityAgent(),
            AgentRole.CONFIG_AGENT: ConfigAgent(),
            AgentRole.LOG_AGENT: LogAgent(),
            AgentRole.SYNTHESIZER_AGENT: SynthesizerAgent(),
            AgentRole.WIFI_SERVICES_AGENT: WifiServicesAgent(),
        }
        if ClassifierAgent is not None:
            self._in_process_agents[AgentRole.CLASSIFIER_AGENT] = ClassifierAgent()

    def get_degraded_limitations(self) -> List[str]:
        """Return audit notes of agents operating in dead or degraded state."""
        return [f"agent_unavailable: {name} process unreachable; continued in degraded mode" for name in sorted(self.dead_agents)]

    def dispatch(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Route envelope to the designated recipient agent and record in audit log."""
        # 1. Log outbound envelope to SQLite and notify listeners (WebSocket stream)
        log_envelope(envelope)
        notify_envelope_listeners(envelope)

        target_role = envelope.header.recipient

        # 2. Dispatch via HTTP if mode is 'http'
        if self.mode == "http":
            # Check circuit breaker
            if self.circuit_breaker.is_open(target_role):
                logger.debug(f"Circuit open for {target_role.value}, skipping HTTP dispatch.")
                self.dead_agents.add(target_role.value)
                if not settings.in_process_fallback:
                    return self._handle_unavailable_agent(envelope, target_role, "Circuit breaker open")
            else:
                url = settings.get_agent_url(target_role)
                payload_data = envelope.model_dump(mode="json")
                retries = settings.agent_max_retries

                for attempt in range(retries + 1):
                    try:
                        with httpx.Client(timeout=settings.agent_timeout_seconds) as client:
                            response = client.post(url, json=payload_data)

                        if response.status_code == 200:
                            self.circuit_breaker.record_success(target_role)
                            self.dead_agents.discard(target_role.value)
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
                        if isinstance(exc, httpx.ConnectError):
                            # Agent port closed or process inactive -> trip breaker & fallback immediately without retry delay
                            self.circuit_breaker.record_failure(target_role)
                            self.circuit_breaker.record_failure(target_role)
                            self.dead_agents.add(target_role.value)
                            if not settings.in_process_fallback:
                                return self._handle_unavailable_agent(envelope, target_role, str(exc))
                            break
                        if attempt < retries:
                            time.sleep(0.05 * (attempt + 1))
                            continue

                        self.circuit_breaker.record_failure(target_role)
                        self.dead_agents.add(target_role.value)
                        logger.warning(
                            f"HTTP dispatch to {target_role.value} failed ({exc}). "
                            f"Fallback enabled: {settings.in_process_fallback}"
                        )
                        if not settings.in_process_fallback:
                            return self._handle_unavailable_agent(envelope, target_role, str(exc))

        # 3. In-process fallback or direct execution
        agent = self._in_process_agents.get(target_role)
        if not agent:
            self.dead_agents.add(target_role.value)
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

    def _handle_unavailable_agent(
        self, original_envelope: AgentEnvelope, role: AgentRole, reason: str
    ) -> AgentEnvelope:
        """Construct error envelope for an unreachable agent and record audit."""
        error_resp = AgentEnvelope.create_error_response(
            original=original_envelope,
            error_code="AGENT_UNAVAILABLE",
            message=f"Agent process for {role.value} unavailable over HTTP: {reason}",
        )
        log_envelope(error_resp)
        notify_envelope_listeners(error_resp)
        return error_resp
