"""Unit and integration tests for isolated agent FastAPI servers and mediator dispatch."""

import pytest
from fastapi.testclient import TestClient

from core.envelope import (
    AgentEnvelope,
    AgentRole,
    EnvelopePayload,
    MessageType,
    NetworkScope,
    ProtocolHeader,
)
from agents.server import create_agent_app
from orchestrator.mediator import AgentMediator


def test_agent_server_health_endpoints():
    """Verify health endpoints on specialist agent apps."""
    for role in [
        AgentRole.TELEMETRY_AGENT,
        AgentRole.TOPOLOGY_AGENT,
        AgentRole.CONFIG_AGENT,
        AgentRole.LOG_AGENT,
        AgentRole.SYNTHESIZER_AGENT,
    ]:
        app = create_agent_app(role)
        client = TestClient(app)
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["agent"] == role.value


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

