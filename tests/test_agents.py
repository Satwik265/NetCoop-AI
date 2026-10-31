"""Unit tests for the five domain specialist agents."""

from netcoop.agents.config_agent import ConfigAgent
from netcoop.agents.log_agent import LogAgent
from netcoop.agents.synthesizer_agent import SynthesizerAgent
from netcoop.agents.telemetry_agent import TelemetryAgent
from netcoop.agents.topology_agent import TopologyAgent
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    EnvelopePayload,
    MessageType,
    NetworkScope,
    Observation,
    ObservationCategory,
    ProtocolHeader,
    Severity,
)


def create_mock_dispatch_envelope(raw_data: dict) -> AgentEnvelope:
    """Helper to create an inbound dispatch envelope."""
    return AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="test-corr-001",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.BROADCAST,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="lab-01", devices=["sw1", "sw2"]),
            raw_data=raw_data,
        ),
    )


def test_telemetry_agent_detects_queue_drops_and_optics() -> None:
    """Verify TelemetryAgent extracts anomalies from counters and optic metrics."""
    agent = TelemetryAgent()
    raw = {
        "telemetry": [
            {
                "device": "sw1",
                "interface": "et-0/0/1",
                "metric": "egress_queue_drops",
                "value": 1500,
                "unit": "packets",
            },
            {
                "device": "sw1",
                "interface": "et-0/0/1",
                "metric": "rx_power_dbm",
                "value": -18.2,
                "unit": "dbm",
            },
        ]
    }
    env = create_mock_dispatch_envelope(raw)
    out = agent.handle_envelope(env)

    assert out.header.sender == AgentRole.TELEMETRY_AGENT
    assert len(out.payload.observations) == 2
    metrics = {o.metric_name for o in out.payload.observations}
    assert "egress_queue_drops" in metrics
    assert "rx_power_dbm" in metrics


def test_topology_agent_detects_bgp_flaps() -> None:
    """Verify TopologyAgent identifies BGP instability."""
    agent = TopologyAgent()
    raw = {
        "routing_state": {
            "bgp_sessions": [
                {
                    "device": "r1",
                    "peer_ip": "192.0.2.1",
                    "state": "Active",
                    "flaps_count": 6,
                }
            ]
        }
    }
    env = create_mock_dispatch_envelope(raw)
    out = agent.handle_envelope(env)

    assert out.header.sender == AgentRole.TOPOLOGY_AGENT
    assert len(out.payload.observations) == 1
    assert out.payload.observations[0].metric_name == "bgp_state_flaps"


def test_config_agent_detects_mtu_mismatch() -> None:
    """Verify ConfigAgent detects MTU discrepancy across endpoints."""
    agent = ConfigAgent()
    raw = {
        "configurations": [
            {
                "device": "leaf1",
                "running_config": {"interfaces": {"et-1": {"mtu": 9000}}},
            },
            {
                "device": "spine1",
                "running_config": {"interfaces": {"et-1": {"mtu": 1500}}},
            },
        ]
    }
    env = create_mock_dispatch_envelope(raw)
    out = agent.handle_envelope(env)

    assert out.header.sender == AgentRole.CONFIG_AGENT
    has_mtu = any(o.metric_name == "mtu_mismatch" for o in out.payload.observations)
    assert has_mtu is True


def test_log_agent_detects_bfd_and_dampening() -> None:
    """Verify LogAgent flags BFD drops and flap damping messages."""
    agent = LogAgent()
    raw = {
        "logs": [
            {"device": "r1", "message": "BFD session down for neighbor 1.1.1.1", "severity": 3},
            {"device": "r1", "message": "BGP route dampening active: Prefix 10.0.0.0/24 suppressed", "severity": 3},
        ]
    }
    env = create_mock_dispatch_envelope(raw)
    out = agent.handle_envelope(env)

    assert out.header.sender == AgentRole.LOG_AGENT
    assert len(out.payload.observations) == 2


def test_synthesizer_agent_enforces_insufficient_evidence() -> None:
    """Verify SynthesizerAgent returns insufficient_evidence when sparse single anomaly is passed."""
    agent = SynthesizerAgent()
    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="sparse-test",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.SYNTHESIZER_AGENT,
            message_type=MessageType.INQUIRY_REQUEST,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net-sparse", devices=["dev-1"]),
            observations=[
                Observation(
                    category=ObservationCategory.METRIC_ANOMALY,
                    entity="dev-1",
                    metric_name="packet_loss_pct",
                    observed_value=2.0,
                    unit="percent",
                    severity=Severity.WARNING,
                    context={"agent_domain": "telemetry_agent"},
                )
            ],
        ),
    )
    out = agent.handle_envelope(envelope)
    assert out.context["diagnostic_status"] == "insufficient_evidence"
    assert len(out.payload.hypotheses) == 0
