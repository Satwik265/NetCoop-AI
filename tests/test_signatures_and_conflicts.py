"""Comprehensive tests for fault signatures, causal chains, and conflict arbitration."""

import pytest
from netcoop.core.envelope import AgentRole, Hypothesis, Observation, ObservationCategory, Severity
from netcoop.core.signatures import (
    EvidencePrecedence,
    HypothesisKey,
    SIGNATURE_REGISTRY,
    SignatureMatcher,
)
from netcoop.orchestrator.conflict_resolver import ConflictResolver


def test_signature_registry_all_ten_hypotheses() -> None:
    """Verify all 10 standard network hypothesis models are formally defined with causal chains."""
    expected_keys = [
        HypothesisKey.LINK_CONGESTION,
        HypothesisKey.UPSTREAM_CONGESTION,
        HypothesisKey.WEAK_WIFI_SIGNAL,
        HypothesisKey.INTERFACE_OR_CABLE_FAULT,
        HypothesisKey.DEVICE_CPU_OVERLOAD,
        HypothesisKey.DNS_FAILURE,
        HypothesisKey.DHCP_FAILURE,
        HypothesisKey.DEVICE_HARDWARE_FAILURE,
        HypothesisKey.NO_FAULT,
        HypothesisKey.UNKNOWN,
    ]

    for k in expected_keys:
        assert k in SIGNATURE_REGISTRY, f"Missing signature: {k}"
        sig = SIGNATURE_REGISTRY[k]
        assert sig.title
        assert sig.description
        assert len(sig.causal_chain) >= 2, f"Causal chain too short for {k}"
        assert sig.discriminating_test


def test_conflict_resolver_direct_over_correlated() -> None:
    """Verify direct evidence (e.g. optical degradation or hardware failure) takes precedence over soft queue congestion."""
    hyp_congestion = Hypothesis(
        probable_cause="Link utilization saturation causing buffer queue drops and latency spikes",
        confidence=0.88,
        supporting_observation_ids=["obs-drops"],
    )
    hyp_optics = Hypothesis(
        probable_cause="Physical Layer Optical Signal Degradation (SFP/Fiber Loss)",
        confidence=0.85,
        supporting_observation_ids=["obs-optics"],
    )

    observations = [
        Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity="sw-1:et-0/0/1",
            metric_name="rx_power_dbm",
            observed_value=-18.5,
            unit="dbm",
            severity=Severity.CRITICAL,
        ),
        Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity="sw-1:et-0/0/1",
            metric_name="queue_drops",
            observed_value=250,
            unit="packets",
            severity=Severity.WARNING,
        ),
    ]

    winner, rationale, resolved = ConflictResolver.arbitrate(
        [hyp_congestion, hyp_optics], observations
    )
    assert winner is not None
    assert winner.probable_cause == hyp_optics.probable_cause
    assert "Optical" in rationale or "DIRECT" in str(resolved)
    assert len(resolved) >= 1
    assert resolved[0]["precedence"] == "DIRECT"


def test_conflict_resolver_hardware_failure_over_congestion() -> None:
    """Verify catastrophic hardware failure takes precedence over secondary buffer congestion."""
    hyp_hw = Hypothesis(
        probable_cause="Device hardware failure or catastrophic control plane crash",
        confidence=0.95,
        supporting_observation_ids=["obs-hw"],
    )
    hyp_cong = Hypothesis(
        probable_cause="Link utilization saturation causing buffer queue drops and latency spikes",
        confidence=0.90,
        supporting_observation_ids=["obs-cong"],
    )

    observations = [
        Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity="SW_CAMPUS_1",
            metric_name="cpu_pct",
            observed_value=99.9,
            unit="percent",
            severity=Severity.CRITICAL,
        ),
        Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity="SW_CAMPUS_1",
            metric_name="queue_drops",
            observed_value=8500,
            unit="packets",
            severity=Severity.CRITICAL,
        ),
    ]

    winner, rationale, resolved = ConflictResolver.arbitrate([hyp_cong, hyp_hw], observations)
    assert winner is not None
    assert winner.probable_cause == hyp_hw.probable_cause
    assert "Hardware Failure" in resolved[0]["conflict"]


def test_conflict_resolver_tie_triggers_arbitration_tie() -> None:
    """Verify equal precedence candidates within 0.05 margin yield arbitration tie and inquiries."""
    hyp_a = Hypothesis(
        probable_cause="Control-plane CPU exhaustion on core router driving queue drops",
        confidence=0.88,
        supporting_observation_ids=["obs-cpu"],
    )
    hyp_b = Hypothesis(
        probable_cause="Link utilization saturation causing buffer queue drops and latency spikes",
        confidence=0.86,
        supporting_observation_ids=["obs-util"],
    )

    # Both are CORRELATED precedence, delta = 0.02 <= 0.05
    winner, rationale, resolved = ConflictResolver.arbitrate([hyp_a, hyp_b], [])
    assert winner is None
    assert "Arbitration tie" in rationale
    assert resolved[0]["winner"] == "TIE"


def test_cross_inquiry_generation() -> None:
    """Verify that ambiguities generate targeted inquiries for corroboration."""
    hyp_drops = Hypothesis(
        probable_cause="Link congestion",
        confidence=0.85,
        supporting_observation_ids=["obs-drops"],
    )
    obs = [
        Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity="leaf-01:et-0/0/1",
            metric_name="queue_drops",
            observed_value=500,
            unit="packets",
            severity=Severity.CRITICAL,
        )
    ]

    inquiries = ConflictResolver.generate_cross_inquiries([hyp_drops], obs)
    assert len(inquiries) >= 1
    # Check that MTU audit was queried
    target_agents = [inq.target_agent for inq in inquiries]
    assert AgentRole.CONFIG_AGENT in target_agents


def test_signature_matcher_organizer_hardware_pattern() -> None:
    """Verify SignatureMatcher accurately isolates organizer hardware_failure dataset."""
    telemetry = [
        {
            "device_id": "SW_CAMPUS_1",
            "device_status": "Critical",
            "cpu_pct": 99.9,
            "packet_loss_pct": 24.5,
            "queue_drops": 9500,
            "latency_ms": 520.0,
        }
    ]

    key, conf, aff_devs, alternatives, limitations = SignatureMatcher.evaluate_telemetry(telemetry)
    assert key == HypothesisKey.DEVICE_HARDWARE_FAILURE
    assert conf >= 0.85
    assert "SW_CAMPUS_1" in aff_devs


def test_signature_matcher_organizer_latency_spike_pattern() -> None:
    """Verify SignatureMatcher yields link_congestion and ranked upstream_congestion with discriminating test."""
    telemetry = [
        {
            "device_id": "SW_CAMPUS_1",
            "device_status": "Warning",
            "latency_ms": 210.0,
            "jitter_ms": 65.0,
            "link_utilization_pct": 68.0,
            "queue_drops": 45,
        }
    ]

    key, conf, aff_devs, alternatives, limitations = SignatureMatcher.evaluate_telemetry(
        telemetry, topology_available=True
    )
    assert key == HypothesisKey.LINK_CONGESTION
    assert len(alternatives) >= 1
    alt = alternatives[0]
    assert "Upstream" in alt["cause"]
    assert "discriminating_test" in alt
    assert alt["confidence"] > 0.0
