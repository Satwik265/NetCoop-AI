import os
import sys
import json
from collections import defaultdict
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "true"
os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"
from netcoop.config import settings
settings.agents_mode = "in_process"
settings.in_process_fallback = True
settings.allow_dev_in_process_fallback = True

from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.models.splits import DatasetSplitter
from orchestrator.graph import run_diagnosis
from eval.run_eval import CLASSES
from joblib import Parallel, delayed

def eval_single(sc, s, spec):
    os.environ["AGENTS_MODE"] = "in_process"
    os.environ["IN_PROCESS_FALLBACK"] = "true"
    os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"
    from netcoop.config import settings
    settings.agents_mode = "in_process"
    settings.in_process_fallback = True
    settings.allow_dev_in_process_fallback = True

    rng = np.random.RandomState(s)
    sev = spec.severities[rng.randint(0, len(spec.severities))]
    n_shape = spec.noise_shapes[rng.randint(0, len(spec.noise_shapes))]
    miss_rate = round(float(rng.uniform(spec.missing_rate_range[0], spec.missing_rate_range[1])), 4)
    onset = round(float(rng.uniform(spec.onset_offset_range[0], spec.onset_offset_range[1])), 2)

    inc = SyntheticNetworkGenerator.generate(
        scenario=sc,
        seed=s,
        severity=sev,
        noise_level=0.1,
        noise_shape=n_shape,
        missing_sample_rate=miss_rate,
        onset_offset_seconds=onset,
    )
    rep = run_diagnosis(inc)
    c_set = set(rep.conformal_prediction_set or [])
    is_cov = (sc in c_set)

    return {
        "scenario": sc,
        "seed": s,
        "noise_shape": n_shape.value,
        "is_covered": is_cov,
        "prediction_set": list(rep.conformal_prediction_set or []),
    }

def main():
    spec = DatasetSplitter.VALIDATION_SPEC
    print(f"Validation spec seeds: {spec.seed_start} to {spec.seed_end}")

    tasks = [(sc, s) for sc in CLASSES for s in range(spec.seed_start, spec.seed_end + 1)]
    results = Parallel(n_jobs=4)(delayed(eval_single)(sc, s, spec) for sc, s in tasks)

    noise_cov = defaultdict(lambda: {"total": 0, "covered": 0})
    class_cov = defaultdict(lambda: {"total": 0, "covered": 0})

    for r in results:
        ns = r["noise_shape"]
        sc = r["scenario"]
        cov = r["is_covered"]

        noise_cov[ns]["total"] += 1
        if cov:
            noise_cov[ns]["covered"] += 1

        class_cov[sc]["total"] += 1
        if cov:
            class_cov[sc]["covered"] += 1

    total_samples = len(results)
    total_covered = sum(1 for r in results if r["is_covered"])
    overall_cov = total_covered / total_samples if total_samples else 0.0

    print(f"\n=== VALIDATION CONFORMAL COVERAGE (Overall: {overall_cov*100:.2f}%) ===")
    print("\n--- Conformal Coverage by Noise Level ---")
    for n, data in sorted(noise_cov.items()):
        c = data["covered"] / data["total"] if data["total"] else 0
        print(f"  {n:12s}: {c*100:6.2f}% ({data['covered']}/{data['total']})")

    print("\n--- Conformal Coverage by Class ---")
    for cl, data in sorted(class_cov.items()):
        c = data["covered"] / data["total"] if data["total"] else 0
        print(f"  {cl:28s}: {c*100:6.2f}% ({data['covered']}/{data['total']})")

    out_data = {
        "overall_coverage": round(overall_cov, 4),
        "by_noise_level": {n: round(d["covered"] / d["total"], 4) for n, d in noise_cov.items()},
        "by_class": {c: round(d["covered"] / d["total"], 4) for c, d in class_cov.items()},
    }
    with open("eval/results/validation_conformal_breakdown.json", "w") as f:
        json.dump(out_data, f, indent=2)

if __name__ == "__main__":
    main()
