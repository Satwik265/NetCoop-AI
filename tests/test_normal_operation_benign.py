"""Regression test suite for normal_operation resolution and non-fault boundaries.

Verifies:
1. normal_operation over 20 distinct seeds consistently returns benign status (DiagnosticStatus.BENIGN).
2. Every fault scenario, ambiguous_multi_fault, and insufficient_data never return benign.
"""

from __future__ import annotations

import os
import pytest

from netcoop.config import settings
from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.reporting.builder import DiagnosticReportBuilder
from netcoop.reporting.models import DiagnosticStatus


@pytest.fixture(autouse=True)
def setup_in_process_mode():
    old_env = {k: os.environ.get(k) for k in ("AGENTS_MODE", "IN_PROCESS_FALLBACK", "ALLOW_DEV_IN_PROCESS_FALLBACK")}
    old_mode = settings.agents_mode
    old_fb = settings.in_process_fallback
    old_allow = settings.allow_dev_in_process_fallback

    os.environ["AGENTS_MODE"] = "in_process"
    os.environ["IN_PROCESS_FALLBACK"] = "true"
    os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"
    settings.agents_mode = "in_process"
    settings.in_process_fallback = True
    settings.allow_dev_in_process_fallback = True

    yield

    for k, v in old_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    settings.agents_mode = old_mode
    settings.in_process_fallback = old_fb
    settings.allow_dev_in_process_fallback = old_allow


@pytest.mark.parametrize("seed", list(range(200, 220)))
def test_normal_operation_returns_benign_over_20_seeds(seed: int) -> None:
    """Requirement 2a: normal_operation over 20 seeds returns status 'benign' and V2 DiagnosticStatus.BENIGN."""
    gen = SyntheticNetworkGenerator()
    incident = gen.generate(scenario="normal_operation", seed=seed)
    report_v1 = run_diagnosis(incident)

    assert report_v1.status == "benign", f"Expected benign on seed {seed}, got {report_v1.status}"
    assert report_v1.confidence >= 0.80, f"Expected confidence >= 0.80, got {report_v1.confidence}"
    assert report_v1.probable_cause == "Normal Operation"

    # Verify V2 adapter conversion
    report_v2 = DiagnosticReportBuilder.from_unified_report(report_v1)
    assert report_v2.executive.diagnostic_status == DiagnosticStatus.BENIGN
    assert report_v2.executive.probable_root_cause == "Normal Operation"


@pytest.mark.parametrize(
    "fault_scenario",
    [
        "link_congestion",
        "weak_wifi_signal",
        "ethernet_interface_fault",
        "dns_failure",
        "dhcp_failure",
        "device_cpu_overload",
        "upstream_failure_cascade",
        "insufficient_data",
        "ambiguous_multi_fault",
    ],
)
def test_fault_and_ambiguous_scenarios_never_return_benign(fault_scenario: str) -> None:
    """Requirement 2b: Every fault scenario, ambiguous_multi_fault, and insufficient_data never return benign."""
    gen = SyntheticNetworkGenerator()
    for seed in (101, 102, 103):
        incident = gen.generate(scenario=fault_scenario, seed=seed)
        report_v1 = run_diagnosis(incident)

        assert report_v1.status != "benign", (
            f"Scenario '{fault_scenario}' with seed {seed} unexpectedly returned 'benign'!"
        )
        report_v2 = DiagnosticReportBuilder.from_unified_report(report_v1)
        assert report_v2.executive.diagnostic_status != DiagnosticStatus.BENIGN, (
            f"Scenario '{fault_scenario}' with seed {seed} produced DiagnosticStatus.BENIGN!"
        )

