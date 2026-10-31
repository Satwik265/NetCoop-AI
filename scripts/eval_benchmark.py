"""Unified benchmark evaluator testing diagnostic accuracy against manifest scenarios and multi-dataset holdouts."""

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rich.console import Console
from rich.table import Table
from rich import box

from orchestrator.graph import run_diagnosis
from gateway.adapters.organizer_adapter import OrganizerAdapter
from eval.run_eval import run_evaluation_benchmark

console = Console()
SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


def run_manifest_evaluation() -> bool:
    """Run diagnostic engine across all manifest scenarios and report accuracy."""
    manifest_path = SCENARIOS_DIR / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    scenarios = manifest.get("scenarios", [])
    table = Table(title="NetCoop AI Scenario Ground-Truth Benchmark", box=box.SQUARE)
    table.add_column("Scenario", style="cyan")
    table.add_column("Category", style="dim")
    table.add_column("Expected Status", style="white")
    table.add_column("Actual Status", style="bold")
    table.add_column("Confidence", style="white")
    table.add_column("Score", style="bold")

    total = 0
    passed = 0

    for item in scenarios:
        total += 1
        name = item["name"]
        file_path = SCENARIOS_DIR / item["file"]
        if not file_path.exists():
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as sf:
                raw_data = sf.read()

            adapted = OrganizerAdapter.adapt_dataset(raw_data)
            report = run_diagnosis(adapted)

            exp_status = item["expected_status"]
            min_conf = item["target_confidence_min"]

            status_match = report.status == exp_status or (
                exp_status == "benign" and report.status in ("benign", "insufficient_evidence")
            )
            conf_match = report.confidence >= min_conf if exp_status == "diagnosed" else True

            is_ok = status_match and conf_match
            if is_ok:
                passed += 1

            status_style = "green" if report.status == "diagnosed" else "yellow"
            score_text = "[green]PASS[/green]" if is_ok else "[red]FAIL[/red]"

            table.add_row(
                name,
                item.get("category", ""),
                exp_status,
                f"[{status_style}]{report.status}[/{status_style}]",
                f"{int(report.confidence * 100)}%",
                score_text,
            )
        except Exception as e:
            table.add_row(name, item.get("category", ""), exp_status, "[red]ERROR[/red]", "0%", f"[red]{str(e)[:15]}[/red]")

    console.print(table)
    accuracy = (passed / max(1, total)) * 100
    console.print(f"[bold]Total Manifest Benchmark Accuracy:[/bold] {passed}/{total} ({accuracy:.1f}%)\n")
    return passed == total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NetCoop AI Evaluation Benchmark")
    parser.add_argument("--manifest-only", action="store_true", help="Run only the 21 ground-truth scenario files")
    parser.add_argument("--quick", action="store_true", help="Run fast multi-dataset evaluation")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker threads")
    args = parser.parse_args()

    if args.manifest_only:
        success = run_manifest_evaluation()
        exit(0 if success else 1)
    else:
        # Run full multi-dataset benchmark across in-distribution, held-out, and organizer datasets
        run_manifest_evaluation()
        results = run_evaluation_benchmark(quick=args.quick, workers=args.workers)
        exit(0)
