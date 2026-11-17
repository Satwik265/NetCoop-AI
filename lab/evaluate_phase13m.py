#!/usr/bin/env python3
"""evaluate_phase13m.py: Evaluates 50 new emulated network episodes in HTTP mode.

Requirements (Phase 13M):
  - Run in HTTP mode (FastAPI TestClient against full REST API) with no tuning
  - Report per class: diagnosed, abstained, wrong, faults-called-normal, confidence,
    contributing agents, evidence from logs/config, Wilson CIs, rule-of-three bounds.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Enforce deterministic in-process agent execution for HTTP state machine
os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"

from netcoop.config import settings
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

# Gateway & Core Imports
from gateway.adapters.organizer_adapter import OrganizerAdapter
from core.auth import get_auth_headers, ROLE_NETWORK_ENGINEER
from netcoop.core.bench_eval import compute_wilson_ci, compute_rule_of_three

# FastAPI TestClient for true HTTP mode execution
from fastapi.testclient import TestClient
from api.main import app


DEFAULT_CAPTURES_DIR = Path("C:/Users/agraw/.gemini/antigravity/brain/a5970755-df51-4b7a-a6cd-5a44f5fb5355/scratch/phase13m_raw_captures")


KEY_MAP = {
    "LINK_CONGESTION": "link_congestion",
    "ETHERNET_INTERFACE_FAULT": "ethernet_interface_fault",
    "MTU_MISMATCH_BLACKHOLE": "ethernet_interface_fault",
    "DEVICE_CPU_OVERLOAD": "device_cpu_overload",
    "UPSTREAM_FAILURE_CASCADE": "upstream_failure_cascade",
    "WEAK_WIFI_SIGNAL": "weak_wifi_signal",
    "DNS_FAILURE": "dns_failure",
    "DHCP_FAILURE": "dhcp_failure",
    "NO_FAULT": "normal_operation",
}


def evaluate_phase13m(captures_dir: Path = DEFAULT_CAPTURES_DIR) -> Dict[str, Any]:
    """Execute HTTP mode evaluation over all 50 captured episodes."""
    client = TestClient(app)
    auth_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")

    capture_files = sorted(list(captures_dir.glob("ep-*.json")))
    if not capture_files:
        raise FileNotFoundError(f"No capture files found in {captures_dir}. Run emulate_episodes.py first.")

    print(f"[*] Starting Phase 13M HTTP Mode Evaluation over {len(capture_files)} episodes...")

    episode_results: List[Dict[str, Any]] = []
    classes = ["congestion", "link_flap", "mtu_mismatch", "cpu_stress", "healthy_run"]

    class_stats: Dict[str, Dict[str, Any]] = {
        cls_name: {
            "total": 0,
            "diagnosed": 0,
            "abstained": 0,
            "wrong": 0,
            "faults_called_normal": 0,
            "confidences": [],
            "contributing_agents": set(),
            "evidence_sources": set(),
            "evidence_from_logs": 0,
            "evidence_from_config": 0,
        }
        for cls_name in classes
    }

    t0_all = time.perf_counter()

    for cap_path in capture_files:
        with open(cap_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        ep_id = raw_data["episode_id"]
        sc_type = raw_data["scenario_type"]
        gt = raw_data["ground_truth"]
        intensity = raw_data.get("intensity", "moderate")
        seed = raw_data.get("seed", 0)

        # 1. Adapt raw container through Gateway OrganizerAdapter
        adapted = OrganizerAdapter.adapt_dataset(raw_data)

        # 2. HTTP POST to /api/diagnose
        t_http0 = time.perf_counter()
        resp = client.post("/api/diagnose", json=adapted, headers=auth_headers)
        duration_ms = round((time.perf_counter() - t_http0) * 1000.0, 2)

        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} on {ep_id}: {resp.text}")

        report = resp.json()

        status = report.get("status")
        cause_key = report.get("hypothesis_key") or report.get("suspected_root_cause") or ""
        mapped_pred = KEY_MAP.get(cause_key, cause_key.lower() if isinstance(cause_key, str) else "")

        if status == "benign":
            mapped_pred = "normal_operation"

        conf = report.get("confidence") or report.get("final_confidence") or 0.0

        # Class evaluation metrics
        stats = class_stats[sc_type]
        stats["total"] += 1

        is_accepted = status in ("diagnosed", "benign")
        is_abstained = status in ("insufficient_evidence", "inconclusive")

        # Ground truth matching
        is_correct = False
        is_fault_called_normal = False

        if gt == "normal_operation":
            if status == "benign":
                is_correct = True
            elif is_accepted and mapped_pred != "normal_operation":
                stats["wrong"] += 1
            else:
                stats["abstained"] += 1
        else:
            # Active fault
            if status == "benign":
                is_fault_called_normal = True
                stats["faults_called_normal"] += 1
                stats["wrong"] += 1
            elif is_accepted:
                if mapped_pred == gt:
                    is_correct = True
                    stats["diagnosed"] += 1
                else:
                    stats["wrong"] += 1
            else:
                stats["abstained"] += 1

        if is_accepted and is_correct:
            stats["confidences"].append(conf)

        # Extract evidence & contributing agents
        evidence_items = report.get("evidence") or []
        for ev in evidence_items:
            src = ev.get("source_agent") or ev.get("source_type") or "unknown"
            stats["contributing_agents"].add(src)
            dom = ev.get("domain") or ev.get("category") or ""
            if dom:
                stats["evidence_sources"].add(dom)

            desc = str(ev.get("description", "")).lower()
            if "log" in desc or "syslog" in desc or "bfd" in desc or "carrier" in desc:
                stats["evidence_from_logs"] += 1
            if "mtu" in desc or "config" in desc:
                stats["evidence_from_config"] += 1

        episode_results.append({
            "episode_id": ep_id,
            "scenario_type": sc_type,
            "ground_truth": gt,
            "intensity": intensity,
            "seed": seed,
            "status": status,
            "predicted_cause": mapped_pred,
            "confidence": conf,
            "is_correct": is_correct,
            "is_accepted": is_accepted,
            "is_abstained": is_abstained,
            "is_fault_called_normal": is_fault_called_normal,
            "http_duration_ms": duration_ms,
        })

    total_eval_time = round(time.perf_counter() - t0_all, 2)
    print(f"[+] HTTP Evaluation complete in {total_eval_time}s")

    # Aggregate metrics
    summary: Dict[str, Any] = {
        "evaluation_mode": "HTTP (FastAPI TestClient)",
        "total_episodes": len(episode_results),
        "total_time_seconds": total_eval_time,
        "per_class": {},
    }

    total_accepted = sum(s["diagnosed"] for s in class_stats.values()) + class_stats["healthy_run"]["diagnosed"]
    total_wrong = sum(s["wrong"] for s in class_stats.values())
    total_abstained = sum(s["abstained"] for s in class_stats.values())
    total_faults_called_normal = sum(s["faults_called_normal"] for s in class_stats.values())

    # Build per-class summary
    for cls_name, s in class_stats.items():
        n = s["total"]
        diag = s["diagnosed"] if cls_name != "healthy_run" else (n - s["abstained"] - s["wrong"])
        mean_conf = round(sum(s["confidences"]) / len(s["confidences"]), 3) if s["confidences"] else 0.0

        # Wilson CI for coverage / acceptance rate
        p_hat, p_low, p_high = compute_wilson_ci(diag, n)

        summary["per_class"][cls_name] = {
            "total": n,
            "diagnosed": diag,
            "abstained": s["abstained"],
            "wrong": s["wrong"],
            "faults_called_normal": s["faults_called_normal"],
            "mean_confidence": mean_conf,
            "coverage_pct": round((diag / n) * 100.0, 1),
            "wilson_95_ci": [round(p_low, 3), round(p_high, 3)],
            "contributing_agents": sorted(list(s["contributing_agents"])),
            "evidence_sources": sorted(list(s["evidence_sources"])),
            "evidence_from_logs": s["evidence_from_logs"],
            "evidence_from_config": s["evidence_from_config"],
        }

    # Safety metrics
    fault_episodes = [r for r in episode_results if r["ground_truth"] != "normal_operation"]
    n_faults = len(fault_episodes)
    rule_of_three = compute_rule_of_three(n_faults)

    summary["safety"] = {
        "fault_episodes_evaluated": n_faults,
        "faults_called_normal": total_faults_called_normal,
        "rule_of_three_upper_bound_95": round(rule_of_three, 4),
    }

    # Print scorecard
    print("\n" + "=" * 90)
    print(" PHASE 13M EMULATION EVALUATION SCORECARD (HTTP MODE)")
    print("=" * 90)
    print(f"{'Condition':<16} | {'N':<3} | {'Diag':<5} | {'Abs':<5} | {'Wrong':<5} | {'F->Norm':<7} | {'MeanConf':<8} | {'Wilson 95% CI':<15}")
    print("-" * 90)
    for cls_name, s in summary["per_class"].items():
        ci_str = f"[{s['wilson_95_ci'][0]:.2f}, {s['wilson_95_ci'][1]:.2f}]"
        print(f"{cls_name:<16} | {s['total']:<3} | {s['diagnosed']:<5} | {s['abstained']:<5} | {s['wrong']:<5} | {s['faults_called_normal']:<7} | {s['mean_confidence']:<8.3f} | {ci_str:<15}")
    print("-" * 90)
    print(f"Safety: Faults Called Normal = {total_faults_called_normal}/{n_faults} (Rule-of-Three Upper Bound: {rule_of_three * 100:.2f}%)")
    print("=" * 90 + "\n")

    return {
        "summary": summary,
        "episodes": episode_results,
    }


if __name__ == "__main__":
    c_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CAPTURES_DIR
    res = evaluate_phase13m(c_dir)
    out_path = PROJECT_ROOT / "eval" / "results" / "phase13m_emulation_evaluation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"[+] Saved evaluation report to {out_path}")
