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


# ==============================================================================
# SECTION 12 — CORE ORCHESTRATION RELIABILITY & INTEGRATION TEST SUITE (TESTS 1-12)
# ==============================================================================

from netcoop.orchestrator.mediator import AgentExecutionStatus, CircuitBreakerState
from netcoop.orchestrator.graph import run_diagnosis, node_specialists, node_inquiry, _convert_inquiry_to_observation
from netcoop.orchestrator.conflict_resolver import ConflictResolver
from netcoop.core.envelope import Inquiry, Hypothesis


def test_test1_normal_successful_diagnosis_all_specialists():
    """TEST 1: Normal successful diagnosis where all specialists return valid evidence."""
    scenario_path = Path("data/scenarios/link_congestion.json")
    with open(scenario_path, "r", encoding="utf-8") as f:
        incident_data = json.load(f)

    report = run_diagnosis(incident_data)
    assert report.status == "diagnosed"
    assert report.confidence >= 0.80
    assert len(report.evidence) >= 1
    # Check that execution telemetry was recorded in provenance
    agent_exec = report.provenance.get("agent_execution", {})
    assert len(agent_exec) >= 1
    for agent_id, meta in agent_exec.items():
        assert meta["execution_status"] in (AgentExecutionStatus.SUCCESS.value, AgentExecutionStatus.PARTIAL_SUCCESS.value)
        assert meta["duration_ms"] >= 0.0


def test_test2_inquiry_propagation_changes_diagnosis():
    """TEST 2: Inquiry receives a useful answer, preserves records, and changes subsequent arbitration."""
    # Scenario: CRC errors are reported, prompting dispute between Optical degradation and Ethernet fault.
    # An inquiry to TelemetryAgent about optical power returns nominal (-10.5 dBm).
    # This refutes optical degradation and crowns Ethernet interface fault!
    incident_data = {
        "incident_id": "inc-test2-inquiry-prop",
        "network_id": "campus-lan",
        "telemetry": [
            {
                "device_id": "sw-dist-01",
                "timestamp": "2026-11-01T00:00:00Z",
                "crc_errors": 450,
                "link_flaps": 5,
                "interface_errors": 520,
            }
        ],
        "topology": {
            "nodes": [{"id": "sw-dist-01", "role": "switch"}],
            "edges": [],
        },
    }

    # Verify _convert_inquiry_to_observation directly
    inq = Inquiry(
        inquiry_id="inq-optics-001",
        target_agent=AgentRole.TELEMETRY_AGENT,
        question="Retrieve optical DOM transceiver power levels for interfaces reporting CRC errors.",
        target_entity="sw-dist-01:et-0/0/1",
        answer="Optical transceiver diagnostics report Rx power levels within specification (-10.5 dBm nominal).",
    )
    fake_env = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-test",
            sender=AgentRole.TELEMETRY_AGENT,
            recipient=AgentRole.ORCHESTRATOR,
            message_type=MessageType.INQUIRY_RESPONSE,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net", devices=["sw-dist-01"]),
            inquiries=[inq],
        ),
    )
    obs = _convert_inquiry_to_observation(inq, fake_env)
    assert obs is not None
    assert obs.metric_name == "rx_power_dbm"
    assert obs.observed_value == -10.5
    assert obs.context["inquiry_id"] == "inq-optics-001"

    # Now verify end-to-end diagnosis
    report = run_diagnosis(incident_data)
    assert report.status == "diagnosed"
    assert "ethernet" in report.probable_cause.lower() or "crc" in report.probable_cause.lower()


def test_test3_agent_internal_exception_recorded_as_error(monkeypatch):
    """TEST 3: Agent raises internal exception; recorded as internal_error, not successful empty output."""
    mediator = AgentMediator(mode="http")
    role = AgentRole.LOG_AGENT

    # Mock server returning 500 with error envelope
    error_env = AgentEnvelope.create_error_response(
        original=AgentEnvelope(
            header=ProtocolHeader(
                correlation_id="corr-err",
                sender=AgentRole.ORCHESTRATOR,
                recipient=role,
                message_type=MessageType.TELEMETRY_DISPATCH,
            ),
            payload=EnvelopePayload(
                scope=NetworkScope(network_id="net", devices=["sw-1"]),
            ),
        ),
        error_code="INTERNAL_ERROR",
        message="Simulated internal database crash",
    )

    class MockResponse:
        status_code = 500
        text = "Internal error"
        def json(self):
            return error_env.model_dump(mode="json")

    def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.Client, "post", mock_post)
    monkeypatch.setattr(settings, "in_process_fallback", False)
    monkeypatch.setattr(settings, "allow_dev_in_process_fallback", False)

    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-err",
            sender=AgentRole.ORCHESTRATOR,
            recipient=role,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net", devices=["sw-1"]),
        ),
    )

    resp = mediator.dispatch(envelope)
    assert resp.payload.error is not None
    assert resp.payload.error.error_code == "INTERNAL_ERROR"

    records = mediator.get_execution_records()
    assert role.value in records
    assert records[role.value]["execution_status"] == AgentExecutionStatus.INTERNAL_ERROR.value
    assert records[role.value]["error_code"] == "INTERNAL_ERROR"
    assert role.value in mediator.dead_agents


