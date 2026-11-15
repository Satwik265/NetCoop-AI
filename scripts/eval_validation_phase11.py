"""Evaluate complete validation split (seeds 251-300) across all classes.
Measures:
- Coverage
- Per-class precision, recall, F1, support
- Selective error (selective risk)
- False-diagnosis rate on ambiguous/sparse cases (safe abstention rate)
- Conformal empirical coverage
"""

import os
import sys
import json
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"

from netcoop.config import settings
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.models.splits import DatasetSplitter
from orchestrator.graph import run_diagnosis
from eval.run_eval import (
    CLASSES,
    compute_classification_metrics,
    compute_calibration_curve,
    compute_risk_coverage,
    determine_predicted_category,
)

from joblib import Parallel, delayed

def eval_single(sc, s, spec):
    rng = np.random.RandomState(s)
    sev = spec.severities[rng.randint(0, len(spec.severities))]
    n_shape = spec.noise_shapes[rng.randint(0, len(spec.noise_shapes))]
    miss_rate = round(float(rng.uniform(spec.missing_rate_range[0], spec.missing_rate_range[1])), 4)
    onset = round(float(rng.uniform(spec.onset_offset_range[0], spec.onset_offset_range[1])), 2)

    inc = SyntheticNetworkGenerator.generate(
        scenario=sc,
        seed=s,
        severity=sev,
        noise_level=0.1,
        noise_shape=n_shape,
        missing_sample_rate=miss_rate,
        onset_offset_seconds=onset,
    )
    rep = run_diagnosis(inc)
    pred_class = determine_predicted_category(rep.status, rep.probable_cause)

    if sc == "normal_operation":
        is_correct = (rep.status == "benign" or pred_class == "normal_operation")
    elif sc in ("ambiguous_multi_fault", "insufficient_data"):
        is_correct = (rep.status in ("insufficient_evidence", "ambiguous") or pred_class == "insufficient_evidence")
    else:
        is_correct = (rep.status == "diagnosed" and pred_class == sc)

    conf_set = rep.conformal_prediction_set or []
    conformal_contains_gt = (sc in conf_set) if sc in CLASSES else (len(conf_set) == 0 or "insufficient_evidence" in conf_set)

    return {
        "scenario": sc,
        "seed": s,
        "status": rep.status,
        "confidence": float(rep.confidence),
        "predicted_class": pred_class,
        "is_correct": is_correct,
        "is_diagnosed": (rep.status in ("diagnosed", "benign")),
        "conformal_contains_gt": conformal_contains_gt,
        "conformal_set": conf_set,
    }

def evaluate_validation_split(seeds_range=range(251, 301), workers=4):
    all_scenarios = CLASSES + ["ambiguous_multi_fault", "insufficient_data"]
    print(f"Running validation evaluation across {len(all_scenarios)} scenarios x {len(seeds_range)} seeds = {len(all_scenarios)*len(seeds_range)} runs (workers={workers})...")
    spec = DatasetSplitter.TEST_SPEC
    tasks = [(sc, s) for sc in all_scenarios for s in seeds_range]
    results = Parallel(n_jobs=workers)(delayed(eval_single)(sc, s, spec) for sc, s in tasks)

    # Metrics
    total = len(results)
    diagnosed = [r for r in results if r["is_diagnosed"]]
    coverage = len(diagnosed) / max(1, total)
    selective_acc = sum(1 for r in diagnosed if r["is_correct"]) / max(1, len(diagnosed)) if diagnosed else 0.0
    selective_error = 1.0 - selective_acc

    # Ambiguous / sparse evaluation
    ambig_cases = [r for r in results if r["scenario"] in ("ambiguous_multi_fault", "insufficient_data")]
    safe_abstentions = sum(1 for r in ambig_cases if r["is_correct"])
    false_diagnoses = len(ambig_cases) - safe_abstentions
    false_diagnosis_rate = false_diagnoses / max(1, len(ambig_cases))

    # Multi-class metrics for the 8 canonical classes
    fault_results = [r for r in results if r["scenario"] in CLASSES]
    y_true = [r["scenario"] for r in fault_results]
    y_pred = [r["predicted_class"] for r in fault_results]
    per_class, cm, macro_f1, weighted_f1 = compute_classification_metrics(y_true, y_pred, CLASSES, include_abstentions_column=True)

    # Conformal coverage
    conf_cov = sum(1 for r in fault_results if r["conformal_contains_gt"]) / max(1, len(fault_results))

    # ECE
    confs = [r["confidence"] for r in fault_results]
    accs = [r["is_correct"] for r in fault_results]
    ece, mce, rel_bins = compute_calibration_curve(confs, accs, n_bins=5)

    summary = {
        "total_samples": total,
        "coverage": round(coverage, 4),
        "selective_accuracy": round(selective_acc, 4),
        "selective_error": round(selective_error, 4),
        "macro_f1": round(macro_f1, 4),
        "false_diagnosis_rate_ambiguous": round(false_diagnosis_rate, 4),
        "safe_abstention_rate_ambiguous": round(1.0 - false_diagnosis_rate, 4),
        "conformal_empirical_coverage": round(conf_cov, 4),
        "expected_calibration_error": round(ece, 4),
        "per_class": {
            c: {
                "precision": round(per_class[c]["precision"], 4),
                "recall": round(per_class[c]["recall"], 4),
                "f1": round(per_class[c]["f1"], 4),
                "support": per_class[c]["support"],
                "abstentions": per_class[c].get("abstentions", 0),
            }
            for c in CLASSES
        },
        "confusion_matrix": cm,
    }
    return summary, results

if __name__ == "__main__":
    summary, results = evaluate_validation_split()
    print("\n=== VALIDATION SPLIT BASELINE (SEEDS 251-300) ===")
    print(json.dumps(summary, indent=2))
    with open("eval/results/validation_baseline_phase11.json", "w") as f:
        json.dump(summary, f, indent=2)
