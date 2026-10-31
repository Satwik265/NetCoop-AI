"""Unit tests verifying envelope serialization, SI unit validation, and JSON schema compliance."""

import json
from pathlib import Path
import jsonschema
import pytest
from pydantic import ValidationError

from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    EnvelopePayload,
    Hypothesis,
    MessageType,
    NetworkScope,
    Observation,
    ObservationCategory,
    Priority,
    ProtocolHeader,
    Severity,
)


def load_envelope_schema() -> dict:
    """Load formal JSON schema from disk."""
    schema_path = Path(__file__).parent.parent / "schemas" / "envelope.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_valid_agent_envelope_creation() -> None:
    """Verify that a well-formed envelope complies with Pydantic and JSON Schema."""
    envelope = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-12345",
            sender=AgentRole.TELEMETRY_AGENT,
            recipient=AgentRole.ORCHESTRATOR,
            schema_version="1.0.0",
            message_type=MessageType.FINDING_SUBMISSION,
            priority=Priority.NORMAL,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(
                network_id="dc-fabric-01",
                devices=["spine-01", "leaf-01"],
                interfaces=["et-0/0/1"],
            ),
            observations=[
                Observation(
                    category=ObservationCategory.METRIC_ANOMALY,
                    entity="leaf-01:et-0/0/1",
                    metric_name="egress_queue_drops",
                    observed_value=1240,
                    baseline_value=0,
                    unit="packets",
                    severity=Severity.CRITICAL,
                )
            ],
            hypotheses=[
                Hypothesis(
                    probable_cause="Egress buffer exhaustion under microbursts",
                    confidence=0.85,
                    supporting_observation_ids=["obs-001"],
                    required_corroboration=["config_agent:qos_policy"],
                )
            ],
        ),
    )

    # Validate against JSON Schema
    envelope_dict = json.loads(envelope.to_json())
    schema = load_envelope_schema()
    jsonschema.validate(instance=envelope_dict, schema=schema)

    assert envelope.header.sender == AgentRole.TELEMETRY_AGENT
    assert envelope.payload.observations[0].unit == "packets"
    assert envelope.payload.hypotheses[0].confidence == 0.85


def test_invalid_unit_raises_validation_error() -> None:
    """Verify that unsupported units trigger validation error."""
    with pytest.raises(ValidationError):
        Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity="spine-01",
            metric_name="unknown_metric",
            observed_value=100,
            unit="arbitrary_unknown_unit",
            severity=Severity.WARNING,
        )


def test_invalid_schema_version_rejected() -> None:
    """Verify incompatible schema version numbers are caught."""
    with pytest.raises(ValidationError):
        ProtocolHeader(
            correlation_id="corr-test",
            sender=AgentRole.CONFIG_AGENT,
            recipient=AgentRole.ORCHESTRATOR,
            schema_version="2.0.0",  # Requires 1.x.x
            message_type=MessageType.FINDING_SUBMISSION,
        )


def test_protocol_error_response_generation() -> None:
    """Verify protocol error envelopes are properly formatted."""
    original = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="corr-err-test",
            sender=AgentRole.CONFIG_AGENT,
            recipient=AgentRole.ORCHESTRATOR,
            message_type=MessageType.FINDING_SUBMISSION,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net-1", devices=["sw-1"]),
        ),
    )

    error_env = AgentEnvelope.create_error_response(
        original=original,
        error_code="SCHEMA_VALIDATION_FAILED",
        message="Field 'unit' must be a recognized SI standard",
        field_path="payload.observations[0].unit",
    )

    assert error_env.header.message_type == MessageType.PROTOCOL_ERROR
    assert error_env.header.sender == AgentRole.ORCHESTRATOR
    assert error_env.header.recipient == AgentRole.CONFIG_AGENT
    assert error_env.payload.error is not None
    assert error_env.payload.error.error_code == "SCHEMA_VALIDATION_FAILED"
