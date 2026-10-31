"""Tests for new HITL, simulation, resume, and feature flags endpoints."""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from core.auth import get_auth_headers, ROLE_PLATFORM_ADMIN, ROLE_NETWORK_ENGINEER, ROLE_NETWORK_ADMIN

client = TestClient(app)
admin_headers = get_auth_headers(role=ROLE_NETWORK_ADMIN, username="admin")
plat_headers = get_auth_headers(role=ROLE_PLATFORM_ADMIN, username="platform_admin")
eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")


def test_get_features_endpoint():
    res = client.get("/api/features")
    assert res.status_code == 200
    data = res.json()
    assert "FEATURE_HITL" in data
    assert "FEATURE_REMEDIATION_SIM" in data
    assert "FEATURE_RESUME" in data


def test_simulate_remediation_endpoint():
    payload = {
        "scenario_or_incident_id": "link_congestion.json",
        "action_type": "rebalance traffic",
        "device": "spine-01",
        "interface": "et-0/0/1",
    }
    res = client.post("/api/remediate/simulate", json=payload, headers=eng_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["disclaimer"] == "Simulated, no production changes"
    assert data["is_simulated"] is True
    assert "before_metrics" in data
    assert "after_metrics" in data
    assert "delta" in data
    assert len(data["executed_commands"]) > 0


def test_hitl_decision_and_logs():
    decision_payload = {
        "action_id": "act-mtu-spine-01",
        "decision": "approve",
        "rationale": "Verified packet loss signature is strictly Path MTU blackholing.",
        "operator": "operator_alice",
    }
    res = client.post("/api/incidents/inc-test-hitl/hitl-decision", json=decision_payload, headers=eng_headers)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    assert res_data["decision"] == "approve"

    # Verify log retrieval
    logs_res = client.get("/api/remediation/logs?incident_id=inc-test-hitl", headers=plat_headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) >= 1
    assert logs[0]["action_id"] == "act-mtu-spine-01"


def test_resume_incident_endpoint():
    res = client.post("/api/incidents/inc-paused-session-07/resume")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "resumed"


def test_mcp_info_endpoint():
    res = client.get("/api/mcp/info")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["server_name"] == "netcoop-mcp-server"
    assert data["transport"] == "stdio"
    assert len(data["tools"]) >= 5
    tool_names = [t["name"] for t in data["tools"]]
    assert "diagnose_network" in tool_names
    assert "simulate_remediation" in tool_names


def test_devices_endpoint():
    res = client.get("/api/devices", headers=admin_headers)
    assert res.status_code == 200
    devices = res.json()
    assert isinstance(devices, list)
    assert len(devices) >= 5
    dev_ids = [d["device_id"] for d in devices]
    assert "spine-01" in dev_ids
    assert "leaf-01" in dev_ids


def test_platform_status_endpoint():
    res = client.get("/api/platform/status", headers=plat_headers)
    assert res.status_code == 200
    status = res.json()
    assert status["status"] == "healthy"
    assert "database" in status
    assert status["database"]["connected"] is True
    assert len(status["microservices"]) >= 7
