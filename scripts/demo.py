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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCENARIOS_DIR = PROJECT_ROOT / "data" / "scenarios"

DEMO_SCENARIOS = [
    ("normal_operation", SCENARIOS_DIR / "normal_operation.json"),
    ("link_congestion", SCENARIOS_DIR / "link_congestion.json"),
    ("ethernet_interface_fault", SCENARIOS_DIR / "ethernet_interface_fault.json"),
]


_DEMO_CHILD_PROCS: List[Any] = []


def ensure_agents_running() -> bool:
    """Check if agent microservices are running; launch them as supervised processes if not."""
    import httpx
    from scripts.run_agents import (
        AGENT_ROLES,
        GATEWAY_SERVICE,
        start_agent_process,
        start_gateway_process,
    )

    ports = [
        settings.telemetry_agent_port,
        settings.topology_agent_port,
        settings.config_agent_port,
        settings.log_agent_port,
        settings.synthesizer_agent_port,
        settings.gateway_port,
        settings.classifier_agent_port,
        settings.wifi_services_agent_port,
    ]

    missing = []
    for port in ports:
        try:
            with httpx.Client(timeout=0.5) as client:
                res = client.get(f"http://127.0.0.1:{port}/health")
                if res.status_code != 200:
                    missing.append(port)
        except Exception:
            missing.append(port)

    if missing:
        console.print(f"[dim]Launching {len(missing)} inactive agent microservices as supervised child processes...[/dim]")
        if settings.gateway_port in missing:
            gw_proc = start_gateway_process(settings.gateway_port, PROJECT_ROOT)
            _DEMO_CHILD_PROCS.append(gw_proc)

        for role, port in AGENT_ROLES:
            if port in missing:
                proc = start_agent_process(role, port, PROJECT_ROOT)
                _DEMO_CHILD_PROCS.append(proc)

        # Wait for all to be healthy concurrently
        all_services = AGENT_ROLES + [GATEWAY_SERVICE]
        pending = {r: p for r, p in all_services if p in missing}
        start_wait = time.time()
        timeout = 25.0
        while pending and (time.time() - start_wait < timeout):
            for role in list(pending.keys()):
                port = pending[role]
                url = f"http://127.0.0.1:{port}/health"
                try:
                    with httpx.Client(timeout=0.5) as client:
                        res = client.get(url)
                        if res.status_code == 200:
                            del pending[role]
                except Exception:
                    pass
            if pending:
                time.sleep(0.5)

        for role, port in all_services:
            try:
                with httpx.Client(timeout=0.5) as client:
                    res = client.get(f"http://127.0.0.1:{port}/health")
                    status = "healthy" if res.status_code == 200 else "UNRESPONSIVE"
            except Exception:
                status = "UNRESPONSIVE"
            console.print(f"  [dim]{role:<22} (port {port}): {status}[/dim]")

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

    # 1. Gateway Ingestion and Canonicalization over HTTP
    console.print(f"[dim]1. Ingesting and canonicalizing telemetry through Gateway HTTP microservice (port {settings.gateway_port})...[/dim]")
    import httpx
    gateway_url = settings.get_gateway_url()
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(gateway_url, json=raw_dataset)
            if resp.status_code == 200:
                canonical_data = resp.json()
            else:
                raise RuntimeError(f"Gateway HTTP error {resp.status_code}: {resp.text}")
    except Exception as exc:
        console.print(f"[bold red]Gateway service unreachable at {gateway_url}: {exc}[/bold red]")
        raise

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

    try:
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
    finally:
        from scripts.run_agents import terminate_pid
        if _DEMO_CHILD_PROCS:
            console.print("\n[dim]Cleaning up supervised demo microservice processes...[/dim]")
            for p in _DEMO_CHILD_PROCS:
                try:
                    terminate_pid(p.pid)
                except Exception:
                    pass
            _DEMO_CHILD_PROCS.clear()


if __name__ == "__main__":
    main()

