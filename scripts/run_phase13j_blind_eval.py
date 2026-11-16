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
from netcoop.data.topology_generator import TopologyRandomizedGenerator
from netcoop.orchestrator.graph import run_diagnosis


KEY_MAP = {
    "DEVICE_HARDWARE_FAILURE": "device_hardware_failure",
    "LINK_CONGESTION": "link_congestion",
    "UPSTREAM_CONGESTION": "upstream_failure_cascade",
    "UPSTREAM_FAILURE_CASCADE": "upstream_failure_cascade",
    "WEAK_WIFI_SIGNAL": "weak_wifi_signal",
    "ETHERNET_INTERFACE_FAULT": "ethernet_interface_fault",
    "DNS_FAILURE": "dns_failure",
    "DHCP_FAILURE": "dhcp_failure",
    "DEVICE_CPU_OVERLOAD": "device_cpu_overload",
    "NO_FAULT": "normal_operation",
}


def evaluate_sample(scen: str, seed: int, topology_name: str) -> Dict[str, Any]:
    inc = TopologyRandomizedGenerator.generate(
        scenario=scen,
        seed=seed,
        topology_name=topology_name,
        noise_level=0.1,
    )
    t0 = time.time()
    rep = run_diagnosis(inc)
    dur_ms = (time.time() - t0) * 1000.0

    is_diagnosed = (rep.status == "diagnosed")
    is_benign = (rep.status == "benign")
    is_abstain = (rep.status in ("insufficient_evidence", "ambiguous", "inconclusive"))

    # Map predicted cause
    pred_cls = None
    if getattr(rep, "hypothesis_key", None):
        pred_cls = KEY_MAP.get(str(rep.hypothesis_key).upper())

    if not pred_cls and is_diagnosed and rep.probable_cause:
        pc = str(rep.probable_cause).lower()
        for c in CLASSES:
            if c in pc:
                pred_cls = c
                break
        if not pred_cls:
            if "congestion" in pc:
                pred_cls = "link_congestion"
            elif "wifi" in pc or "rf attenuation" in pc:
                pred_cls = "weak_wifi_signal"
            elif "ethernet" in pc or "interface" in pc:
                pred_cls = "ethernet_interface_fault"
            elif "dns" in pc:
                pred_cls = "dns_failure"
            elif "dhcp" in pc:
                pred_cls = "dhcp_failure"
            elif "cpu" in pc:
                pred_cls = "device_cpu_overload"
            elif "upstream" in pc or "cascade" in pc:
                pred_cls = "upstream_failure_cascade"
    elif is_benign:
        pred_cls = "normal_operation"

    is_accepted = is_diagnosed or is_benign
    is_correct = False
    if scen == "normal_operation":
        is_correct = is_benign
    elif scen in ("ambiguous_multi_fault", "insufficient_data"):
        is_correct = is_abstain
    else:
        is_correct = (pred_cls == scen)

    c_set = list(getattr(rep, "conformal_prediction_set", []) or [])

    # Check conformal coverage
    # For a true label: is true label in conformal set?
    if scen == "normal_operation":
        conformal_covered = ("normal_operation" in c_set)
    elif scen in ("ambiguous_multi_fault", "insufficient_data"):
        # For ambiguous or insufficient, empty set or multiple competing causes
        conformal_covered = (len(c_set) != 1) or ("insufficient_evidence" in c_set)
    else:
        conformal_covered = (scen in c_set)

    return {
        "topology": topology_name,
        "scenario": scen,
        "seed": seed,
        "status": rep.status,
        "probable_cause": rep.probable_cause,
        "confidence": float(rep.confidence),
        "predicted_class": pred_cls,
        "is_accepted": is_accepted,
        "is_correct": is_correct,
        "conformal_prediction_set": c_set,
        "conformal_covered": conformal_covered,
        "is_ood": getattr(rep, "is_ood", False),
        "duration_ms": dur_ms,
    }


def compute_wilson_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float, float]:
    """Wilson score confidence interval for a proportion."""
    if n == 0:
        return 0.0, 0.0, 0.0
    z = 1.959963984540054  # 95%
    p_hat = k / n
    denom = 1.0 + (z ** 2) / n
    center = (p_hat + (z ** 2) / (2 * n)) / denom
    margin = (z / denom) * math.sqrt((p_hat * (1 - p_hat)) / n + (z ** 2) / (4 * (n ** 2)))
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return p_hat, low, high


def compute_accepted_ece(results: List[Dict[str, Any]], n_bins: int = 10) -> float:
    """Compute ECE on accepted predictions."""
    accepted = [r for r in results if r["is_accepted"]]
    if not accepted:
        return 0.0
    confs = np.array([r["confidence"] for r in accepted], dtype=np.float64)
    accs = np.array([1.0 if r["is_correct"] else 0.0 for r in accepted], dtype=np.float64)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(accepted)
    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        mask = (confs >= low) & (confs <= high if i == n_bins - 1 else confs < high)
        cnt = np.sum(mask)
        if cnt > 0:
            bin_acc = np.mean(accs[mask])
            bin_conf = np.mean(confs[mask])
            ece += (cnt / n) * abs(bin_acc - bin_conf)
    return float(ece)


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
