"""Master asset generation script for NetCoop AI.

Regenerates all visual assets:
1. docs/assets/architecture.svg
2. docs/assets/confusion_matrix.svg
3. docs/assets/reliability_curve.svg
4. docs/assets/risk_coverage.svg
5. docs/assets/dashboard_dark.png
6. docs/assets/dashboard_light.png
7. docs/assets/interop_inspector.png
8. docs/assets/agent_graph.png
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPTS_DIR))

from generate_architecture_svg import generate_architecture_svg
from generate_eval_charts import main as generate_eval_charts
from capture_screenshots import capture_screenshots


def main() -> None:
    print("=== 1. Generating Architecture SVG ===")
    generate_architecture_svg()

    print("\n=== 2. Generating Evaluation Charts (SVGs) ===")
    generate_eval_charts()

    print("\n=== 3. Capturing Headless Dashboard Screenshots ===")
    capture_screenshots()

    print("\nAll assets successfully generated in docs/assets/")


if __name__ == "__main__":
    main()

