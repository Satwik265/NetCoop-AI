"""test_docs_consistency.py: Ensure documentation numbers, LaTeX, and contracts match benchmark artifacts."""

import json
import re
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
README_PATH = BASE_DIR / "README.md"
SCORECARD_PATH = BASE_DIR / "docs" / "scorecard.json"
HOLDOUTS_PATH = BASE_DIR / "eval" / "results" / "phase13o_fresh_holdouts_evaluation.json"
EVIDENCE_LEDGER_PATH = BASE_DIR / "docs" / "evidence_ledger.md"
DERIVED_PATH = BASE_DIR / "eval" / "results" / "benchmark_phase11_derived.json"
FINAL_RC_PATH = BASE_DIR / "docs" / "final_release_candidate_report.md"
PROGRESS_PATH = BASE_DIR / "docs" / "progress.md"
MODEL_CARD_PATH = BASE_DIR / "netcoop" / "models" / "MODEL_CARD.md"


@pytest.fixture
def scorecard_data():
    with open(SCORECARD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def holdouts_data():
    with open(HOLDOUTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def readme_text():
    with open(README_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_readme_numbers_match_scorecard_json(scorecard_data, readme_text):
    """Verify that scorecard metrics in README match docs/scorecard.json."""
    meta = scorecard_data["metadata"]
    splits = scorecard_data["splits"]
    latency = scorecard_data["latency"]
    det = scorecard_data["determinism"]

    assert meta["version"] in readme_text, f"Expected {meta['version']} in README"
    assert (str(meta["total_samples_evaluated"]) in readme_text or f"{meta['total_samples_evaluated']:,}" in readme_text)

    # Verify split metrics appear in README
    for k, sp in splits.items():
        assert sp["split_name"] in readme_text
        cov_pct = f"{sp['outcomes']['coverage_pct']}%"
        assert cov_pct in readme_text
        sel_acc_pct = f"{sp['selective_metrics']['selective_accuracy'] * 100:.1f}%"
        assert sel_acc_pct in readme_text

    # Latency
    in_proc = latency.get("in_process_testclient", latency)
    assert f"{in_proc['p50_latency_ms']} ms" in readme_text
    assert f"{in_proc['p95_latency_ms']} ms" in readme_text

    # Determinism
    assert f"{det['differing_seeds_count']}" in readme_text


def test_readme_fresh_holdouts_match_json(holdouts_data, readme_text):
    """Verify fresh holdout metrics in README match evaluation JSON."""
    fresh = holdouts_data["fresh_holdouts"]
    for split_key in ["unseen_topologies_450", "organizer_suite_300", "heldout_suite_150", "emulation_episodes_50"]:
        sp = fresh[split_key]
        assert sp["split_name"] in readme_text
        assert str(sp["total_samples"]) in readme_text


def test_readme_evidence_ledger_consistency(readme_text):
    """Verify evidence ledger summary numbers match in README."""
    assert "3,015" in readme_text  # Clean holdouts
    assert "1,100" in readme_text  # Development
    assert "1,600" in readme_text  # Tuned
    assert "5,715" in readme_text  # Total


def test_no_stale_metrics_in_docs(readme_text):
    """Verify that stale evaluation figures from earlier phases are completely removed."""
    stale_patterns = [
        "Exact-Match Accuracy: 98.7%",
        "Macro F1: 0.985",
        "ECE: 0.038",
        "overall accuracy 55.2%",
        "ECE of 0.180",
    ]
    for sp in stale_patterns:
        assert sp not in readme_text, f"Stale pattern '{sp}' found in README.md"

    with open(FINAL_RC_PATH, "r", encoding="utf-8") as f:
        rc_text = f.read()
    assert "Exact-Match Accuracy: 98.7%" not in rc_text
    assert "Macro F1: 0.985" not in rc_text


def test_no_broken_latex_or_ascii_bell(readme_text):
    """Verify that broken LaTeX like '\\x07lpha' or unescaped tabs in math do not exist."""
    assert "\x07lpha" not in readme_text
    assert " lpha" not in readme_text
    assert "\\alpha" in readme_text


def test_no_literal_secrets_in_docs(readme_text):
    """Verify that no literal service tokens or hardcoded secrets are present in tracked docs."""
    assert "4f8b2c1e7a9d3f5b8e0c2a4d6f8a1b3c5e7d9a0f2b4c6e8a0d2f4b6c8e0a2d4f" not in readme_text
    assert "<generate-32-byte-hex-token>" in readme_text


def test_derived_artifact_row_8_accounting():
    """Verify that the derived benchmark artifact accurately documents the row 8 trace."""
    assert DERIVED_PATH.exists(), "Derived benchmark artifact must exist"
    with open(DERIVED_PATH, "r", encoding="utf-8") as f:
        derived = json.load(f)

    meta = derived.get("derived_metadata", {})
    trace = meta.get("row_8_upstream_cascade_trace", {})
    assert trace.get("row_sum") == 40
    assert trace.get("misdiagnosed_as_link_congestion") == 1
    assert "seed 313" in trace.get("misdiagnosed_seed", "")


def test_progress_md_consistency():
    """Verify progress.md contains correct classifier architecture and no stale claims."""
    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        ptext = f.read()

    assert "RandomForest" not in ptext
    assert "Platt scaling" not in ptext
    assert "HistGradientBoostingClassifier" in ptext
    assert "Isotonic Regression" in ptext
    assert "## 11. Member C" in ptext
    assert "coverage across all 23 scenarios" not in ptext


def test_model_card_consistency():
    """Verify MODEL_CARD.md does not claim uncalibrated guarantees."""
    with open(MODEL_CARD_PATH, "r", encoding="utf-8") as f:
        mtext = f.read()

    assert "guaranteeing >= 90%" not in mtext
    assert "targeting nominal 90%" in mtext
    assert "HistGradientBoostingClassifier" in mtext
