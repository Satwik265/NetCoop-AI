"""FastAPI backend server for NetCoop AI multi-agent diagnostic platform."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from netcoop import __version__
from netcoop.config import settings
from netcoop.core.report import RemediationActionItem, UnifiedDiagnosticReport
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.remediation.engine import RemediationEngine
from netcoop.storage.db import (
    get_envelope_logs,
    get_incident,
    init_db,
    list_incidents,
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


@app.on_event("startup")
def on_startup() -> None:
    """Initialize SQLite database tables on application start."""
    init_db()


@app.get("/api/health")
def health() -> Dict[str, str]:
    """Healthcheck endpoint."""
    return {"status": "ok", "version": __version__}


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
    """Execute multi-agent diagnosis on network incident input."""
    try:
        report = run_diagnosis(incident_data)
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


@app.get("/api/schemas/{schema_name}")
def get_schema_endpoint(schema_name: str) -> Dict[str, Any]:
    """Retrieve formal protocol JSON schema by name."""
    schema_path = SCHEMAS_DIR / f"{schema_name}.json"
    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="Schema not found.")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Serve frontend static assets if built
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

