"""Phase 13J: Post-freeze single blind evaluation on unseen topologies.

Anti-leakage: Executed strictly ONCE after freeze on the two unseen topologies:
- test_blind_topology_1 (blind_edge_iot_6, seeds 801-815, 150 samples)
- test_blind_topology_2 (blind_spine_leaf_10, seeds 801-815, 150 samples)

Reports:
1. Coverage
2. Selective risk with Wilson 95% CI
3. Healthy recall
4. Faults-called-normal with rule-of-three upper bound
5. Per-class recall
6. Accepted-only ECE
7. Conformal empirical coverage by topology
"""

import math
import os
import sys
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from collections import defaultdict
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

from eval.run_eval import CLASSES
from netcoop.core.bench_eval import (
    KEY_MAP,
    compute_accepted_ece,
    compute_wilson_ci,
    run_unseen_topology_sample,
)
from netcoop.data.topology_generator import TopologyRandomizedGenerator
from netcoop.orchestrator.graph import run_diagnosis


def evaluate_sample(scen: str, seed: int, topology_name: str) -> Dict[str, Any]:
    """Delegate to canonical benchmark evaluation harness in netcoop.core.bench_eval."""
    res = run_unseen_topology_sample(topology_name, scen, seed)
    res["scenario"] = scen
    res["seed"] = seed
    res["is_ood"] = res.get("is_ood", False)
    return res


