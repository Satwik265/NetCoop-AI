"""eval_organizer_suite.py: Evaluate 900 organizer samples on a specified repo directory."""

import argparse
from collections import defaultdict
import json
import os
import sys
import time
from pathlib import Path
from joblib import Parallel, delayed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", type=str, required=True, help="Absolute path to repository directory")
    parser.add_argument("--output-file", type=str, required=True, help="Path to output JSON")
    parser.add_argument("--workers", type=int, default=6, help="Parallel workers")
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir).resolve()
    sys.path.insert(0, str(repo_dir))

    os.environ["AGENTS_MODE"] = "in_process"
    os.environ["IN_PROCESS_FALLBACK"] = "true"
    os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"

    from netcoop.config import settings
    settings.agents_mode = "in_process"
    settings.in_process_fallback = True
    settings.allow_dev_in_process_fallback = True

    from eval.run_eval import evaluate_single_organizer, load_organizer_label_map

    label_map = load_organizer_label_map()
    fault_types = ["normal", "latency_spike", "hardware_failure"]
    sample_tasks = []

    for is_win in [True, False]:
        for ft in fault_types:
            for s in range(5001, 5151):
                sample_tasks.append((ft, s, is_win))

    t0 = time.time()
    results = Parallel(n_jobs=args.workers, backend="loky")(
        delayed(evaluate_single_organizer)(ft, s, is_win, label_map)
        for (ft, s, is_win) in sample_tasks
    )
    elapsed = time.time() - t0

    # Aggregate by mode and fault_type
    groups = defaultdict(lambda: {
        "total": 0,
        "exact_match": 0,
        "set_match": 0,
        "status_counts": defaultdict(int),
        "cause_counts": defaultdict(int),
    })

    overall_exact = 0
    overall_set = 0

    for r in results:
        mode = "windowed" if r["is_window"] else "snapshot"
        ft = r["fault_type"]
        k = f"{mode}_{ft}"
        groups[k]["total"] += 1
        groups[k]["mode"] = mode
        groups[k]["fault_type"] = ft
        if r["exact_match"]:
            groups[k]["exact_match"] += 1
            overall_exact += 1
        if r["set_match"]:
            groups[k]["set_match"] += 1
            overall_set += 1
        groups[k]["status_counts"][r["status"]] += 1
        groups[k]["cause_counts"][r["predicted_class"]] += 1

    summary = {
        "repo_dir": str(repo_dir),
        "total_samples": len(results),
        "overall_exact_match": overall_exact,
        "overall_exact_accuracy": overall_exact / len(results),
        "overall_set_match": overall_set,
        "overall_set_accuracy": overall_set / len(results),
        "duration_seconds": elapsed,
        "groups": {
            k: {
                "mode": v["mode"],
                "fault_type": v["fault_type"],
                "total": v["total"],
                "exact_match": v["exact_match"],
                "accuracy": v["exact_match"] / v["total"],
                "status_counts": dict(v["status_counts"]),
                "cause_counts": dict(v["cause_counts"]),
            }
            for k, v in groups.items()
        },
        "raw_results": results,
    }

    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Completed {len(results)} samples in {elapsed:.2f}s. Exact match: {overall_exact}/{len(results)} ({overall_exact/len(results)*100:.2f}%)")

if __name__ == "__main__":
    main()
