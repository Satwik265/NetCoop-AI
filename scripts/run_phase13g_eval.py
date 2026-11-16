"""Phase 13G Frozen Benchmark Runner.
Executes seeds 601-615, 501-515, and in-distribution 301-325 strictly once after code freeze.
Computes before/after comparison metrics and conformal coverage breakdowns.
"""

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"
from netcoop.config import settings
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from eval.run_eval import (
    CLASSES,
    NpEncoder,
    compute_calibration_curve,
    compute_classification_metrics,
    compute_risk_coverage,
    determine_predicted_category,
    evaluate_single_heldout,
    evaluate_single_in_distribution,
    evaluate_single_organizer,
    load_organizer_label_map,
    run_ablations,
    run_stress_tests,
    measure_latency_profile,
    get_git_commit,
)
from netcoop.data.heldout_generator import HeldoutNetworkGenerator
from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.models.splits import DatasetSplitter
from orchestrator.graph import run_diagnosis

RESULTS_DIR = Path("eval/results")

def eval_heldout_seed_range(seeds_range: range, workers: int = 4) -> List[Dict[str, Any]]:
    scenarios = CLASSES + ["ambiguous_multi_fault", "insufficient_data"]
    tasks = [(sc, s) for sc in scenarios for s in seeds_range]
    results = Parallel(n_jobs=workers)(delayed(evaluate_single_heldout)(sc, s) for sc, s in tasks)
    return results

def compute_metrics_for_eval_set(results: List[Dict[str, Any]], dataset_name: str) -> Dict[str, Any]:
    total = len(results)
    diagnosed = [r for r in results if r.get("is_diagnosed") or (r.get("scenario") == "normal_operation" and r.get("status") == "benign")]
    coverage = len(diagnosed) / max(1, total)
    selective_acc = sum(1 for r in diagnosed if r["is_correct"]) / max(1, len(diagnosed)) if diagnosed else 0.0
    selective_error = 1.0 - selective_acc

    # Ambiguous / sparse evaluation
    ambig_cases = [r for r in results if r["scenario"] in ("ambiguous_multi_fault", "insufficient_data")]
    safe_abstentions = sum(1 for r in ambig_cases if r["is_correct"])
    false_diagnoses = len(ambig_cases) - safe_abstentions
    false_diagnosis_rate = false_diagnoses / max(1, len(ambig_cases)) if ambig_cases else 0.0

    # Multi-class metrics for the 8 canonical classes
    fault_results = [r for r in results if r["scenario"] in CLASSES]
    y_true = [r["scenario"] for r in fault_results]
    y_pred = [r["predicted_class"] for r in fault_results]
    per_class, cm, macro_f1, weighted_f1 = compute_classification_metrics(y_true, y_pred, CLASSES, include_abstentions_column=True)

    # Conformal empirical coverage
    conf_cov_count = 0
    class_conformal = defaultdict(lambda: {"total": 0, "covered": 0})
    for r in fault_results:
        sc = r["scenario"]
        c_set = set(r.get("conformal_prediction_set") or [])
        is_cov = (sc in c_set)
        class_conformal[sc]["total"] += 1
        if is_cov:
            class_conformal[sc]["covered"] += 1
            conf_cov_count += 1
    conf_cov = conf_cov_count / max(1, len(fault_results))

    # Faults called normal
    fault_samples = [r for r in fault_results if r["scenario"] != "normal_operation"]
    faults_called_normal = sum(1 for r in fault_samples if r["predicted_class"] == "normal_operation" or r["status"] == "benign")

    # Calibration View (a): All samples (abstentions confidence = 0.0)
    confs_zero = [
        0.0 if (r.get("status") in ("insufficient_evidence", "ambiguous") or (not r.get("is_diagnosed") and r.get("scenario") != "normal_operation"))
        else float(r["confidence"])
        for r in fault_results
    ]
    accs_zero = [r["is_correct"] for r in fault_results]
    ece_all, _, _ = compute_calibration_curve(confs_zero, accs_zero, n_bins=5)
    brier_all = float(np.mean([(c - (1.0 if a else 0.0)) ** 2 for c, a in zip(confs_zero, accs_zero)]))

    # Calibration View (b): Accepted samples only
    if diagnosed:
        diag_faults = [r for r in fault_results if r in diagnosed]
        confs_acc = [float(r["confidence"]) for r in diag_faults]
        accs_acc = [r["is_correct"] for r in diag_faults]
        ece_accepted, _, _ = compute_calibration_curve(confs_acc, accs_acc, n_bins=5)
        brier_accepted = float(np.mean([(c - (1.0 if a else 0.0)) ** 2 for c, a in zip(confs_acc, accs_acc)]))
    else:
        ece_accepted, brier_accepted = 0.0, 0.0

    return {
        "dataset_name": dataset_name,
        "total_samples": total,
        "coverage": round(coverage, 4),
        "selective_accuracy": round(selective_acc, 4),
        "selective_risk": round(selective_error, 4),
        "macro_f1": round(macro_f1, 4),
        "safe_abstention_rate_ambiguous": round(1.0 - false_diagnosis_rate, 4),
        "faults_called_normal": faults_called_normal,
        "conformal_coverage": round(conf_cov, 4),
        "ece_all": round(ece_all, 4),
        "ece_accepted": round(ece_accepted, 4),
        "brier_all": round(brier_all, 4),
        "brier_accepted": round(brier_accepted, 4),
        "per_class": per_class,
        "class_conformal": {c: round(d["covered"] / d["total"], 4) for c, d in class_conformal.items()},
        "confusion_matrix": cm,
    }

