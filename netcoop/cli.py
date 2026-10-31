"""Command-line interface for NetCoop AI using Typer and Rich."""

import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from netcoop import __version__
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.remediation.engine import RemediationEngine
from netcoop.storage.db import get_envelope_logs, get_incident, init_db, list_incidents

app = typer.Typer(
    name="netcoop",
    help="NetCoop AI: Multi-agent network fault diagnosis and simulated remediation platform.",
    no_args_is_help=True,
)
incidents_app = typer.Typer(help="Manage and inspect diagnostic incidents.")
envelopes_app = typer.Typer(help="Inspect inter-agent envelope audit traces.")
remediate_app = typer.Typer(help="Manage simulated remediation actions.")

app.add_typer(incidents_app, name="incidents")
app.add_typer(envelopes_app, name="envelopes")
app.add_typer(remediate_app, name="remediate")

console = Console()


@app.command("version")
def version_cmd() -> None:
    """Print the current NetCoop AI version."""
    console.print(f"[bold]NetCoop AI[/bold] version {__version__}")


@app.command("diagnose")
def diagnose_cmd(
    file_path: Path = typer.Option(
        ...,
        "--file",
        "-f",
        help="Path to network incident JSON file conforming to schemas/telemetry.json",
        exists=True,
    ),
) -> None:
    """Run full multi-agent diagnostic pipeline on network incident input."""
    init_db()
    with open(file_path, "r", encoding="utf-8") as f:
        incident_data = json.load(f)

    console.print(
        Panel(
            f"[bold]Starting Multi-Agent Diagnosis[/bold]\n"
            f"Incident ID: {incident_data.get('incident_id')}\n"
            f"Network ID: {incident_data.get('network_id')}\n"
            f"Description: {incident_data.get('description')}",
            box=box.SQUARE,
            title="[bold]NetCoop AI Orchestrator[/bold]",
        )
    )

    with console.status("[dim]Orchestrating agents and cross-correlating evidence...[/dim]"):
        report = run_diagnosis(incident_data)

    status_style = "green" if report.status == "diagnosed" else "yellow"
    summary_panel = (
        f"[bold]Status:[/bold] [{status_style}]{report.status}[/{status_style}]\n"
        f"[bold]Probable Cause:[/bold] {report.probable_cause or 'N/A'}\n"
        f"[bold]Confidence:[/bold] {int(report.confidence * 100)}%\n"
        f"[bold]Affected Devices:[/bold] {', '.join(report.affected_devices) if report.affected_devices else 'None'}\n"
        f"[bold]Processing Time:[/bold] {report.processing_time_ms} ms\n\n"
        f"[bold]Executive Summary:[/bold]\n{report.summary}"
    )
    console.print(Panel(summary_panel, box=box.SQUARE, title="[bold]Diagnostic Report[/bold]"))

    # Evidence Table
    if report.evidence:
        table = Table(title="Corroborated Evidence Chains", box=box.SQUARE)
        table.add_column("Agent Domain", style="cyan")
        table.add_column("Category", style="dim")
        table.add_column("Entity", style="white")
        table.add_column("Finding", style="white")
        table.add_column("Severity", style="bold")

        for ev in report.evidence:
            sev = ev.get("severity", "info")
            sev_style = "red" if sev == "critical" else "yellow" if sev == "warning" else "white"
            table.add_row(
                ev.get("source_agent", ""),
                ev.get("category", ""),
                ev.get("entity", ""),
                ev.get("finding", ""),
                f"[{sev_style}]{sev}[/{sev_style}]",
            )
        console.print(table)

    # Uncertainty details if insufficient evidence
    if report.status == "insufficient_evidence":
        unc_panel = (
            f"[bold]Uncertainty Score:[/bold] {report.uncertainty.score:.2f}\n"
            f"[bold]Missing Corroboration Required:[/bold]\n"
            + "\n".join(f"- {m}" for m in report.uncertainty.missing_evidence)
        )
        console.print(Panel(unc_panel, box=box.SQUARE, title="[bold]Uncertainty Analysis[/bold]"))

    # Remediation Table
    if report.remediation_actions:
        rem_table = Table(title="Recommended Simulated Remediation Actions", box=box.SQUARE)
        rem_table.add_column("Action ID", style="cyan")
        rem_table.add_column("Title", style="white")
        rem_table.add_column("Device", style="white")
        rem_table.add_column("Risk", style="yellow")
        rem_table.add_column("Status", style="dim")

        for act in report.remediation_actions:
            rem_table.add_row(
                act.action_id,
                act.title,
                act.device,
                act.risk_level,
                act.status,
            )
        console.print(rem_table)
        console.print("[dim]Use 'netcoop remediate approve <incident-id> <action-id>' to simulate execution.[/dim]")


