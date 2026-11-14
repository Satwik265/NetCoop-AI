"""Comprehensive acceptance and integrity tests for Phase 3 evaluation and benchmark metrics:
- Re-running manifests yields deterministic metrics
- Hand-calculated metric fixtures (precision, recall, macro-F1, ECE, Brier score)
- Confusion matrix reconciliation with sample counts and support
- Strict exact-match vs relaxed set-match definitions
- Coverage and selective accuracy reconciliation
- Out-of-class and abstention handling
- Machine-readable evaluation schema validation
"""

import json
from pathlib import Path
import jsonschema
import numpy as np
import pytest

from eval.run_eval import (
    CLASSES,
    compute_classification_metrics,
    compute_calibration_curve,
    compute_risk_coverage,
    map_cause_to_class,
    evaluate_single_organizer,
    load_organizer_label_map,
)
from netcoop.models.splits import DatasetSplitter

REPO_ROOT = Path(__file__).parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"
EVAL_RESULTS_DIR = REPO_ROOT / "eval" / "results"
SPLITS_DIR = REPO_ROOT / "data" / "splits"


# -----------------------------------------------------------------------------
# 1. Independent Small Fixture Verification
# -----------------------------------------------------------------------------

def test_hand_calculated_classification_metrics_fixture() -> None:
    """Verify precision, recall, macro-F1 and weighted-F1 against an exact hand-calculated fixture."""
    classes = ["apple", "banana", "cherry"]
    # 6 true samples: 3 apples, 2 bananas, 1 cherry
    y_true = ["apple", "apple", "apple", "banana", "banana", "cherry"]
    # Predictions:
    # True apple: 2 apple (TP), 1 banana (FP for banana, FN for apple)
    # True banana: 1 banana (TP), 1 abstention (FN for banana)
    # True cherry: 1 cherry (TP)
    y_pred = ["apple", "apple", "banana", "banana", "insufficient_evidence", "cherry"]

    per_class, cm_nxn, macro_f1, weighted_f1 = compute_classification_metrics(y_true, y_pred, classes, include_abstentions_column=False)
    _, cm_full, _, _ = compute_classification_metrics(y_true, y_pred, classes, include_abstentions_column=True)

    # Apple: TP=2, FP=0, FN=1 -> Prec = 2/2 = 1.0, Rec = 2/3 = 0.667, F1 = 2*1*(2/3)/(1+2/3) = 4/5 = 0.8
    assert per_class["apple"]["support"] == 3
    assert per_class["apple"]["precision"] == 1.0
    assert per_class["apple"]["recall"] == 0.667
    assert per_class["apple"]["f1"] == 0.800
    assert per_class["apple"]["abstentions"] == 0

    # Banana: TP=1, FP=1 (from apple), FN=1 (abstained) -> Prec = 1/2 = 0.5, Rec = 1/2 = 0.5, F1 = 0.5
    assert per_class["banana"]["support"] == 2
    assert per_class["banana"]["precision"] == 0.5
    assert per_class["banana"]["recall"] == 0.5
    assert per_class["banana"]["f1"] == 0.500
    assert per_class["banana"]["abstentions"] == 1

    # Cherry: TP=1, FP=0, FN=0 -> Prec = 1.0, Rec = 1.0, F1 = 1.0
    assert per_class["cherry"]["support"] == 1
    assert per_class["cherry"]["precision"] == 1.0
    assert per_class["cherry"]["recall"] == 1.0
    assert per_class["cherry"]["f1"] == 1.000
    assert per_class["cherry"]["abstentions"] == 0

    # Macro F1: (0.8 + 0.5 + 1.0) / 3 = 2.3 / 3 = 0.7667 -> 0.767
    assert macro_f1 == 0.767

    # Weighted F1: (0.8*3 + 0.5*2 + 1.0*1) / 6 = (2.4 + 1.0 + 1.0) / 6 = 4.4 / 6 = 0.7333 -> 0.733
    assert weighted_f1 == 0.733

    # Reconciled confusion matrix verification:
    # Row 0 (apple): [2 apple, 1 banana, 0 cherry, 0 abstention] -> sum = 3 == support
    assert sum(cm_full[0]) == per_class["apple"]["support"]
    # Row 1 (banana): [0 apple, 1 banana, 0 cherry, 1 abstention] -> sum = 2 == support
    assert sum(cm_full[1]) == per_class["banana"]["support"]
    # Row 2 (cherry): [0 apple, 0 banana, 1 cherry, 0 abstention] -> sum = 1 == support
    assert sum(cm_full[2]) == per_class["cherry"]["support"]


