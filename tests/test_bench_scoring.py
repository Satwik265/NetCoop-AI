"""tests/test_bench_scoring.py: Unit tests verifying bench scoring parity and known-correct scenarios."""

import json
import os
from pathlib import Path
import pytest

from netcoop.config import settings

os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from netcoop.core.bench_eval import evaluate_sample, extract_predicted_class
from scripts.bench import eval_interop_suite_split, eval_evidence_suite_split

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_link_congestion_known_correct():
    """Verify that a known-correct link_congestion scenario scores is_correct=True."""
    scenario_path = PROJECT_ROOT / "data" / "scenarios" / "link_congestion.json"
    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    res = evaluate_sample(data, "link_congestion")
    assert res["is_accepted"] is True
    assert res["is_diagnosed"] is True
    assert res["predicted_class"] == "link_congestion"
    assert res["is_correct"] is True
    assert res["is_fault_called_normal"] is False
    assert res["decision_category"] == "diagnosed"


def test_interop_suite_scoring():
    """Verify that interop suite evaluates against actual ground truth scenarios."""
    summary = eval_interop_suite_split()
    assert summary["total_samples"] == 8
    # 6 accepted (diagnosed), 2 abstained (interop_null_nan, interop_renamed_fields)
    assert summary["outcomes"]["accepted"] == 6
    assert summary["outcomes"]["abstained"] == 2
    # All 6 accepted must be correctly diagnosed link_congestion (100% selective accuracy)
    assert summary["selective_metrics"]["correct_count"] == 6
    assert summary["selective_metrics"]["wrong_count"] == 0
    assert summary["selective_metrics"]["selective_accuracy"] == 1.0


def test_evidence_suite_scoring():
    """Verify that evidence suite fixtures evaluate against canonical classes."""
    summary = eval_evidence_suite_split()
    assert summary["total_samples"] == 7
    # 4 diagnosed (mtu, link_congestion_with_logs, ethernet_fault_with_logs, conflicting_evidence)
    # 3 abstained (05_sparse, ambiguous_multi_fault, insufficient_data)
    assert summary["outcomes"]["accepted"] == 4
    assert summary["outcomes"]["abstained"] == 3
    # All 4 accepted are correctly diagnosed (100% selective accuracy)
    assert summary["selective_metrics"]["correct_count"] == 4
    assert summary["selective_metrics"]["wrong_count"] == 0
    assert summary["selective_metrics"]["selective_accuracy"] == 1.0
