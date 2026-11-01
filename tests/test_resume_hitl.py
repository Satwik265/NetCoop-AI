"""Comprehensive tests for Checkpoint Pause/Resume (FEATURE_RESUME) and Human-in-the-Loop (FEATURE_HITL)."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from netcoop.config import settings
from netcoop.orchestrator.graph import (
    node_specialists,
    pause_diagnosis,
    resume_diagnosis,
    run_diagnosis,
)
from netcoop.remediation.engine import RemediationEngine
from netcoop.storage.db import (
    get_envelope_logs,
    get_incident,
    get_latest_checkpoint,
    get_remediation_action_log,
    init_db,
    list_checkpoints,
    list_remediation_action_logs,
    save_checkpoint,
)
from api.main import app
from core.auth import get_auth_headers, ROLE_NETWORK_ENGINEER

SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


def load_scenario(filename: str) -> dict:
    """Load benchmark scenario JSON."""
    path = SCENARIOS_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def ensure_db():
    """Ensure database schema is initialized for tests."""
    init_db()


def test_checkpointing_saves_state_at_each_node():
    """Verify orchestrator saves intermediate state checkpoints to SQLite."""
    settings.feature_resume = True
    settings.feature_hitl = True

    data = load_scenario("01_mtu_mismatch_blackhole.json")
    incident_id = data["incident_id"]

    report = run_diagnosis(data)
    assert report.status == "diagnosed"

    checkpoints = list_checkpoints(incident_id)
    assert len(checkpoints) >= 4

    node_names = [cp.node_name for cp in checkpoints]
    assert "specialists" in node_names
    assert "mediation" in node_names
    assert "synthesis" in node_names
    assert "report" in node_names

    latest = get_latest_checkpoint(incident_id)
    assert latest is not None
    assert latest.node_name == "report"


def test_pause_diagnosis_marks_session():
    """Verify pause_diagnosis flags latest checkpoint and incident record as paused."""
    settings.feature_resume = True
    data = load_scenario("01_mtu_mismatch_blackhole.json")
    incident_id = data["incident_id"]

    run_diagnosis(data)

    success = pause_diagnosis(incident_id)
    assert success is True

    latest = get_latest_checkpoint(incident_id)
    assert latest is not None
    assert latest.is_paused is True

    inc = get_incident(incident_id)
    assert inc is not None
    assert inc.status == "paused"


def test_resume_diagnosis_from_checkpoint():
    """Verify resuming an existing diagnosis from checkpoint yields a valid report."""
    settings.feature_resume = True
    data = load_scenario("01_mtu_mismatch_blackhole.json")
    incident_id = data["incident_id"]

    run_diagnosis(data)
    pause_diagnosis(incident_id)

    resumed_report = resume_diagnosis(incident_id)
    assert resumed_report is not None
    assert resumed_report.incident_id == incident_id
    assert resumed_report.status == "diagnosed"
    assert resumed_report.confidence >= 0.85
    assert len(resumed_report.remediation_actions) > 0


def test_resume_after_killed_orchestrator():
    """Simulate an orchestrator kill after specialists node and resume cleanly to completion."""
    settings.feature_resume = True
    settings.feature_hitl = True

    sim_id = "inc-killed-proc-test-01"
    raw_data = load_scenario("01_mtu_mismatch_blackhole.json")
    raw_data["incident_id"] = sim_id

    # Simulate execution of initial state and first node only (as if process crashed right after)
    init_state = {
        "incident_id": sim_id,
        "network_id": "net-killed-test",
        "raw_data": raw_data,
        "scope_devices": ["spine-01", "spine-02"],
        "accumulated_observations": [],
        "accumulated_hypotheses": [],
        "inquiries_queue": [],
        "conflict_detected": False,
        "conflict_summary": None,
        "conflicts_resolved": [],
        "limitations": [],
        "iteration": 0,
        "is_paused": False,
        "status": "running",
        "hypothesis_dict": None,
        "uncertainty_dict": None,
        "remediation_actions": [],
        "report_dict": None,
        "start_time_s": 0.0,
        "classifier_conformal_set": [],
        "classifier_calib_probs": {},
        "classifier_conformal_status": "single",
    }
    specialists_res = node_specialists(init_state)
    interrupted_state = {**init_state, **specialists_res}

    # Save checkpoint representing state when process was killed
    save_checkpoint(
        session_id=sim_id,
        node_name="specialists",
        state_dict=interrupted_state,
        iteration=0,
        is_paused=False,
    )

    # In a new context (orchestrator restarted), resume diagnosis from the checkpoint
    report = resume_diagnosis(sim_id)

    assert report is not None
    assert report.incident_id == sim_id
    assert report.status == "diagnosed"
    assert report.probable_cause is not None
    assert len(report.remediation_actions) > 0


def test_hitl_pending_and_approve_workflow():
    """Verify HITL gating: actions enter pending state, then approve executes simulation."""
    settings.feature_hitl = True
    settings.feature_resume = True

    data = load_scenario("01_mtu_mismatch_blackhole.json")
    data["incident_id"] = "inc-hitl-approve-test"

    report = run_diagnosis(data)
    assert len(report.remediation_actions) > 0
    first_action = report.remediation_actions[0]
    action_id = first_action.action_id

    # Verify action was placed in pending state
    assert first_action.status == "pending"

    pending_list = list_remediation_action_logs(status="pending")
    matching = [a for a in pending_list if a.action_id == action_id]
    assert len(matching) == 1
    assert matching[0].status == "pending"

    # Approve action via RemediationEngine
    approval_res = RemediationEngine.approve_action(
        action_id=action_id,
        operator="operator_admin",
        rationale="Approved after manual verification of packet loss",
    )

    assert approval_res["success"] is True
    assert approval_res["status"] == "approved"
    assert approval_res["operator"] == "operator_admin"
    assert approval_res["simulation"]["success"] is True

    # Verify persistence updated
    updated_log = get_remediation_action_log(action_id)
    assert updated_log is not None
    assert updated_log.status == "approved"
    assert updated_log.approved_by == "operator_admin"
    assert updated_log.rationale == "Approved after manual verification of packet loss"

    # Verify decision logged in EnvelopeLog
    env_logs = get_envelope_logs(data["incident_id"])
    decision_logs = [l for l in env_logs if l.message_type == "REMEDIATION_DECISION"]
    assert len(decision_logs) >= 1
    assert decision_logs[0].sender == "operator_admin"


def test_hitl_reject_workflow():
    """Verify HITL reject transition and audit logging."""
    settings.feature_hitl = True
    data = load_scenario("02_bgp_route_flap_damping.json")
    data["incident_id"] = "inc-hitl-reject-test"

    report = run_diagnosis(data)
    assert len(report.remediation_actions) > 0
    action_id = report.remediation_actions[0].action_id

    reject_res = RemediationEngine.reject_action(
        action_id=action_id,
        operator="operator_secops",
        rationale="Rejected: maintenance window required",
    )
    assert reject_res["success"] is True
    assert reject_res["status"] == "rejected"
    assert reject_res["operator"] == "operator_secops"

    updated_log = get_remediation_action_log(action_id)
    assert updated_log is not None
    assert updated_log.status == "rejected"
    assert updated_log.rationale == "Rejected: maintenance window required"


def test_hitl_modify_workflow():
    """Verify modifying commands on a pending remediation action."""
    settings.feature_hitl = True
    data = load_scenario("03_optical_crc_degradation.json")
    data["incident_id"] = "inc-hitl-modify-test"

    report = run_diagnosis(data)
    assert len(report.remediation_actions) > 0
    action_id = report.remediation_actions[0].action_id

    new_cmds = ["interface HundredGigE0/0/0/0", "rate-limit 50000", "shutdown"]
    mod_res = RemediationEngine.modify_action(
        action_id=action_id,
        new_commands=new_cmds,
        operator="engineer_dave",
        rationale="Modified to add rate-limit prior to shutdown",
    )

    assert mod_res["success"] is True
    assert mod_res["status"] == "modified"
    assert mod_res["modified_commands"] == new_cmds

    updated_log = get_remediation_action_log(action_id)
    assert updated_log is not None
    assert updated_log.status == "modified"
    assert json.loads(updated_log.commands_json) == new_cmds


def test_feature_flags_disabled_executes_untouched():
    """When FEATURE_RESUME and FEATURE_HITL are False, core pipeline executes untouched."""
    settings.feature_resume = False
    settings.feature_hitl = False

    data = load_scenario("04_stp_split_brain_loop.json")
    data["incident_id"] = "inc-flags-off-test"

    report = run_diagnosis(data)
    assert report.status == "diagnosed"
    assert len(report.remediation_actions) > 0

    # With HITL off, action remains pending_approval from catalog
    assert report.remediation_actions[0].status == "pending_approval"

    # With resume off, no checkpoints saved for this incident
    cps = list_checkpoints("inc-flags-off-test")
    assert len(cps) == 0

    # Reset flags to True
    settings.feature_resume = True
    settings.feature_hitl = True


def test_fastapi_endpoints_pause_resume_and_hitl():
    """Test full suite of REST endpoints for pause/resume and HITL in FastAPI."""
    settings.feature_resume = True
    settings.feature_hitl = True
    client = TestClient(app)

    # 1. Diagnose an incident to generate state and pending actions
    data = load_scenario("01_mtu_mismatch_blackhole.json")
    test_id = "inc-api-test-01"
    data["incident_id"] = test_id
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    diag_res = client.post("/api/diagnose", json=data, headers=eng_headers)
    assert diag_res.status_code == 200
    diag_data = diag_res.json()
    assert len(diag_data["remediation_actions"]) > 0
    action_id = diag_data["remediation_actions"][0]["action_id"]

    # 2. Checkpoints list endpoint
    cp_res = client.get(f"/api/orchestrator/checkpoints/{test_id}", headers=eng_headers)
    assert cp_res.status_code == 200
    cps = cp_res.json()
    assert len(cps) >= 4

    # 3. Pause endpoint
    pause_payload = {"session_id": test_id, "rationale": "Testing API pause endpoint"}
    pause_res = client.post("/api/orchestrator/pause", json=pause_payload, headers=eng_headers)
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "paused"

    # 4. Resume endpoint
    resume_res = client.post(f"/api/orchestrator/resume/{test_id}", headers=eng_headers)
    assert resume_res.status_code == 200
    resumed_data = resume_res.json()
    assert resumed_data["incident_id"] == test_id
    assert resumed_data["status"] == "diagnosed"

    # 5. Pending remediation list endpoint
    pending_res = client.get("/api/remediation/pending")
    assert pending_res.status_code == 200
    pending_items = pending_res.json()
    assert any(item["action_id"] == action_id for item in pending_items)

    # 6. Modify endpoint
    modify_payload = {
        "commands": ["interface et-0/0/1", "mtu 9216"],
        "operator": "noc_operator",
        "rationale": "Updated to standard jumbo MTU",
    }
    mod_res = client.post(f"/api/remediation/{action_id}/modify", json=modify_payload, headers=eng_headers)
    assert mod_res.status_code == 200
    assert mod_res.json()["status"] == "modified"

    # 7. Approve endpoint
    approve_payload = {
        "operator": "noc_supervisor",
        "rationale": "Approved for simulation",
    }
    appr_res = client.post(f"/api/remediation/{action_id}/approve", json=approve_payload, headers=eng_headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"
    assert appr_res.json()["simulation"]["success"] is True

    # 8. List actions with filters
    actions_res = client.get(f"/api/remediation/actions?incident_id={test_id}")
    assert actions_res.status_code == 200
    assert len(actions_res.json()) >= 1

    # 9. Test 404 on nonexistent resume session
    err_res = client.post("/api/orchestrator/resume/inc-nonexistent-session", headers=eng_headers)
    assert err_res.status_code == 404
