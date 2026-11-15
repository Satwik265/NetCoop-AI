"""
NetCoop AI — Automated Documentation Examples Generator (Phase 12)
Executes real runs of canonical scenarios through the live in-process pipeline
and outputs authentic, reproducible CLI snippets and hackathon 10-key JSON contracts.
Zero hand-edited numbers.
"""

import json
import os
import sys
from pathlib import Path

# Force in-process execution and local fallback
os.environ["AGENTS_MODE"] = "in_process"
os.environ["IN_PROCESS_FALLBACK"] = "1"
os.environ["NETCOOP_ENV"] = "development"

from typer.testing import CliRunner
from fastapi.testclient import TestClient

from netcoop.cli import app as cli_app
from api.main import app as api_app
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.reporting.builder import export_hackathon_report_json
from gateway.adapters.organizer_adapter import OrganizerAdapter


def run_cli_scenario(file_path: str) -> tuple[int, str]:
    runner = CliRunner()
    res = runner.invoke(cli_app, ["diagnose", "--file", file_path])
    return res.exit_code, res.output


def run_hackathon_export(file_path: str, adapt: bool = True) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    if adapt:
        dataset = OrganizerAdapter.adapt_dataset(raw_data)
    else:
        dataset = raw_data
    report = run_diagnosis(dataset)
    return export_hackathon_report_json(report)


def run_api_malformed(file_path: str) -> tuple[int, dict]:
    client = TestClient(api_app)
    with open(file_path, "rb") as f:
        content = f.read()
    response = client.post("/api/diagnose", content=content, headers={"Content-Type": "application/json"})
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}
    return response.status_code, body


def main():
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)

    print("=================================================================")
    print("NetCoop AI — Generating Real Documentation Examples (Phase 12)")
    print("=================================================================\n")

    # 1. Link Congestion (Diagnosed)
    lc_path = "data/scenarios/link_congestion.json"
    print(f"[*] Running live diagnosis for: {lc_path}")
    lc_exit, lc_cli = run_cli_scenario(lc_path)
    lc_export = run_hackathon_export(lc_path, adapt=True)

    # 2. Normal Operation (Benign)
    no_path = "data/scenarios/normal_operation.json"
    print(f"[*] Running live diagnosis for: {no_path}")
    no_exit, no_cli = run_cli_scenario(no_path)
    no_export = run_hackathon_export(no_path, adapt=True)

    # 3. Insufficient Evidence (Sparse & Ambiguous)
    id_path = "data/scenarios/insufficient_data.json"
    print(f"[*] Running live diagnosis for: {id_path}")
    id_exit, id_cli = run_cli_scenario(id_path)
    id_export = run_hackathon_export(id_path, adapt=True)

    # Unadapted renamed fields (evaluates insufficient_evidence under strict schema)
    rf_path = "data/scenarios/interop_renamed_fields.json"
    print(f"[*] Running live diagnosis for (unadapted): {rf_path}")
    rf_export = run_hackathon_export(rf_path, adapt=False)

    # 4. Invalid / Malformed JSON
    mal_path = "data/scenarios/interop_malformed_json.json"
    print(f"[*] Running CLI & API rejection for: {mal_path}")
    mal_exit, mal_cli = run_cli_scenario(mal_path)
    mal_status, mal_body = run_api_malformed(mal_path)

    # Save artifact examples
    out_dir = root / "docs" / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)

    examples = {
        "link_congestion": {
            "cli_exit_code": lc_exit,
            "cli_output": lc_cli,
            "hackathon_report_10_key": lc_export,
        },
        "normal_operation": {
            "cli_exit_code": no_exit,
            "cli_output": no_cli,
            "hackathon_report_10_key": no_export,
        },
        "insufficient_data": {
            "cli_exit_code": id_exit,
            "cli_output": id_cli,
            "hackathon_report_10_key": id_export,
        },
        "interop_renamed_fields_unadapted": {
            "hackathon_report_10_key": rf_export,
        },
        "malformed_json": {
            "cli_exit_code": mal_exit,
            "cli_output": mal_cli,
            "api_status_code": mal_status,
            "api_response_body": mal_body,
        },
    }

    out_file = out_dir / "executed_doc_examples.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2)

    print(f"\n[+] Wrote executed documentation examples to: {out_file}")

    # Print summary of generated values
    print(f"\n--- Link Congestion 10-Key Summary ---")
    print(f"Status: {lc_export['status']}")
    print(f"Confidence: {lc_export['confidence']}")
    print(f"Probable Cause: {lc_export['suspected_root_cause']}")
    print(f"Affected Devices: {lc_export['affected_devices']}")
    print(f"Supporting Evidence Items: {len(lc_export['supporting_evidence'])}")
    print(f"Evidence Sources: {lc_export['evidence_sources']}")
    print(f"Recommended Actions: {len(lc_export['recommended_actions'])}")

    print(f"\n--- Normal Operation Summary ---")
    print(f"Status: {no_export['status']}")
    print(f"Confidence: {no_export['confidence']}")
    print(f"Probable Cause: {no_export['suspected_root_cause']}")

    print(f"\n--- Insufficient Data Summary ---")
    print(f"Status: {id_export['status']}")
    print(f"Confidence: {id_export['confidence']}")

    print(f"\n--- Malformed JSON Summary ---")
    print(f"CLI Exit Code: {mal_exit} (Error caught gracefully)")
    print(f"API HTTP Status: {mal_status} (Rejected before dispatch)")


if __name__ == "__main__":
    main()
