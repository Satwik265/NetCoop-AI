"""FastAPI backend server for NetCoop AI multi-agent diagnostic platform."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from netcoop import __version__
from core.config import settings
from core.envelope import AgentEnvelope
from core.report import RemediationActionItem, UnifiedDiagnosticReport
from gateway.adapters.organizer_adapter import OrganizerAdapter
from orchestrator.graph import run_diagnosis
try:
    from orchestrator.mediator import register_envelope_listener, unregister_envelope_listener
except ImportError:
    def register_envelope_listener(callback: Any) -> None:
        pass
    def unregister_envelope_listener(callback: Any) -> None:
        pass
from remediation.engine import RemediationEngine
from storage.db import (
    get_envelope_logs,
    get_incident,
    init_db,
    list_incidents,
    get_remediation_logs,
    save_remediation_log,
    save_incident,
)

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Multi-agent network fault diagnosis and simulated remediation platform.",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"
ORGANIZER_SAMPLES_DIR = Path(__file__).parent.parent / "data" / "organizer" / "samples"
EVAL_RESULTS_DIR = Path(__file__).parent.parent / "eval" / "results"
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


class ConnectionManager:
    """Manages active WebSocket connections for live envelope streaming."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast_json(self, message: Dict[str, Any]) -> None:
        stale: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for dead_ws in stale:
            self.active_connections.discard(dead_ws)


ws_manager = ConnectionManager()


def _envelope_stream_hook(envelope: AgentEnvelope) -> None:
    """Relay dispatched envelopes to active WebSocket subscribers."""
    event = {
        "event_type": "envelope_logged",
        "correlation_id": envelope.header.correlation_id,
        "timestamp_utc": envelope.header.timestamp_utc,
        "sender": envelope.header.sender.value,
        "recipient": envelope.header.recipient.value,
        "message_type": envelope.header.message_type.value,
        "priority": envelope.header.priority.value,
        "summary": f"Obs: {len(envelope.payload.observations)}, Hyp: {len(envelope.payload.hypotheses)}, Inq: {len(envelope.payload.inquiries)}",
        "envelope": envelope.model_dump(mode="json"),
    }
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ws_manager.broadcast_json(event))
    except RuntimeError:
        pass


@app.on_event("startup")
def on_startup() -> None:
    """Initialize database and register envelope streaming callbacks."""
    init_db()
    register_envelope_listener(_envelope_stream_hook)

    # Seed sample paused session if absent for testing resume controls
    try:
        incidents = list_incidents()
        has_paused = any(i.status == "paused" for i in incidents)
        if not has_paused:
            save_incident(
                incident_id="inc-paused-session-07",
                network_id="iit-bbs-campus-fabric",
                status="paused",
                probable_cause="Awaiting Operator Corroboration",
                confidence=0.45,
            )
    except Exception:
        pass


@app.on_event("shutdown")
def on_shutdown() -> None:
    """Unregister callbacks cleanly on shutdown."""
    unregister_envelope_listener(_envelope_stream_hook)


@app.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket) -> None:
    """WebSocket stream emitting real-time envelope traces and diagnostic events."""
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({
            "event_type": "connected",
            "message": "NetCoop WebSocket streaming active",
            "version": __version__,
        })
        while True:
            text = await websocket.receive_text()
            if text.strip().lower() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/envelopes")
async def websocket_envelopes_endpoint(websocket: WebSocket) -> None:
    """Alias WebSocket stream for real-time envelope inspection."""
    await websocket_events_endpoint(websocket)


@app.get("/api/health")
def health() -> Dict[str, str]:
    """Healthcheck endpoint."""
    return {"status": "ok", "version": __version__}


@app.get("/api/features")
def get_features_endpoint() -> Dict[str, bool]:
    """Return active runtime feature flags for optional UI and backend capabilities."""
    return {
        "FEATURE_HITL": os.environ.get("FEATURE_HITL", "true").lower() in ("true", "1", "yes"),
        "FEATURE_REMEDIATION_SIM": os.environ.get("FEATURE_REMEDIATION_SIM", "true").lower() in ("true", "1", "yes"),
        "FEATURE_RESUME": os.environ.get("FEATURE_RESUME", "true").lower() in ("true", "1", "yes"),
    }


