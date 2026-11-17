#!/usr/bin/env python3
"""Phase 13O: Final Evidence Freeze Evaluation Runner.

Evaluates fresh holdout splits (strictly run once, zero tuning):
1. Fresh unseen topologies (Seeds 1001-1015 on blind_edge_iot_6, blind_spine_leaf_10, blind_branch_9) [450 samples]
2. Fresh organizer seeds (Seeds 7000-7099 across windowed and snapshot, 50 per class) [300 samples]
3. Fresh HeldoutNetworkGenerator (Seeds 1101-1115 across 10 classes) [150 samples]
4. Fresh containerized network emulation (Seeds 20001-20050, 50 episodes) [50 episodes]
5. Borderline non-saturated suite (0.3-0.8x nominal severity, 0-40% missingness, seeds 1201-1240) [400 samples]

Computes:
- Coverage %
- Selective Risk with Wilson 95% CI
- Selective Accuracy
- Faults called normal with Rule-of-Three bound
- Healthy Recall
- Accepted-only ECE
- Conformal empirical coverage
- Confidence distribution (< 0.70 count and data quality penalty audit)
- Risk-Coverage curve on borderline suite
"""

import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Tuple

import numpy as np
from joblib import Parallel, delayed

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from gateway.adapters.organizer_adapter import OrganizerAdapter
from netcoop.core.bench_eval import (
    ALL_SCENARIOS,
    compute_accepted_ece,
    compute_rule_of_three,
    compute_wilson_ci,
    evaluate_sample,
    run_unseen_topology_sample,
    summarize_results,
)
from netcoop.data.generator import SeverityLevel, SyntheticNetworkGenerator
from netcoop.data.heldout_generator import HeldoutNetworkGenerator
from data.organizer.organizer_generator import OrganizerTelemetryGenerator
from netcoop.data.topology_generator import TopologyRandomizedGenerator
from netcoop.orchestrator.graph import run_diagnosis


# -----------------------------------------------------------------------------
# 1. Fresh Unseen Topologies Evaluation (450 Samples)
# -----------------------------------------------------------------------------

def eval_fresh_unseen_topologies() -> Dict[str, Any]:
    """Evaluate 450 fresh unseen topology samples across 3 blind topologies."""
    topologies = ["blind_edge_iot_6", "blind_spine_leaf_10", "blind_branch_9"]
    seeds = list(range(1001, 1016))  # 15 seeds per class
    tasks = []
    for topo in topologies:
        for sc in ALL_SCENARIOS:
            for s in seeds:
                tasks.append((topo, sc, s))

    print(f"[*] Running Fresh Unseen Topologies: {len(tasks)} samples across {len(topologies)} topologies...")
    raw_results = Parallel(n_jobs=8)(
        delayed(run_unseen_topology_sample)(topo, sc, s) for topo, sc, s in tasks
    )

    by_topo = {}
    for topo in topologies:
        t_res = [r for r in raw_results if r.get("topology") == topo]
        by_topo[topo] = summarize_results(f"fresh_unseen_{topo}", t_res)

    overall = summarize_results("fresh_unseen_topologies_450", raw_results)
    overall["by_topology"] = by_topo
    return overall


# -----------------------------------------------------------------------------
# 2. Fresh Organizer Telemetry Evaluation (300 Samples)
# -----------------------------------------------------------------------------

def run_organizer_fresh_worker(cls_name: str, seed: int, is_window: bool) -> Dict[str, Any]:
    inc = OrganizerTelemetryGenerator.generate_incident(fault_type=cls_name, seed=seed, is_window=is_window)
    adapted = OrganizerAdapter.adapt_dataset(inc["payload"])
    gt = "normal_operation" if cls_name == "normal" else ("link_congestion" if cls_name == "latency_spike" else "device_hardware_failure")
    res = evaluate_sample(adapted, gt)
    res["organizer_class"] = cls_name
    res["is_window"] = is_window
    return res


def eval_fresh_organizer() -> Dict[str, Any]:
    """Evaluate 300 fresh organizer telemetry samples (50 windowed + 50 snapshot per class)."""
    classes = ["normal", "latency_spike", "hardware_failure"]
    tasks = []
    # Windowed: seeds 7000-7049
    for c in classes:
        for s in range(7000, 7050):
            tasks.append((c, s, True))
    # Snapshot: seeds 7050-7099
    for c in classes:
        for s in range(7050, 7100):
            tasks.append((c, s, False))

    print(f"[*] Running Fresh Organizer Suite: {len(tasks)} samples...")
    raw_results = Parallel(n_jobs=8)(
        delayed(run_organizer_fresh_worker)(c, s, w) for c, s, w in tasks
    )

    by_class = {}
    for c in classes:
        c_res = [r for r in raw_results if r.get("organizer_class") == c]
        by_class[c] = summarize_results(f"fresh_organizer_{c}", c_res)

    overall = summarize_results("fresh_organizer_suite_300", raw_results)
    overall["by_organizer_class"] = by_class
    return overall


