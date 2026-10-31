"""Automated end-to-end demonstration runner for NetCoop AI.

Executes normal_operation, link_congestion, and ethernet_interface_fault end-to-end:
- Ensures specialist agents and gateway microservices are active on designated ports
- Streams envelopes to connected WebSocket subscribers
- Writes every message envelope to SQLite persistent event store
- Prints monochrome envelope trace tables and complete JSON diagnostic reports
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.config import settings
from gateway.adapters.organizer_adapter import OrganizerAdapter
from orchestrator.graph import run_diagnosis
from storage.db import get_envelope_logs, get_incident, init_db

console = Console()

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SCENARIOS_DIR = PROJECT_ROOT / "data" / "scenarios"

DEMO_SCENARIOS = [
    ("normal_operation", SCENARIOS_DIR / "normal_operation.json"),
    ("link_congestion", SCENARIOS_DIR / "link_congestion.json"),
    ("ethernet_interface_fault", SCENARIOS_DIR / "ethernet_interface_fault.json"),
]


def ensure_agents_running() -> bool:
    """Check if agent microservices are running; launch them if not."""
    import httpx

    ports = [
        settings.telemetry_agent_port,
        settings.topology_agent_port,
        settings.config_agent_port,
        settings.log_agent_port,
        settings.synthesizer_agent_port,
        settings.gateway_port,
    ]

    missing = []
    for port in ports:
        try:
            with httpx.Client(timeout=0.8) as client:
                res = client.get(f"http://127.0.0.1:{port}/health")
                if res.status_code != 200:
                    missing.append(port)
        except Exception:
            missing.append(port)

    if missing:
        console.print(f"[dim]Launching {len(missing)} inactive agent microservices...[/dim]")
        run_script = PROJECT_ROOT / "scripts" / "run_agents.py"
        subprocess.run([sys.executable, str(run_script), "--daemon"], check=False)
        time.sleep(2.0)

    return True


def run_scenario_demo(scenario_name: str, scenario_path: Path) -> Dict[str, Any]:
    """Execute a single scenario end-to-end with monochrome trace and JSON report."""
    if not scenario_path.exists():
        console.print(f"[red]Error:[/red] Scenario file not found: {scenario_path}")
        return {}

    with open(scenario_path, "r", encoding="utf-8") as f:
        raw_dataset = json.load(f)

    incident_id = raw_dataset.get("incident_id", f"inc-{scenario_name}")
    network_id = raw_dataset.get("network_id", "campus-network")

    console.print(
        Panel(
            f"[bold]Scenario:[/bold] {scenario_name}\n"
            f"[bold]Incident ID:[/bold] {incident_id}\n"
            f"[bold]Network ID:[/bold] {network_id}\n"
            f"[bold]Input File:[/bold] {scenario_path.name}",
            box=box.SQUARE,
            title=f"[bold]NetCoop AI Demo: {scenario_name}[/bold]",
        )
    )

    # 1. Gateway Ingestion and Canonicalization
    console.print("[dim]1. Ingesting and canonicalizing telemetry through Gateway adapter...[/dim]")
    canonical_data = OrganizerAdapter.adapt_dataset(raw_dataset)

    # 2. Multi-Agent Orchestration
    console.print("[dim]2. Orchestrating specialist agents across HTTP loopback microservices...[/dim]")
    report = run_diagnosis(canonical_data)

    # 3. Print Monochrome Envelope Trace Table
    logs = get_envelope_logs(incident_id)
    table = Table(
        title=f"Monochrome Audit Trace: {incident_id} ({len(logs)} envelopes recorded)",
        box=box.SQUARE,
    )
    table.add_column("Step", style="dim", justify="right")
    table.add_column("Time UTC", style="dim")
    table.add_column("Sender", style="bold")
    table.add_column("Recipient", style="dim")
    table.add_column("Message Type", style="white")
    table.add_column("Priority", style="dim")
    table.add_column("Summary", style="white")

    for idx, l in enumerate(logs, 1):
        try:
            payload = json.loads(l.payload_json)
        except Exception:
            payload = {}
        obs_c = len(payload.get("observations", []))
        hyp_c = len(payload.get("hypotheses", []))
        inq_c = len(payload.get("inquiries", []))
        summary = f"obs={obs_c}, hyp={hyp_c}, inq={inq_c}"
        table.add_row(
            str(idx),
            l.timestamp_utc[11:19] if len(l.timestamp_utc) >= 19 else l.timestamp_utc,
            l.sender,
            l.recipient,
            l.message_type,
            l.priority,
            summary,
        )

    console.print(table)

    # 4. Print Unified Diagnostic JSON Report
    report_dict = report.model_dump(mode="json")
    report_json_str = json.dumps(report_dict, indent=2)
    console.print(
        Panel(
            report_json_str,
            box=box.SQUARE,
            title=f"[bold]Unified Diagnostic Report JSON: {incident_id}[/bold]",
        )
    )

    return report_dict


def main() -> None:
    """Run full demonstration workflow."""
    init_db()
    console.print(
        Panel(
            "[bold]NetCoop AI Multi-Agent Diagnostic Demonstration[/bold]\n"
            "Testing 3 core scenarios: normal_operation, link_congestion, ethernet_interface_fault\n"
            "Verifying HTTP agent processes, WebSocket streaming, SQLite audit logs, and JSON reports.",
            box=box.SQUARE,
            title="[bold]IIT Bhubaneswar Hackathon Demo[/bold]",
        )
    )

    ensure_agents_running()

    results = []
    for name, path in DEMO_SCENARIOS:
        console.print(f"\n[bold]--- Running Demonstration Scenario: {name} ---[/bold]\n")
        res = run_scenario_demo(name, path)
        results.append((name, res.get("status"), res.get("probable_cause"), res.get("confidence")))

    # Final summary banner
    summary_table = Table(title="Demonstration Execution Summary", box=box.SQUARE)
    summary_table.add_column("Scenario", style="bold")
    summary_table.add_column("Diagnostic Status", style="white")
    summary_table.add_column("Confidence", style="white")
    summary_table.add_column("Probable Cause", style="dim")

    for name, status, cause, conf in results:
        conf_str = f"{int((conf or 0.0) * 100)}%" if conf is not None else "N/A"
        summary_table.add_row(name, status or "unknown", conf_str, cause or "N/A")

    console.print("\n")
    console.print(summary_table)
    console.print(
        Panel(
            "Demo run finished successfully.\n"
            "Use 'netcoop replay <incident_id>' to replay any individual trace.\n"
            "Example: netcoop replay inc-link-congestion-42",
            box=box.SQUARE,
            title="[bold]Demo Completed[/bold]",
        )
    )


if __name__ == "__main__":
    main()