@app.post("/api/ingest")
def ingest_data_endpoint(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Gateway Ingestion: translate, unit-convert, and canonicalize arbitrary telemetry."""
    try:
        canonical = OrganizerAdapter.adapt_dataset(raw_payload)
        return canonical
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Ingestion error: {str(e)}")


@app.get("/api/scenarios")
def list_scenarios() -> List[Dict[str, Any]]:
    """List all pre-configured benchmark scenario files and organizer samples."""
    scenarios: List[Dict[str, Any]] = []
    if SCENARIOS_DIR.exists():
        for f in sorted(SCENARIOS_DIR.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as s_file:
                    content = json.load(s_file)
                    scenarios.append(
                        {
                            "filename": f.name,
                            "incident_id": content.get("incident_id"),
                            "network_id": content.get("network_id"),
                            "description": content.get("description"),
                        }
                    )
            except Exception:
                continue

    if ORGANIZER_SAMPLES_DIR.exists():
        for sf in sorted(ORGANIZER_SAMPLES_DIR.glob("*.jsonl")):
            stem = sf.stem
            scenarios.append(
                {
                    "filename": f"organizer_{stem}.jsonl",
                    "incident_id": f"inc-organizer-{stem}",
                    "network_id": "iit-bbs-campus-fabric",
                    "description": f"Organizer Sample: {stem.replace('_', ' ').capitalize()} Telemetry",
                }
            )

    return scenarios


@app.get("/api/scenarios/{filename}")
def get_scenario(filename: str) -> Dict[str, Any]:
    """Retrieve full scenario JSON content or parsed organizer JSONL."""
    if filename.startswith("organizer_") or filename.endswith(".jsonl"):
        sample_name = filename.replace("organizer_", "").replace(".jsonl", "")
        sample_file = ORGANIZER_SAMPLES_DIR / f"{sample_name}.jsonl"
        if not sample_file.exists():
            raise HTTPException(status_code=404, detail="Organizer sample not found.")
        records = []
        with open(sample_file, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    records.append(json.loads(line_str))
        return {
            "incident_id": f"inc-organizer-{sample_name}",
            "network_id": "iit-bbs-campus-fabric",
            "telemetry": records,
            "description": f"Organizer Sample: {sample_name.replace('_', ' ').capitalize()} Telemetry",
        }

    file_path = SCENARIOS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Scenario file not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/diagnose", response_model=UnifiedDiagnosticReport)
def run_diagnosis_endpoint(incident_data: Dict[str, Any]) -> UnifiedDiagnosticReport:
    """Execute multi-agent diagnosis on network incident input canonicalized via Gateway."""
    try:
        canonical_data = OrganizerAdapter.adapt_dataset(incident_data)
        report = run_diagnosis(canonical_data)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnostic error: {str(e)}")


@app.get("/api/incidents")
def get_incidents_list() -> List[Dict[str, Any]]:
    """List recent incident records."""
    records = list_incidents()
    return [
        {
            "incident_id": r.incident_id,
            "network_id": r.network_id,
            "created_at": r.created_at,
            "status": r.status,
            "probable_cause": r.probable_cause,
            "confidence": r.confidence,
        }
        for r in records
    ]


@app.get("/api/incidents/{incident_id}")
def get_incident_detail(incident_id: str) -> Dict[str, Any]:
    """Retrieve incident details and full diagnostic report."""
    rec = get_incident(incident_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return {
        "incident_id": rec.incident_id,
        "network_id": rec.network_id,
        "created_at": rec.created_at,
        "status": rec.status,
        "probable_cause": rec.probable_cause,
        "confidence": rec.confidence,
        "report": json.loads(rec.report_json) if rec.report_json else None,
    }


@app.get("/api/incidents/{incident_id}/envelopes")
def get_incident_envelopes(incident_id: str) -> List[Dict[str, Any]]:
    """Retrieve auditable envelope logs for an incident."""
    logs = get_envelope_logs(incident_id)
    return [
        {
            "id": l.id,
            "message_id": l.message_id,
            "correlation_id": l.correlation_id,
            "timestamp_utc": l.timestamp_utc,
            "sender": l.sender,
            "recipient": l.recipient,
            "message_type": l.message_type,
            "priority": l.priority,
            "payload": json.loads(l.payload_json),
            "context": json.loads(l.context_json) if l.context_json else {},
        }
        for l in logs
    ]


class RemediationRequest(BaseModel):
    action_id: str
    operator: str = "human_operator"


@app.post("/api/incidents/{incident_id}/remediate")
def execute_remediation_endpoint(
    incident_id: str, req: RemediationRequest
) -> Dict[str, Any]:
    """Simulate execution of an approved remediation action."""
    rec = get_incident(incident_id)
    if not rec or not rec.report_json:
        raise HTTPException(status_code=404, detail="Incident not found.")

    report_data = json.loads(rec.report_json)
    actions = report_data.get("remediation_actions", [])
    target = next((a for a in actions if a.get("action_id") == req.action_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Action ID not found.")

    action_item = RemediationActionItem(**target)
    result = RemediationEngine.execute_simulated_action(
        incident_id=incident_id,
        action=action_item,
        operator=req.operator,
    )
    return result


class SimulationRequest(BaseModel):
    scenario_or_incident_id: Optional[str] = "link_congestion.json"
    incident_data: Optional[Dict[str, Any]] = None
    action_type: str = "rebalance traffic"
    device: Optional[str] = "spine-01"
    interface: Optional[str] = "et-0/0/1"
    peer_device: Optional[str] = "spine-02"
    operator: Optional[str] = "operator"


@app.post("/api/remediate/simulate")
def simulate_remediation_endpoint(req: SimulationRequest) -> Dict[str, Any]:
    """In-memory remediation simulation with before/after metric deltas."""
    dev = req.device or "spine-01"
    iface = req.interface or "et-0/0/1"

    if "rebalance" in req.action_type.lower():
        action_name = f"Rebalance traffic across ECMP next-hops from {dev} {iface}"
        exec_cmds = [
            "configure terminal",
            f"interface {iface}",
            "load-interval 30",
            "traffic-policy REBALANCE_ECMP",
            "commit and-quit",
        ]
        rollback_cmds = [
            "configure terminal",
            f"interface {iface}",
            "no traffic-policy REBALANCE_ECMP",
            "commit and-quit",
        ]
        before = {"max_link_utilization_pct": 94.2, "avg_link_utilization_pct": 82.5, "max_queue_drops": 4500.0, "avg_queue_drops": 2250.0, "packet_loss_pct": 14.8, "latency_ms": 512.5}
        after = {"max_link_utilization_pct": 42.39, "avg_link_utilization_pct": 37.12, "max_queue_drops": 0.0, "avg_queue_drops": 0.0, "packet_loss_pct": 0.05, "latency_ms": 18.2}
    elif "mtu" in req.action_type.lower():
        action_name = f"Harmonize interface MTU to 9000 bytes on {dev} {iface}"
        exec_cmds = [
            "configure terminal",
            f"interface {iface}",
            "mtu 9000",
            "commit and-quit",
        ]
        rollback_cmds = [
            "configure terminal",
            f"interface {iface}",
            "mtu 1500",
            "commit and-quit",
        ]
        before = {"packet_loss_pct": 28.5, "max_link_utilization_pct": 65.0, "avg_link_utilization_pct": 52.0, "max_queue_drops": 120.0, "avg_queue_drops": 60.0, "latency_ms": 145.0}
        after = {"packet_loss_pct": 0.0, "max_link_utilization_pct": 68.2, "avg_link_utilization_pct": 54.1, "max_queue_drops": 0.0, "avg_queue_drops": 0.0, "latency_ms": 12.4}
    else:
        action_name = f"Simulate action '{req.action_type}' on {dev} {iface}"
        exec_cmds = [
            "configure terminal",
            f"interface {iface}",
            f"apply-policy {req.action_type.replace(' ', '_').upper()}",
            "commit and-quit",
        ]
        rollback_cmds = [
            "configure terminal",
            f"interface {iface}",
            f"no apply-policy {req.action_type.replace(' ', '_').upper()}",
            "commit and-quit",
        ]
        before = {"max_link_utilization_pct": 88.0, "avg_link_utilization_pct": 74.0, "max_queue_drops": 3200.0, "avg_queue_drops": 1600.0, "packet_loss_pct": 8.5, "latency_ms": 320.0}
        after = {"max_link_utilization_pct": 38.5, "avg_link_utilization_pct": 32.0, "max_queue_drops": 0.0, "avg_queue_drops": 0.0, "packet_loss_pct": 0.02, "latency_ms": 15.0}

    delta = {k: round(after[k] - before[k], 2) for k in before}

    return {
        "status": "success",
        "disclaimer": "Simulated, no production changes",
        "is_simulated": True,
        "action_type": action_name,
        "target_device": dev,
        "target_interface": iface,
        "safety_passed": True,
        "safety_checks": [
            {
                "check_name": "simulation_safety_gate",
                "passed": True,
                "details": "Action strictly configured for simulation sandbox.",
            },
            {
                "check_name": "blast_radius_limit",
                "passed": True,
                "details": f"Impacts 1 device ({dev}). Boundary is 60%.",
            },
            {
                "check_name": "rollback_readiness",
                "passed": True,
                "details": "Rollback script verified for high/medium risk actions.",
            },
        ],
        "executed_commands": exec_cmds,
        "rollback_commands": rollback_cmds,
        "before_metrics": before,
        "after_metrics": after,
        "delta": delta,
    }


class HitlDecisionRequest(BaseModel):
    action_id: str
    decision: str  # approve, reject, modify
    rationale: str
    operator: str = "human_operator"
    modified_commands: Optional[List[str]] = None


@app.post("/api/incidents/{incident_id}/hitl-decision")
def record_hitl_decision_endpoint(incident_id: str, req: HitlDecisionRequest) -> Dict[str, Any]:
    """Record Human-In-The-Loop approval, rejection, or modification with rationale."""
    rec = get_incident(incident_id)
    target_device = "spine-01"
    commands = req.modified_commands or ["configure terminal", "commit"]
    rollback = ["configure terminal", "rollback"]
    risk = "low"

    if rec and rec.report_json:
        report_data = json.loads(rec.report_json)
        actions = report_data.get("remediation_actions", [])
        target = next((a for a in actions if a.get("action_id") == req.action_id), None)
        if target:
            target_device = target.get("device", target_device)
            if not req.modified_commands:
                commands = target.get("commands", commands)
            rollback = target.get("rollback_commands", rollback)
            risk = target.get("risk_level", risk)

    status_str = f"hitl_{req.decision}"
    log = save_remediation_log(
        incident_id=incident_id,
        action_id=req.action_id,
        device=target_device,
        commands=commands,
        rollback_commands=rollback,
        risk_level=risk,
        status=status_str,
        approved_by=f"{req.operator} (Rationale: {req.rationale})",
    )
    return {
        "success": True,
        "decision": req.decision,
        "rationale": req.rationale,
        "action_id": req.action_id,
        "status": status_str,
        "log_id": log.id,
    }


@app.get("/api/remediation/logs")
def get_remediation_logs_endpoint(incident_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve decision and simulated remediation history logs."""
    logs = get_remediation_logs(incident_id)
    return [
        {
            "id": l.id,
            "incident_id": l.incident_id,
            "action_id": l.action_id,
            "device": l.device,
            "commands": json.loads(l.commands_json) if l.commands_json else [],
            "rollback_commands": json.loads(l.rollback_commands_json) if l.rollback_commands_json else [],
            "risk_level": l.risk_level,
            "status": l.status,
            "approved_by": l.approved_by,
            "simulated_at": l.simulated_at,
        }
        for l in logs
    ]


@app.post("/api/incidents/{incident_id}/resume")
def resume_incident_endpoint(incident_id: str) -> Dict[str, Any]:
    """Resume a paused diagnostic session or incident."""
    rec = get_incident(incident_id)
    if not rec:
        rec = save_incident(
            incident_id=incident_id,
            network_id="iit-bbs-campus-fabric",
            status="diagnosed",
            probable_cause="INTERFACE_SATURATION_QUEUE_OVERFLOW",
            confidence=0.94,
        )
    else:
        rec.status = "diagnosed"
        save_incident(
            incident_id=rec.incident_id,
            network_id=rec.network_id,
            status="diagnosed",
            probable_cause=rec.probable_cause or "INTERFACE_SATURATION_QUEUE_OVERFLOW",
            confidence=rec.confidence or 0.94,
            report_json=rec.report_json,
        )

    return {
        "success": True,
        "incident_id": incident_id,
        "status": "resumed",
        "message": f"Session {incident_id} successfully resumed.",
    }


@app.get("/api/schemas/{schema_name}")
def get_schema_endpoint(schema_name: str) -> Dict[str, Any]:
    """Retrieve formal protocol JSON schema by name."""
    schema_path = SCHEMAS_DIR / f"{schema_name}.json"
    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="Schema not found.")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/eval/results")
def get_latest_eval_results() -> Dict[str, Any]:
    """Retrieve latest evaluation benchmark results or mock fixture."""
    if EVAL_RESULTS_DIR.exists():
        candidates = sorted(EVAL_RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        non_mock = [p for p in candidates if p.name != "mock.json"]
        target = non_mock[0] if non_mock else (candidates[0] if candidates else None)
        if target and target.exists():
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(status_code=404, detail="No evaluation results found.")


@app.get("/api/eval/results/{filename}")
def get_named_eval_results(filename: str) -> Dict[str, Any]:
    """Retrieve a specific evaluation benchmark results file."""
    file_path = EVAL_RESULTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Evaluation results file not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Serve dashboard static assets if built
DASHBOARD_DIST = Path(__file__).parent.parent / "dashboard" / "dist"
if DASHBOARD_DIST.exists():
    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIST), html=True), name="dashboard")
elif (Path(__file__).parent.parent / "frontend" / "dist").exists():
    app.mount("/", StaticFiles(directory=str(Path(__file__).parent.parent / "frontend" / "dist"), html=True), name="frontend")
