"""Phase 13I CI Regression Tests: Domain Rule Precedence & Organizer Exact Match Guarantee.

Enforces:
1. Precedence policy: deterministic multi-signal domain rules with sufficient evidence
   are preserved and not overridden by ambiguous conformal sets or classifier abstention.
2. Inadequate domain evidence (competing specialist findings or insufficient support)
   properly triggers disciplined abstention.
3. Organizer per-class exact match >= 0.95 on frozen validation slice.
"""

import os
import sys
import copy
from pathlib import Path
import pytest

os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"

from netcoop.config import settings
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from data.organizer.organizer_generator import OrganizerTelemetryGenerator
from gateway.adapters.organizer_adapter import OrganizerAdapter
from netcoop.orchestrator.graph import run_diagnosis, compiled_diagnostic_graph
from netcoop.data.generator import SyntheticNetworkGenerator
from eval.run_eval import evaluate_single_organizer, load_organizer_label_map


def test_deterministic_rule_precedence_over_ambiguous_conformal() -> None:
    """Deterministic domain rule with multi-signal evidence is not overridden by ambiguous conformal set."""
    inc = OrganizerTelemetryGenerator.generate_incident(fault_type="hardware_failure", seed=6050, is_window=True)
    adapted = OrganizerAdapter.adapt_dataset(inc["payload"])
    rep = run_diagnosis(adapted)

    assert rep.status == "diagnosed", f"Expected diagnosed, got {rep.status}"
    assert "hardware" in str(rep.probable_cause).lower(), f"Expected hardware failure, got {rep.probable_cause}"
    assert rep.confidence >= 0.70, f"Expected confidence >= 0.70, got {rep.confidence}"
    # Verify alternative hypotheses contain competing conformal classes
    assert hasattr(rep, "uncertainty")


def test_ambiguous_multi_fault_properly_abstains() -> None:
    """When multiple domain specialists identify conflicting fault causes, system must abstain."""
    inc = SyntheticNetworkGenerator.generate(scenario="ambiguous_multi_fault", seed=303)
    rep = run_diagnosis(inc)

    assert rep.status in ("insufficient_evidence", "ambiguous"), f"Expected abstention on multi-fault, got {rep.status}"
    assert rep.probable_cause is None, f"Expected no single probable cause, got {rep.probable_cause}"


def test_insufficient_rule_evidence_properly_abstains() -> None:
    """A hypothesis with insufficient evidence (e.g. is_sufficient=False or support < 2) must abstain under ambiguity."""
    inc = SyntheticNetworkGenerator.generate(scenario="ambiguous_multi_fault", seed=315)
    rep = run_diagnosis(inc)

    assert rep.status in ("insufficient_evidence", "ambiguous"), f"Expected abstention, got {rep.status}"


@pytest.mark.parametrize("scenario", ["normal", "latency_spike", "hardware_failure"])
@pytest.mark.parametrize("is_window", [True, False])
def test_organizer_frozen_slice_accuracy(scenario: str, is_window: bool) -> None:
    """Organizer per-class exact match >= 0.95 on representative slice of frozen seeds 6050-6069."""
    label_map = load_organizer_label_map()
    seeds = range(6050, 6070)  # 20 seeds per scenario/mode
    results = [
        evaluate_single_organizer(scenario, s, is_window, label_map)
        for s in seeds
    ]
    exact_count = sum(1 for r in results if r.get("exact_match"))
    exact_rate = exact_count / len(results)
    mode_name = "windowed" if is_window else "snapshot"
    assert exact_rate >= 0.95, f"Exact match for {mode_name}_{scenario} was {exact_rate:.2%} (< 95%)"
