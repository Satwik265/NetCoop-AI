"""audit_organizer_guards.py: Test per-guard toggles on organizer tuning seeds 6000-6049."""

import copy
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"

from netcoop.config import settings
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from data.organizer.organizer_generator import OrganizerTelemetryGenerator
from gateway.adapters.organizer_adapter import OrganizerAdapter
from orchestrator.graph import run_diagnosis
from eval.run_eval import load_organizer_label_map, determine_predicted_category

def evaluate_sample(fault_type: str, seed: int, is_window: bool, label_map: dict):
    inc = OrganizerTelemetryGenerator.generate_incident(fault_type=fault_type, seed=seed, is_window=is_window)
    adapted = OrganizerAdapter.adapt_dataset(inc["payload"])
    rep = run_diagnosis(adapted)

    cfg = label_map.get(fault_type, {})
    canonical_target = cfg.get("canonical", fault_type)
    
    if getattr(rep, "hypothesis_key", None):
        key_upper = str(rep.hypothesis_key).upper()
        key_map = {
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
        pred_class = key_map.get(key_upper, determine_predicted_category(rep.status, rep.probable_cause))
    else:
        pred_class = determine_predicted_category(rep.status, rep.probable_cause)

    if fault_type == "normal":
        exact_match = (rep.status == "benign" or pred_class == "normal_operation")
    else:
        exact_match = (rep.status == "diagnosed" and pred_class == canonical_target)

    # Inspect reasons / guards
    reasons = rep.uncertainty.reasons if hasattr(rep, "uncertainty") and hasattr(rep.uncertainty, "reasons") else []
    conformal_set = list(rep.conformal_prediction_set or [])
    
    return {
        "fault_type": fault_type,
        "seed": seed,
        "is_window": is_window,
        "status": rep.status,
        "pred_class": pred_class,
        "exact_match": exact_match,
        "hypothesis_key": getattr(rep, "hypothesis_key", None),
        "conformal_set": conformal_set,
        "reasons": reasons,
    }

def run_tuning_slice(seeds=range(6000, 6050)):
    label_map = load_organizer_label_map()
    fault_types = ["normal", "latency_spike", "hardware_failure"]
    
    results = []
    for is_win in [True, False]:
        for ft in fault_types:
            for s in seeds:
                res = evaluate_sample(ft, s, is_win, label_map)
                results.append(res)
                
    # Summary
    groups = defaultdict(lambda: {"total": 0, "exact": 0, "statuses": defaultdict(int), "causes": defaultdict(int), "reasons": defaultdict(int)})
    for r in results:
        mode = "windowed" if r["is_window"] else "snapshot"
        k = f"{mode}_{r['fault_type']}"
        groups[k]["total"] += 1
        if r["exact_match"]:
            groups[k]["exact"] += 1
        groups[k]["statuses"][r["status"]] += 1
        groups[k]["causes"][r["pred_class"]] += 1
        for reas in r["reasons"]:
            # truncate reason
            short_r = reas[:50]
            groups[k]["reasons"][short_r] += 1
            
    return groups

if __name__ == "__main__":
    print("Evaluating current codebase on tuning slice (seeds 6000-6049)...")
    res = run_tuning_slice()
    for k, v in res.items():
        print(f"\nGroup: {k} (Exact: {v['exact']}/{v['total']} = {v['exact']/v['total']*100:.1f}%)")
        print(f"  Statuses: {dict(v['statuses'])}")
        print(f"  Causes: {dict(v['causes'])}")
        print(f"  Top Reasons: {dict(v['reasons'])}")
