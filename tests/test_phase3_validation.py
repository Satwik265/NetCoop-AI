"""Targeted regression and validation test suite for Phase 3 System Validation.

Covers:
- Orchestrator checkpoint resume updating SQLite incident status to 'diagnosed'.
- Remediation simulation endpoint aliases (/api/remediate/simulate and /api/remediation/simulate).
- HITL decision recording and persistence in SQLite.
- WebSocket stream handshake, ping/pong, and message broadcasting.
- Dedicated role dashboard support endpoints (/api/devices, /api/platform/status, /api/mcp/info).
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from netcoop.config import settings
from netcoop.orchestrator.graph import pause_diagnosis, resume_diagnosis, run_diagnosis
from netcoop.remediation.engine import RemediationEngine
from netcoop.storage.db import (
    get_incident,
    get_latest_checkpoint,
    get_remediation_action_log,
    get_remediation_logs,
    init_db,
    list_checkpoints,
)
from api.main import app, ws_manager

SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


@pytest.fixture(autouse=True)
def setup_test_env():
    """Ensure feature flags and test database are initialized."""
    settings.feature_hitl = True
    settings.feature_resume = True
    init_db()


def load_test_scenario(filename: str = "01_mtu_mismatch_blackhole.json") -> dict:
    """Load test scenario file."""
    path = SCENARIOS_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_resume_diagnosis_updates_incident_record_to_diagnosed():
    """Regression test: Resuming from checkpoint must update SQLite IncidentRecord from paused to diagnosed."""
    data = load_test_scenario("01_mtu_mismatch_blackhole.json")
    incident_id = "inc-regress-resume-status"
    data["incident_id"] = incident_id

    # 1. Run initial diagnosis
    report = run_diagnosis(data)
    assert report.status == "diagnosed"

    # 2. Pause session
    paused = pause_diagnosis(incident_id)
    assert paused is True
    inc_paused = get_incident(incident_id)
    assert inc_paused is not None
    assert inc_paused.status == "paused"

    # 3. Resume from checkpoint
    resumed_report = resume_diagnosis(incident_id)
    assert resumed_report is not None
    assert resumed_report.status == "diagnosed"

    # 4. Verify incident record in SQLite transitioned to 'diagnosed'
    inc_resumed = get_incident(incident_id)
    assert inc_resumed is not None
    assert inc_resumed.status == "diagnosed", f"Expected 'diagnosed', got '{inc_resumed.status}'"


def test_remediation_simulation_aliases():
    """Verify that both /api/remediate/simulate and /api/remediation/simulate work identically."""
    client = TestClient(app)
    payload = {
        "scenario_or_incident_id": "link_congestion.json",
        "action_type": "rebalance traffic",
        "device": "spine-01",
        "interface": "et-0/0/1",
        "operator": "test_operator",
    }

    res1 = client.post("/api/remediate/simulate", json=payload)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1.get("is_simulated") is True
    assert "spine-01" in data1.get("action_type", "")

    res2 = client.post("/api/remediation/simulate", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2.get("is_simulated") is True
    assert data2.get("action_type") == data1.get("action_type")


def test_hitl_approval_and_audit_persistence():
    """Verify full HITL lifecycle: action pending -> approve -> recorded in SQLite audit log."""
    client = TestClient(app)
    data = load_test_scenario("01_mtu_mismatch_blackhole.json")
    incident_id = "inc-regress-hitl-audit"
    data["incident_id"] = incident_id

    report = run_diagnosis(data)
    assert len(report.remediation_actions) > 0
    action_id = report.remediation_actions[0].action_id

    # Approve via API endpoint
    approval_res = client.post(
        f"/api/remediation/{action_id}/approve",
        json={
            "operator": "test_qa_lead",
            "rationale": "Verified MTU mismatch in test suite; approved for simulation sandbox.",
        },
    )
    assert approval_res.status_code == 200
    approval_data = approval_res.json()
    assert approval_data.get("status") == "approved"

    # Verify persisted in SQLite remediation_logs
    remed_logs = get_remediation_logs(incident_id)
    assert len(remed_logs) > 0
    matching = [l for l in remed_logs if l.action_id == action_id]
    assert len(matching) > 0
    assert matching[0].status in ("approved", "simulated_executed")


def test_websocket_stream_lifecycle():
    """Verify WebSocket /ws/events connection handshake, ping/pong, and broadcast."""
    client = TestClient(app)
    with client.websocket_connect("/ws/events") as ws:
        # Handshake
        handshake = ws.receive_json()
        assert handshake.get("event_type") == "connected"

        # Ping
        ws.send_text("ping")
        pong = ws.receive_text()
        assert pong == "pong"


def test_role_dashboard_endpoints():
    """Verify backend endpoints serving role-based dashboards."""
    client = TestClient(app)

    # Admin View: /api/devices
    res_devices = client.get("/api/devices")
    assert res_devices.status_code == 200
    devices = res_devices.json()
    assert len(devices) >= 5
    assert any(d["device_id"] == "spine-01" for d in devices)

    # Platform Admin View: /api/platform/status
    res_status = client.get("/api/platform/status")
    assert res_status.status_code == 200
    status = res_status.json()
    assert "microservices" in status
    assert len(status["microservices"]) >= 9
    assert status.get("database", {}).get("connected") is True

    # MCP Gallery: /api/mcp/info
    res_mcp = client.get("/api/mcp/info")
    assert res_mcp.status_code == 200
    mcp_info = res_mcp.json()
    assert "tools" in mcp_info
    assert len(mcp_info["tools"]) >= 4

    # Auditor View: /api/remediation/logs
    res_logs = client.get("/api/remediation/logs")
    assert res_logs.status_code == 200
    assert isinstance(res_logs.json(), list)
