"""Tests for RemediationEngine cause-key normalization and campus coverage."""

from __future__ import annotations

import os
import pytest

from netcoop.config import settings
from netcoop.core.evidence import DiagnosticHypothesis
from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.remediation.engine import RemediationEngine
from netcoop.remediation.safety import RemediationSafetyChecker
from netcoop.reporting.builder import export_hackathon_report_json


@pytest.fixture(autouse=True)
def setup_in_process_mode() -> None:
    os.environ["AGENTS_MODE"] = "in_process"
    os.environ["IN_PROCESS_FALLBACK"] = "true"
    os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"
    settings.agents_mode = "in_process"
    settings.in_process_fallback = True
    settings.allow_dev_in_process_fallback = True


ALL_EMITTED_CAUSES = [
    "BGP_ROUTE_FLAP_DAMPING",
    "DEVICE_CPU_OVERLOAD",
    "DEVICE_HARDWARE_FAILURE",
    "DHCP_FAILURE",
    "DNS_FAILURE",
    "ETHERNET_INTERFACE_FAULT",
    "LINK_CONGESTION",
    "MTU_MISMATCH_BLACKHOLE",
    "NO_FAULT",
    "OPTICAL_TRANSCEIVER_DEGRADATION",
    "STP_SPLIT_BRAIN_LOOP",
    "UPSTREAM_FAILURE_CASCADE",
    "WEAK_WIFI_SIGNAL",
]

NORMAL_TOPOLOGY = [
    "core-rtr-01",
    "dist-sw-core",
    "dept-sw-cs-01",
    "dist-sw-hostel",
    "ap-hostel-b1",
    "host-student-01",
]


@pytest.mark.parametrize("cause_key", ALL_EMITTED_CAUSES)
def test_every_cause_key_remediation_coverage(cause_key: str) -> None:
    """Verify generate_plan returns >=1 action for all causes except NO_FAULT (which returns 0)."""
    hyp = DiagnosticHypothesis(
        cause_key=cause_key,
        title=f"Test hypothesis for {cause_key}",
        description="Hypothesis description",
        affected_devices=["core-rtr-01", "dist-sw-core"] if cause_key != "NO_FAULT" else [],
        supporting_evidence=[],
    )
    actions = RemediationEngine.generate_plan(hyp, NORMAL_TOPOLOGY)

    if cause_key == "NO_FAULT":
        assert len(actions) == 0, f"NO_FAULT unexpectedly returned {len(actions)} actions"
    else:
        assert len(actions) >= 1, f"Cause '{cause_key}' returned 0 actions"
        for act in actions:
            passed, checks = RemediationSafetyChecker.evaluate_preflight(act, NORMAL_TOPOLOGY)
            assert passed is True, f"Action '{act.title}' failed safety preflight: {checks}"


@pytest.mark.parametrize(
    "lower_key, upper_key",
    [
        ("link_congestion", "LINK_CONGESTION"),
        ("weak_wifi_signal", "WEAK_WIFI_SIGNAL"),
        ("dns_failure", "DNS_FAILURE"),
        ("dhcp_failure", "DHCP_FAILURE"),
        ("device_cpu_overload", "DEVICE_CPU_OVERLOAD"),
        ("upstream_failure_cascade", "UPSTREAM_FAILURE_CASCADE"),
        ("ethernet_interface_fault", "ETHERNET_INTERFACE_FAULT"),
    ],
)
def test_case_variant_cause_keys_produce_identical_actions(lower_key: str, upper_key: str) -> None:
    """Verify case variants give identical remediation actions."""
    hyp_lower = DiagnosticHypothesis(
        cause_key=lower_key,
        title="Test",
        description="Test",
        affected_devices=["core-rtr-01"],
        supporting_evidence=[],
    )
    hyp_upper = DiagnosticHypothesis(
        cause_key=upper_key,
        title="Test",
        description="Test",
        affected_devices=["core-rtr-01"],
        supporting_evidence=[],
    )

    actions_lower = RemediationEngine.generate_plan(hyp_lower, NORMAL_TOPOLOGY)
    actions_upper = RemediationEngine.generate_plan(hyp_upper, NORMAL_TOPOLOGY)

    assert len(actions_lower) == len(actions_upper)
    for a1, a2 in zip(actions_lower, actions_upper):
        assert a1.title == a2.title
        assert a1.commands == a2.commands
        assert a1.rollback_commands == a2.rollback_commands
        assert a1.risk_level == a2.risk_level
        assert a1.blast_radius_devices == a2.blast_radius_devices


@pytest.mark.parametrize(
    "scenario, expected_non_empty",
    [
        ("link_congestion", True),
        ("weak_wifi_signal", True),
        ("dns_failure", True),
        ("dhcp_failure", True),
        ("device_cpu_overload", True),
        ("upstream_failure_cascade", True),
        ("ethernet_interface_fault", True),
        ("normal_operation", False),
    ],
)
def test_live_scenarios_recommended_actions(scenario: str, expected_non_empty: bool) -> None:
    """Verify run_diagnosis produces non-empty recommended_actions strings for fault scenarios, and [] for normal_operation."""
    gen = SyntheticNetworkGenerator()
    inc = gen.generate(scenario=scenario, seed=42)
    rep = run_diagnosis(inc)

    h_rep = export_hackathon_report_json(rep)
    recommended = h_rep.get("recommended_actions", [])

    if expected_non_empty:
        assert len(recommended) > 0, f"Scenario '{scenario}' produced empty recommended_actions"
        assert all(isinstance(a, str) for a in recommended), f"Non-string items in recommended_actions: {recommended}"
        assert all(len(a.strip()) > 0 for a in recommended), f"Empty strings in recommended_actions: {recommended}"
    else:
        assert recommended == [], f"Scenario '{scenario}' expected empty recommended_actions, got {recommended}"
