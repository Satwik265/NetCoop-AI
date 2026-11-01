"""Property-based testing with Hypothesis verifying system resilience to dirty or malformed inputs."""

from hypothesis import given, strategies as st
from pydantic import ValidationError

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
from netcoop.core.normalizer import TelemetryNormalizer


@given(
    val=st.one_of(
        st.integers(min_value=-10**9, max_value=10**9),
        st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
        st.text(min_size=0, max_size=50),
    ),
    unit=st.sampled_from(["bps", "kbps", "mbps", "gbps", "packets", "ms", "s", "us", "dbm", "percent", "ratio", "unknown_unit"]),
)
def test_normalizer_metric_fuzzing(val: object, unit: str) -> None:
    """Property: TelemetryNormalizer.normalize_metric must never raise an unhandled exception."""
    norm_val, std_unit = TelemetryNormalizer.normalize_metric(val, unit)
    assert norm_val is None or isinstance(norm_val, (float, int))
    assert isinstance(std_unit, str)


@given(ts_str=st.text(min_size=0, max_size=100))
def test_normalizer_timestamp_fuzzing(ts_str: str) -> None:
    """Property: parse_iso_timestamp must return a datetime or None, never crash."""
    res = TelemetryNormalizer.parse_iso_timestamp(ts_str)
    assert res is None or hasattr(res, "isoformat")


@given(if_str=st.text(min_size=0, max_size=50))
def test_normalizer_interface_fuzzing(if_str: str) -> None:
    """Property: standardize_interface_name must return a clean string without crashing."""
    res = TelemetryNormalizer.standardize_interface_name(if_str)
    assert isinstance(res, str)


@given(
    confidence=st.floats(min_value=0.0, max_value=1.0),
    observed_val=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_observation_property_validity(confidence: float, observed_val: float) -> None:
    """Property: Valid numeric values in observations must cleanly serialize and validate."""
    obs = Observation(
        category=ObservationCategory.METRIC_ANOMALY,
        entity="dev-1:et-0/0/1",
        metric_name="egress_queue_drops",
        observed_value=observed_val,
        unit="packets",
        severity=Severity.WARNING,
    )
    assert obs.observed_value == observed_val
    assert obs.unit == "packets"