@pytest.mark.strict_isolation
def test_test4_agent_unavailable_degraded_execution():
    """TEST 4: One specialist is unavailable; healthy agents are preserved and degraded mode continues."""
    mediator = AgentMediator(mode="http")
    role = AgentRole.WIFI_SERVICES_AGENT

    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-unavail",
            sender=AgentRole.ORCHESTRATOR,
            recipient=role,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net", devices=["ap-1"]),
        ),
    )

    # Dispatched to offline port in strict isolation
    resp = mediator.dispatch(envelope)
    assert resp.payload.error is not None
    assert resp.payload.error.error_code == "AGENT_UNAVAILABLE"
    assert role.value in mediator.dead_agents

    records = mediator.get_execution_records()
    assert records[role.value]["execution_status"] == AgentExecutionStatus.UNAVAILABLE.value
    assert "continued in degraded mode" in mediator.get_degraded_limitations()[0]


def test_test5_agent_timeout_bounded_reporting(monkeypatch):
    """TEST 5: Verify bounded execution, retry limit, and TIMEOUT status reporting."""
    mediator = AgentMediator(mode="http")
    role = AgentRole.TOPOLOGY_AGENT
    attempts = []

    def mock_post(*args, **kwargs):
        attempts.append(time.time())
        raise httpx.TimeoutException("Read timeout on socket")

    monkeypatch.setattr(httpx.Client, "post", mock_post)
    monkeypatch.setattr(settings, "agent_max_retries", 1)
    monkeypatch.setattr(settings, "in_process_fallback", False)
    monkeypatch.setattr(settings, "allow_dev_in_process_fallback", False)

    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-timeout-test",
            sender=AgentRole.ORCHESTRATOR,
            recipient=role,
            message_type=MessageType.TELEMETRY_DISPATCH,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net", devices=["sw-1"]),
        ),
    )

    resp = mediator.dispatch(envelope)
    assert len(attempts) == 2  # 1 initial + 1 retry
    records = mediator.get_execution_records()
    assert records[role.value]["execution_status"] == AgentExecutionStatus.TIMEOUT.value
    assert records[role.value]["error_code"] == "TIMEOUT"
    assert records[role.value]["retry_count"] == 1


def test_test6_invalid_agent_envelope_protocol_error():
    """TEST 6: Invalid AgentEnvelope produces explicit PROTOCOL_ERROR status."""
    app = create_agent_app(AgentRole.TELEMETRY_AGENT)
    client = TestClient(app)

    # Payload missing required schema_version format
    bad_payload = {
        "header": {
            "correlation_id": "test-bad-envelope",
            "sender": "orchestrator",
            "recipient": "telemetry_agent",
            "schema_version": "9.9.9",
            "message_type": "telemetry_dispatch",
        },
        "payload": {
            "scope": {"network_id": "net-bad", "devices": ["d-1"]},
        },
    }

    res = client.post("/process", json=bad_payload)
    assert res.status_code == 400
    assert "schema validation failed" in res.json()["detail"].lower()


def test_test7_conflicting_hypotheses_preserved_and_arbitrated():
    """TEST 7: Two agents produce contradictory hypotheses; conflict resolver evaluates both."""
    hyp_congestion = Hypothesis(
        hypothesis_id="hyp-1",
        probable_cause="Link congestion and queue drops",
        confidence=0.88,
        supporting_observation_ids=["obs-drops"],
    )
    hyp_hardware = Hypothesis(
        hypothesis_id="hyp-2",
        probable_cause="Catastrophic hardware forwarding crash",
        confidence=0.92,
        supporting_observation_ids=["obs-cpu", "obs-drops"],
    )

    # Conflict detection
    has_conflict = ConflictResolver.detect_conflicts([hyp_congestion, hyp_hardware])
    assert has_conflict is True

    # Arbitration without severe observations -> ties or falls to precedence
    result = ConflictResolver.arbitrate([hyp_congestion, hyp_hardware], [])
    assert len(result.conflicts_resolved) >= 1


def test_test8_insufficient_evidence_abstention():
    """TEST 8: Incomplete/ambiguous data leads to insufficient_evidence, not fabricated cause."""
    sparse_incident = {
        "incident_id": "inc-test8-sparse",
        "network_id": "campus-lan",
        "telemetry": [
            {
                "device_id": "rtr-border",
                "timestamp": "2026-11-01T00:00:00Z",
                # No anomalies, clean baseline
                "link_utilization_pct": 5.0,
                "packet_loss_pct": 0.0,
            }
        ],
        "topology": {"nodes": [{"id": "rtr-border"}], "edges": []},
    }

    report = run_diagnosis(sparse_incident)
    assert report.status in ("insufficient_evidence", "benign")
    assert report.confidence <= 0.50
    if report.status == "insufficient_evidence":
        assert report.probable_cause is None


