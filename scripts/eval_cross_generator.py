"""scripts/eval_cross_generator.py: Cross-generator validation on heldout, emulation, and organizer sets."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from joblib import Parallel, delayed

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"

from netcoop.config import settings
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from netcoop.core.bench_eval import (
    ALL_SCENARIOS,
    evaluate_sample,
    run_organizer_sample,
    summarize_results,
)
from netcoop.data.heldout_generator import HeldoutNetworkGenerator
from gateway.adapters.organizer_adapter import OrganizerAdapter


def run_heldout_sample(sc: str, s: int) -> Dict[str, Any]:
    inc = HeldoutNetworkGenerator.generate(scenario=sc, seed=s)
    res = evaluate_sample(inc, sc)
    res["seed"] = s
    return res


def eval_heldout_split(seeds_range: range, split_name: str) -> Dict[str, Any]:
    tasks = [(sc, s) for sc in ALL_SCENARIOS for s in seeds_range]
    raw_results = Parallel(n_jobs=8)(delayed(run_heldout_sample)(sc, s) for sc, s in tasks)
    return summarize_results(split_name, raw_results)


def eval_emulation_captures(captures_dir: Path) -> Dict[str, Any]:
    """Evaluate 50 Phase 13L emulation captures from disk."""
    if not captures_dir.exists():
        print(f"Directory {captures_dir} not found!")
        return {}

    capture_files = sorted(list(captures_dir.glob("*.json")))
    raw_results = []

    for f in capture_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            fname = f.name
            if "congestion" in fname:
                gt = "link_congestion"
            elif "cpu_stress" in fname:
                gt = "device_cpu_overload"
            elif "healthy_run" in fname:
                gt = "normal_operation"
            elif "link_flap" in fname:
                gt = "ethernet_interface_fault"
            elif "mtu_mismatch" in fname:
                gt = "mtu_mismatch_blackhole"
            else:
                gt = "unknown"

            res = evaluate_sample(data, gt)
            res["filename"] = fname
            raw_results.append(res)
        except Exception as e:
            print(f"Error loading {f}: {e}")

    return summarize_results("phase13l_emulation_50", raw_results)


def print_summary(name: str, summary: Dict[str, Any]):
    print(f"\n=======================================================")
    print(f"=== {name} Summary ===")
    print(f"=======================================================")
    total = summary.get("total_samples", 0)
    outcomes = summary.get("outcomes", {})
    sel = summary.get("selective_metrics", {})
    safety = summary.get("safety_metrics", {})
    classes = summary.get("per_class_breakdown", {})

    print(f"Total Samples: {total}")
    print(f"Accepted: {outcomes.get('accepted', 0)} / {total} ({outcomes.get('coverage_pct', 0.0):.2f}%)")
    print(f"  Diagnosed: {outcomes.get('diagnosed', 0)}, Benign: {outcomes.get('benign', 0)}, Abstained: {outcomes.get('abstained', 0)}")
    print(f"Selective Accuracy: {sel.get('selective_accuracy', 0.0)*100:.2f}%")
    print(f"Selective Risk: {sel.get('selective_risk', 0.0)*100:.2f}% (Wilson 95% CI: [{sel.get('selective_risk_wilson_ci_lower', 0.0):.4f}, {sel.get('selective_risk_wilson_ci_upper', 0.0):.4f}])")
    print(f"Faults Called Normal: {safety.get('faults_called_normal', 0)} (Rule of Three Upper Bound: {safety.get('faults_called_normal_rule_of_three_bound', 0.0):.4f})")
    print(f"Normal Operation Recall: {safety.get('normal_operation_recall', 0.0)*100:.2f}%")
    print("\nPer-class Recall / Status Breakdown:")
    for c, info in classes.items():
        print(f"  {c:28s}: total={info.get('total', 0)}, diag={info.get('diagnosed', 0)}, ben={info.get('benign', 0)}, abs={info.get('abstained', 0)}, corr={info.get('correct', 0)}")


def main():
    print("Running Cross-Generator Validation Suite...")

    # 1. Heldout Generator Seeds 701-715 (150 samples)
    print("\n[1/4] Running Heldout Generator Seeds 701-715 (Development Split)...")
    h701_res = eval_heldout_split(range(701, 716), "heldout_generator_seeds_701_715")
    print_summary("Heldout Seeds 701-715", h701_res)

    # 2. Heldout Generator Seeds 901-915 (150 samples - Strictly Unseen)
    print("\n[2/4] Running Heldout Generator Seeds 901-915 (Unseen Split)...")
    h901_res = eval_heldout_split(range(901, 916), "heldout_generator_seeds_901_915_unseen")
    print_summary("Heldout Seeds 901-915 (Unseen)", h901_res)

    # 3. Emulation Captures (50 episodes)
    print("\n[3/4] Running 13L Emulation Captures (50 episodes)...")
    cap_dir = Path(r"C:\Users\agraw\.gemini\antigravity\brain\a5970755-df51-4b7a-a6cd-5a44f5fb5355\archive_phase13l\phase13l_raw_captures")
    emu_res = eval_emulation_captures(cap_dir)
    print_summary("13L Emulation Captures (50)", emu_res)

    # 4. Save results to demo_artifacts/cross_generator_eval.json
    out_path = PROJECT_ROOT / "demo_artifacts" / "cross_generator_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "heldout_701_715": h701_res,
            "heldout_901_915": h901_res,
            "emulation_50": emu_res,
        }, f, indent=2)
    print(f"\n[+] Saved cross-generator validation results to {out_path}")


if __name__ == "__main__":
    main()
