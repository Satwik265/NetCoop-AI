"""Tests for new HITL, simulation, resume, and feature flags endpoints."""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


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
    res = client.post("/api/remediate/simulate", json=payload)
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
    res = client.post("/api/incidents/inc-test-hitl/hitl-decision", json=decision_payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    assert res_data["decision"] == "approve"

    # Verify log retrieval
    logs_res = client.get("/api/remediation/logs?incident_id=inc-test-hitl")
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

