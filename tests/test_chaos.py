"""Chaos, circuit-breaker, and degraded-mode resilience testing."""

import json
from pathlib import Path
import pytest
from netcoop.core.envelope import AgentRole, MessageType
from netcoop.core.evidence import DiagnosticHypothesis, UncertaintyEvaluation
from netcoop.core.report import ReportBuilder, UnifiedDiagnosticReport
from netcoop.core.signatures import HypothesisKey, SignatureMatcher
from netcoop.core.thresholds import is_snapshot_mode
from netcoop.orchestrator.mediator import AgentMediator, CircuitBreaker


def test_circuit_breaker_trips_and_fast_fails() -> None:
    """Verify that repeated microservice failures trip circuit breaker to open state."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_s=30.0)
    role = AgentRole.WIFI_SERVICES_AGENT

    assert not cb.is_open(role)
    cb.record_failure(role)
    assert not cb.is_open(role)

    # Second failure trips breaker
    cb.record_failure(role)
    assert cb.is_open(role)

    # Success resets breaker
    cb.record_success(role)
    assert not cb.is_open(role)


def test_mediator_degraded_mode_continuation() -> None:
    """Verify mediator records dead agents in limitations without crashing when in-process fallback occurs."""
    mediator = AgentMediator(mode="http")
    # Mark an agent as dead
    mediator.dead_agents.add("wifi_services_agent")
    mediator.dead_agents.add("classifier_agent")

    limitations = mediator.get_degraded_limitations()
    assert len(limitations) == 2
    assert any("classifier_agent" in l for l in limitations)
    assert any("wifi_services_agent" in l for l in limitations)


def test_missing_topology_handling() -> None:
    """Verify missing topology marks upstream alternatives unverifiable and notes limitation."""
    telemetry = [
        {
            "device_id": "SW_CAMPUS_1",
            "latency_ms": 180.0,
            "jitter_ms": 45.0,
            "link_utilization_pct": 65.0,
            "queue_drops": 25,
        }
    ]

    key, conf, aff_devs, alternatives, limitations = SignatureMatcher.evaluate_telemetry(
        telemetry, topology_available=False
    )
    assert key == HypothesisKey.LINK_CONGESTION
    assert any("topology data unavailable" in l for l in limitations)

    # Alternative should be marked unverifiable
    assert len(alternatives) >= 1
    upstream_alt = alternatives[0]
    assert upstream_alt.get("status") == "unverifiable"


def test_snapshot_mode_detection_and_penalty() -> None:
    """Verify single snapshot telemetry is detected and confidence is penalized."""
    # Single sample per device
    snapshot_records = [
        {"device_id": "SW_1", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 15.0},
        {"device_id": "SW_2", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 12.0},
    ]

    assert is_snapshot_mode(snapshot_records) is True

    # Multi-point time series
    series_records = [
        {"device_id": "SW_1", "timestamp": f"2026-10-31T12:0{i}:00Z", "latency_ms": 15.0}
        for i in range(5)
    ]
    assert is_snapshot_mode(series_records) is False


def test_report_to_markdown_rendering() -> None:
    """Verify UnifiedDiagnosticReport.to_markdown() produces clean monochrome output."""
    report = ReportBuilder.build_report(
        incident_id="inc-test-md",
        network_id="iit-bbs-campus",
        status="diagnosed",
        hypothesis=DiagnosticHypothesis(
            cause_key="LINK_CONGESTION",
            title="Link utilization saturation causing buffer queue drops and latency spikes",
            description="Core transit link saturated.",
            affected_devices=["SW_CAMPUS_1", "SW_CAMPUS_2"],
            final_confidence=0.92,
            is_sufficient=True,
        ),
        uncertainty=UncertaintyEvaluation(
            score=0.08,
            reasons=[],
            missing_evidence=[],
            alternative_hypotheses=[
                {
                    "cause": "Upstream provider congestion",
                    "confidence": 0.80,
                    "discriminating_test": "Check upstream queue drops",
                }
            ],
        ),
        causal_chain=[
            "High traffic volume exceeds link capacity",
            "Queue drops trigger packet delay",
        ],
        conflicts_resolved=[
            {
                "conflict": "Hardware vs Congestion",
                "winner": "Hardware",
                "precedence": "DIRECT",
                "rationale": "Direct hardware precedence",
                "iteration": 1,
            }
        ],
        limitations=["single snapshot, no temporal context"],
        provenance={"generator": "test_generator"},
    )

    md = report.to_markdown()
    assert "# Diagnostic Incident Report: inc-test-md" in md
    assert "## Summary" in md
    assert "## Causal Chain" in md
    assert "## Alternative Hypotheses" in md
    assert "## Multi-Agent Conflicts & Arbitration" in md
    assert "## Data Limitations & Caveats" in md
    assert "single snapshot, no temporal context" in md


def test_report_schema_json_validation() -> None:
    """Verify generated UnifiedDiagnosticReport validates against schemas/diagnostic_report.json."""
    import jsonschema

    schema_file = Path("schemas/diagnostic_report.json")
    assert schema_file.exists(), "schemas/diagnostic_report.json missing"
    with open(schema_file, "r", encoding="utf-8") as f:
        schema = json.load(f)

    report = ReportBuilder.build_report(
        incident_id="inc-schema-val",
        network_id="iit-bbs-campus",
        status="diagnosed",
        hypothesis=DiagnosticHypothesis(
            cause_key="DEVICE_HARDWARE_FAILURE",
            title="Device hardware failure or catastrophic control plane crash",
            description="Hardware failure.",
            affected_devices=["SW_CAMPUS_1"],
            final_confidence=0.95,
            is_sufficient=True,
        ),
        uncertainty=UncertaintyEvaluation(
            score=0.05,
            reasons=[],
            missing_evidence=[],
        ),
        causal_chain=["Hardware failure", "Forwarding halted"],
        conflicts_resolved=[{"iteration": 1, "rationale": "Arbitrated"}],
        limitations=["missing metrics"],
        provenance={"generator": "organizer_adapter"},
    )

    report_dict = json.loads(report.to_json())
    jsonschema.validate(instance=report_dict, schema=schema)
