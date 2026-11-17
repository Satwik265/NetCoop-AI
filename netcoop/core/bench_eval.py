"""Core evaluation functions and statistical metrics for NetCoop AI benchmarking."""

from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# In-process settings
os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"

from netcoop.config import settings
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from eval.run_eval import CLASSES
from gateway.adapters.organizer_adapter import OrganizerAdapter
from data.organizer.organizer_generator import OrganizerTelemetryGenerator
from netcoop.data.generator import SyntheticNetworkGenerator
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
    "MTU_MISMATCH_BLACKHOLE": "mtu_mismatch_blackhole",
}

ALL_SCENARIOS = [
    "normal_operation",
    "link_congestion",
    "weak_wifi_signal",
    "ethernet_interface_fault",
    "dns_failure",
    "dhcp_failure",
    "device_cpu_overload",
    "upstream_failure_cascade",
    "ambiguous_multi_fault",
    "insufficient_data",
]


def compute_wilson_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float, float]:
    """Wilson score confidence interval for a binomial proportion."""
    if n == 0:
        return 0.0, 0.0, 0.0
    z = 1.959963984540054  # 95% confidence standard normal quantile
    p_hat = k / n
    denom = 1.0 + (z ** 2) / n
    center = (p_hat + (z ** 2) / (2 * n)) / denom
    margin = (z / denom) * math.sqrt((p_hat * (1 - p_hat)) / n + (z ** 2) / (4 * (n ** 2)))
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return p_hat, low, high


def compute_rule_of_three(n: int) -> float:
    """Rule-of-three upper 95% confidence bound when zero events occur in n trials."""
    return 3.0 / n if n > 0 else 1.0


def compute_accepted_ece(results: List[Dict[str, Any]], n_bins: int = 10) -> float:
    """Expected Calibration Error (ECE) computed strictly on accepted predictions."""
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


def extract_predicted_class(rep: Any) -> Optional[str]:
    """Extract canonical predicted class from UnifiedDiagnosticReport."""
    if rep.status == "benign":
        return "normal_operation"
    if rep.status in ("insufficient_evidence", "inconclusive", "ambiguous", "invalid", "failed"):
        return None
    if getattr(rep, "hypothesis_key", None):
        return KEY_MAP.get(str(rep.hypothesis_key).upper())
    pc = str(rep.probable_cause or "").lower()
    for c in CLASSES:
        if c in pc:
            return c
    if "congestion" in pc:
        return "link_congestion"
    if "wifi" in pc or "rf attenuation" in pc:
        return "weak_wifi_signal"
    if "ethernet" in pc or "interface" in pc:
        return "ethernet_interface_fault"
    if "dns" in pc:
        return "dns_failure"
    if "dhcp" in pc:
        return "dhcp_failure"
    if "cpu" in pc:
        return "device_cpu_overload"
    if "upstream" in pc or "cascade" in pc:
        return "upstream_failure_cascade"
    if "hardware" in pc:
        return "device_hardware_failure"
    if "mtu" in pc:
        return "mtu_mismatch_blackhole"
    return None