# -----------------------------------------------------------------------------
# 3. Fresh HeldoutNetworkGenerator (150 Samples)
# -----------------------------------------------------------------------------

def run_heldout_worker(sc: str, seed: int) -> Dict[str, Any]:
    inc = HeldoutNetworkGenerator.generate(
        scenario=sc,
        seed=seed,
        noise_level=0.15,
    )
    return evaluate_sample(inc, sc)


def eval_fresh_heldout() -> Dict[str, Any]:
    """Evaluate 150 fresh HeldoutNetworkGenerator samples (seeds 1101-1115)."""
    seeds = list(range(1101, 1116))
    tasks = [(sc, s) for sc in ALL_SCENARIOS for s in seeds]

    print(f"[*] Running Fresh Heldout Suite: {len(tasks)} samples...")
    raw_results = Parallel(n_jobs=8)(
        delayed(run_heldout_worker)(sc, s) for sc, s in tasks
    )
    return summarize_results("fresh_heldout_1101_1115", raw_results)


# -----------------------------------------------------------------------------
# 4. Borderline Non-Saturated Suite (400 Samples)
# -----------------------------------------------------------------------------

def run_borderline_worker(sc: str, seed: int) -> Dict[str, Any]:
    rng = random.Random(seed * 31 + 17)
    # 0.3x to 0.8x nominal severity
    sev_mult = rng.uniform(0.3, 0.8)
    # 0% to 40% missingness
    missing_rate = rng.uniform(0.0, 0.40)

    # Generate baseline incident with missingness
    inc = SyntheticNetworkGenerator.generate(
        scenario=sc,
        seed=seed,
        severity=SeverityLevel.HIGH,
        noise_level=0.1,
        missing_sample_rate=missing_rate,
    )

    # Scale metric anomalies in telemetry to borderline severity (0.3 - 0.8x)
    if sc != "normal_operation":
        for rec in inc.get("telemetry", []):
            if rec.get("link_utilization_pct") is not None and rec["link_utilization_pct"] > 40.0:
                rec["link_utilization_pct"] = round(35.0 + (rec["link_utilization_pct"] - 35.0) * sev_mult, 1)
            if rec.get("cpu_pct") is not None and rec["cpu_pct"] > 40.0:
                rec["cpu_pct"] = round(30.0 + (rec["cpu_pct"] - 30.0) * sev_mult, 1)
            if rec.get("queue_drops") is not None and rec["queue_drops"] > 10:
                rec["queue_drops"] = int(rec["queue_drops"] * sev_mult)
            if rec.get("packet_loss_pct") is not None and rec["packet_loss_pct"] > 0.5:
                rec["packet_loss_pct"] = round(rec["packet_loss_pct"] * sev_mult, 2)
            if rec.get("wifi_rssi_dbm") is not None and rec["wifi_rssi_dbm"] < -65.0:
                rec["wifi_rssi_dbm"] = round(-60.0 + (rec["wifi_rssi_dbm"] - (-60.0)) * sev_mult, 1)
            if rec.get("wifi_retransmission_pct") is not None and rec["wifi_retransmission_pct"] > 8.0:
                rec["wifi_retransmission_pct"] = round(5.0 + (rec["wifi_retransmission_pct"] - 5.0) * sev_mult, 1)

    res = evaluate_sample(inc, sc)
    res["severity_multiplier"] = round(sev_mult, 3)
    res["missing_sample_rate"] = round(missing_rate, 3)
    return res


