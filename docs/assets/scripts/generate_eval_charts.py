"""Generate grayscale SVG charts for confusion matrix, reliability diagram, and risk-coverage."""

import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent
MOCK_RESULTS_PATH = Path(__file__).parent.parent.parent.parent / "eval" / "results" / "mock.json"


def generate_confusion_matrix_svg(data: dict) -> None:
    cm = data["confusion_matrix"]
    classes = cm["classes"]
    matrix = cm["matrix"]
    n = len(classes)

    cell_size = 42
    margin_left = 180
    margin_top = 100
    width = margin_left + n * cell_size + 40
    height = margin_top + n * cell_size + 60

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #0F0F10; font-family: \'JetBrains Mono\', monospace;">',
        '  <text x="40" y="40" fill="#EDEDEA" font-size="15" font-weight="700">CONFUSION MATRIX (10 CANONICAL CLASSES)</text>',
        '  <text x="40" y="58" fill="#6B6B66" font-size="10">Overall Evaluation Accuracy: 95.8% | Macro F1: 0.952</text>',
    ]

    # Column headers
    for j, c in enumerate(classes):
        cx = margin_left + j * cell_size + cell_size / 2
        svg.append(f'  <text x="{cx}" y="{margin_top - 12}" fill="#6B6B66" font-size="9" text-anchor="middle">C{j+1}</text>')

    # Rows
    for i, row in enumerate(matrix):
        ry = margin_top + i * cell_size
        class_label = f"C{i+1}: {classes[i]}"
        svg.append(f'  <text x="{margin_left - 12}" y="{ry + cell_size/2 + 3}" fill="#EDEDEA" font-size="9" text-anchor="end">{class_label}</text>')
        row_total = sum(row)

        for j, val in enumerate(row):
            rx = margin_left + j * cell_size
            is_diag = i == j
            intensity = val / row_total if row_total > 0 else 0

            if val > 0:
                bg = f"rgba(71, 85, 105, {max(0.2, intensity):.2f})" if is_diag else f"rgba(154, 91, 91, {max(0.2, intensity):.2f})"
                text_color = "#FFFFFF" if is_diag else "#9A5B5B"
            else:
                bg = "#161618"
                text_color = "#2A2A2D"

            svg.append(f'  <rect x="{rx}" y="{ry}" width="{cell_size-2}" height="{cell_size-2}" fill="{bg}" stroke="#2A2A2D" stroke-width="0.5" />')
            if val > 0:
                svg.append(f'  <text x="{rx + cell_size/2 - 1}" y="{ry + cell_size/2 + 3}" fill="{text_color}" font-size="10" font-weight="700" text-anchor="middle">{val}</text>')

    svg.append('</svg>')
    out_file = OUTPUT_DIR / "confusion_matrix.svg"
    out_file.write_text("\n".join(svg), encoding="utf-8")
    print(f"Generated confusion matrix SVG: {out_file}")