def analyze_topology_results(topo_name: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    n_total = len(results)
    accepted = [r for r in results if r["is_accepted"]]
    n_accepted = len(accepted)
    coverage = n_accepted / n_total if n_total > 0 else 0.0

    # Selective accuracy and risk
    n_correct_accepted = sum(1 for r in accepted if r["is_correct"])
    n_errors_accepted = n_accepted - n_correct_accepted
    sel_acc = n_correct_accepted / n_accepted if n_accepted > 0 else 0.0
    sel_risk_hat, sel_risk_low, sel_risk_high = compute_wilson_ci(n_errors_accepted, n_accepted)

    # Healthy recall
    normal_samples = [r for r in results if r["scenario"] == "normal_operation"]
    n_normal = len(normal_samples)
    n_healthy_correct = sum(1 for r in normal_samples if r["status"] == "benign")
    healthy_recall = n_healthy_correct / n_normal if n_normal > 0 else 0.0

    # Faults called normal
    fault_samples = [r for r in results if r["scenario"] not in ("normal_operation", "ambiguous_multi_fault", "insufficient_data")]
    n_faults = len(fault_samples)
    faults_called_normal = sum(
        1 for r in fault_samples
        if r["status"] == "benign" or r["predicted_class"] == "normal_operation"
    )
    if faults_called_normal == 0:
        rule_of_three_bound = 3.0 / n_faults if n_faults > 0 else 1.0
    else:
        _, _, rule_of_three_bound = compute_wilson_ci(faults_called_normal, n_faults)

    # Per-class recall
    all_scenarios = sorted(list(set(r["scenario"] for r in results)))
    per_class_recall: Dict[str, Dict[str, Any]] = {}
    for sc in all_scenarios:
        sc_samples = [r for r in results if r["scenario"] == sc]
        sc_correct = sum(1 for r in sc_samples if r["is_correct"])
        sc_acc = sum(1 for r in sc_samples if r["is_accepted"])
        per_class_recall[sc] = {
            "total": len(sc_samples),
            "correct": sc_correct,
            "accepted": sc_acc,
            "recall": sc_correct / len(sc_samples) if sc_samples else 0.0,
        }

    # Accepted-only ECE
    accepted_ece = compute_accepted_ece(results)

    # Conformal empirical coverage
    conformal_covered_count = sum(1 for r in results if r["conformal_covered"])
    conformal_coverage = conformal_covered_count / n_total if n_total > 0 else 0.0

    return {
        "topology": topo_name,
        "total_samples": n_total,
        "accepted_count": n_accepted,
        "coverage": coverage,
        "selective_accuracy": sel_acc,
        "selective_risk": sel_risk_hat,
        "selective_risk_ci_95": [sel_risk_low, sel_risk_high],
        "healthy_recall": healthy_recall,
        "faults_called_normal": faults_called_normal,
        "total_fault_samples": n_faults,
        "faults_called_normal_bound_95": rule_of_three_bound,
        "accepted_ece": accepted_ece,
        "conformal_coverage": conformal_coverage,
        "per_class_recall": per_class_recall,
    }


def main():
    print("=" * 80)
    print("PHASE 13J: UNSEEN BLIND TOPOLOGY EVALUATION (POST-FREEZE ONCE-ONLY)")
    print("=" * 80)

    blind_topos = ["blind_edge_iot_6", "blind_spine_leaf_10"]
    scenarios = CLASSES + ["ambiguous_multi_fault", "insufficient_data"]
    blind_seeds = list(range(801, 816))  # 15 seeds: 801-815

    all_tasks = []
    for topo in blind_topos:
        for sc in scenarios:
            for s in blind_seeds:
                all_tasks.append((sc, s, topo))

    print(f"Total blind runs: {len(all_tasks)} ({len(blind_topos)} topologies x {len(scenarios)} scenarios x {len(blind_seeds)} seeds)")
    print(f"Executing in parallel (4 jobs)...")

    results = Parallel(n_jobs=4)(
        delayed(evaluate_sample)(sc, s, topo) for sc, s, topo in all_tasks
    )

    # Save raw results
    out_dir = Path("demo_artifacts/phase13j")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "blind_topology_eval_raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Raw results saved to {raw_path}")

    # Aggregate by topology
    reports = {}
    for topo in blind_topos:
        topo_res = [r for r in results if r["topology"] == topo]
        rep = analyze_topology_results(topo, topo_res)
        reports[topo] = rep

    # Overall aggregate
    overall_rep = analyze_topology_results("combined_blind", results)
    reports["combined_blind"] = overall_rep

    summary_path = out_dir / "blind_topology_eval_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)
    print(f"Summary report saved to {summary_path}")

    # Print Report
    for topo in blind_topos + ["combined_blind"]:
        r = reports[topo]
        print(f"\n{'='*30} {topo.upper()} {'='*30}")
        print(f"Total Samples:             {r['total_samples']}")
        print(f"Accepted Predictions:      {r['accepted_count']} ({r['coverage']:.2%})")
        print(f"Selective Accuracy:        {r['selective_accuracy']:.4f} ({r['selective_accuracy']:.2%})")
        ci_str = f"[{r['selective_risk_ci_95'][0]:.4f}, {r['selective_risk_ci_95'][1]:.4f}]"
        print(f"Selective Risk:            {r['selective_risk']:.4f} ({r['selective_risk']:.2%}) 95% Wilson CI: {ci_str}")
        print(f"Healthy Recall:            {r['healthy_recall']:.4f} ({r['healthy_recall']:.2%})")
        print(f"Faults Called Normal:      {r['faults_called_normal']} / {r['total_fault_samples']} (95% Rule-of-3 bound: <= {r['faults_called_normal_bound_95']:.4f})")
        print(f"Accepted-Only ECE:         {r['accepted_ece']:.4f}")
        print(f"Conformal Empirical Cov:   {r['conformal_coverage']:.4f} ({r['conformal_coverage']:.2%})")
        print("\nPer-Class Breakdown:")
        print(f"  {'Class':30s} {'Total':6s} {'Accepted':9s} {'Correct':8s} {'Recall':8s}")
        print("  " + "-" * 65)
        for cname, pcr in r["per_class_recall"].items():
            print(f"  {cname:30s} {pcr['total']:<6d} {pcr['accepted']:<9d} {pcr['correct']:<8d} {pcr['recall']:.2%}")

    print("\n" + "=" * 80)
    print("PHASE 13J BLIND EVALUATION COMPLETE.")
    print("=" * 80)


if __name__ == "__main__":
    main()