def test_test9_circuit_breaker_transitions():
    """TEST 9: Circuit breaker transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_s=0.2)
    role = AgentRole.CONFIG_AGENT

    assert cb.get_state(role) == CircuitBreakerState.CLOSED

    # 1 failure -> still closed
    cb.record_failure(role)
    assert cb.get_state(role) == CircuitBreakerState.CLOSED

    # 2 failures -> trips to OPEN
    cb.record_failure(role)
    assert cb.get_state(role) == CircuitBreakerState.OPEN
    assert cb.is_open(role) is True

    # Wait for recovery timeout
    time.sleep(0.25)
    # is_open check transitions to HALF_OPEN
    assert cb.is_open(role) is False
    assert cb.get_state(role) == CircuitBreakerState.HALF_OPEN
    assert cb.is_half_open(role) is True

    # Successful probe restores to CLOSED
    cb.record_success(role)
    assert cb.get_state(role) == CircuitBreakerState.CLOSED
    assert cb.is_open(role) is False


def test_test10_bounded_concurrency_deterministic_aggregation():
    """TEST 10: Multiple simultaneous agent dispatches execute concurrently with deterministic order."""
    mediator = AgentMediator(mode="in_process")
    roles = [
        AgentRole.TELEMETRY_AGENT,
        AgentRole.TOPOLOGY_AGENT,
        AgentRole.CONFIG_AGENT,
        AgentRole.LOG_AGENT,
        AgentRole.WIFI_SERVICES_AGENT,
    ]

    envelopes = [
        AgentEnvelope(
            header=ProtocolHeader(
                correlation_id=f"corr-concurrent-{i}",
                sender=AgentRole.ORCHESTRATOR,
                recipient=r,
                message_type=MessageType.TELEMETRY_DISPATCH,
            ),
            payload=EnvelopePayload(
                scope=NetworkScope(network_id="net", devices=["dev-1"]),
            ),
        )
        for i, r in enumerate(roles)
    ]

    responses = mediator.dispatch_concurrent(envelopes)
    assert len(responses) == len(roles)
    # Verify deterministic response order matches input envelopes
    for r_role, resp in zip(roles, responses):
        assert resp.header.sender == r_role


def test_test11_duplicate_inquiry_does_not_create_duplicate_observations():
    """TEST 11: Duplicate inquiry responses do not create duplicate observations in state."""
    state = {
        "incident_id": "inc-dup-test",
        "network_id": "campus-lan",
        "scope_devices": ["sw-1"],
        "raw_data": {"telemetry": []},
        "accumulated_observations": [
            {
                "observation_id": "obs-1",
                "category": "metric_anomaly",
                "entity": "sw-1",
                "metric_name": "rx_power_dbm",
                "observed_value": -10.5,
                "unit": "dbm",
                "severity": "info",
            }
        ],
        "inquiries_queue": [
            {
                "inquiry_id": "inq-dup-1",
                "target_agent": "telemetry_agent",
                "question": "Retrieve optical DOM transceiver power levels for interfaces reporting CRC errors.",
                "target_entity": "sw-1",
                "answer": "Optical transceiver diagnostics report Rx power levels within specification (-10.5 dBm nominal).",
            }
        ],
        "inquiries_history": [],
        "processed_inquiry_hashes": [],
        "agent_execution": {},
        "iteration": 1,
    }

    res = node_inquiry(state)
    # The inquiry converted observation has the exact same entity/metric_name/observed_value/unit as obs-1.
    # Deduplication ensures count does not double!
    obs_list = res["accumulated_observations"]
    rx_power_obs = [o for o in obs_list if o.get("metric_name") == "rx_power_dbm"]
    assert len(rx_power_obs) == 1


def test_test12_service_auth_header_rejection():
    """TEST 12: Service authentication contract rejects unauthorized requests when token is configured."""
    app = create_agent_app(AgentRole.TELEMETRY_AGENT)
    client = TestClient(app)

    from netcoop.config import settings
    # Set internal service token
    orig_token = settings.internal_service_token
    try:
        settings.internal_service_token = "secret-netcoop-token-xyz"

        envelope = AgentEnvelope(
            header=ProtocolHeader(
                correlation_id="corr-auth-test",
                sender=AgentRole.ORCHESTRATOR,
                recipient=AgentRole.TELEMETRY_AGENT,
                message_type=MessageType.TELEMETRY_DISPATCH,
            ),
            payload=EnvelopePayload(
                scope=NetworkScope(network_id="net", devices=["sw-1"]),
            ),
        )

        # 1. Request without auth header -> 401
        res = client.post("/process", json=envelope.model_dump(mode="json"))
        assert res.status_code == 401

        # 2. Request with valid auth header -> 200
        headers = {settings.service_auth_header: "secret-netcoop-token-xyz"}
        res2 = client.post("/process", json=envelope.model_dump(mode="json"), headers=headers)
        assert res2.status_code == 200

        # 3. Health check remains unauthenticated
        res_health = client.get("/health")
        assert res_health.status_code == 200
    finally:
        settings.internal_service_token = orig_token
