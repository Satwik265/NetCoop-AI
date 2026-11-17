"""Phase 13I Once-Only Evaluation on Frozen Organizer Test Seeds (6100-6149).
Anti-leakage: Executed strictly once after code freeze.
Evaluates 300 test samples: 3 fault categories x 50 seeds x 2 modes (windowed & snapshot).
"""

import os
import sys
import json
import time
from pathlib import Path
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

from eval.run_eval import evaluate_single_organizer, load_organizer_label_map

def main():
    print("=" * 80)
    print("RUNNING ONCE-ONLY EVALUATION ON ORGANIZER TEST SEEDS 6100-6149")
    print("=" * 80)

    label_map = load_organizer_label_map()
    scenarios = ["normal", "latency_spike", "hardware_failure"]
    modes = [("windowed", True), ("snapshot", False)]

    tasks = []
    for mode_name, is_win in modes:
        for sc in scenarios:
            for seed in range(6100, 6150):
                tasks.append((sc, seed, is_win, mode_name))

    print(f"Executing {len(tasks)} runs across 4 workers...")
    t0 = time.time()
    results = Parallel(n_jobs=4)(
        delayed(evaluate_single_organizer)(sc, seed, is_win, label_map)
        for sc, seed, is_win, _ in tasks
    )
    elapsed = time.time() - t0
    print(f"Completed in {elapsed:.2f}s.")

    # Aggregate by mode and category
    grouped = defaultdict(list)
    for r in results:
        mode_str = "windowed" if r["is_window"] else "snapshot"
        k = f"{mode_str}_{r['fault_type']}"
        grouped[k].append(r)

    summary_table = []
    print("\n" + "=" * 105)
    print(f"{'Category':<28} | {'Total':<6} | {'Exact':<6} | {'Exact%':<8} | {'SetMatch':<8} | {'Status Breakdown':<20} | {'Mean Conf':<10}")
    print("=" * 105)

    for k in sorted(grouped.keys()):
        items = grouped[k]
        total = len(items)
        exact = sum(1 for x in items if x.get("exact_match"))
        exact_pct = (exact / total) * 100
        set_m = sum(1 for x in items if x.get("set_match"))
        set_pct = (set_m / total) * 100

        statuses = defaultdict(int)
        causes = defaultdict(int)
        confs = []
        for x in items:
            statuses[x.get("status", "unknown")] += 1
            causes[x.get("predicted_class", "unknown")] += 1
            confs.append(float(x.get("confidence", 0.0)))

        status_str = ", ".join(f"{s}:{cnt}" for s, cnt in sorted(statuses.items()))
        mean_c = np.mean(confs)

        print(f"{k:<28} | {total:<6} | {exact:<6} | {exact_pct:>6.1f}% | {set_pct:>6.1f}%  | {status_str:<20} | {mean_c:.3f}")

        summary_table.append({
            "category": k,
            "total": total,
            "exact_matches": exact,
            "exact_match_rate": round(exact / total, 4),
            "set_matches": set_m,
            "set_match_rate": round(set_m / total, 4),
            "statuses": dict(statuses),
            "causes": dict(causes),
            "confidence_stats": {
                "mean": round(float(np.mean(confs)), 4),
                "std": round(float(np.std(confs)), 4),
                "min": round(float(np.min(confs)), 4),
                "max": round(float(np.max(confs)), 4),
            }
        })

    print("=" * 105)
    overall_exact = sum(s["exact_matches"] for s in summary_table)
    overall_total = sum(s["total"] for s in summary_table)
    print(f"OVERALL EXACT MATCH: {overall_exact}/{overall_total} ({overall_exact/overall_total*100:.2f}%)")

    # Save artifact
    artifact_path = Path("eval/results/phase13i_organizer_test_seeds_6100_6149.json")
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump({
            "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "seeds_evaluated": "6100-6149",
            "total_samples": overall_total,
            "overall_exact_match_rate": round(overall_exact / overall_total, 4),
            "categories": summary_table,
            "raw_results": results,
        }, f, indent=2)
    print(f"\nArtifact saved to: {artifact_path}")

if __name__ == "__main__":
    main()
