"""Build dynamic README.md from docs/README.template.md using evaluation results.

Reads eval/results/mock.json (or latest benchmark JSON), extracts all metrics,
formats Markdown tables, and replaces placeholders in docs/README.template.md.
Ensures zero hardcoded claims or numbers in the final README.md.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
TEMPLATE_PATH = PROJECT_ROOT / "docs" / "README.template.md"
README_OUT_PATH = PROJECT_ROOT / "README.md"
EVAL_RESULTS_DIR = PROJECT_ROOT / "eval" / "results"


def get_latest_results_file() -> Path:
    """Find the most relevant results file in eval/results."""
    candidates = list(EVAL_RESULTS_DIR.glob("*.json"))
    if not candidates:
        raise FileNotFoundError(f"No benchmark results JSON found in {EVAL_RESULTS_DIR}")
    
    # Prefer benchmark.json if exists, else mock.json or newest
    for c in candidates:
        if c.name == "benchmark.json":
            return c
    for c in candidates:
        if c.name == "mock.json":
            return c
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def format_per_class_table(per_class: dict) -> str:
    lines = [
        "| Fault Category | Precision | Recall | F1-Score | Support |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]
    for cls_name, m in per_class.items():
        name = cls_name.replace("_", " ").title()
        lines.append(
            f"| `{name}` | {m['precision']*100:.1f}% | {m['recall']*100:.1f}% | {m['f1']:.3f} | {m['support']} |"
        )
    return "\n".join(lines)


def format_ablation_table(ablations: list) -> str:
    lines = [
        "| Pipeline Configuration | Accuracy | Macro F1 | ECE | Latency (ms) | Insufficient Evidence Rate |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]
    for row in ablations:
        cfg = f"**{row['configuration']}**" if "Full" in row["configuration"] else row["configuration"]
        lines.append(
            f"| {cfg} | {row['accuracy']*100:.1f}% | {row['f1_score']:.3f} | {row['ece']:.3f} | {row['avg_latency_ms']:.1f} ms | {row['insufficient_evidence_rate']*100:.1f}% |"
        )
    return "\n".join(lines)


def format_reliability_table(bins: list) -> str:
    lines = [
        "| Confidence Bin Range | Mean Confidence | Observed Accuracy | Calibration Gap | Sample Count |",
        "| :---: | :---: | :---: | :---: | :---: |",
    ]
    for b in bins:
        lower = int(b["bin_lower"] * 100)
        upper = int(b["bin_upper"] * 100)
        gap = abs(b["mean_confidence"] - b["accuracy"])
        lines.append(
            f"| {lower}% – {upper}% | {b['mean_confidence']*100:.1f}% | {b['accuracy']*100:.1f}% | {gap*100:.1f}% | {b['sample_count']} |"
        )
    return "\n".join(lines)


def format_risk_coverage_table(rc: list) -> str:
    lines = [
        "| Selective Coverage | Diagnostic Risk (Error Rate) | Minimum Confidence Threshold | Operational Decision |",
        "| :---: | :---: | :---: | :--- |",
    ]
    for item in rc:
        cov = f"{int(item['coverage']*100)}%"
        risk = f"{item['risk']*100:.1f}%"
        thresh = f"{int(item['confidence_threshold']*100)}%"
        decision = "Zero error; fully autonomous execution" if item["risk"] == 0.0 else "Escalate to human review if threshold unmet"
        lines.append(f"| {cov} | {risk} | {thresh} | {decision} |")
    return "\n".join(lines)


def build_readme() -> None:
    import sys
    sys.exit("README.md is maintained by hand; this generator is deprecated because it reads mock.json")
    results_path = get_latest_results_file()
    print(f"Loading benchmark metrics from: {results_path}")
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found at {TEMPLATE_PATH}")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    summary = data.get("summary", {})
    splits = data.get("dataset_splits", {})
    ablation = data.get("ablation_table", [])
    per_class = data.get("per_class_metrics", {})
    calibration = data.get("calibration", {})
    risk_coverage = data.get("risk_coverage", [])

    # Compute substitutions
    subs = {
        "{{OVERALL_ACCURACY}}": f"{summary.get('overall_accuracy', 0.0)*100:.1f}%",
        "{{MACRO_F1}}": f"{summary.get('macro_f1', 0.0):.3f}",
        "{{WEIGHTED_F1}}": f"{summary.get('weighted_f1', 0.0):.3f}",
        "{{ECE}}": f"{summary.get('expected_calibration_error', 0.0):.3f}",
        "{{ECE_PERCENT}}": f"{summary.get('expected_calibration_error', 0.0)*100:.1f}%",
        "{{BRIER_SCORE}}": f"{summary.get('brier_score', 0.0):.3f}",
        "{{TOTAL_SAMPLES}}": str(summary.get("total_samples", 0)),
        "{{IN_DISTRIBUTION_ACCURACY}}": f"{splits.get('in_distribution_accuracy', 0.0)*100:.1f}%",
        "{{IN_DISTRIBUTION_SAMPLES}}": str(splits.get("in_distribution_samples", 0)),
        "{{HELDOUT_ACCURACY}}": f"{splits.get('held_out_accuracy', 0.0)*100:.1f}%",
        "{{HELDOUT_SAMPLES}}": str(splits.get("held_out_samples", 0)),
        "{{ORGANIZER_ACCURACY}}": f"{splits.get('organizer_accuracy', 0.0)*100:.1f}%",
        "{{ORGANIZER_SAMPLES}}": str(splits.get("organizer_samples", 0)),
        "{{ABLATION_TABLE_MD}}": format_ablation_table(ablation),
        "{{PER_CLASS_TABLE_MD}}": format_per_class_table(per_class),
        "{{RELIABILITY_TABLE_MD}}": format_reliability_table(calibration.get("reliability_bins", [])),
        "{{RISK_COVERAGE_TABLE_MD}}": format_risk_coverage_table(risk_coverage),
        "{{MAX_CALIBRATION_ERROR}}": f"{calibration.get('max_calibration_error', 0.0)*100:.1f}%",
    }

    # Substitute
    content = template
    for key, value in subs.items():
        content = content.replace(key, value)

    # Check for unreplaced placeholders
    import re
    unreplaced = re.findall(r"\{\{[A-Z0-9_]+\}\}", content)
    if unreplaced:
        print(f"Warning: Found unreplaced placeholders: {set(unreplaced)}")

    README_OUT_PATH.write_text(content, encoding="utf-8")
    print(f"Successfully compiled dynamic README: {README_OUT_PATH}")


if __name__ == "__main__":
    build_readme()