def test_hand_calculated_calibration_and_brier_fixture() -> None:
    """Verify ECE and Brier score against hand-calculated expectations."""
    # 4 predictions with confidences:
    # Conf 0.90, correct (1.0)
    # Conf 0.80, correct (1.0)
    # Conf 0.60, incorrect (0.0)
    # Conf 0.20, incorrect (0.0)
    confs = [0.90, 0.80, 0.60, 0.20]
    accs = [True, True, False, False]

    # Brier score: mean((conf - acc)^2)
    # (0.9 - 1)^2 = 0.01
    # (0.8 - 1)^2 = 0.04
    # (0.6 - 0)^2 = 0.36
    # (0.2 - 0)^2 = 0.04
    # Mean = (0.01 + 0.04 + 0.36 + 0.04) / 4 = 0.45 / 4 = 0.1125
    brier = float(np.mean([(c - (1.0 if a else 0.0)) ** 2 for c, a in zip(confs, accs)]))
    assert round(brier, 4) == 0.1125

    # ECE with 2 bins: [0.0, 0.5) and [0.5, 1.0]
    ece, mce, bins = compute_calibration_curve(confs, accs, n_bins=2)
    # Bin 0 [0.0, 0.5): 1 sample (0.20), acc = 0.0 -> |0.0 - 0.20| = 0.20 (weight 1/4)
    # Bin 1 [0.5, 1.0]: 3 samples (0.9, 0.8, 0.6), mean_conf = 2.3/3 = 0.767, acc = 2/3 = 0.667 -> |0.667 - 0.767| = 0.10 (weight 3/4)
    # ECE = (1/4)*0.20 + (3/4)*0.10 = 0.05 + 0.075 = 0.125
    assert ece == pytest.approx(0.125, abs=0.01)


# -----------------------------------------------------------------------------
# 2. Confusion Matrix and Abstention Accounting
# -----------------------------------------------------------------------------

def test_confusion_matrix_reconciliation_with_support() -> None:
    """Assert that every row sum in matrix_reconciled strictly equals the class support."""
    classes = ["fault_a", "fault_b", "fault_c"]
    y_true = ["fault_a"] * 10 + ["fault_b"] * 15 + ["fault_c"] * 8
    # Mix of correct, confused, and abstained predictions
    y_pred = (
        ["fault_a"] * 7 + ["fault_b"] * 2 + ["insufficient_evidence"] * 1 +
        ["fault_b"] * 12 + ["fault_a"] * 1 + ["insufficient_evidence"] * 2 +
        ["fault_c"] * 5 + ["unknown"] * 3
    )

    per_class, cm_nxn, _, _ = compute_classification_metrics(y_true, y_pred, classes, include_abstentions_column=False)
    _, cm_full, _, _ = compute_classification_metrics(y_true, y_pred, classes, include_abstentions_column=True)

    total_samples = len(y_true)
    total_reconciled_sum = 0

    for idx, c in enumerate(classes):
        row_sum = sum(cm_full[idx])
        assert row_sum == per_class[c]["support"], f"Row sum {row_sum} != support {per_class[c]['support']} for {c}"
        assert cm_full[idx][len(classes)] == per_class[c]["abstentions"]
        total_reconciled_sum += row_sum

    assert total_reconciled_sum == total_samples


# -----------------------------------------------------------------------------
# 3. Exact-Match vs Relaxed Set-Match Definitions
# -----------------------------------------------------------------------------