def main():
    print("================================================================================")
    print("PHASE 13G FROZEN BENCHMARK EVALUATION (STRICTLY ONCE)")
    print("================================================================================")
    start_time = datetime.now(timezone.utc)

    # 1. Evaluate historical held-out seeds 501-515
    print("\n--- Evaluating Historical Held-Out Split (Seeds 501-515, 150 samples) ---")
    heldout_hist_results = eval_heldout_seed_range(range(501, 516), workers=4)
    metrics_hist = compute_metrics_for_eval_set(heldout_hist_results, "heldout_historical_501_515")

    # 2. Evaluate blind held-out seeds 601-615
    print("\n--- Evaluating Blind Held-Out Split v2 (Seeds 601-615, 150 samples) ---")
    heldout_blind_results = eval_heldout_seed_range(range(601, 616), workers=4)
    metrics_blind = compute_metrics_for_eval_set(heldout_blind_results, "heldout_blind_601_615")

    # 3. Evaluate in-distribution test seeds 301-325
    print("\n--- Evaluating In-Distribution Test Split (Seeds 301-325, 250 samples) ---")
    in_dist_scenarios = CLASSES + ["ambiguous_multi_fault", "insufficient_data"]
    in_dist_tasks = [(sc, s) for sc in in_dist_scenarios for s in range(301, 326)]
    in_dist_results = Parallel(n_jobs=4)(delayed(evaluate_single_in_distribution)(sc, s) for sc, s in in_dist_tasks)
    metrics_indist = compute_metrics_for_eval_set(in_dist_results, "in_distribution_301_325")

    # 4. In-Distribution conformal breakdown by noise level
    in_dist_faults = [r for r in in_dist_results if r["scenario"] in CLASSES]
    noise_conformal_indist = defaultdict(lambda: {"total": 0, "covered": 0})
    for r in in_dist_faults:
        ns = r.get("noise_shape", "unknown")
        sc = r["scenario"]
        c_set = set(r.get("conformal_prediction_set") or [])
        is_cov = (sc in c_set)
        noise_conformal_indist[ns]["total"] += 1
        if is_cov:
            noise_conformal_indist[ns]["covered"] += 1

    noise_cov_breakdown = {
        ns: round(d["covered"] / d["total"], 4)
        for ns, d in noise_conformal_indist.items()
    }

    # 5. Combined Primary Benchmark (In-Dist 301-325 + Blind Heldout 601-615 = 400 samples)
    combined_primary = in_dist_results + heldout_blind_results
    metrics_combined = compute_metrics_for_eval_set(combined_primary, "combined_primary_400")

    # 6. Organizer Telemetry Evaluation (900 samples)
    print("\n--- Evaluating Organizer Colab Telemetry (900 samples) ---")
    org_label_map = load_organizer_label_map()
    org_tasks = []
    for ft in ["normal", "latency_spike", "hardware_failure"]:
        for is_win in [False, True]:
            for seed in range(6000 if is_win else 7000, (6000 if is_win else 7000) + 150):
                org_tasks.append((ft, seed, is_win))

    org_results = Parallel(n_jobs=4)(
        delayed(evaluate_single_organizer)(ft, s, is_win, org_label_map)
        for ft, s, is_win in org_tasks
    )

    org_set_matches = sum(1 for r in org_results if r["set_match"])
    org_exact_matches = sum(1 for r in org_results if r["exact_match"])
    org_set_acc = org_set_matches / len(org_results)
    org_exact_acc = org_exact_matches / len(org_results)

    # 7. Compile Final Comprehensive Phase 13G Benchmark Result
    benchmark_data = {
        "version": "2.0.0",
        "phase": "13G",
        "evaluation_timestamp": start_time.isoformat(),
        "git_commit": get_git_commit(),
        "splits": {
            "validation_conformal": json.load(open("eval/results/validation_conformal_breakdown.json")),
            "in_distribution": metrics_indist,
            "in_distribution_conformal_by_noise": noise_cov_breakdown,
            "heldout_historical_501_515": metrics_hist,
            "heldout_blind_601_615": metrics_blind,
            "combined_primary": metrics_combined,
            "organizer": {
                "total_samples": len(org_results),
                "set_match_accuracy": round(org_set_acc, 4),
                "exact_match_accuracy": round(org_exact_acc, 4),
            },
        },
    }

    out_path = RESULTS_DIR / "benchmark_phase13g_20261115.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, cls=NpEncoder)

    print(f"\nSaved Phase 13G benchmark results to {out_path}")
    print("\n=== SUMMARY COMPARISON METRICS ===")
    print(f"Historical Heldout (501-515) Normal Recall: {metrics_hist['per_class']['normal_operation']['recall']*100:.1f}%")
    print(f"Blind Heldout (601-615) Normal Recall:      {metrics_blind['per_class']['normal_operation']['recall']*100:.1f}%")
    print(f"In-Distribution (301-325) Normal Recall:    {metrics_indist['per_class']['normal_operation']['recall']*100:.1f}%")
    print(f"Combined Primary Normal Recall:             {metrics_combined['per_class']['normal_operation']['recall']*100:.1f}%")
    print(f"Faults Called Normal (Combined Primary):    {metrics_combined['faults_called_normal']}")
    print(f"Faults Called Normal (Historical Heldout):  {metrics_hist['faults_called_normal']}")
    print(f"Faults Called Normal (Blind Heldout):       {metrics_blind['faults_called_normal']}")
    print(f"Faults Called Normal (In-Distribution):     {metrics_indist['faults_called_normal']}")
    print(f"Conformal Coverage (In-Distribution):       {metrics_indist['conformal_coverage']*100:.2f}%")
    print(f"Conformal Coverage (Blind Heldout):         {metrics_blind['conformal_coverage']*100:.2f}%")
    print(f"Combined Selective Accuracy:                {metrics_combined['selective_accuracy']*100:.2f}%")
    print(f"Combined Selective Risk:                    {metrics_combined['selective_risk']*100:.2f}%")
    print(f"Combined ECE (All Samples View):            {metrics_combined['ece_all']:.4f}")
    print(f"Combined ECE (Accepted Only View):          {metrics_combined['ece_accepted']:.4f}")

if __name__ == "__main__":
    main()
