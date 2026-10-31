"""FastAPI backend server for NetCoop AI multi-agent diagnostic platform."""

import asyncio
import httpx
import json
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
from orchestrator.graph import pause_diagnosis, resume_diagnosis, run_diagnosis
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
    list_checkpoints,
    list_remediation_action_logs,
    get_remediation_action_log,
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


@app.post("/api/ingest")
def ingest_data_endpoint(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Gateway Ingestion: translate, unit-convert, and canonicalize arbitrary telemetry via Gateway HTTP microservice."""
    gateway_url = settings.get_gateway_url()
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(gateway_url, json=raw_payload)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 422:
                detail = resp.json().get("detail", "Gateway normalization failure")
                raise HTTPException(status_code=422, detail=detail)
            elif resp.status_code == 400:
                detail = resp.json().get("detail", "Malformed payload")
                raise HTTPException(status_code=400, detail=detail)
            else:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Gateway service returned HTTP {resp.status_code}: {resp.text}",
                )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Gateway service on port {settings.gateway_port} unavailable over HTTP: {str(exc)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion communication error: {str(e)}")


@app.get("/api/scenarios")
def list_scenarios() -> List[Dict[str, Any]]:
    """List all pre-configured benchmark scenario files."""
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
    return scenarios


@app.get("/api/scenarios/{filename}")
def get_scenario(filename: str) -> Dict[str, Any]:
    """Retrieve full scenario JSON content."""
    file_path = SCENARIOS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Scenario file not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/diagnose", response_model=UnifiedDiagnosticReport)
def run_diagnosis_endpoint(incident_data: Dict[str, Any]) -> UnifiedDiagnosticReport:
    """Execute multi-agent diagnosis on network incident input canonicalized via Gateway."""
    try:
        format_detected = OrganizerAdapter.detect_format(incident_data)
        if format_detected == "organizer":
            gateway_url = settings.get_gateway_url()
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(gateway_url, json=incident_data)
                    if resp.status_code == 200:
                        canonical_data = resp.json()
                    elif resp.status_code == 422:
                        detail = resp.json().get("detail", "Gateway normalization failure")
                        raise HTTPException(status_code=422, detail=detail)
                    else:
                        raise HTTPException(
                            status_code=resp.status_code,
                            detail=f"Gateway normalization failed: {resp.text}",
                        )
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Gateway service on port {settings.gateway_port} unavailable over HTTP: {str(exc)}",
                )
            report = run_diagnosis(canonical_data)
        else:
            report = run_diagnosis(incident_data)
        return report
    except HTTPException:
        raise
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


# -----------------------------------------------------------------------------
# Pause and Resume Orchestrator Endpoints (FEATURE_RESUME)
# -----------------------------------------------------------------------------

class PauseRequest(BaseModel):
    session_id: str
    rationale: Optional[str] = "Operator requested pause"


@app.post("/api/orchestrator/pause")
def pause_orchestrator_endpoint(req: PauseRequest) -> Dict[str, Any]:
    """Signal an active diagnostic session to halt cleanly at its next checkpoint."""
    success = pause_diagnosis(req.session_id)
    return {
        "session_id": req.session_id,
        "status": "paused" if success else "failed",
        "message": f"Diagnostic session {req.session_id} marked as paused.",
        "rationale": req.rationale,
    }


@app.post("/api/orchestrator/resume/{session_id}", response_model=UnifiedDiagnosticReport)
def resume_orchestrator_endpoint(session_id: str) -> UnifiedDiagnosticReport:
    """Resume execution of an interrupted or paused diagnosis from latest checkpoint."""
    try:
        report = resume_diagnosis(session_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume failed: {str(e)}")


@app.get("/api/orchestrator/checkpoints/{session_id}")
def get_session_checkpoints_endpoint(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve chronological checkpoints recorded for a diagnostic session."""
    cps = list_checkpoints(session_id)
    return [
        {
            "id": cp.id,
            "session_id": cp.session_id,
            "node_name": cp.node_name,
            "iteration": cp.iteration,
            "is_paused": cp.is_paused,
            "created_at": cp.created_at,
            "state": json.loads(cp.state_json) if cp.state_json else {},
        }
        for cp in cps
    ]


# -----------------------------------------------------------------------------
# Human-in-the-Loop Remediation Endpoints (FEATURE_HITL)
# -----------------------------------------------------------------------------

class RemediationRequest(BaseModel):
    action_id: str
    operator: str = "human_operator"


class HITLDecisionRequest(BaseModel):
    operator: str = "human_operator"
    rationale: Optional[str] = None


class HITLModifyRequest(BaseModel):
    commands: List[str]
    operator: str = "human_operator"
    rationale: Optional[str] = None


@app.get("/api/remediation/pending")
def get_pending_remediation_actions_endpoint() -> List[Dict[str, Any]]:
    """List all remediation actions awaiting operator approval under Human-in-the-Loop."""
    logs = list_remediation_action_logs(status="pending")
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
            "rationale": l.rationale,
            "modified_commands": json.loads(l.modified_commands_json) if l.modified_commands_json else None,
            "simulated_at": l.simulated_at,
            "decision_timestamp": l.decision_timestamp,
        }
        for l in logs
    ]


