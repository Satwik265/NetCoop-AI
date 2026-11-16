import json
import os
import sys
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

from netcoop.data.heldout_generator import HeldoutNetworkGenerator
from orchestrator.graph import run_diagnosis

print("=" * 140)
print(f"{'Seed':<5} | {'Status':<22} | {'Conformal Set':<35} | {'Largest Metric Dev (vs nominal threshold)':<42} | {'Abstention Reason'}")
print("=" * 140)

for seed in range(601, 616):
    scenario_data = HeldoutNetworkGenerator.generate(scenario="normal_operation", seed=seed)
    report = run_diagnosis(scenario_data)
    
    # Compute largest metric deviation vs nominal thresholds
    # Nominal bounds: util <= 75%, queue_drops == 0, iface_err == 0, latency <= 10.0, cpu <= 75%, loss == 0.0
    telemetry = scenario_data.get("telemetry", [])
    max_dev_ratio = 0.0
    max_dev_desc = "All metrics nominal"
    
    for metrics in telemetry:
        dev_id = metrics.get("device_id", "unknown")
        # CPU
        cpu = metrics.get("cpu_pct", 0.0)
        ratio = cpu / 75.0
        if ratio > max_dev_ratio:
            max_dev_ratio = ratio
            max_dev_desc = f"{dev_id} cpu={cpu:.1f}% (lim 75%, {ratio:.2f}x)"
            
        # Utilization
        util = metrics.get("link_utilization_pct", 0.0)
        u_ratio = util / 75.0
        if u_ratio > max_dev_ratio:
            max_dev_ratio = u_ratio
            max_dev_desc = f"{dev_id} util={util:.1f}% (lim 75%, {u_ratio:.2f}x)"
            
        # Queue drops & iface errors
        qd = metrics.get("queue_drops", 0)
        if qd > 0:
            max_dev_desc = f"{dev_id} queue_drops={qd}"
            max_dev_ratio = 999.0
        err = metrics.get("interface_errors", 0)
        if err > 0:
            max_dev_desc = f"{dev_id} iface_err={err}"
            max_dev_ratio = 999.0
            
        # Latency / loss
        lat = metrics.get("latency_ms", 0.0)
        l_ratio = lat / 10.0
        if l_ratio > max_dev_ratio:
            max_dev_ratio = l_ratio
            max_dev_desc = f"{dev_id} lat={lat:.1f}ms (lim 10ms, {l_ratio:.2f}x)"
            
        loss = metrics.get("packet_loss_pct", 0.0)
        if loss > 0.0:
            max_dev_desc = f"{dev_id} loss={loss:.2f}%"
            max_dev_ratio = 999.0
            
    conf_set = str(report.conformal_prediction_set)
    # Abstention reason from report
    reasons = report.uncertainty.reasons if hasattr(report, "uncertainty") and hasattr(report.uncertainty, "reasons") else []
    reason_str = "; ".join(reasons) if reasons else report.summary
    if len(reason_str) > 55:
        reason_str = reason_str[:52] + "..."
        
    print(f"{seed:<5} | {report.status:<22} | {conf_set:<35} | {max_dev_desc:<42} | {reason_str}")