def eval_borderline_suite() -> Dict[str, Any]:
    """Evaluate 400 borderline non-saturated samples (seeds 1201-1240)."""
    seeds = list(range(1201, 1241))  # 40 per class * 10 classes = 400
    tasks = [(sc, s) for sc in ALL_SCENARIOS for s in seeds]

    print(f"[*] Running Borderline Suite: {len(tasks)} samples...")
    raw_results = Parallel(n_jobs=8)(
        delayed(run_borderline_worker)(sc, s) for sc, s in tasks
    )

    summary = summarize_results("borderline_suite_400", raw_results)

    # Compute Risk-Coverage Curve across varying confidence thresholds
    thresholds = [0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90]
    rc_curve = []
    total = len(raw_results)

    for th in thresholds:
        accepted_at_th = [r for r in raw_results if (r.get("is_accepted") and r.get("confidence", 0.0) >= th)]
        n_acc = len(accepted_at_th)
        cov = n_acc / total if total > 0 else 0.0
        n_correct = sum(1 for r in accepted_at_th if r.get("is_correct"))
        n_wrong = n_acc - n_correct
        sel_acc = n_correct / n_acc if n_acc > 0 else 1.0
        sel_risk = n_wrong / n_acc if n_acc > 0 else 0.0
        r_hat, r_low, r_high = compute_wilson_ci(n_wrong, n_acc)
        rc_curve.append({
            "threshold": th,
            "accepted": n_acc,
            "coverage_pct": round(cov * 100.0, 2),
            "selective_accuracy": round(sel_acc, 4),
            "selective_risk": round(sel_risk, 4),
            "selective_risk_wilson_ci": [round(r_low, 4), round(r_high, 4)],
        })

    # Abstention reasons breakdown
    abstentions = [r for r in raw_results if r.get("is_abstained")]
    reasons_counts: Dict[str, int] = {}
    for r in abstentions:
        reas = r.get("probable_cause") or "insufficient_evidence"
        c_set = r.get("conformal_prediction_set", [])
        if "ambiguous" in c_set or len(c_set) > 1:
            key = "conformal_prediction_set_ambiguity"
        elif r.get("status") == "insufficient_evidence":
            key = "insufficient_evidence_gating"
        else:
            key = "low_calibrated_confidence"
        reasons_counts[key] = reasons_counts.get(key, 0) + 1

    summary["risk_coverage_curve"] = rc_curve
    summary["abstention_reasons"] = reasons_counts
    return summary


# -----------------------------------------------------------------------------
# 5. Fresh Containerized Emulation Episodes (Seeds 20001-20050)
# -----------------------------------------------------------------------------

def eval_fresh_emulation(raw_captures_dir: Path) -> Dict[str, Any]:
    """Evaluate 50 fresh containerized physical emulation episodes."""
    files = sorted(list(raw_captures_dir.glob("*.json")))
    if not files:
        return {"error": f"No emulation capture files found in {raw_captures_dir}"}

    print(f"[*] Evaluating Fresh Emulation Episodes: {len(files)} captures...")
    results = []

    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        cond = data.get("scenario_type") or data.get("condition", "healthy_run")

        # Normalize via Gateway adapter
        adapted = OrganizerAdapter.adapt_dataset(data)

        # Expected ground truth
        if cond == "healthy_run":
            gt = "normal_operation"
        elif cond == "congestion":
            gt = "link_congestion"
        elif cond == "link_flap":
            gt = "ethernet_interface_fault"
        elif cond == "mtu_mismatch":
            gt = "mtu_mismatch_blackhole"
        elif cond == "cpu_stress":
            gt = "device_cpu_overload"
        else:
            gt = cond

        res = evaluate_sample(adapted, gt)
        res["episode_id"] = data.get("episode_id", f.name)
        res["condition"] = cond
        results.append(res)

    summary = summarize_results("fresh_emulation_20001_20050", results)
    by_cond = {}
    for cond in ["congestion", "link_flap", "mtu_mismatch", "cpu_stress", "healthy_run"]:
        c_res = [r for r in results if r.get("condition") == cond]
        by_cond[cond] = summarize_results(f"emulation_{cond}", c_res)
    summary["by_condition"] = by_cond
    return summary


# -----------------------------------------------------------------------------
# Main Evaluation Orchestration
# -----------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("=== NetCoop AI Phase 13O Final Evidence Freeze Evaluation ===")
    print("=" * 70)

    t0 = time.time()
    out_dir = PROJECT_ROOT / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fresh Unseen Topologies
    unseen_res = eval_fresh_unseen_topologies()

    # 2. Fresh Organizer Telemetry
    org_res = eval_fresh_organizer()

    # 3. Fresh Heldout Suite
    heldout_res = eval_fresh_heldout()

    # 4. Borderline Non-Saturated Suite
    borderline_res = eval_borderline_suite()

    # 5. Fresh Emulation Episodes
    raw_captures_dir = Path("C:/Users/agraw/.gemini/antigravity/brain/a5970755-df51-4b7a-a6cd-5a44f5fb5355/scratch/phase13o_raw_captures")
    emul_res = eval_fresh_emulation(raw_captures_dir)

    all_data = {
        "metadata": {
            "version": "phase13o_freeze_v1",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_execution_seconds": round(time.time() - t0, 2),
        },
        "fresh_holdouts": {
            "unseen_topologies_450": unseen_res,
            "organizer_suite_300": org_res,
            "heldout_suite_150": heldout_res,
            "borderline_suite_400": borderline_res,
            "emulation_episodes_50": emul_res,
        },
    }

    out_file = PROJECT_ROOT / "eval" / "results" / "phase13o_fresh_holdouts_evaluation.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2)

    print(f"\n[+] Wrote complete Phase 13O Fresh Holdouts evaluation to {out_file}")
    print(f"Total time: {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
