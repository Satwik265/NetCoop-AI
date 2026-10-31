"""Unit and integration tests for WifiServicesAgent."""

import pytest
from netcoop.agents.wifi_services_agent import WifiServicesAgent
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    EnvelopePayload,
    Inquiry,
    MessageType,
    NetworkScope,
    ObservationCategory,
    Priority,
    ProtocolHeader,
    Severity,
)


@pytest.fixture
def wifi_agent() -> WifiServicesAgent:
    return WifiServicesAgent()


def test_wifi_services_agent_weak_rf(wifi_agent: WifiServicesAgent) -> None:
    """Verify weak RSSI and high retransmission trigger wireless observations and hypothesis."""
    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="test-rf-001",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.WIFI_SERVICES_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="campus-net", devices=["AP_HOSTEL_1"]),
            raw_data={
                "telemetry": [
                    {
                        "device_id": "AP_HOSTEL_1",
                        "timestamp": "2026-10-31T12:00:00Z",
                        "wifi_rssi_dbm": -84.0,
                        "wifi_retransmission_pct": 28.5,
                        "client_density": 50,
                    }
                ]
            },
        ),
    )

    response = wifi_agent.handle_envelope(envelope)
    assert response.header.message_type == MessageType.FINDING_SUBMISSION
    assert len(response.payload.observations) >= 2

    # Check RSSI observation
    rssi_obs = next(o for o in response.payload.observations if o.metric_name == "wifi_rssi_dbm")
    assert rssi_obs.observed_value == -84.0
    assert rssi_obs.severity == Severity.CRITICAL

    # Check hypothesis
    assert len(response.payload.hypotheses) == 1
    hyp = response.payload.hypotheses[0]
    assert "Wi-Fi" in hyp.probable_cause or "attenuation" in hyp.probable_cause


def test_wifi_services_agent_dns_failure(wifi_agent: WifiServicesAgent) -> None:
    """Verify elevated DNS query failure rate triggers DNS failure hypothesis."""
    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="test-dns-002",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.WIFI_SERVICES_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="campus-net", devices=["DNS_SRV_1"]),
            raw_data={
                "telemetry": [
                    {
                        "device_id": "DNS_SRV_1",
                        "timestamp": "2026-10-31T12:00:00Z",
                        "dns_failure_pct": 35.0,
                        "dns_resolution_ms": 210.0,
                    }
                ]
            },
        ),
    )

    response = wifi_agent.handle_envelope(envelope)
    assert len(response.payload.observations) >= 2
    assert len(response.payload.hypotheses) == 1
    assert "DNS" in response.payload.hypotheses[0].probable_cause


def test_wifi_services_agent_dhcp_failure(wifi_agent: WifiServicesAgent) -> None:
    """Verify DHCP lease allocation failure triggers DHCP hypothesis."""
    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="test-dhcp-003",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.WIFI_SERVICES_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="campus-net", devices=["DHCP_CORE"]),
            raw_data={
                "telemetry": [
                    {
                        "device_id": "DHCP_CORE",
                        "timestamp": "2026-10-31T12:00:00Z",
                        "dhcp_failure_pct": 18.0,
                    }
                ]
            },
        ),
    )

    response = wifi_agent.handle_envelope(envelope)
    assert len(response.payload.observations) == 1
    assert "DHCP" in response.payload.hypotheses[0].probable_cause


def test_wifi_services_agent_missing_metrics_limitations(wifi_agent: WifiServicesAgent) -> None:
    """Verify that absent WiFi and service metrics populate limitations cleanly."""
    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="test-missing-004",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.WIFI_SERVICES_AGENT,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="campus-net", devices=["SW_CORE"]),
            raw_data={
                "telemetry": [
                    {
                        "device_id": "SW_CORE",
                        "timestamp": "2026-10-31T12:00:00Z",
                        "cpu_pct": 25.0,
                        "link_utilization_pct": 30.0,
                    }
                ]
            },
        ),
    )

    response = wifi_agent.handle_envelope(envelope)
    limitations = response.context.get("limitations", [])
    assert any("wifi metrics missing" in l for l in limitations)
    assert any("service metrics missing" in l for l in limitations)


def test_wifi_services_agent_inquiry_handling(wifi_agent: WifiServicesAgent) -> None:
    """Verify inquiry responses regarding wireless RF and DNS health."""
    inquiry = Inquiry(
        target_agent=AgentRole.WIFI_SERVICES_AGENT,
        question="Assess RF channel interference and client density vs switch uplink port drops.",
        target_entity="AP_HOSTEL_1",
    )
    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="test-inq-005",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.WIFI_SERVICES_AGENT,
            message_type=MessageType.INQUIRY_REQUEST,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="campus-net", devices=["AP_HOSTEL_1"]),
            inquiries=[inquiry],
            raw_data={
                "telemetry": [
                    {
                        "device_id": "AP_HOSTEL_1",
                        "wifi_rssi_dbm": -85.0,
                    }
                ]
            },
        ),
    )

    response = wifi_agent.handle_envelope(envelope)
    assert response.header.message_type == MessageType.INQUIRY_RESPONSE
    assert len(response.payload.inquiries) == 1
    answer = response.payload.inquiries[0].answer
    assert answer is not None
    assert "Wi-Fi RF degradation identified" in answer
