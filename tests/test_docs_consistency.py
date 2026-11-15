"""test_docs_consistency.py: Ensure documentation numbers, LaTeX, and contracts match benchmark artifacts."""

import json
import re
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
README_PATH = BASE_DIR / "README.md"
BENCHMARK_PATH = BASE_DIR / "eval" / "results" / "benchmark_phase11_20261115.json"
DERIVED_PATH = BASE_DIR / "eval" / "results" / "benchmark_phase11_derived.json"
FINAL_RC_PATH = BASE_DIR / "docs" / "final_release_candidate_report.md"
PROGRESS_PATH = BASE_DIR / "docs" / "progress.md"
MODEL_CARD_PATH = BASE_DIR / "netcoop" / "models" / "MODEL_CARD.md"


@pytest.fixture
def benchmark_data():
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def readme_text():
    with open(README_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_readme_numbers_match_benchmark_json(benchmark_data, readme_text):
    """Verify that headline benchmark numbers in README match the latest evaluation JSON."""
    summary = benchmark_data["summary"]
    splits = benchmark_data["dataset_splits"]

    # 1. Combined Primary Accuracy (56.8%)
    combined_acc_pct = f"{summary['combined_primary_accuracy'] * 100:.1f}%"
    assert combined_acc_pct in readme_text, f"Expected {combined_acc_pct} in README"

    # 2. In-Distribution Accuracy (71.6%)
    in_dist_pct = f"{splits['in_distribution_accuracy'] * 100:.1f}%"
    assert in_dist_pct in readme_text, f"Expected {in_dist_pct} in README"

    # 3. Held-Out Accuracy (32.0%)
    held_out_pct = f"{splits['held_out_accuracy'] * 100:.1f}%"
    assert held_out_pct in readme_text, f"Expected {held_out_pct} in README"

    # 4. Safe Abstention Rate (97.5%)
    safe_abs_pct = f"{summary['safe_abstention_rate'] * 100:.1f}%"
    assert safe_abs_pct in readme_text, f"Expected {safe_abs_pct} in README"

    # 5. Organizer Colab Set Match (66.7%) and Exact Match (33.3%)
    org_set_pct = f"{splits['organizer_accuracy'] * 100:.1f}%"
    org_exact_pct = f"{splits['organizer_exact_accuracy'] * 100:.1f}%"
    assert org_set_pct in readme_text, f"Expected {org_set_pct} in README"
    assert org_exact_pct in readme_text, f"Expected {org_exact_pct} in README"

    # 6. Macro F1 (0.620)
    macro_f1_str = f"{summary['macro_f1']:.3f}"
    assert macro_f1_str in readme_text, f"Expected {macro_f1_str} in README"

    # 7. Sample Counts: 400 primary, 900 organizer, 1,300 total
    assert "400" in readme_text
    assert "900" in readme_text
    assert ("1,300" in readme_text or "1300" in readme_text)


def test_selective_accuracy_definitions_consistency(benchmark_data, readme_text):
    """Verify selective accuracy and risk definitions are internally consistent."""
    summary = benchmark_data["summary"]

    # Fault-only selective accuracy (97.9%) and risk (2.1%)
    assert "97.9%" in readme_text
    assert "2.1%" in readme_text

    # Operating threshold >= 0.80 row in Section 3.4 must have consistent values (97.2% + 2.8% = 100%)
    pattern = re.compile(r"\|\s*\$\\ge 0\.80\$\s*\|\s*36\.0%\s*\|\s*2\.8%\s*\|\s*144\s*/\s*400\s*\|\s*.*97\.2%.*\|")
    assert pattern.search(readme_text), "README threshold table row for >= 0.80 must show consistent 97.2% accuracy and 2.8% risk"


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
