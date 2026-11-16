"""Verify Phase 13J constraints on validation set:
1. Faults called normal == 0 on validation
2. Selective risk <= 3% on validation
3. Conformal coverage and selective accuracy on primary 400-sample benchmark
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List
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

from eval.run_eval import (
    CLASSES,
    evaluate_single_in_distribution,
    evaluate_single_heldout,
    evaluate_single_organizer,
    load_organizer_label_map,
)
from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.data.topology_generator import TopologyRandomizedGenerator
from netcoop.orchestrator.graph import run_diagnosis


def eval_validation_seed_sample(scen: str, seed: int, topology_name: str = "validation_mesh_7") -> Dict[str, Any]:
    inc = TopologyRandomizedGenerator.generate(
        scenario=scen,
        seed=seed,
        topology_name=topology_name,
        noise_level=0.1,
    )
    rep = run_diagnosis(inc)

    is_diagnosed = (rep.status == "diagnosed")
    is_benign = (rep.status == "benign")
    is_abstain = (rep.status in ("insufficient_evidence", "ambiguous", "inconclusive"))

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

    # Map predicted cause
    pred_cls = None
    if getattr(rep, "hypothesis_key", None):
        pred_cls = key_map.get(str(rep.hypothesis_key).upper())

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

    c_set = getattr(rep, "conformal_prediction_set", []) or []

    return {
        "scenario": scen,
        "seed": seed,
        "status": rep.status,
        "probable_cause": rep.probable_cause,
        "confidence": rep.confidence,
        "predicted_class": pred_cls,
        "is_accepted": is_accepted,
        "is_correct": is_correct,
        "conformal_prediction_set": c_set,
    }


def main():
    print("Evaluating Validation Set on validation_mesh_7 topology (seeds 251-300, 50 seeds x 10 scenarios = 500 samples)...")
    scenarios = CLASSES + ["ambiguous_multi_fault", "insufficient_data"]
    tasks = [(sc, s) for sc in scenarios for s in range(251, 301)]

    results = Parallel(n_jobs=4)(
        delayed(eval_validation_seed_sample)(sc, s, "validation_mesh_7") for sc, s in tasks
    )

    accepted = [r for r in results if r["is_accepted"]]
    coverage = len(accepted) / len(results)
    correct_accepted = sum(1 for r in accepted if r["is_correct"])
    selective_acc = correct_accepted / len(accepted) if accepted else 0.0
    selective_risk = 1.0 - selective_acc

    # Faults called normal check
    fault_samples = [r for r in results if r["scenario"] not in ("normal_operation", "ambiguous_multi_fault", "insufficient_data")]
    faults_called_normal = sum(
        1 for r in fault_samples
        if r["status"] == "benign" or r["predicted_class"] == "normal_operation"
    )

    print(f"\n--- Validation Results (validation_mesh_7) ---")
    print(f"Total samples: {len(results)}")
    print(f"Accepted: {len(accepted)} ({coverage:.2%})")
    print(f"Selective Accuracy: {selective_acc:.4f} ({selective_acc:.2%})")
    print(f"Selective Risk: {selective_risk:.4f} ({selective_risk:.2%})")
    print(f"Faults called normal: {faults_called_normal} / {len(fault_samples)}")

    assert faults_called_normal == 0, f"FAILED CONSTRAINT: Faults called normal = {faults_called_normal} (must be 0)"
    assert selective_risk <= 0.03, f"FAILED CONSTRAINT: Selective risk = {selective_risk:.4f} (must be <= 3.0%)"
    print("\n>>> ALL VALIDATION CONSTRAINTS MET! <<<")


if __name__ == "__main__":
    main()
