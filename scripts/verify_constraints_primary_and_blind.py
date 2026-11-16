"""Verification of hard constraints on Primary Benchmark (400 samples) and Blind Held-Out v3 (150 samples).
Checks:
- Selective risk does not increase vs Phase 13H
- Conformal coverage does not fall vs Phase 13H
- Faults called normal remains 0
"""

import os
import sys
import json
import time
from pathlib import Path
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
    evaluate_single_in_distribution,
    evaluate_single_heldout,
)
from scripts.run_phase13h_eval import eval_heldout_seed_range, compute_metrics_for_eval_set

def main():
    print("=" * 80)
    print("VERIFYING PHASE 13I HARD CONSTRAINTS")
    print("=" * 80)

    # 1. Evaluate In-Distribution Test Set (seeds 301-325, 250 samples)
    print("\n1. Evaluating In-Distribution Test Set (seeds 301-325, 250 samples)...")
    scenarios_indist = CLASSES + ["ambiguous_multi_fault", "insufficient_data"]
    indist_tasks = [(sc, s) for sc in scenarios_indist for s in range(301, 326)]
    indist_results = Parallel(n_jobs=4)(
        delayed(evaluate_single_in_distribution)(sc, s) for sc, s in indist_tasks
    )

    # 2. Evaluate Phase 13C Held-Out Split (seeds 601-615, 150 samples)
    print("2. Evaluating Phase 13C Held-Out Split (seeds 601-615, 150 samples)...")
    heldout_601_results = eval_heldout_seed_range(range(601, 616), workers=4)

    primary_results = indist_results + heldout_601_results
    primary_metrics = compute_metrics_for_eval_set(primary_results, "primary_benchmark_400")

    # 3. Evaluate Blind Split v3 (seeds 701-715, 150 samples)
    print("3. Evaluating Blind Split v3 (seeds 701-715, 150 samples)...")
    blind_701_results = eval_heldout_seed_range(range(701, 716), workers=4)
    blind_701_metrics = compute_metrics_for_eval_set(blind_701_results, "blind_heldout_701_715")

    # Load 13H baselines
    with open("eval/results/benchmark_phase13h_20261116.json") as f:
        baseline_data = json.load(f)
    p_base = baseline_data["primary_benchmark_400"]
    b_base = baseline_data["blind_heldout_701_715"]

    print("\n" + "=" * 80)
    print("CONSTRAINT VERIFICATION REPORT")
    print("=" * 80)

    print("\n--- Primary Benchmark (400 samples) ---")
    print(f"Coverage:           Baseline={p_base['coverage']:.4f}  | Current={primary_metrics['coverage']:.4f}")
    print(f"Selective Accuracy: Baseline={p_base['selective_accuracy']:.4f}  | Current={primary_metrics['selective_accuracy']:.4f}")
    print(f"Selective Risk:     Baseline={p_base['selective_risk']:.4f}  | Current={primary_metrics['selective_risk']:.4f}")
    print(f"Conformal Coverage: Baseline={p_base['conformal_empirical_coverage']:.4f}  | Current={primary_metrics['conformal_empirical_coverage']:.4f}")
    print(f"Faults Called Norm: Baseline={p_base['faults_called_normal']}       | Current={primary_metrics['faults_called_normal']}")

    p_risk_ok = primary_metrics['selective_risk'] <= p_base['selective_risk']
    p_conf_ok = primary_metrics['conformal_empirical_coverage'] >= p_base['conformal_empirical_coverage'] - 1e-4
    p_norm_ok = primary_metrics['faults_called_normal'] == 0
    print(f"Primary Constraints: Risk OK={p_risk_ok}, Conformal OK={p_conf_ok}, Norm OK={p_norm_ok}")

    print("\n--- Blind Held-Out v3 (seeds 701-715, 150 samples) ---")
    print(f"Coverage:           Baseline={b_base['coverage']:.4f}  | Current={blind_701_metrics['coverage']:.4f}")
    print(f"Selective Accuracy: Baseline={b_base['selective_accuracy']:.4f}  | Current={blind_701_metrics['selective_accuracy']:.4f}")
    print(f"Selective Risk:     Baseline={b_base['selective_risk']:.4f}  | Current={blind_701_metrics['selective_risk']:.4f}")
    print(f"Conformal Coverage: Baseline={b_base['conformal_empirical_coverage']:.4f}  | Current={blind_701_metrics['conformal_empirical_coverage']:.4f}")
    print(f"Faults Called Norm: Baseline={b_base['faults_called_normal']}       | Current={blind_701_metrics['faults_called_normal']}")

    b_risk_ok = blind_701_metrics['selective_risk'] <= b_base['selective_risk']
    b_conf_ok = blind_701_metrics['conformal_empirical_coverage'] >= b_base['conformal_empirical_coverage'] - 1e-4
    b_norm_ok = blind_701_metrics['faults_called_normal'] == 0
    print(f"Blind v3 Constraints: Risk OK={b_risk_ok}, Conformal OK={b_conf_ok}, Norm OK={b_norm_ok}")

    assert p_risk_ok, f"Primary selective risk increased: {primary_metrics['selective_risk']} > {p_base['selective_risk']}"
    assert p_conf_ok, f"Primary conformal coverage fell: {primary_metrics['conformal_empirical_coverage']} < {p_base['conformal_empirical_coverage']}"
    assert p_norm_ok, f"Primary faults called normal > 0: {primary_metrics['faults_called_normal']}"
    assert b_risk_ok, f"Blind v3 selective risk increased: {blind_701_metrics['selective_risk']} > {b_base['selective_risk']}"
    assert b_conf_ok, f"Blind v3 conformal coverage fell: {blind_701_metrics['conformal_empirical_coverage']} < {b_base['conformal_empirical_coverage']}"
    assert b_norm_ok, f"Blind v3 faults called normal > 0: {blind_701_metrics['faults_called_normal']}"

    print("\nALL HARD CONSTRAINTS VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
