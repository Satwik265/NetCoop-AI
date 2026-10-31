"""Unit and integration tests for isolated agent FastAPI servers and mediator dispatch."""

import json
from pathlib import Path
import time
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import httpx
import pytest

from netcoop.config import settings
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    EnvelopePayload,
    MessageType,
    NetworkScope,
    Observation,
    ObservationCategory,
    Priority,
    ProtocolHeader,
    Severity,
)
from agents.server import create_agent_app
from gateway.api import create_gateway_app
from netcoop.orchestrator.mediator import AgentMediator, CircuitBreaker
from scripts.run_agents import save_pids, load_pids, PID_FILE, ALL_PORTS


def test_agent_server_health_endpoints():
    """Verify health endpoints on all specialist agent microservices and gateway."""
    roles = [
        AgentRole.TELEMETRY_AGENT,
        AgentRole.TOPOLOGY_AGENT,
        AgentRole.CONFIG_AGENT,
        AgentRole.LOG_AGENT,
        AgentRole.SYNTHESIZER_AGENT,
        AgentRole.CLASSIFIER_AGENT,
        AgentRole.WIFI_SERVICES_AGENT,
    ]
    for role in roles:
        app = create_agent_app(role)
        client = TestClient(app)
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["agent"] == role.value

    # Verify Gateway health endpoint
    gw_app = create_gateway_app()
    gw_client = TestClient(gw_app)
    gw_res = gw_client.get("/health")
    assert gw_res.status_code == 200
    assert gw_res.json()["status"] == "ok"
    assert gw_res.json()["service"] == "gateway"


def test_telemetry_agent_process_via_http_client():
    """Verify TelemetryAgent processes envelopes through FastAPI test client."""
    app = create_agent_app(AgentRole.TELEMETRY_AGENT)
    client = TestClient(app)

    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-http-001",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.TELEMETRY_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net-lab", devices=["rtr-1"]),
            raw_data={
                "telemetry": [
                    {
                        "device": "rtr-1",
                        "interface": "et-0/0/1",
                        "metric": "egress_queue_drops",
                        "value": 2500,
                        "unit": "packets",
                    }
                ]
            },
        ),
    )

    response = client.post("/process", json=envelope.model_dump(mode="json"))
    assert response.status_code == 200
    resp_data = response.json()
    resp_env = AgentEnvelope.model_validate(resp_data)

    assert resp_env.header.correlation_id == "corr-http-001"
    assert resp_env.header.sender == AgentRole.TELEMETRY_AGENT
    assert len(resp_env.payload.observations) >= 1


def test_wifi_services_agent_process_via_http_client():
    """Verify WifiServicesAgent processes wireless telemetry envelopes through FastAPI test client."""
    app = create_agent_app(AgentRole.WIFI_SERVICES_AGENT)
    client = TestClient(app)

    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-wifi-001",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.WIFI_SERVICES_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="campus-wifi", devices=["ap-hostel-01"]),
            raw_data={
                "telemetry": [
                    {
                        "device_id": "ap-hostel-01",
                        "timestamp": "2026-10-31T12:00:00Z",
                        "wifi_rssi_dbm": -85.0,
                        "wifi_retransmission_pct": 28.0,
                        "client_density": 50,
                    }
                ]
            },
        ),
    )

    response = client.post("/process", json=envelope.model_dump(mode="json"))
    assert response.status_code == 200
    resp_data = response.json()
    resp_env = AgentEnvelope.model_validate(resp_data)

    assert resp_env.header.correlation_id == "corr-wifi-001"
    assert resp_env.header.sender == AgentRole.WIFI_SERVICES_AGENT
    assert len(resp_env.payload.hypotheses) >= 1


def test_classifier_agent_process_via_http_client():
    """Verify ClassifierAgent processes tabular telemetry through FastAPI test client."""
    app = create_agent_app(AgentRole.CLASSIFIER_AGENT)
    client = TestClient(app)

    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-cls-001",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.CLASSIFIER_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="campus-net", devices=["sw-1"]),
            raw_data={
                "telemetry": [
                    {
                        "device": "sw-1",
                        "packet_loss_pct": 15.0,
                        "link_utilization_pct": 98.0,
                        "queue_drops": 2400,
                    }
                ]
            },
        ),
    )

    response = client.post("/process", json=envelope.model_dump(mode="json"))
    assert response.status_code == 200
    resp_env = AgentEnvelope.model_validate(response.json())
    assert resp_env.header.sender == AgentRole.CLASSIFIER_AGENT


def test_unsupported_protocol_schema_version_rejection():
    """Verify that an envelope with incompatible schema version is rejected with HTTP 400."""
    app = create_agent_app(AgentRole.TELEMETRY_AGENT)
    client = TestClient(app)

    raw_payload = {
        "header": {
            "correlation_id": "test-bad-version",
            "sender": "orchestrator",
            "recipient": "telemetry_agent",
            "schema_version": "2.0.0",  # Incompatible with 1.x.x
            "message_type": "telemetry_dispatch",
        },
        "payload": {
            "scope": {"network_id": "net-1", "devices": ["d-1"]},
        },
    }

    res = client.post("/process", json=raw_payload)
    assert res.status_code == 400
    assert "schema validation failed" in res.json()["detail"].lower()


