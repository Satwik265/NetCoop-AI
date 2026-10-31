"""Tests for conflict detection and deterministic arbitration."""

from netcoop.core.envelope import Hypothesis, Observation, ObservationCategory, Severity
from netcoop.orchestrator.conflict_resolver import ConflictResolver


def test_conflict_detection_multiple_domains() -> None:
    """Verify conflict is detected when competing hypotheses are proposed."""
    hyp1 = Hypothesis(
        probable_cause="Path MTU size disparity between interconnected endpoints",
        confidence=0.85,
        supporting_observation_ids=["obs-1"],
    )
    hyp2 = Hypothesis(
        probable_cause="Physical transceiver optical signal degradation",
        confidence=0.82,
        supporting_observation_ids=["obs-2"],
    )
    assert ConflictResolver.detect_conflicts([hyp1, hyp2]) is True


def test_arbitration_physical_optics_precedence() -> None:
    """Verify optical power degradation below threshold arbitrates over soft counter anomalies."""
    hyp_optics = Hypothesis(
        probable_cause="Physical transceiver optical signal degradation",
        confidence=0.85,
        supporting_observation_ids=["obs-optics"],
    )
    hyp_queue = Hypothesis(
        probable_cause="Egress buffer congestion",
        confidence=0.80,
        supporting_observation_ids=["obs-queue"],
    )
    obs = [
        Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity="core-a:et-1",
            metric_name="rx_power_dbm",
            observed_value=-18.5,
            unit="dbm",
            severity=Severity.CRITICAL,
        ),
        Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity="core-a:et-1",
            metric_name="fcs_errors",
            observed_value=200,
            unit="packets",
            severity=Severity.CRITICAL,
        ),
    ]

    winner, rationale = ConflictResolver.arbitrate([hyp_queue, hyp_optics], obs)
    assert winner is not None
    assert "optical" in winner.probable_cause.lower()
    assert "Optical Rx power attenuation" in rationale


def test_arbitration_tie_returns_none() -> None:
    """Verify tie within 0.10 margin without decisive rule yields None (insufficient evidence)."""
    hyp1 = Hypothesis(
        probable_cause="Software bug A in routing daemon",
        confidence=0.62,
        supporting_observation_ids=["obs-1"],
    )
    hyp2 = Hypothesis(
        probable_cause="Hardware memory leak B in linecard",
        confidence=0.60,
        supporting_observation_ids=["obs-2"],
    )
    winner, rationale = ConflictResolver.arbitrate([hyp1, hyp2], [])
    assert winner is None
    assert "Arbitration tie" in rationale