def evaluate_sample(inc: Dict[str, Any], ground_truth: str) -> Dict[str, Any]:
    """Execute diagnosis on an incident dict and compute decision classification."""
    t0 = time.perf_counter()
    rep = run_diagnosis(inc)
    dur_ms = (time.perf_counter() - t0) * 1000.0

    is_diagnosed = (rep.status == "diagnosed")
    is_benign = (rep.status == "benign")
    is_abstained = (rep.status in ("insufficient_evidence", "inconclusive", "ambiguous", "invalid", "failed"))
    is_accepted = is_diagnosed or is_benign
    pred_cls = extract_predicted_class(rep)

    is_correct = False
    is_fault_called_normal = False

    if ground_truth == "normal_operation":
        is_correct = is_benign
    elif ground_truth in ("ambiguous_multi_fault", "insufficient_data", "insufficient_evidence", "05_insufficient_evidence_sparse"):
        is_correct = is_abstained
    else:
        # Fault scenario
        if is_benign or pred_cls == "normal_operation":
            is_fault_called_normal = True
            is_correct = False
        else:
            is_correct = (pred_cls == ground_truth)

    # Conformal coverage
    c_set = list(getattr(rep, "conformal_prediction_set", []) or [])
    if ground_truth == "normal_operation":
        conformal_covered = ("normal_operation" in c_set)
    elif ground_truth in ("ambiguous_multi_fault", "insufficient_data", "insufficient_evidence", "05_insufficient_evidence_sparse"):
        conformal_covered = (len(c_set) != 1) or ("insufficient_evidence" in c_set)
    else:
        conformal_covered = (ground_truth in c_set)

    # Decision category: diagnosed (correct/accepted), misdiagnosed (accepted wrong), or abstain
    if is_accepted:
        decision_category = "diagnosed" if is_correct else "misdiagnosed"
    else:
        decision_category = "abstain"

    return {
        "ground_truth": ground_truth,
        "status": rep.status,
        "probable_cause": rep.probable_cause,
        "confidence": float(rep.confidence),
        "predicted_class": pred_cls,
        "is_accepted": is_accepted,
        "is_diagnosed": is_diagnosed,
        "is_benign": is_benign,
        "is_abstained": is_abstained,
        "is_correct": is_correct,
        "is_fault_called_normal": is_fault_called_normal,
        "decision_category": decision_category,
        "conformal_prediction_set": c_set,
        "conformal_covered": conformal_covered,
        "duration_ms": dur_ms,
    }


def run_in_distribution_sample(sc: str, s: int) -> Dict[str, Any]:
    """Joblib worker for in-distribution primary sample."""
    inc = SyntheticNetworkGenerator.generate(
        scenario=sc,
        seed=s,
        noise_level=0.1,
    )
    return evaluate_sample(inc, sc)


def run_unseen_topology_sample(topo: str, sc: str, s: int) -> Dict[str, Any]:
    """Joblib worker for unseen topology sample."""
    inc = TopologyRandomizedGenerator.generate(
        scenario=sc,
        seed=s,
        topology_name=topo,
        noise_level=0.1,
    )
    res = evaluate_sample(inc, sc)
    res["topology"] = topo
    return res


def run_organizer_sample(cls_name: str, s: int, is_win: bool) -> Dict[str, Any]:
    """Joblib worker for organizer telemetry sample."""
    inc = OrganizerTelemetryGenerator.generate_incident(fault_type=cls_name, seed=6000 + s, is_window=is_win)
    adapted = OrganizerAdapter.adapt_dataset(inc["payload"])
    gt = "normal_operation" if cls_name == "normal" else ("link_congestion" if cls_name == "latency_spike" else "device_hardware_failure")
    res = evaluate_sample(adapted, gt)
    res["organizer_class"] = cls_name
    return res


def run_noise_sample(nl: float, sc: str, s: int) -> Dict[str, Any]:
    """Joblib worker for noise stress sample."""
    inc = SyntheticNetworkGenerator.generate(
        scenario=sc,
        seed=s,
        noise_level=nl,
    )
    res = evaluate_sample(inc, sc)
    res["noise_level"] = nl
    return res


def run_determinism_sample(s: int, sc: str) -> Tuple[int, Dict[str, Any]]:
    """Joblib worker for determinism diff check."""
    inc = SyntheticNetworkGenerator.generate(scenario=sc, seed=s, noise_level=0.1)
    rep = run_diagnosis(inc)
    return s, {
        "status": rep.status,
        "probable_cause": rep.probable_cause,
        "confidence": round(float(rep.confidence), 3),
    }