@app.get("/api/remediation/actions")
def list_remediation_actions_endpoint(
    incident_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List recorded remediation action items filtered by incident or status."""
    logs = list_remediation_action_logs(incident_id=incident_id, status=status)
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
            "rationale": l.rationale,
            "modified_commands": json.loads(l.modified_commands_json) if l.modified_commands_json else None,
            "simulated_at": l.simulated_at,
            "decision_timestamp": l.decision_timestamp,
        }
        for l in logs
    ]


@app.post("/api/remediation/{action_id}/approve")
def approve_remediation_action_endpoint(
    action_id: str,
    req: HITLDecisionRequest = HITLDecisionRequest(),
) -> Dict[str, Any]:
    """Approve a pending remediation action and execute simulated remediation."""
    res = RemediationEngine.approve_action(
        action_id=action_id,
        operator=req.operator,
        rationale=req.rationale,
    )
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Action not found."))
    return res


@app.post("/api/remediation/{action_id}/reject")
def reject_remediation_action_endpoint(
    action_id: str,
    req: HITLDecisionRequest = HITLDecisionRequest(),
) -> Dict[str, Any]:
    """Reject a pending remediation action and record the decision audit log."""
    res = RemediationEngine.reject_action(
        action_id=action_id,
        operator=req.operator,
        rationale=req.rationale,
    )
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Action not found."))
    return res


@app.post("/api/remediation/{action_id}/modify")
def modify_remediation_action_endpoint(
    action_id: str,
    req: HITLModifyRequest,
) -> Dict[str, Any]:
    """Modify parameters/commands of a pending action and record the decision audit log."""
    res = RemediationEngine.modify_action(
        action_id=action_id,
        new_commands=req.commands,
        operator=req.operator,
        rationale=req.rationale,
    )
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Action not found."))
    return res


class SimulationRequest(BaseModel):
    scenario_or_incident_id: Optional[str] = None
    incident_data: Optional[Dict[str, Any]] = None
    action_type: str = "rebalance traffic"
    device: Optional[str] = None
    interface: Optional[str] = "et-0/0/1"
    peer_device: Optional[str] = None
    operator: str = "operator"


@app.post("/api/remediate/simulate")
def simulate_remediation_endpoint(req: SimulationRequest) -> Dict[str, Any]:
    """Execute in-memory remediation simulation with before/after metrics delta."""
    if not getattr(settings, "feature_remediation_sim", True):
        raise HTTPException(status_code=403, detail="FEATURE_REMEDIATION_SIM is disabled.")

    target_data = req.incident_data
    if not target_data and req.scenario_or_incident_id:
        target_name = req.scenario_or_incident_id
        scenario_file = SCENARIOS_DIR / target_name
        if not scenario_file.exists() and not target_name.endswith(".json"):
            scenario_file = SCENARIOS_DIR / f"{target_name}.json"

        if scenario_file.exists():
            with open(scenario_file, "r", encoding="utf-8") as f:
                target_data = json.load(f)
        else:
            rec = get_incident(target_name)
            if rec and rec.report_json:
                target_data = json.loads(rec.report_json)

    if not target_data:
        default_file = SCENARIOS_DIR / "link_congestion.json"
        if default_file.exists():
            with open(default_file, "r", encoding="utf-8") as f:
                target_data = json.load(f)
        else:
            raise HTTPException(status_code=400, detail="No incident or scenario data available for simulation.")

    try:
        res = RemediationEngine.simulate_proposed_action(
            scenario_data=target_data,
            action_name=req.action_type,
            device=req.device,
            interface=req.interface,
            peer_device=req.peer_device,
            operator=req.operator,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")



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


@app.get("/api/schemas/{schema_name}")
def get_schema_endpoint(schema_name: str) -> Dict[str, Any]:
    """Retrieve formal protocol JSON schema by name."""
    schema_path = SCHEMAS_DIR / f"{schema_name}.json"
    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="Schema not found.")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Serve dashboard static assets if built
DASHBOARD_DIST = Path(__file__).parent.parent / "dashboard" / "dist"
if DASHBOARD_DIST.exists():
    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIST), html=True), name="dashboard")
elif (Path(__file__).parent.parent / "frontend" / "dist").exists():
    app.mount("/", StaticFiles(directory=str(Path(__file__).parent.parent / "frontend" / "dist"), html=True), name="frontend")
