"""Sync evaluation benchmark results into dashboard/public/results."""

import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
EVAL_RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
DASHBOARD_PUBLIC_RESULTS = PROJECT_ROOT / "dashboard" / "public" / "results"


def sync_eval_results() -> None:
    """Copy all eval/results JSON files to dashboard/public/results."""
    DASHBOARD_PUBLIC_RESULTS.mkdir(parents=True, exist_ok=True)
    copied = 0
    if EVAL_RESULTS_DIR.exists():
        for f in EVAL_RESULTS_DIR.glob("*.json"):
            dest = DASHBOARD_PUBLIC_RESULTS / f.name
            shutil.copy2(f, dest)
            copied += 1
            print(f"Synced {f.name} -> {dest}")

    print(f"Total synced benchmark files: {copied}")


if __name__ == "__main__":
    sync_eval_results()