@pytest.mark.strict_isolation
def test_missing_agent_behavior_in_strict_mode():
    """Verify mediator fails closed to degraded mode and records limitations when agent is unreachable."""
    mediator = AgentMediator(mode="http")
    mediator.reset_dead_agents()

    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-strict-001",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.TELEMETRY_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net-lab", devices=["rtr-1"]),
        ),
    )

    # In strict isolation mode, unreachable agent returns an error envelope, NOT a local substitute
    res_env = mediator.dispatch(envelope)
    assert res_env.header.message_type == MessageType.PROTOCOL_ERROR
    assert res_env.payload.error is not None
    assert res_env.payload.error.error_code == "AGENT_UNAVAILABLE"
    assert "telemetry_agent" in mediator.dead_agents

    limitations = mediator.get_degraded_limitations()
    assert len(limitations) == 1
    assert "agent_unavailable: telemetry_agent" in limitations[0]
    assert "continued in degraded mode" in limitations[0]


@pytest.mark.strict_isolation
def test_no_in_process_fallback_in_strict_mode(monkeypatch):
    """Verify that direct in-process execution is completely prohibited in strict isolation mode."""
    # Ensure both fallback flags are False
    monkeypatch.setattr(settings, "in_process_fallback", False)
    monkeypatch.setattr(settings, "allow_dev_in_process_fallback", False)

    mediator = AgentMediator(mode="in_process")  # Even if mediator initialized with in_process mode
    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-no-fallback",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.LOG_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net-lab", devices=["sw-1"]),
        ),
    )

    res_env = mediator.dispatch(envelope)
    assert res_env.header.message_type == MessageType.PROTOCOL_ERROR
    assert res_env.payload.error.error_code == "AGENT_UNAVAILABLE"
    assert "log_agent" in mediator.dead_agents


def test_circuit_breaker_behavior():
    """Verify circuit breaker trips to OPEN after threshold consecutive failures and fast-fails."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_s=1.0)
    role = AgentRole.TOPOLOGY_AGENT

    assert not cb.is_open(role)

    # First failure
    cb.record_failure(role)
    assert not cb.is_open(role)

    # Second failure -> trips breaker
    cb.record_failure(role)
    assert cb.is_open(role)

    # While open, stays open
    assert cb.is_open(role)

    # Success resets breaker
    cb.record_success(role)
    assert not cb.is_open(role)


@pytest.mark.strict_isolation
def test_circuit_breaker_fast_fails_mediator(monkeypatch):
    """Verify mediator fast-fails open circuit without making HTTP requests."""
    mediator = AgentMediator(mode="http")
    role = AgentRole.CONFIG_AGENT
    # Trip circuit breaker for config agent
    mediator.circuit_breaker.record_failure(role)
    mediator.circuit_breaker.record_failure(role)
    assert mediator.circuit_breaker.is_open(role)

    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-cb-fastfail",
            sender=AgentRole.ORCHESTRATOR,
            recipient=role,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net-lab", devices=["rtr-1"]),
        ),
    )

    res_env = mediator.dispatch(envelope)
    assert res_env.payload.error is not None
    assert res_env.payload.error.error_code == "AGENT_UNAVAILABLE"
    assert "Circuit breaker open" in res_env.payload.error.message


@pytest.mark.strict_isolation
def test_timeout_and_retry_limit(monkeypatch):
    """Verify mediator retries up to agent_max_retries and times out gracefully."""
    mediator = AgentMediator(mode="http")
    attempts = []

    def mock_post(*args, **kwargs):
        attempts.append(time.time())
        raise httpx.TimeoutException("Read timed out")

    monkeypatch.setattr(httpx.Client, "post", mock_post)
    monkeypatch.setattr(settings, "agent_max_retries", 2)
    monkeypatch.setattr(settings, "in_process_fallback", False)
    monkeypatch.setattr(settings, "allow_dev_in_process_fallback", False)

    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-timeout",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.LOG_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net-lab", devices=["sw-1"]),
        ),
    )

    res_env = mediator.dispatch(envelope)
    # Attempt count must be exactly max_retries + 1 (1 initial + 2 retries = 3 attempts)
    assert len(attempts) == 3
    assert res_env.payload.error is not None
    assert res_env.payload.error.error_code == "AGENT_UNAVAILABLE"


def test_process_supervision_pid_lifecycle(tmp_path, monkeypatch):
    """Verify save_pids, load_pids, and clean PID file lifecycle in supervision script."""
    fake_pid_file = tmp_path / ".agents.pid"
    import scripts.run_agents as ra
    monkeypatch.setattr(ra, "PID_FILE", fake_pid_file)

    assert ra.load_pids() == {}

    test_pids = {"telemetry_agent": 12345, "gateway": 12346}
    ra.save_pids(test_pids)
    assert fake_pid_file.exists()

    loaded = ra.load_pids()
    assert loaded == test_pids

    fake_pid_file.unlink()
    assert ra.load_pids() == {}
