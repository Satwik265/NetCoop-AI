"""test_guard_toggles.py: Measure exact effect of each guard toggle on organizer seeds 6000-6049."""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from joblib import Parallel, delayed

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
import netcoop.orchestrator.graph as graph_mod
from eval.run_eval import load_organizer_label_map, determine_predicted_category

def eval_single(ft, seed, is_win, label_map):
    inc = OrganizerTelemetryGenerator.generate_incident(fault_type=ft, seed=seed, is_window=is_win)
    adapted = OrganizerAdapter.adapt_dataset(inc["payload"])
    rep = run_diagnosis(adapted)

    cfg = label_map.get(ft, {})
    canonical_target = cfg.get("canonical", ft)
    
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

    if ft == "normal":
        exact_match = (rep.status == "benign" or pred_class == "normal_operation")
    else:
        exact_match = (rep.status == "diagnosed" and pred_class == canonical_target)

    return {
        "fault_type": ft,
        "seed": seed,
        "is_window": is_win,
        "status": rep.status,
        "pred_class": pred_class,
        "exact_match": exact_match,
    }

def run_suite(label_map, seeds=range(6000, 6050)):
    fault_types = ["normal", "latency_spike", "hardware_failure"]
    tasks = []
    for is_win in [True, False]:
        for ft in fault_types:
            for s in seeds:
                tasks.append((ft, s, is_win))

    results = [eval_single(ft, s, is_win, label_map) for (ft, s, is_win) in tasks]

    summary = defaultdict(lambda: {"total": 0, "exact": 0})
    total_exact = 0
    for r in results:
        mode = "windowed" if r["is_window"] else "snapshot"
        k = f"{mode}_{r['fault_type']}"
        summary[k]["total"] += 1
        if r["exact_match"]:
            summary[k]["exact"] += 1
            total_exact += 1
    return total_exact, len(results), summary

if __name__ == "__main__":
    label_map = load_organizer_label_map()
    print("Baseline:")
    tot, count, summ = run_suite(label_map)
    print(f"Total: {tot}/{count} ({tot/count*100:.1f}%)")
    for k, v in summ.items():
        print(f"  {k}: {v['exact']}/{v['total']} ({v['exact']/v['total']*100:.1f}%)")
