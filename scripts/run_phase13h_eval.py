"""Phase 13H Frozen Benchmark Runner.
Executes:
1. Primary 400-sample benchmark (in-dist seeds 301-325 + held-out seeds 601-615).
2. NEW Blind split v3 (seeds 701-715, 15 per class = 150 samples) strictly ONCE after freeze.
3. Hackathon organizer Colab multi-mode suite (900 samples: 450 windowed, 450 snapshot).
Outputs:
- Full evaluation artifact: eval/results/benchmark_phase13h_20261116.json (and benchmark_current.json)
- Per-class before/after table for 400 primary and 150 new blind (701-715)
- Organizer exact-match and predicted status/cause table
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
    ece_zero, mce_zero, _ = compute_calibration_curve(confs_zero, accs_zero, n_bins=10)
    brier_zero = float(np.mean([(c - (1.0 if a else 0.0)) ** 2 for c, a in zip(confs_zero, accs_zero)])) if fault_results else 0.0

    # Calibration View (b): Diagnosed subset only
    diag_results = [r for r in fault_results if r.get("is_diagnosed") or (r.get("scenario") == "normal_operation" and r.get("status") == "benign")]
    if diag_results:
        confs_diag = [float(r["confidence"]) for r in diag_results]
        accs_diag = [r["is_correct"] for r in diag_results]
        ece_diag, mce_diag, _ = compute_calibration_curve(confs_diag, accs_diag, n_bins=10)
        brier_diag = float(np.mean([(c - (1.0 if a else 0.0)) ** 2 for c, a in zip(confs_diag, accs_diag)]))
    else:
        ece_diag, brier_diag = 0.0, 0.0

    # Per-class summary counts (correct, wrong, abstained)
    class_table = {}
    for sc in CLASSES + ["ambiguous_multi_fault", "insufficient_data"]:
        sc_res = [r for r in results if r["scenario"] == sc]
        n_tot = len(sc_res)
        n_corr = sum(1 for r in sc_res if r["is_correct"])
        n_abstained = sum(1 for r in sc_res if r["status"] in ("insufficient_evidence", "ambiguous", "inconclusive"))
        n_wrong = n_tot - n_corr - (n_abstained if sc not in ("ambiguous_multi_fault", "insufficient_data") else 0)
        if sc in ("ambiguous_multi_fault", "insufficient_data"):
            # For ambiguous/sparse, correct is abstention
            n_wrong = n_tot - n_corr
            n_abstained = n_corr
        class_table[sc] = {
            "total": n_tot,
            "correct": n_corr,
            "wrong": max(0, n_wrong),
            "abstained": n_abstained,
            "accuracy": round(n_corr / max(1, n_tot), 4),
        }

    return {
        "dataset_name": dataset_name,
        "sample_count": total,
        "coverage": round(coverage, 4),
        "selective_accuracy": round(selective_acc, 4),
        "selective_risk": round(selective_error, 4),
        "conformal_empirical_coverage": round(conf_cov, 4),
        "faults_called_normal": faults_called_normal,
        "ece_all": round(ece_zero, 4),
        "brier_all": round(brier_zero, 4),
        "ece_diagnosed": round(ece_diag, 4),
        "brier_diagnosed": round(brier_diag, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "class_table": class_table,
        "confusion_matrix": cm,
        "raw_results": results,
    }


def eval_organizer_traces(workers: int = 4) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    label_map = load_organizer_label_map()
    faults = ["normal", "latency_spike", "hardware_failure"]
    samples_per_mode = 150

    tasks = []
    # Windowed mode: seeds 6000-6149
    for f in faults:
        for s in range(samples_per_mode):
            tasks.append((f, 6000 + s, True))
    # Snapshot mode: seeds 7000-7149
    for f in faults:
        for s in range(samples_per_mode):
            tasks.append((f, 7000 + s, False))

    raw_org = Parallel(n_jobs=workers)(
        delayed(evaluate_single_organizer)(f, s, is_win, label_map)
        for f, s, is_win in tasks
    )

    table_data = defaultdict(lambda: {"total": 0, "correct": 0, "statuses": defaultdict(int), "causes": defaultdict(int)})
    for r in raw_org:
        mode = "windowed" if r["is_window"] else "snapshot"
        key = (mode, r["fault_type"])
        table_data[key]["total"] += 1
        if r.get("exact_match"):
            table_data[key]["correct"] += 1
        st = r.get("status", "unknown")
        table_data[key]["statuses"][st] += 1
        cause = r.get("probable_cause") or r.get("predicted_class") or "none"
        table_data[key]["causes"][cause] += 1

    summary = {
        "total_samples": len(raw_org),
        "exact_matches": sum(1 for r in raw_org if r.get("exact_match")),
        "accuracy": round(sum(1 for r in raw_org if r.get("exact_match")) / len(raw_org), 4),
        "breakdown": {
            f"{k[0]}_{k[1]}": {
                "mode": k[0],
                "fault_type": k[1],
                "total": v["total"],
                "correct": v["correct"],
                "accuracy": round(v["correct"] / max(1, v["total"]), 4),
                "statuses": dict(v["statuses"]),
                "causes": dict(v["causes"]),
            }
            for k, v in table_data.items()
        }
    }
    return summary, raw_org


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 13H Frozen Benchmark Runner")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker threads")
    args = parser.parse_args()

    t_start = time.time()
    print("=" * 80)
    print("STARTING PHASE 13H FROZEN POST-CODE-FREEZE EVALUATION")
    print("=" * 80)

    # 1. In-Distribution Evaluation (seeds 301-325, 250 samples)
    print("\n1. Evaluating In-Distribution Test Set (seeds 301-325, 25 per scenario = 250 samples)...")
    scenarios_indist = CLASSES + ["ambiguous_multi_fault", "insufficient_data"]
    indist_tasks = [(sc, s) for sc in scenarios_indist for s in range(301, 326)]
    indist_results = Parallel(n_jobs=args.workers)(
        delayed(evaluate_single_in_distribution)(sc, s) for sc, s in indist_tasks
    )

    # 2. Held-Out Evaluation (seeds 601-615, 150 samples)
    print("2. Evaluating Phase 13C Held-Out Split (seeds 601-615, 15 per scenario = 150 samples)...")
    heldout_601_results = eval_heldout_seed_range(range(601, 616), workers=args.workers)

    # 3. Combine into Primary Benchmark (400 samples)
    primary_results = indist_results + heldout_601_results
    primary_metrics = compute_metrics_for_eval_set(primary_results, "primary_benchmark_400")

    # 4. NEW Blind Split v3 Evaluation (seeds 701-715, 150 samples) STRICTLY ONCE
    print("3. Evaluating NEW Blind Split v3 (seeds 701-715, 15 per scenario = 150 samples)...")
    blind_701_results = eval_heldout_seed_range(range(701, 716), workers=args.workers)
    blind_701_metrics = compute_metrics_for_eval_set(blind_701_results, "blind_heldout_701_715")

    # 5. Organizer Evaluation (900 samples)
    print("4. Evaluating Hackathon Organizer Colab Traces (900 samples: 450 win, 450 snap)...")
    org_summary, org_raw = eval_organizer_traces(workers=args.workers)

    # 6. Assemble Full Benchmark JSON Artifact
    total_time = round(time.time() - t_start, 2)
    benchmark_data = {
        "benchmark_metadata": {
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": get_git_commit(),
            "split_manifest": "data/splits/eval_split_manifest_v3.json",
            "eval_version": "phase13h_frozen_v3",
            "evaluation_duration_seconds": total_time,
            "total_samples_evaluated": len(primary_results) + len(blind_701_results) + len(org_raw),
        },
        "primary_benchmark_400": primary_metrics,
        "blind_heldout_701_715": blind_701_metrics,
        "organizer_benchmark_900": org_summary,
        "in_distribution_250": compute_metrics_for_eval_set(indist_results, "in_distribution_301_325"),
        "heldout_601_615": compute_metrics_for_eval_set(heldout_601_results, "heldout_601_615"),
    }

    # Save to disk
    out_13h = RESULTS_DIR / "benchmark_phase13h_20261116.json"
    with open(out_13h, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, cls=NpEncoder)
    print(f"\n[SAVED] Phase 13H benchmark artifact saved to: {out_13h}")

    # Also update benchmark_current.json
    out_cur = RESULTS_DIR / "benchmark_current.json"
    with open(out_cur, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, cls=NpEncoder)
    print(f"[SAVED] Updated {out_cur}")

    # 7. Print Required Tables
    print("\n" + "=" * 80)
    print("PHASE 13H VERIFIED BENCHMARK RESULTS")
    print("=" * 80)

    print("\n### 1. Primary Benchmark (400 Samples: In-Dist 301-325 + Held-Out 601-615)")
    print(f"- Coverage: {primary_metrics['coverage']*100:.2f}%")
    print(f"- Selective Accuracy: {primary_metrics['selective_accuracy']*100:.2f}%")
    print(f"- Selective Risk: {primary_metrics['selective_risk']*100:.2f}%")
    print(f"- Conformal Empirical Coverage: {primary_metrics['conformal_empirical_coverage']*100:.2f}%")
    print(f"- Faults Called Normal: {primary_metrics['faults_called_normal']} (HARD CONSTRAINT: 0)")
    print(f"- Expected Calibration Error (All): {primary_metrics['ece_all']:.4f}")
    print(f"- Brier Score (All): {primary_metrics['brier_all']:.4f}")

    print("\n| Scenario | Total | Correct | Wrong | Abstained | Accuracy |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: |")
    for sc, row in primary_metrics["class_table"].items():
        print(f"| `{sc}` | {row['total']} | {row['correct']} | {row['wrong']} | {row['abstained']} | {row['accuracy']*100:.1f}% |")

    print("\n### 2. NEW Blind Split v3 (150 Samples: Seeds 701-715)")
    print(f"- Coverage: {blind_701_metrics['coverage']*100:.2f}%")
    print(f"- Selective Accuracy: {blind_701_metrics['selective_accuracy']*100:.2f}%")
    print(f"- Selective Risk: {blind_701_metrics['selective_risk']*100:.2f}%")
    print(f"- Conformal Empirical Coverage: {blind_701_metrics['conformal_empirical_coverage']*100:.2f}%")
    print(f"- Faults Called Normal: {blind_701_metrics['faults_called_normal']} (HARD CONSTRAINT: 0)")

    print("\n| Scenario | Total | Correct | Wrong | Abstained | Accuracy |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: |")
    for sc, row in blind_701_metrics["class_table"].items():
        print(f"| `{sc}` | {row['total']} | {row['correct']} | {row['wrong']} | {row['abstained']} | {row['accuracy']*100:.1f}% |")

    print("\n### 3. Organizer Colab Telemetry Evaluation (900 Samples)")
    print(f"- Overall Exact-Match Accuracy: {org_summary['accuracy']*100:.2f}% ({org_summary['exact_matches']}/{org_summary['total_samples']})")
    print("\n| Mode | Fault Type | Total | Exact Match | Accuracy | Top Statuses | Top Causes |")
    print("| :--- | :--- | :---: | :---: | :---: | :--- | :--- |")
    for k, v in org_summary["breakdown"].items():
        st_str = ", ".join(f"{st}: {c}" for st, c in v["statuses"].items())
        cause_str = ", ".join(f"{cs}: {c}" for cs, c in list(v["causes"].items())[:3])
        print(f"| {v['mode']} | `{v['fault_type']}` | {v['total']} | {v['correct']} | {v['accuracy']*100:.1f}% | {st_str} | {cause_str} |")


if __name__ == "__main__":
    main()
