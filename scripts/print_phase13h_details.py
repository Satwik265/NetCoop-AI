import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_FILE = BASE_DIR / "eval" / "results" / "benchmark_phase13h_20261116.json"

with open(RESULTS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 80)
print("1. HELD-OUT 601-615 (BLIND IN 13G) NORMAL OPERATION SAMPLES (15)")
print("=" * 80)
for r in data["heldout_601_615"]["raw_results"]:
    if r["scenario"] == "normal_operation":
        print(f"Seed {r['seed']}: status={r['status']}, conf={r['confidence']:.2f}, conformal={r['conformal_prediction_set']}, pred={r['predicted_class']}, is_correct={r['is_correct']}")

print("\n" + "=" * 80)
print("2. NEW BLIND SPLIT v3 (SEEDS 701-715) NORMAL OPERATION SAMPLES (15)")
print("=" * 80)
for r in data["blind_heldout_701_715"]["raw_results"]:
    if r["scenario"] == "normal_operation":
        print(f"Seed {r['seed']}: status={r['status']}, conf={r['confidence']:.2f}, conformal={r['conformal_prediction_set']}, pred={r['predicted_class']}, is_correct={r['is_correct']}")

print("\n" + "=" * 80)
print("3. PRIMARY BENCHMARK (400 SAMPLES) PER-CLASS TABLE")
print("=" * 80)
p_ct = data["primary_benchmark_400"]["class_table"]
print(f"{'Scenario':<28} | {'Total':<6} | {'Correct':<8} | {'Wrong':<6} | {'Abstained':<10} | {'Accuracy':<8}")
print("-" * 75)
for k, v in p_ct.items():
    print(f"{k:<28} | {v['total']:<6} | {v['correct']:<8} | {v['wrong']:<6} | {v['abstained']:<10} | {v['accuracy']*100:.1f}%")

print("\n" + "=" * 80)
print("4. NEW BLIND SPLIT v3 (SEEDS 701-715) PER-CLASS TABLE")
print("=" * 80)
b_ct = data["blind_heldout_701_715"]["class_table"]
print(f"{'Scenario':<28} | {'Total':<6} | {'Correct':<8} | {'Wrong':<6} | {'Abstained':<10} | {'Accuracy':<8}")
print("-" * 75)
for k, v in b_ct.items():
    print(f"{k:<28} | {v['total']:<6} | {v['correct']:<8} | {v['wrong']:<6} | {v['abstained']:<10} | {v['accuracy']*100:.1f}%")

print("\n" + "=" * 80)
print("5. ORGANIZER COLAB BENCHMARK (900 SAMPLES)")
print("=" * 80)
org = data["organizer_benchmark_900"]
print(f"Total: {org['total_samples']}, Exact Matches: {org['exact_matches']}, Accuracy: {org['accuracy']*100:.2f}%\n")
print(f"{'Mode':<10} | {'Fault Type':<18} | {'Total':<6} | {'Exact Match':<12} | {'Accuracy':<8} | {'Top Statuses':<40} | {'Top Causes':<40}")
print("-" * 125)
for k, row in org["breakdown"].items():
    status_str = ", ".join(f"{sk}: {sv}" for sk, sv in row["statuses"].items())
    cause_str = ", ".join(f"{ck}: {cv}" for ck, cv in row["causes"].items())
    print(f"{row['mode']:<10} | {row['fault_type']:<18} | {row['total']:<6} | {row['correct']:<12} | {row['accuracy']*100:.1f}% | {status_str:<40} | {cause_str:<40}")