@incidents_app.command("list")
def list_incidents_cmd() -> None:
    """List recent network diagnostic incidents."""
    init_db()
    records = list_incidents()
    if not records:
        console.print("[dim]No incidents recorded in database.[/dim]")
        return

    table = Table(title="Recorded Diagnostic Incidents", box=box.SQUARE)
    table.add_column("Incident ID", style="cyan")
    table.add_column("Network ID", style="white")
    table.add_column("Created At", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Confidence", style="white")
    table.add_column("Probable Cause", style="white")

    for r in records:
        status_style = "green" if r.status == "diagnosed" else "yellow"
        table.add_row(
            r.incident_id,
            r.network_id,
            r.created_at[:19],
            f"[{status_style}]{r.status}[/{status_style}]",
            f"{int(r.confidence * 100)}%",
            r.probable_cause or "[dim]N/A[/dim]",
        )
    console.print(table)


@incidents_app.command("show")
def show_incident_cmd(
    incident_id: str = typer.Argument(..., help="Unique incident identifier")
) -> None:
    """Display full diagnostic report for a specific incident."""
    init_db()
    rec = get_incident(incident_id)
    if not rec or not rec.report_json:
        console.print(f"[red]Error:[/red] Incident '{incident_id}' not found.")
        return

    console.print(Panel(rec.report_json, box=box.SQUARE, title=f"Report: {incident_id}"))


@envelopes_app.command("trace")
def trace_envelopes_cmd(
    correlation_id: str = typer.Argument(..., help="Correlation ID of the incident")
) -> None:
    """Print the complete auditable message envelope exchange trace."""
    init_db()
    logs = get_envelope_logs(correlation_id)
    if not logs:
        console.print(f"[dim]No message envelopes found for correlation ID '{correlation_id}'.[/dim]")
        return

    table = Table(title=f"Auditable Envelope Trace: {correlation_id}", box=box.SQUARE)
    table.add_column("Time UTC", style="dim")
    table.add_column("Sender", style="cyan")
    table.add_column("Recipient", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Payload Summary", style="white")

    for l in logs:
        payload = json.loads(l.payload_json)
        obs_count = len(payload.get("observations", []))
        hyp_count = len(payload.get("hypotheses", []))
        inq_count = len(payload.get("inquiries", []))
        summary = f"obs={obs_count}, hyp={hyp_count}, inq={inq_count}"
        table.add_row(
            l.timestamp_utc[11:19],
            l.sender,
            l.recipient,
            l.message_type,
            summary,
        )
    console.print(table)


@remediate_app.command("approve")
def approve_remediation_cmd(
    incident_id: str = typer.Argument(..., help="Incident identifier"),
    action_id: Optional[str] = typer.Argument(None, help="Specific action ID to execute"),
    operator: str = typer.Option("operator_cli", "--operator", help="Operator username"),
) -> None:
    """Simulate execution of an approved remediation action with safety gates."""
    init_db()
    rec = get_incident(incident_id)
    if not rec or not rec.report_json:
        console.print(f"[red]Error:[/red] Incident '{incident_id}' not found.")
        return

    report_data = json.loads(rec.report_json)
    actions = report_data.get("remediation_actions", [])
    if not actions:
        console.print("[dim]No remediation actions available for this incident.[/dim]")
        return

    from netcoop.core.report import RemediationActionItem

    target_dict = actions[0] if not action_id else next((a for a in actions if a.get("action_id") == action_id), None)
    if not target_dict:
        console.print(f"[red]Error:[/red] Action ID '{action_id}' not found in report.")
        return

    action_item = RemediationActionItem(**target_dict)
    res = RemediationEngine.execute_simulated_action(
        incident_id=incident_id,
        action=action_item,
        operator=operator,
    )

    if res["success"]:
        console.print(
            Panel(
                f"[bold green]Simulated Execution Success[/bold green]\n\n"
                f"Action ID: {action_item.action_id}\n"
                f"Device: {action_item.device}\n"
                f"Commands Simulated:\n" + "\n".join(f"  {c}" for c in action_item.commands),
                box=box.SQUARE,
                title="[bold]Remediation Sandbox Output[/bold]",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]Pre-Flight Checks Failed[/bold red]\n{res['message']}",
                box=box.SQUARE,
                title="[bold]Safety Gate Violation[/bold]",
            )
        )


@app.command("mcp-serve")
def mcp_serve_cmd() -> None:
    """Launch Model Context Protocol (MCP) stdio server."""
    from netcoop.mcp.server import NetCoopMCPServer

    NetCoopMCPServer.run_stdio_server()


if __name__ == "__main__":
    app()