def generate_reliability_curve_svg(data: dict) -> None:
    calib = data["calibration"]
    bins = calib["reliability_bins"]
    ece = calib["expected_calibration_error"]

    width = 500
    height = 360
    ox, oy = 60, 290
    gw, gh = 380, 220

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #0F0F10; font-family: \'JetBrains Mono\', monospace;">',
        '  <text x="40" y="32" fill="#EDEDEA" font-size="14" font-weight="700">RELIABILITY DIAGRAM &amp; CALIBRATION</text>',
        f'  <text x="40" y="48" fill="#6B6B66" font-size="10">Expected Calibration Error (ECE): {ece*100:.1f}% | Brier Score: {data["summary"]["brier_score"]:.3f}</text>',
        # Grid lines
        f'  <line x1="{ox}" y1="{oy}" x2="{ox+gw}" y2="{oy}" stroke="#2A2A2D" stroke-width="1" />',
        f'  <line x1="{ox}" y1="{oy-gh}" x2="{ox}" y2="{oy}" stroke="#2A2A2D" stroke-width="1" />',
    ]

    for f in [0.25, 0.5, 0.75, 1.0]:
        y = oy - f * gh
        x = ox + f * gw
        svg.append(f'  <line x1="{ox}" y1="{y}" x2="{ox+gw}" y2="{y}" stroke="#2A2A2D" stroke-width="0.5" stroke-dasharray="2,2" />')
        svg.append(f'  <text x="{ox-10}" y="{y+3}" fill="#6B6B66" font-size="8" text-anchor="end">{int(f*100)}%</text>')
        svg.append(f'  <text x="{x}" y="{oy+16}" fill="#6B6B66" font-size="8" text-anchor="middle">{int(f*100)}%</text>')

    # Diagonal ideal
    svg.append(f'  <line x1="{ox}" y1="{oy}" x2="{ox+gw}" y2="{oy-gh}" stroke="#6B6B66" stroke-width="1.2" stroke-dasharray="4,3" />')

    points = []
    for b in bins:
        px = ox + b["mean_confidence"] * gw
        py = oy - b["accuracy"] * gh
        points.append(f"{px:.1f},{py:.1f}")

    svg.append(f'  <polyline fill="none" stroke="#475569" stroke-width="2.5" points="{" ".join(points)}" />')
    for b in bins:
        px = ox + b["mean_confidence"] * gw
        py = oy - b["accuracy"] * gh
        svg.append(f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#EDEDEA" stroke="#475569" stroke-width="1.5" />')

    svg.append(f'  <text x="{ox+gw/2}" y="{oy+34}" fill="#6B6B66" font-size="9" text-anchor="middle">Mean Predicted Confidence</text>')
    svg.append('</svg>')

    out_file = OUTPUT_DIR / "reliability_curve.svg"
    out_file.write_text("\n".join(svg), encoding="utf-8")
    print(f"Generated reliability curve SVG: {out_file}")


def generate_risk_coverage_svg(data: dict) -> None:
    rc_data = data["risk_coverage"]

    width = 500
    height = 360
    ox, oy = 60, 290
    gw, gh = 380, 220

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #0F0F10; font-family: \'JetBrains Mono\', monospace;">',
        '  <text x="40" y="32" fill="#EDEDEA" font-size="14" font-weight="700">SELECTIVE CLASSIFICATION (RISK-COVERAGE)</text>',
        '  <text x="40" y="48" fill="#6B6B66" font-size="10">Zero error rate achieved when accepting predictions &gt;= 88% confidence (80% coverage)</text>',
        f'  <line x1="{ox}" y1="{oy}" x2="{ox+gw}" y2="{oy}" stroke="#2A2A2D" stroke-width="1" />',
        f'  <line x1="{ox}" y1="{oy-gh}" x2="{ox}" y2="{oy}" stroke="#2A2A2D" stroke-width="1" />',
    ]

    # Y ticks for risk: 0% to 5%
    for r in [0.01, 0.02, 0.03, 0.04, 0.05]:
        y = oy - (r / 0.05) * gh
        svg.append(f'  <line x1="{ox}" y1="{y}" x2="{ox+gw}" y2="{y}" stroke="#2A2A2D" stroke-width="0.5" stroke-dasharray="2,2" />')
        svg.append(f'  <text x="{ox-10}" y="{y+3}" fill="#6B6B66" font-size="8" text-anchor="end">{r*100:.1f}%</text>')

    # X ticks for coverage: 70% to 100%
    for cov in [0.70, 0.80, 0.90, 1.00]:
        x = ox + ((cov - 0.65) / 0.35) * gw
        svg.append(f'  <text x="{x}" y="{oy+16}" fill="#6B6B66" font-size="8" text-anchor="middle">{int(cov*100)}%</text>')

    points = []
    for item in rc_data:
        x = ox + ((item["coverage"] - 0.65) / 0.35) * gw
        y = oy - (item["risk"] / 0.05) * gh
        points.append(f"{x:.1f},{y:.1f}")

    svg.append(f'  <polyline fill="none" stroke="#475569" stroke-width="2.5" points="{" ".join(points)}" />')
    for item in rc_data:
        x = ox + ((item["coverage"] - 0.65) / 0.35) * gw
        y = oy - (item["risk"] / 0.05) * gh
        svg.append(f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#EDEDEA" stroke="#475569" stroke-width="1.5" />')

    svg.append(f'  <text x="{ox+gw/2}" y="{oy+34}" fill="#6B6B66" font-size="9" text-anchor="middle">Accepted Coverage Proportion</text>')
    svg.append('</svg>')

    out_file = OUTPUT_DIR / "risk_coverage.svg"
    out_file.write_text("\n".join(svg), encoding="utf-8")
    print(f"Generated risk-coverage SVG: {out_file}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(MOCK_RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    generate_confusion_matrix_svg(data)
    generate_reliability_curve_svg(data)
    generate_risk_coverage_svg(data)


if __name__ == "__main__":
    main()

