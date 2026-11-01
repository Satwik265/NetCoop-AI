"""Mediator routing envelopes between specialist agents and orchestrator via HTTP microservices.

Includes dynamic agent discovery from registry, circuit breaker with half-open probing,
bounded concurrent dispatch, retry with backoff, explicit execution states, and
degraded-mode continuation recording dead agents in limitations.
"""

from datetime import datetime, timezone
from enum import Enum
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set
import concurrent.futures
import httpx
from pydantic import BaseModel, Field

from netcoop.config import settings
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    MessageType,
    Priority,
    ProtocolErrorDetail,
    ProtocolHeader,
)
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


class AgentExecutionStatus(str, Enum):
    """Explicit lifecycle execution status for specialist microservices."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    PROTOCOL_ERROR = "protocol_error"
    INTERNAL_ERROR = "internal_error"
    CIRCUIT_OPEN = "circuit_open"


class AgentExecutionRecord(BaseModel):
    """Detailed telemetry on individual agent dispatch and execution."""

    agent_id: str
    execution_status: AgentExecutionStatus
    started_at: str
    completed_at: str
    duration_ms: float
    retry_count: int = 0
    observation_count: int = 0
    hypothesis_count: int = 0
    inquiry_count: int = 0
    error_code: Optional[str] = None
    correlation_id: str


class CircuitBreakerState(str, Enum):
    """Circuit breaker states for microservice resilience."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Tracks per-agent microservice health and fast-fails persistently dead agents."""

    def __init__(self, failure_threshold: int = 2, recovery_timeout_s: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self._failures: Dict[AgentRole, int] = {}
        self._last_failure_time: Dict[AgentRole, float] = {}
        self._open_circuits: Set[AgentRole] = set()
        self._half_open_probes: Set[AgentRole] = set()

    def is_open(self, role: AgentRole) -> bool:
        """Check if circuit is open (agent unreachable)."""
        if role in self._open_circuits:
            # Check if recovery timeout expired (half-open check)
            if time.time() - self._last_failure_time.get(role, 0) > self.recovery_timeout_s:
                self._open_circuits.remove(role)
                self._half_open_probes.add(role)
                return False
            return True
        return False

    def is_half_open(self, role: AgentRole) -> bool:
        """Check if circuit is in half-open canary probe state."""
        return role in self._half_open_probes

    def get_state(self, role: AgentRole) -> CircuitBreakerState:
        """Return the current circuit state for an agent."""
        if role in self._open_circuits:
            if time.time() - self._last_failure_time.get(role, 0) > self.recovery_timeout_s:
                return CircuitBreakerState.HALF_OPEN
            return CircuitBreakerState.OPEN
        if role in self._half_open_probes:
            return CircuitBreakerState.HALF_OPEN
        return CircuitBreakerState.CLOSED

    def record_success(self, role: AgentRole) -> None:
        """Reset failure tracking upon successful response."""
        self._failures[role] = 0
        self._open_circuits.discard(role)
        self._half_open_probes.discard(role)

    def record_failure(self, role: AgentRole) -> None:
        """Record an agent communication failure and trip circuit if threshold reached."""
        count = self._failures.get(role, 0) + 1
        self._failures[role] = count
        self._last_failure_time[role] = time.time()
        self._half_open_probes.discard(role)
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
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout_s=settings.circuit_breaker_recovery_timeout_s,
        )
        self.dead_agents: Set[str] = set()
        self.execution_records: Dict[str, AgentExecutionRecord] = {}

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

    def reset_dead_agents(self) -> None:
        """Clear recorded dead agents."""
        self.dead_agents.clear()

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker failure states."""
        self.circuit_breaker._failures.clear()
        self.circuit_breaker._open_circuits.clear()
        self.circuit_breaker._half_open_probes.clear()
        self.circuit_breaker._last_failure_time.clear()

    def reset_execution_records(self) -> None:
        """Clear recorded agent execution records."""
        self.execution_records.clear()

    def get_execution_records(self) -> Dict[str, Dict[str, Any]]:
        """Export serialized execution records for audit and reporting."""
        return {k: v.model_dump(mode="json") for k, v in self.execution_records.items()}

    def get_degraded_limitations(self) -> List[str]:
        """Return audit notes of agents operating in dead or degraded state."""
        return [
            f"agent_unavailable: {name} process unreachable; continued in degraded mode"
            for name in sorted(self.dead_agents)
        ]

    def dispatch(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Route envelope to the designated recipient agent and record in audit log."""
        t0 = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        target_role = envelope.header.recipient
        corr_id = envelope.header.correlation_id

        # 1. Log outbound envelope to SQLite and notify listeners (WebSocket stream)
        log_envelope(envelope)
        notify_envelope_listeners(envelope)

        # 2. Dispatch via HTTP if mode is 'http'
        active_mode = self.mode if self.mode is not None else settings.agents_mode
        if active_mode == "http" and settings.agents_mode == "in_process":
            active_mode = "in_process"

        if active_mode == "http":
            # Check circuit breaker
            if self.circuit_breaker.is_open(target_role):
                duration_ms = round((time.time() - t0) * 1000, 2)
                completed_at = datetime.now(timezone.utc).isoformat()
                logger.debug(f"Circuit open for {target_role.value}, skipping HTTP dispatch.")
                self.dead_agents.add(target_role.value)
                rec = AgentExecutionRecord(
                    agent_id=target_role.value,
                    execution_status=AgentExecutionStatus.CIRCUIT_OPEN,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    retry_count=0,
                    error_code="CIRCUIT_OPEN",
                    correlation_id=corr_id,
                )
                self.execution_records[target_role.value] = rec
                if not settings.fallback_enabled:
                    resp = self._handle_unavailable_agent(envelope, target_role, "Circuit breaker open")
                    resp.context["execution_record"] = rec.model_dump(mode="json")
                    return resp
            else:
                url = settings.get_agent_url(target_role)
                payload_data = envelope.model_dump(mode="json")
                retries = settings.agent_max_retries
                headers = {"Content-Type": "application/json"}
                if settings.internal_service_token:
                    headers[settings.service_auth_header] = settings.internal_service_token

                for attempt in range(retries + 1):
                    try:
                        with httpx.Client(timeout=settings.agent_timeout_seconds) as client:
                            response = client.post(url, json=payload_data, headers=headers)

                        duration_ms = round((time.time() - t0) * 1000, 2)
                        completed_at = datetime.now(timezone.utc).isoformat()

                        # Case A: HTTP 200 Success or Error Envelope
                        if response.status_code == 200:
                            resp_data = response.json()
                            response_envelope = AgentEnvelope.model_validate(resp_data)

                            # Inspect if response envelope contains an error payload
                            if (
                                response_envelope.payload.error is not None
                                or response_envelope.header.message_type == MessageType.PROTOCOL_ERROR
                            ):
                                err = response_envelope.payload.error
                                err_code = err.error_code if err else "INTERNAL_ERROR"
                                self.circuit_breaker.record_failure(target_role)
                                self.dead_agents.add(target_role.value)
                                status = (
                                    AgentExecutionStatus.PROTOCOL_ERROR
                                    if "PROTOCOL" in err_code
                                    else AgentExecutionStatus.INTERNAL_ERROR
                                )
                                rec = AgentExecutionRecord(
                                    agent_id=target_role.value,
                                    execution_status=status,
                                    started_at=started_at,
                                    completed_at=completed_at,
                                    duration_ms=duration_ms,
                                    retry_count=attempt,
                                    error_code=err_code,
                                    correlation_id=corr_id,
                                )
                                self.execution_records[target_role.value] = rec
                                response_envelope.context["execution_record"] = rec.model_dump(mode="json")
                                lim_msg = f"agent_failed: {target_role.value} reported error {err_code}: {err.message if err else 'error'}"
                                response_envelope.context.setdefault("limitations", []).append(lim_msg)
                                log_envelope(response_envelope)
                                notify_envelope_listeners(response_envelope)
                                return response_envelope

                            # Truly successful response
                            self.circuit_breaker.record_success(target_role)
                            self.dead_agents.discard(target_role.value)
                            obs_count = len(response_envelope.payload.observations)
                            hyp_count = len(response_envelope.payload.hypotheses)
                            inq_count = len(response_envelope.payload.inquiries)
                            status = (
                                AgentExecutionStatus.PARTIAL_SUCCESS
                                if response_envelope.context.get("has_partial_findings")
                                else AgentExecutionStatus.SUCCESS
                            )
                            rec = AgentExecutionRecord(
                                agent_id=target_role.value,
                                execution_status=status,
                                started_at=started_at,
                                completed_at=completed_at,
                                duration_ms=duration_ms,
                                retry_count=attempt,
                                observation_count=obs_count,
                                hypothesis_count=hyp_count,
                                inquiry_count=inq_count,
                                correlation_id=corr_id,
                            )
                            self.execution_records[target_role.value] = rec
                            response_envelope.context["execution_record"] = rec.model_dump(mode="json")
                            log_envelope(response_envelope)
                            notify_envelope_listeners(response_envelope)
                            return response_envelope

                        # Case B: HTTP 500 Agent Internal Error
                        elif response.status_code == 500:
                            self.circuit_breaker.record_failure(target_role)
                            self.dead_agents.add(target_role.value)
                            try:
                                resp_data = response.json()
                                response_envelope = AgentEnvelope.model_validate(resp_data)
                            except Exception:
                                response_envelope = AgentEnvelope.create_error_response(
                                    original=envelope,
                                    error_code="INTERNAL_ERROR",
                                    message=f"Agent process returned 500: {response.text[:200]}",
                                )
                            rec = AgentExecutionRecord(
                                agent_id=target_role.value,
                                execution_status=AgentExecutionStatus.INTERNAL_ERROR,
                                started_at=started_at,
                                completed_at=completed_at,
                                duration_ms=duration_ms,
                                retry_count=attempt,
                                error_code="INTERNAL_ERROR",
                                correlation_id=corr_id,
                            )
                            self.execution_records[target_role.value] = rec
                            response_envelope.context["execution_record"] = rec.model_dump(mode="json")
                            lim_msg = f"agent_failed: {target_role.value} crashed with internal 500"
                            response_envelope.context.setdefault("limitations", []).append(lim_msg)
                            log_envelope(response_envelope)
                            notify_envelope_listeners(response_envelope)
                            return response_envelope

                        # Case C: HTTP 400 Bad Request / Protocol Error (Non-retryable)
                        elif response.status_code == 400:
                            self.circuit_breaker.record_failure(target_role)
                            self.dead_agents.add(target_role.value)
                            response_envelope = AgentEnvelope.create_error_response(
                                original=envelope,
                                error_code="PROTOCOL_ERROR",
                                message=f"Protocol validation error 400: {response.text[:200]}",
                            )
                            rec = AgentExecutionRecord(
                                agent_id=target_role.value,
                                execution_status=AgentExecutionStatus.PROTOCOL_ERROR,
                                started_at=started_at,
                                completed_at=completed_at,
                                duration_ms=duration_ms,
                                retry_count=attempt,
                                error_code="PROTOCOL_ERROR",
                                correlation_id=corr_id,
                            )
                            self.execution_records[target_role.value] = rec
                            response_envelope.context["execution_record"] = rec.model_dump(mode="json")
                            lim_msg = f"protocol_error: {target_role.value} rejected envelope with 400"
                            response_envelope.context.setdefault("limitations", []).append(lim_msg)
                            log_envelope(response_envelope)
                            notify_envelope_listeners(response_envelope)
                            return response_envelope

                        # Case D: HTTP 401 Unauthorized (Auth failure)
                        elif response.status_code == 401:
                            self.circuit_breaker.record_failure(target_role)
                            self.dead_agents.add(target_role.value)
                            response_envelope = AgentEnvelope.create_error_response(
                                original=envelope,
                                error_code="UNAUTHORIZED",
                                message="Service-to-service authentication rejected request",
                            )
                            rec = AgentExecutionRecord(
                                agent_id=target_role.value,
                                execution_status=AgentExecutionStatus.PROTOCOL_ERROR,
                                started_at=started_at,
                                completed_at=completed_at,
                                duration_ms=duration_ms,
                                retry_count=attempt,
                                error_code="UNAUTHORIZED",
                                correlation_id=corr_id,
                            )
                            self.execution_records[target_role.value] = rec
                            response_envelope.context["execution_record"] = rec.model_dump(mode="json")
                            log_envelope(response_envelope)
                            notify_envelope_listeners(response_envelope)
                            return response_envelope

                        else:
                            logger.warning(
                                f"Agent {target_role.value} returned status {response.status_code}: {response.text}"
                            )

                    except (httpx.ConnectError, httpx.TimeoutException, Exception) as exc:
                        duration_ms = round((time.time() - t0) * 1000, 2)
                        completed_at = datetime.now(timezone.utc).isoformat()

                        # Connection refused / inactive process -> fast fail
                        if isinstance(exc, httpx.ConnectError):
                            self.circuit_breaker.record_failure(target_role)
                            self.circuit_breaker.record_failure(target_role)
                            self.dead_agents.add(target_role.value)
                            rec = AgentExecutionRecord(
                                agent_id=target_role.value,
                                execution_status=AgentExecutionStatus.UNAVAILABLE,
                                started_at=started_at,
                                completed_at=completed_at,
                                duration_ms=duration_ms,
                                retry_count=attempt,
                                error_code="AGENT_UNAVAILABLE",
                                correlation_id=corr_id,
                            )
                            self.execution_records[target_role.value] = rec
                            if not settings.fallback_enabled:
                                resp = self._handle_unavailable_agent(envelope, target_role, str(exc))
                                resp.context["execution_record"] = rec.model_dump(mode="json")
                                return resp
                            break

                        # Timeout exception -> bounded retry
                        if isinstance(exc, httpx.TimeoutException):
                            if attempt < retries:
                                time.sleep(0.05 * (attempt + 1))
                                continue
                            self.circuit_breaker.record_failure(target_role)
                            self.dead_agents.add(target_role.value)
                            rec = AgentExecutionRecord(
                                agent_id=target_role.value,
                                execution_status=AgentExecutionStatus.TIMEOUT,
                                started_at=started_at,
                                completed_at=completed_at,
                                duration_ms=duration_ms,
                                retry_count=retries,
                                error_code="TIMEOUT",
                                correlation_id=corr_id,
                            )
                            self.execution_records[target_role.value] = rec
                            logger.warning(f"HTTP dispatch to {target_role.value} timed out after {retries} retries.")
                            if not settings.fallback_enabled:
                                resp = self._handle_unavailable_agent(envelope, target_role, "Request timed out")
                                resp.context["execution_record"] = rec.model_dump(mode="json")
                                return resp
                            break

                        # Generic retryable exception
                        if attempt < retries:
                            time.sleep(0.05 * (attempt + 1))
                            continue

                        self.circuit_breaker.record_failure(target_role)
                        self.dead_agents.add(target_role.value)
                        rec = AgentExecutionRecord(
                            agent_id=target_role.value,
                            execution_status=AgentExecutionStatus.UNAVAILABLE,
                            started_at=started_at,
                            completed_at=completed_at,
                            duration_ms=duration_ms,
                            retry_count=retries,
                            error_code="AGENT_UNAVAILABLE",
                            correlation_id=corr_id,
                        )
                        self.execution_records[target_role.value] = rec
                        logger.warning(
                            f"HTTP dispatch to {target_role.value} failed ({exc}). "
                            f"Fallback enabled: {settings.fallback_enabled}"
                        )
                        if not settings.fallback_enabled:
                            resp = self._handle_unavailable_agent(envelope, target_role, str(exc))
                            resp.context["execution_record"] = rec.model_dump(mode="json")
                            return resp

        # 3. In-process fallback or direct execution
        duration_ms = round((time.time() - t0) * 1000, 2)
        completed_at = datetime.now(timezone.utc).isoformat()

        if not settings.fallback_enabled:
            self.dead_agents.add(target_role.value)
            rec = AgentExecutionRecord(
                agent_id=target_role.value,
                execution_status=AgentExecutionStatus.UNAVAILABLE,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                retry_count=0,
                error_code="STRICT_ISOLATION_ENFORCED",
                correlation_id=corr_id,
            )
            self.execution_records[target_role.value] = rec
            resp = self._handle_unavailable_agent(
                envelope,
                target_role,
                "Direct in-process execution is disabled in strict isolation mode",
            )
            resp.context["execution_record"] = rec.model_dump(mode="json")
            return resp

        logger.warning(
            f"[DEV ONLY] Falling back to in-process execution for {target_role.value}."
        )
        agent = self._in_process_agents.get(target_role)
        if not agent:
            self.dead_agents.add(target_role.value)
            rec = AgentExecutionRecord(
                agent_id=target_role.value,
                execution_status=AgentExecutionStatus.UNAVAILABLE,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                retry_count=0,
                error_code="UNKNOWN_RECIPIENT",
                correlation_id=corr_id,
            )
            self.execution_records[target_role.value] = rec
            error_resp = AgentEnvelope.create_error_response(
                original=envelope,
                error_code="UNKNOWN_RECIPIENT",
                message=f"No agent registered for role {target_role.value}",
            )
            error_resp.context["execution_record"] = rec.model_dump(mode="json")
            log_envelope(error_resp)
            notify_envelope_listeners(error_resp)
            return error_resp

        try:
            response_envelope = agent.handle_envelope(envelope)
            duration_ms = round((time.time() - t0) * 1000, 2)
            completed_at = datetime.now(timezone.utc).isoformat()
            obs_count = len(response_envelope.payload.observations)
            hyp_count = len(response_envelope.payload.hypotheses)
            inq_count = len(response_envelope.payload.inquiries)
            rec = AgentExecutionRecord(
                agent_id=target_role.value,
                execution_status=AgentExecutionStatus.SUCCESS,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                retry_count=0,
                observation_count=obs_count,
                hypothesis_count=hyp_count,
                inquiry_count=inq_count,
                correlation_id=corr_id,
            )
            self.execution_records[target_role.value] = rec
            response_envelope.context["execution_record"] = rec.model_dump(mode="json")
            log_envelope(response_envelope)
            notify_envelope_listeners(response_envelope)
            return response_envelope
        except Exception as exc:
            duration_ms = round((time.time() - t0) * 1000, 2)
            completed_at = datetime.now(timezone.utc).isoformat()
            self.dead_agents.add(target_role.value)
            rec = AgentExecutionRecord(
                agent_id=target_role.value,
                execution_status=AgentExecutionStatus.INTERNAL_ERROR,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                retry_count=0,
                error_code="INTERNAL_ERROR",
                correlation_id=corr_id,
            )
            self.execution_records[target_role.value] = rec
            error_resp = AgentEnvelope.create_error_response(
                original=envelope,
                error_code="INTERNAL_ERROR",
                message=f"In-process execution error: {str(exc)}",
            )
            error_resp.context["execution_record"] = rec.model_dump(mode="json")
            lim_msg = f"agent_failed: {target_role.value} threw exception: {str(exc)}"
            error_resp.context.setdefault("limitations", []).append(lim_msg)
            log_envelope(error_resp)
            notify_envelope_listeners(error_resp)
            return error_resp

    def dispatch_concurrent(self, envelopes: List[AgentEnvelope]) -> List[AgentEnvelope]:
        """Dispatch multiple envelopes concurrently across specialist agents with bounded threads.

        Preserves exact deterministic response order corresponding to input envelopes list.
        """
        if not envelopes:
            return []
        if len(envelopes) == 1:
            return [self.dispatch(envelopes[0])]

        max_workers = min(len(envelopes), settings.max_concurrent_agent_calls)
        results: List[Optional[AgentEnvelope]] = [None] * len(envelopes)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self.dispatch, env): idx
                for idx, env in enumerate(envelopes)
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    target_role = envelopes[idx].header.recipient
                    results[idx] = self._handle_unavailable_agent(envelopes[idx], target_role, str(exc))

        return [r for r in results if r is not None]

    def _handle_unavailable_agent(
        self, original_envelope: AgentEnvelope, role: AgentRole, reason: str
    ) -> AgentEnvelope:
        """Construct error envelope for an unreachable agent and record audit."""
        error_resp = AgentEnvelope.create_error_response(
            original=original_envelope,
            error_code="AGENT_UNAVAILABLE",
            message=f"Agent process for {role.value} unavailable over HTTP: {reason}",
        )
        limitation_msg = f"agent_unavailable: {role.value} process unreachable; continued in degraded mode"
        error_resp.context["limitations"] = [limitation_msg]
        log_envelope(error_resp)
        notify_envelope_listeners(error_resp)
        return error_resp
