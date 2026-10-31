"""Demonstration runner for hackathon organizer telemetry format.

Ingests sample JSONL files (normal, latency_spike, hardware_failure) through the Gateway,
canonicalizes the nested telemetry metrics into standard NetCoop schema,
and executes the full multi-agent diagnostic pipeline.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.config import settings
from gateway.adapters.organizer_adapter import OrganizerAdapter
from orchestrator.graph import run_diagnosis
from storage.db import get_envelope_logs, init_db

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SAMPLES_DIR = PROJECT_ROOT / "data" / "organizer" / "samples"


def load_jsonl_records(file_path: Path) -> List[Dict[str, Any]]:
    """Load JSON Lines records from file."""
    records: List[Dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                records.append(json.loads(line_str))
    return records


def ingest_via_gateway(records: List[Dict[str, Any]], incident_id: str) -> Dict[str, Any]:
    """Ingest organizer records through Gateway microservice or direct adapter."""
    raw_payload = {
        "incident_id": incident_id,
        "network_id": "iit-bbs-campus-fabric",
        "telemetry": records,
    }

    # Attempt HTTP ingestion if gateway microservice is reachable
    gateway_url = f"http://127.0.0.1:{settings.gateway_port}/ingest"
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.post(gateway_url, json=raw_payload)
            if resp.status_code == 200:
                console.print("[dim]Successfully canonicalized via Gateway microservice HTTP (port 8006).[/dim]")
                return resp.json()
    except Exception:
        pass

    # Fallback to direct OrganizerAdapter logic
    console.print("[dim]Canonicalizing via Gateway OrganizerAdapter directly...[/dim]")
    return OrganizerAdapter.adapt_dataset(raw_payload)


def ensure_agents_running() -> bool:
    """Check if agent microservices are running; notice if in-process fallback."""
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

    active = 0
    for port in ports:
        try:
            with httpx.Client(timeout=0.3) as client:
                res = client.get(f"http://127.0.0.1:{port}/health")
                if res.status_code == 200:
                    active += 1
        except Exception:
            pass

    if active == len(ports):
        console.print("[dim]All 8 specialist agent microservices detected active over HTTP.[/dim]")
    else:
        console.print(f"[dim]Specialist agents running in standard mediator dispatch mode ({active}/8 microservices active).[/dim]")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="NetCoop AI Organizer Data Pipeline Demo")
    parser.add_argument(
        "--sample",
        choices=["normal", "latency_spike", "hardware_failure"],
        default="hardware_failure",
        help="Sample scenario to ingest from data/organizer/samples/",
    )
    args = parser.parse_args()

    init_db()
    ensure_agents_running()

    sample_file = SAMPLES_DIR / f"{args.sample}.jsonl"
    if not sample_file.exists():
        console.print(f"[red]Error:[/red] Sample file not found: {sample_file}")
        console.print("[dim]Run 'python data/organizer/organizer_generator.py --emit-all-samples' first.[/dim]")
        sys.exit(1)

    records = load_jsonl_records(sample_file)
    incident_id = f"inc-organizer-{args.sample}"

    console.print(
        Panel(
            f"[bold]Organizer Telemetry Ingestion Demonstration[/bold]\n"
            f"Scenario: {args.sample}\n"
            f"Input File: {sample_file.name}\n"
            f"Raw Records: {len(records)}\n"
            f"Incident ID: {incident_id}",
            box=box.SQUARE,
            title="[bold]IIT Bhubaneswar Hackathon Organizer Pipeline[/bold]",
        )
    )

    # 1. Ingestion through Gateway
    canonical_data = ingest_via_gateway(records, incident_id)
    telemetry_count = len(canonical_data.get("telemetry", []))
    console.print(f"[dim]Gateway transformed {len(records)} raw snapshots into {telemetry_count} canonical records.[/dim]")

    # 2. Run multi-agent diagnosis
    console.print("[dim]Executing multi-agent diagnostic state graph...[/dim]")
    report = run_diagnosis(canonical_data)

    # 3. Print Monochrome Envelope Audit Trace Table
    logs = get_envelope_logs(incident_id)
    table = Table(
        title=f"Monochrome Audit Trace: {incident_id} ({len(logs)} envelopes)",
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

    # 4. Print Unified Diagnostic Report
    report_dict = report.model_dump(mode="json")
    console.print(
        Panel(
            json.dumps(report_dict, indent=2),
            box=box.SQUARE,
            title=f"[bold]Unified Diagnostic Report JSON: {incident_id}[/bold]",
        )
    )

    console.print(
        Panel(
            f"Diagnostic Status: {report.status}\n"
            f"Probable Cause: {report.probable_cause or 'N/A'}\n"
            f"Confidence: {int(report.confidence * 100)}%\n"
            f"Affected Devices: {', '.join(report.affected_devices) if report.affected_devices else 'None'}",
            box=box.SQUARE,
            title="[bold]Diagnosis Summary[/bold]",
        )
    )


if __name__ == "__main__":
    main()