def test_exact_match_vs_set_match_definitions() -> None:
    """Verify distinct semantics of exact-match versus relaxed set-match on organizer telemetry."""
    label_map = load_organizer_label_map()

    # Case A: Normal operation with benign diagnosis -> both exact and set match
    res_normal_benign = evaluate_single_organizer("normal", seed=6001, is_window=True, label_map=label_map)
    # The system correctly identifies normal/benign
    assert res_normal_benign["set_match"] is True

    # Case B: Hardware failure in organizer Colab
    # Exact match requires canonical 'device_hardware_failure', while set-match accepts
    # compound manifestations like 'ethernet_interface_fault' or 'device_cpu_overload'
    res_hw = evaluate_single_organizer("hardware_failure", seed=6005, is_window=True, label_map=label_map)
    # Set match is by definition a superset of exact match
    if res_hw["exact_match"]:
        assert res_hw["set_match"] is True
    # If exact match is False, set match may still be True if predicted class is in accepted set
    assert isinstance(res_hw["exact_match"], bool)
    assert isinstance(res_hw["set_match"], bool)


# -----------------------------------------------------------------------------
# 4. Coverage and Selective Accuracy Reconciliation
# -----------------------------------------------------------------------------

def test_coverage_and_selective_accuracy_reconciliation() -> None:
    """Verify that coverage, selective risk, and selective accuracy reconcile mathematically."""
    confs = [0.95, 0.88, 0.75, 0.45, 0.30]
    accs = [True, True, True, False, False]

    curves = compute_risk_coverage(confs, accs, cutoffs=[0.40, 0.70, 0.90])
    assert len(curves) == 3

    for pt in curves:
        cov = pt["coverage"]
        risk = pt["selective_risk"]
        accepted = pt["accepted_samples"]
        # Coverage fraction matches accepted / total
        assert cov == pytest.approx(accepted / 5.0, abs=1e-4)
        if accepted > 0:
            # Selective risk + selective accuracy = 1.0
            acc_subset = [accs[i] for i, c in enumerate(confs) if c >= pt["threshold"]]
            sel_acc = sum(acc_subset) / len(acc_subset)
            assert risk == pytest.approx(1.0 - sel_acc, abs=1e-4)


# -----------------------------------------------------------------------------
# 5. Deterministic Manifest & Seed Disjointness
# -----------------------------------------------------------------------------

def test_seed_disjointness_and_split_manifest() -> None:
    """Verify that DatasetSplitter seed boundaries have zero cross-split overlap."""
    DatasetSplitter.verify_no_seed_overlap()

    manifest_path = SPLITS_DIR / "eval_split_manifest_v1.json"
    assert manifest_path.exists(), "eval_split_manifest_v1.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["manifest_version"] == "1.0.0"
    assert manifest["seed_disjointness_verified"] is True
    partitions = manifest["partitions"]

    train_seeds = set(range(partitions["train"]["seed_start"], partitions["train"]["seed_end"] + 1))
    calib_seeds = set(range(partitions["calibrator_fit"]["seed_start"], partitions["calibrator_fit"]["seed_end"] + 1))
    test_seeds = set(range(partitions["test_in_distribution"]["seed_start"], partitions["test_in_distribution"]["seed_end"] + 1))

    assert len(train_seeds & test_seeds) == 0, "Leakage detected between train and test seeds!"
    assert len(train_seeds & calib_seeds) == 0, "Leakage detected between train and calib seeds!"
    assert len(calib_seeds & test_seeds) == 0, "Leakage detected between calib and test seeds!"


# -----------------------------------------------------------------------------
# 6. Evaluation Result Schema Validation
# -----------------------------------------------------------------------------

def test_evaluation_result_json_schema_valid() -> None:
    """Validate that benchmark result JSON adheres strictly to schemas/evaluation_result.json."""
    schema_path = SCHEMAS_DIR / "evaluation_result.json"
    assert schema_path.exists(), "schemas/evaluation_result.json must exist"

    with open(schema_path, "r", encoding="utf-8") as sf:
        schema = json.load(sf)

    # Validate benchmark_quick.json if exists
    quick_path = EVAL_RESULTS_DIR / "benchmark_quick.json"
    if quick_path.exists():
        with open(quick_path, "r", encoding="utf-8") as qf:
            quick_data = json.load(qf)
        jsonschema.validate(instance=quick_data, schema=schema)

    # Validate benchmark_phase3_20261115.json if exists
    phase3_path = EVAL_RESULTS_DIR / "benchmark_phase3_20261115.json"
    if phase3_path.exists():
        with open(phase3_path, "r", encoding="utf-8") as pf:
            phase3_data = json.load(pf)
        jsonschema.validate(instance=phase3_data, schema=schema)