def summarize_results(name: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute complete statistical summary for an evaluated split."""
    total = len(results)
    if total == 0:
        return {"split_name": name, "total_samples": 0}

    diagnosed = sum(1 for r in results if r.get("is_diagnosed"))
    benign = sum(1 for r in results if r.get("is_benign"))
    abstained = sum(1 for r in results if r.get("is_abstained"))
    accepted = sum(1 for r in results if r.get("is_accepted"))
    coverage = accepted / total if total > 0 else 0.0

    accepted_results = [r for r in results if r.get("is_accepted")]
    correct_accepted = sum(1 for r in accepted_results if r.get("is_correct"))
    wrong_accepted = len(accepted_results) - correct_accepted

    sel_acc = correct_accepted / accepted if accepted > 0 else 0.0
    sel_risk_hat, sel_risk_low, sel_risk_high = compute_wilson_ci(wrong_accepted, accepted)

    # Faults called normal
    fault_samples = [r for r in results if r.get("ground_truth") not in ("normal_operation", "ambiguous_multi_fault", "insufficient_data")]
    n_faults = len(fault_samples)
    faults_called_normal = sum(1 for r in fault_samples if r.get("is_fault_called_normal"))
    rule_of_three_bound = compute_rule_of_three(n_faults) if n_faults > 0 else 0.0

    # Normal operation recall
    normal_samples = [r for r in results if r.get("ground_truth") == "normal_operation"]
    n_normal = len(normal_samples)
    normal_correct = sum(1 for r in normal_samples if r.get("is_correct"))
    normal_recall = normal_correct / n_normal if n_normal > 0 else 0.0

    # Conformal empirical coverage
    conformal_covered = sum(1 for r in results if r.get("conformal_covered"))
    conformal_coverage = conformal_covered / total if total > 0 else 0.0

    # Accepted confidence distribution (< 0.70 count)
    accepted_under_70 = sum(1 for r in accepted_results if float(r.get("confidence", 1.0)) < 0.70)

    # Accepted-only ECE
    accepted_ece = compute_accepted_ece(results)

    # Latencies
    lats = [r.get("duration_ms", 0.0) for r in results if "duration_ms" in r]
    p50_lat = float(np.percentile(lats, 50)) if lats else 0.0
    p95_lat = float(np.percentile(lats, 95)) if lats else 0.0

    # Per-class breakdown
    class_breakdown = {}
    classes_present = sorted(list({r.get("ground_truth") for r in results if r.get("ground_truth")}))
    for c in classes_present:
        c_res = [r for r in results if r.get("ground_truth") == c]
        c_tot = len(c_res)
        c_diag = sum(1 for r in c_res if r.get("is_diagnosed"))
        c_benign = sum(1 for r in c_res if r.get("is_benign"))
        c_abs = sum(1 for r in c_res if r.get("is_abstained"))
        c_corr = sum(1 for r in c_res if r.get("is_correct"))
        class_breakdown[c] = {
            "total": c_tot,
            "diagnosed": c_diag,
            "benign": c_benign,
            "abstained": c_abs,
            "correct": c_corr,
            "accuracy": round(c_corr / c_tot, 4) if c_tot > 0 else 0.0,
        }

    return {
        "split_name": name,
        "total_samples": total,
        "outcomes": {
            "diagnosed": diagnosed,
            "benign": benign,
            "abstained": abstained,  # distinct outcome
            "accepted": accepted,
            "coverage_pct": round(coverage * 100, 2),
        },
        "selective_metrics": {
            "accepted_count": accepted,
            "correct_count": correct_accepted,
            "wrong_count": wrong_accepted,
            "selective_accuracy": round(sel_acc, 4),
            "selective_risk": round(sel_risk_hat, 4),
            "selective_risk_wilson_95_ci": [round(sel_risk_low, 4), round(sel_risk_high, 4)],
        },
        "safety_metrics": {
            "fault_samples_evaluated": n_faults,
            "faults_called_normal": faults_called_normal,
            "rule_of_three_upper_bound_95": round(rule_of_three_bound, 4),
            "normal_operation_samples": n_normal,
            "normal_operation_recall": round(normal_recall, 4),
        },
        "calibration_metrics": {
            "conformal_empirical_coverage": round(conformal_coverage, 4),
            "accepted_only_ece": round(accepted_ece, 4),
        },
        "confidence_distribution": {
            "accepted_confidence_under_0_70": accepted_under_70,
            "acceptance_policy_note": "Acceptance status is determined at decision time before data quality penalty is deducted; degraded telemetry can lower displayed confidence below 0.70 while safely preserving diagnosis.",
        },
        "latency_ms": {
            "p50": round(p50_lat, 2),
            "p95": round(p95_lat, 2),
        },
        "per_class": class_breakdown,
    }
