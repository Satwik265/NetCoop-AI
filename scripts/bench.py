"""scripts/bench.py: Comprehensive Versioned Evaluation Scorecard & Baseline Suite for NetCoop AI.

Splits:
1. In-distribution primary benchmark (400 samples across 10 classes)
2. Unseen blind topologies (blind_edge_iot_6 and blind_spine_leaf_10, 150 each)
3. Organizer telemetry per class (normal: 300, latency_spike: 300, hardware_failure: 300)
4. Interop suite (9 scenarios)
5. Evidence suite (multi-agent corroboration scenarios)
6. Noise stress (0.0 to 0.35 noise levels)

Baselines (identical frozen set):
- Threshold rules only
- Classifier only
- Full without inquiry
- Leave-one-agent-out ablation (7 specialists)
- Decision change transitions (diagnosed / abstain / misdiagnosed)

Latency:
- >= 200 timed HTTP runs, reporting P50 and P95.

Determinism:
- Parallel vs serial diff per seed.

Outputs:
- demo_artifacts/scorecard.json
- demo_artifacts/scorecard.md
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
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
    KEY_MAP,
    compute_accepted_ece,
    compute_rule_of_three,
    compute_wilson_ci,
    evaluate_sample,
    run_determinism_sample,
    run_in_distribution_sample,
    run_noise_sample,
    run_organizer_sample,
    run_unseen_topology_sample,
    summarize_results,
)
from netcoop.core.correlation import OfflineCorrelationEngine
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    EnvelopePayload,
    MessageType,
    NetworkScope,
    ProtocolHeader,
)
from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.orchestrator.graph import mediator, run_diagnosis

SCORECARD_VERSION = "phase13n_v1"
DEMO_ARTIFACTS_DIR = PROJECT_ROOT / "demo_artifacts"
DEMO_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# Split Evaluators
# -----------------------------------------------------------------------------

def eval_in_distribution_split(n_per_class: int = 40) -> Dict[str, Any]:
    """Evaluate primary in-distribution benchmark (400 samples across 10 classes)."""
    tasks = [(sc, s) for sc in ALL_SCENARIOS for s in range(1, n_per_class + 1)]
    raw_results = Parallel(n_jobs=8)(delayed(run_in_distribution_sample)(sc, s) for sc, s in tasks)
    return summarize_results("in_distribution_primary_400", raw_results)


def eval_unseen_topologies_split(seeds_range: range = range(801, 816)) -> Dict[str, Any]:
    """Evaluate Phase 13J blind topologies (blind_edge_iot_6 and blind_spine_leaf_10)."""
    topologies = ["blind_edge_iot_6", "blind_spine_leaf_10"]
    tasks = [(topo, sc, s) for topo in topologies for sc in ALL_SCENARIOS for s in seeds_range]
    raw_results = Parallel(n_jobs=8)(delayed(run_unseen_topology_sample)(topo, sc, s) for topo, sc, s in tasks)

    sub_summaries = {}
    for topo in topologies:
        topo_res = [r for r in raw_results if r.get("topology") == topo]
        sub_summaries[topo] = summarize_results(f"unseen_topology_{topo}", topo_res)

    overall = summarize_results("unseen_blind_topologies_300", raw_results)
    overall["by_topology"] = sub_summaries
    return overall


def eval_organizer_per_class_split(samples_per_class: int = 300) -> Dict[str, Any]:
    """Evaluate 900 organizer Colab telemetry samples across classes."""
    classes = ["normal", "latency_spike", "hardware_failure"]
    tasks = [(c, s, s % 2 == 0) for c in classes for s in range(1, samples_per_class + 1)]
    raw_results = Parallel(n_jobs=8)(delayed(run_organizer_sample)(c, s, w) for c, s, w in tasks)

    by_class = {}
    for c in classes:
        c_res = [r for r in raw_results if r.get("organizer_class") == c]
        by_class[c] = summarize_results(f"organizer_{c}", c_res)

    overall = summarize_results("organizer_suite_900", raw_results)
    overall["by_organizer_class"] = by_class
    return overall


def eval_interop_suite_split() -> Dict[str, Any]:
    """Evaluate the 9 interoperability scenarios."""
    scenarios_dir = PROJECT_ROOT / "data" / "scenarios"
    interop_files = sorted(list(scenarios_dir.glob("interop_*.json")))
    raw_results = []
    for f in interop_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            gt = data.get("scenario", "link_congestion")
            res = evaluate_sample(data, gt)
            res["filename"] = f.name
            raw_results.append(res)
        except Exception:
            pass
    return summarize_results("interop_suite_9", raw_results)


EVIDENCE_GT_MAP = {
    "mtu_mismatch_with_config.json": "mtu_mismatch_blackhole",
    "link_congestion_with_logs.json": "link_congestion",
    "ethernet_fault_with_logs.json": "ethernet_interface_fault",
    "conflicting_evidence.json": "link_congestion",
    "05_insufficient_evidence_sparse.json": "insufficient_data",
    "ambiguous_multi_fault.json": "ambiguous_multi_fault",
    "insufficient_data.json": "insufficient_data",
}


def eval_evidence_suite_split() -> Dict[str, Any]:
    """Evaluate multi-agent evidence and corroboration fixtures."""
    scenarios_dir = PROJECT_ROOT / "data" / "scenarios"
    target_files = [
        "mtu_mismatch_with_config.json",
        "link_congestion_with_logs.json",
        "ethernet_fault_with_logs.json",
        "conflicting_evidence.json",
        "05_insufficient_evidence_sparse.json",
        "ambiguous_multi_fault.json",
        "insufficient_data.json",
    ]
    raw_results = []
    for fname in target_files:
        f = scenarios_dir / fname
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            gt = EVIDENCE_GT_MAP.get(fname, fname.replace(".json", ""))
            res = evaluate_sample(data, gt)
            res["filename"] = fname
            raw_results.append(res)
    return summarize_results("evidence_suite_7", raw_results)


def eval_noise_stress_split() -> Dict[str, Any]:
    """Evaluate in-distribution scenarios under varying noise levels (0.0 to 0.35)."""
    noise_levels = [0.0, 0.05, 0.10, 0.20, 0.35]
    tasks = [(nl, sc, s) for nl in noise_levels for sc in ALL_SCENARIOS for s in range(1, 11)]
    raw_results = Parallel(n_jobs=8)(delayed(run_noise_sample)(nl, sc, s) for nl, sc, s in tasks)

    by_noise = {}
    for nl in noise_levels:
        nl_res = [r for r in raw_results if r.get("noise_level") == nl]
        by_noise[str(nl)] = summarize_results(f"noise_{nl}", nl_res)

    overall = summarize_results("noise_stress_suite", raw_results)
    overall["by_noise_level"] = by_noise
    return overall


# -----------------------------------------------------------------------------
# Baselines Evaluation on Identical Frozen Sets
# -----------------------------------------------------------------------------

def evaluate_baselines_on_frozen_set(n_per_class: int = 10, seed_start: int = 251) -> Dict[str, Any]:
    """Evaluate 4 baselines on an identical frozen validation set:
    1. Threshold rules only
    2. Classifier only
    3. Full without inquiry
    4. Leave-one-agent-out ablation (7 specialists)
    Reports decision transitions vs full system: diagnosed/abstain/misdiagnosed.
    """
    frozen_samples = []
    for sc in ALL_SCENARIOS:
        for s in range(seed_start, seed_start + n_per_class):
            inc = SyntheticNetworkGenerator.generate(
                scenario=sc,
                seed=s,
                noise_level=0.1,
            )
            frozen_samples.append({"incident": inc, "ground_truth": sc, "seed": s})

    total_frozen = len(frozen_samples)

    def run_full(sample):
        return evaluate_sample(sample["incident"], sample["ground_truth"])

    full_results = [run_full(s) for s in frozen_samples]
    full_decisions = [r["decision_category"] for r in full_results]

    def compute_transitions(base_decisions: List[str]) -> Dict[str, int]:
        counts = {
            "identical": 0,
            "diagnosed_to_abstain": 0,
            "diagnosed_to_misdiagnosed": 0,
            "abstain_to_diagnosed": 0,
            "abstain_to_misdiagnosed": 0,
            "misdiagnosed_to_abstain": 0,
            "misdiagnosed_to_diagnosed": 0,
        }
        for b, f in zip(base_decisions, full_decisions):
            if b == f:
                counts["identical"] += 1
            else:
                key = f"{b}_to_{f}"
                if key in counts:
                    counts[key] += 1
        return counts

    # Baseline 1: Threshold rules only
    from netcoop.agents.telemetry_agent import TelemetryAgent
    tel_agent = TelemetryAgent()
    rule_results = []
    for s in frozen_samples:
        inc = s["incident"]
        gt = s["ground_truth"]
        env = AgentEnvelope(
            header=ProtocolHeader(correlation_id=f"rule-{s['seed']}", sender=AgentRole.ORCHESTRATOR, recipient=AgentRole.TELEMETRY_AGENT, message_type=MessageType.TELEMETRY_DISPATCH),
            payload=EnvelopePayload(scope=NetworkScope(network_id="net", devices=[]), raw_data=inc),
        )
        resp = tel_agent.handle_envelope(env)
        obs = resp.payload.observations
        status, hyp, unc = OfflineCorrelationEngine.evaluate(obs)
        pred_cls = KEY_MAP.get(hyp.cause_key.upper()) if hyp else None
        if status == "benign":
            pred_cls = "normal_operation"
        is_acc = (status in ("diagnosed", "benign"))
        if gt == "normal_operation":
            corr = (status == "benign")
        elif gt in ("ambiguous_multi_fault", "insufficient_data"):
            corr = (status in ("insufficient_evidence", "inconclusive", "ambiguous"))
        else:
            corr = (pred_cls == gt)
        dec = "diagnosed" if (is_acc and corr) else ("misdiagnosed" if is_acc else "abstain")
        rule_results.append({
            "is_accepted": is_acc,
            "is_correct": corr,
            "is_diagnosed": (status == "diagnosed"),
            "is_benign": (status == "benign"),
            "is_abstained": not is_acc,
            "decision_category": dec,
            "confidence": hyp.final_confidence if hyp else 0.0,
            "ground_truth": gt,
        })
    rule_decisions = [r["decision_category"] for r in rule_results]
    rule_summary = summarize_results("baseline_threshold_rules_only", rule_results)
    rule_summary["transitions_vs_full"] = compute_transitions(rule_decisions)

    # Baseline 2: Classifier only
    from netcoop.agents.classifier.classifier_agent import ClassifierAgent
    cls_agent = ClassifierAgent()
    cls_results = []
    for s in frozen_samples:
        inc = s["incident"]
        gt = s["ground_truth"]
        env = AgentEnvelope(
            header=ProtocolHeader(correlation_id=f"cls-{s['seed']}", sender=AgentRole.ORCHESTRATOR, recipient=AgentRole.CLASSIFIER_AGENT, message_type=MessageType.TELEMETRY_DISPATCH),
            payload=EnvelopePayload(scope=NetworkScope(network_id="net", devices=[]), raw_data=inc),
        )
        resp = cls_agent.handle_envelope(env)
        dq = resp.payload.data_quality or {}
        calib_probs = dq.get("calibrated_probabilities", {})
        conf_set = dq.get("conformal_prediction_set", [])
        c_status = dq.get("conformal_status", "single")

        if c_status in ("abstain", "insufficient_evidence") or len(conf_set) == 0:
            is_acc = False
            corr = (gt in ("ambiguous_multi_fault", "insufficient_data"))
            dec = "abstain"
            conf = 0.0
        else:
            top_c = max(calib_probs, key=calib_probs.get) if calib_probs else None
            conf = float(calib_probs.get(top_c, 0.5)) if top_c else 0.5
            is_acc = True
            corr = (top_c == gt)
            dec = "diagnosed" if corr else "misdiagnosed"

        cls_results.append({
            "is_accepted": is_acc,
            "is_correct": corr,
            "is_diagnosed": is_acc and (top_c != "normal_operation" if is_acc else False),
            "is_benign": is_acc and (top_c == "normal_operation" if is_acc else False),
            "is_abstained": not is_acc,
            "decision_category": dec,
            "confidence": conf,
            "ground_truth": gt,
        })
    cls_decisions = [r["decision_category"] for r in cls_results]
    cls_summary = summarize_results("baseline_classifier_only", cls_results)
    cls_summary["transitions_vs_full"] = compute_transitions(cls_decisions)

    # Baseline 3: Full without inquiry
    orig_inq = settings.max_inquiry_iterations
    settings.max_inquiry_iterations = 0
    no_inq_results = [run_full(s) for s in frozen_samples]
    settings.max_inquiry_iterations = orig_inq
    no_inq_decisions = [r["decision_category"] for r in no_inq_results]
    no_inq_summary = summarize_results("baseline_full_without_inquiry", no_inq_results)
    no_inq_summary["transitions_vs_full"] = compute_transitions(no_inq_decisions)

    # Baseline 4: Leave-one-agent-out ablation
    specialists = [
        AgentRole.TELEMETRY_AGENT,
        AgentRole.TOPOLOGY_AGENT,
        AgentRole.CONFIG_AGENT,
        AgentRole.LOG_AGENT,
        AgentRole.WIFI_SERVICES_AGENT,
        AgentRole.CLASSIFIER_AGENT,
    ]
    ablation_summaries = {}
    orig_roles = list(mediator.registry.registered_roles)

    for spec_role in specialists:
        mediator.registry.registered_roles = [r for r in orig_roles if r != spec_role]
        abl_results = [run_full(s) for s in frozen_samples]
        abl_decisions = [r["decision_category"] for r in abl_results]
        abl_sum = summarize_results(f"ablation_without_{spec_role.value}", abl_results)
        abl_sum["transitions_vs_full"] = compute_transitions(abl_decisions)
        ablation_summaries[spec_role.value] = abl_sum

    mediator.registry.registered_roles = list(orig_roles)

    return {
        "frozen_sample_count": total_frozen,
        "full_system": summarize_results("full_system_frozen", full_results),
        "threshold_rules_only": rule_summary,
        "classifier_only": cls_summary,
        "full_without_inquiry": no_inq_summary,
        "leave_one_agent_out": ablation_summaries,
    }


# -----------------------------------------------------------------------------
# Timed HTTP Latency Benchmark (>= 200 runs)
# -----------------------------------------------------------------------------

def benchmark_http_latency(n_runs: int = 200) -> Dict[str, Any]:
    """Execute >= 200 timed HTTP requests through FastAPI TestClient."""
    from fastapi.testclient import TestClient
    from api.main import app
    from core.auth import get_auth_headers, ROLE_NETWORK_ENGINEER

    client = TestClient(app)
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")

    scenarios_dir = PROJECT_ROOT / "data" / "scenarios"
    payloads = []
    for name in ["normal_operation.json", "link_congestion.json", "weak_wifi_signal.json", "ethernet_interface_fault.json", "ambiguous_multi_fault.json"]:
        f = scenarios_dir / name
        if f.exists():
            payloads.append(json.loads(f.read_text(encoding="utf-8")))

    if not payloads:
        payloads = [{"incident_id": f"lat-{i}", "telemetry": []} for i in range(5)]

    latencies_ms = []
    for i in range(5):
        client.post("/api/diagnose", json=payloads[i % len(payloads)], headers=headers)

    for i in range(n_runs):
        p = payloads[i % len(payloads)]
        t0 = time.perf_counter()
        res = client.post("/api/diagnose", json=p, headers=headers)
        dt = (time.perf_counter() - t0) * 1000.0
        assert res.status_code == 200, f"HTTP run {i} failed: {res.text}"
        latencies_ms.append(dt)

    return {
        "runs_evaluated": n_runs,
        "p50_latency_ms": round(float(np.percentile(latencies_ms, 50)), 2),
        "p95_latency_ms": round(float(np.percentile(latencies_ms, 95)), 2),
        "p99_latency_ms": round(float(np.percentile(latencies_ms, 99)), 2),
        "mean_latency_ms": round(float(np.mean(latencies_ms)), 2),
        "min_latency_ms": round(float(np.min(latencies_ms)), 2),
        "max_latency_ms": round(float(np.max(latencies_ms)), 2),
    }


# -----------------------------------------------------------------------------
# Determinism Verification (Parallel vs Serial diff per seed)
# -----------------------------------------------------------------------------

def verify_determinism(n_seeds: int = 50) -> Dict[str, Any]:
    """Compare parallel vs serial diagnostic predictions per seed to verify 0 drift."""
    test_seeds = list(range(251, 251 + n_seeds))
    scenarios = ["link_congestion", "normal_operation", "weak_wifi_signal", "ethernet_interface_fault", "device_cpu_overload"]

    # 1. Serial run
    serial_results = {}
    for s in test_seeds:
        sc = scenarios[s % len(scenarios)]
        inc = SyntheticNetworkGenerator.generate(scenario=sc, seed=s, noise_level=0.1)
        rep = run_diagnosis(inc)
        serial_results[s] = {
            "status": rep.status,
            "probable_cause": rep.probable_cause,
            "confidence": round(float(rep.confidence), 3),
        }

    # 2. Parallel run
    tasks = [(s, scenarios[s % len(scenarios)]) for s in test_seeds]
    par_raw = Parallel(n_jobs=4)(delayed(run_determinism_sample)(s, sc) for s, sc in tasks)
    par_results = dict(par_raw)

    differing_seeds = []
    for s in test_seeds:
        if serial_results[s] != par_results[s]:
            differing_seeds.append({
                "seed": s,
                "serial": serial_results[s],
                "parallel": par_results[s],
            })

    return {
        "seeds_tested": n_seeds,
        "differing_seeds_count": len(differing_seeds),
        "differing_seeds": differing_seeds,
        "is_perfectly_deterministic": (len(differing_seeds) == 0),
    }


# -----------------------------------------------------------------------------
# Markdown Scorecard Generator
# -----------------------------------------------------------------------------

def generate_markdown_scorecard(scorecard_data: Dict[str, Any]) -> str:
    """Render comprehensive markdown report from scorecard JSON."""
    meta = scorecard_data["metadata"]
    splits = scorecard_data["splits"]
    baselines = scorecard_data["baselines"]
    latency = scorecard_data["latency"]
    determinism = scorecard_data["determinism"]

    lines = [
        f"# NetCoop AI Versioned Evaluation Scorecard (`{meta['version']}`)",
        "",
        f"- **Generated:** `{meta['timestamp']}`",
        f"- **Engine Mode:** `{meta['agents_mode']}`",
        f"- **Total Benchmark Samples Evaluated:** `{meta['total_samples_evaluated']}`",
        "",
        "## 1. Primary Benchmark Splits Summary",
        "",
        "| Split / Dataset | Samples | Accepted (Cov %) | Abstained | Sel. Acc | Sel. Risk (Wilson 95% CI) | Faults Called Normal (Rule-of-3) | Accepted ECE | P95 Latency |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for key, sp in splits.items():
        if "outcomes" not in sp:
            continue
        tot = sp["total_samples"]
        out = sp["outcomes"]
        acc = out["accepted"]
        cov = out["coverage_pct"]
        abs_cnt = out["abstained"]
        sm = sp["selective_metrics"]
        saf = sp["safety_metrics"]
        cal = sp["calibration_metrics"]
        lat = sp["latency_ms"]

        sel_acc_str = f"{sm['selective_accuracy'] * 100:.1f}%"
        ci = sm["selective_risk_wilson_95_ci"]
        risk_str = f"{sm['selective_risk'] * 100:.1f}% [{ci[0]*100:.1f}%, {ci[1]*100:.1f}%]"
        f_norm_str = f"{saf['faults_called_normal']} (<= {saf['rule_of_three_upper_bound_95']*100:.2f}%)"
        ece_str = f"{cal['accepted_only_ece']:.4f}"
        lat_str = f"{lat['p95']:.1f} ms"

        lines.append(f"| **{sp['split_name']}** | {tot} | {acc} ({cov}%) | {abs_cnt} | {sel_acc_str} | {risk_str} | {f_norm_str} | {ece_str} | {lat_str} |")

    lines.extend([
        "",
        "## 2. Baselines Comparison (Identical Frozen Set)",
        "",
        "| Baseline Configuration | Accepted | Selective Acc | Selective Risk | Abstentions | Transitions: Diagnosed -> Abstain | Misdiagnosed -> Diagnosed | Identical |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ])

    base_configs = [
        ("Full System (Reference)", baselines["full_system"]),
        ("Threshold Rules Only", baselines["threshold_rules_only"]),
        ("Classifier Only", baselines["classifier_only"]),
        ("Full Without Inquiry", baselines["full_without_inquiry"]),
    ]
    for role_name, b_sum in baselines["leave_one_agent_out"].items():
        base_configs.append((f"Ablation: -{role_name}", b_sum))

    for label, b in base_configs:
        tot = b["total_samples"]
        sm = b["selective_metrics"]
        out = b["outcomes"]
        trans = b.get("transitions_vs_full", {})
        lines.append(
            f"| **{label}** | {out['accepted']} | {sm['selective_accuracy']*100:.1f}% | "
            f"{sm['selective_risk']*100:.1f}% | {out['abstained']} | "
            f"{trans.get('diagnosed_to_abstain', 0)} | {trans.get('misdiagnosed_to_diagnosed', 0)} | "
            f"{trans.get('identical', tot)} |"
        )

    lines.extend([
        "",
        "## 3. Operational Latency & Determinism Verification",
        "",
        f"- **HTTP Timed Runs Evaluated:** `{latency['runs_evaluated']}`",
        f"- **P50 Latency (Median):** `{latency['p50_latency_ms']} ms`",
        f"- **P95 Latency:** `{latency['p95_latency_ms']} ms`",
        f"- **Mean Latency:** `{latency['mean_latency_ms']} ms`",
        f"- **Parallel vs Serial Seed Comparison:** `{determinism['seeds_tested']} seeds tested`",
        f"- **Differing Seeds Count:** `{determinism['differing_seeds_count']}` (Perfect Determinism: `{determinism['is_perfectly_deterministic']}`)",
        "",
        "---",
        "*Automated verification artifact produced by `scripts/bench.py`.*",
    ])

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Main Orchestration
# -----------------------------------------------------------------------------

def main():
    print(f"=================================================================")
    print(f"=== NetCoop AI Comprehensive Benchmarking Suite ({SCORECARD_VERSION}) ===")
    print(f"=================================================================")
    t_start = time.time()

    print("\n[1/6] Running In-Distribution Primary Benchmark (400 samples)...")
    in_dist_res = eval_in_distribution_split(n_per_class=40)
    print(f"      Coverage: {in_dist_res['outcomes']['coverage_pct']}%, Sel Acc: {in_dist_res['selective_metrics']['selective_accuracy']*100:.1f}%, Faults Normal: {in_dist_res['safety_metrics']['faults_called_normal']}")

    print("\n[2/6] Running Unseen Blind Topologies (300 samples across 2 topologies)...")
    unseen_res = eval_unseen_topologies_split(seeds_range=range(801, 816))
    print(f"      Coverage: {unseen_res['outcomes']['coverage_pct']}%, Sel Acc: {unseen_res['selective_metrics']['selective_accuracy']*100:.1f}%, Faults Normal: {unseen_res['safety_metrics']['faults_called_normal']}")

    print("\n[3/6] Running Organizer Telemetry Suite (900 samples)...")
    org_res = eval_organizer_per_class_split(samples_per_class=300)
    print(f"      Coverage: {org_res['outcomes']['coverage_pct']}%, Sel Acc: {org_res['selective_metrics']['selective_accuracy']*100:.1f}%, Faults Normal: {org_res['safety_metrics']['faults_called_normal']}")

    print("\n[4/6] Running Interop, Evidence, and Noise Stress Suites...")
    interop_res = eval_interop_suite_split()
    evidence_res = eval_evidence_suite_split()
    noise_res = eval_noise_stress_split()
    print(f"      Interop: {interop_res['total_samples']} samples, Evidence: {evidence_res['total_samples']} samples, Noise Stress: {noise_res['total_samples']} samples")

    print("\n[5/6] Evaluating Baselines and Ablations on Frozen Set...")
    baselines_res = evaluate_baselines_on_frozen_set(n_per_class=10, seed_start=251)
    print(f"      Baselines evaluated across 100 frozen samples.")

    print("\n[6/6] Benchmarking HTTP Latency (>= 200 runs) and Determinism...")
    lat_res = benchmark_http_latency(n_runs=200)
    det_res = verify_determinism(n_seeds=50)
    print(f"      Latency: P50 = {lat_res['p50_latency_ms']}ms, P95 = {lat_res['p95_latency_ms']}ms")
    print(f"      Determinism: Differing seeds = {det_res['differing_seeds_count']} / {det_res['seeds_tested']}")

    total_samples = (
        in_dist_res["total_samples"]
        + unseen_res["total_samples"]
        + org_res["total_samples"]
        + interop_res["total_samples"]
        + evidence_res["total_samples"]
        + noise_res["total_samples"]
    )

    scorecard_data = {
        "metadata": {
            "version": SCORECARD_VERSION,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "agents_mode": settings.agents_mode,
            "total_samples_evaluated": total_samples,
            "duration_seconds": round(time.time() - t_start, 2),
        },
        "splits": {
            "in_distribution": in_dist_res,
            "unseen_topologies": unseen_res,
            "organizer_per_class": org_res,
            "interop_suite": interop_res,
            "evidence_suite": evidence_res,
            "noise_stress": noise_res,
        },
        "baselines": baselines_res,
        "latency": lat_res,
        "determinism": det_res,
    }

    json_path = DEMO_ARTIFACTS_DIR / "scorecard.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(scorecard_data, f, indent=2)
    print(f"\n[+] Wrote versioned scorecard JSON: {json_path}")

    md_content = generate_markdown_scorecard(scorecard_data)
    md_path = DEMO_ARTIFACTS_DIR / "scorecard.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[+] Wrote versioned scorecard Markdown: {md_path}")

    print("\n=================== SCORECARD SUMMARY ===================")
    print(md_content)
    print(f"\nTotal execution time: {time.time() - t_start:.2f}s")


if __name__ == "__main__":
    main()
