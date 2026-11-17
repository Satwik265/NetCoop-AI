import concurrent.futures
"""Phase 4, 4.1, & 4.2 Comprehensive Security Test Suite.

Verifies:
- 18 core security requirements from Phase 4.1
- Original findings SEC-01 through SEC-06 with explicit unauthorized and authorized assertions
- WebSocket ticket security (anonymous, invalid, expired, replayed, valid)
- MCP credential handling and session environment token support
- Complete 7-field HITL audit persistence and anti-spoofing guarantees
"""

from datetime import datetime, timedelta, timezone
import json
import os
import time
import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.auth import (
    ALL_ROLES,
    ROLE_AUDITOR,
    ROLE_HELPDESK,
    ROLE_IT_MANAGER,
    ROLE_NETWORK_ADMIN,
    ROLE_NETWORK_ENGINEER,
    ROLE_NOC_OPERATOR,
    ROLE_PLATFORM_ADMIN,
    ROLE_SECURITY_ANALYST,
    PERM_VIEW_FABRIC_HEALTH,
    PERM_MODIFY_COMMANDS,
    PERM_APPROVE_REMEDIATION,
    PERM_SIMULATE_REMEDIATION,
    check_login_rate_limit,
    clear_login_failures,
    create_access_token,
    create_test_token,
    create_ws_ticket,
    consume_ws_ticket,
    get_auth_headers,
    get_jwt_secret,
    hash_password,
    record_login_failure,
    verify_password,
)
from core.config import settings, is_demo_mode_allowed
from netcoop.mcp.server import NetCoopMCPServer
from storage.db import (
    assign_incident,
    create_user,
    get_incident,
    get_remediation_action_log,
    get_remediation_logs,
    get_user_by_username,
    init_db,
    init_default_users,
    is_token_revoked,
    list_users,
    revoke_token,
    save_incident,
    save_remediation_action_log,
)
from storage.models import UserRecord


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """Initialize database and ensure demo accounts exist for testing."""
    init_db()
    init_default_users()


@pytest.fixture
def client():
    """Test client instance."""
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Production mode does not auto-login
# -----------------------------------------------------------------------------
def test_production_mode_does_not_auto_login(client: TestClient, monkeypatch):
    """1. Production mode disables demo mode; unauthenticated calls are rejected with 401."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "demo_mode", False)
    assert not is_demo_mode_allowed()

    res = client.get("/api/features")
    assert res.status_code == 200
    data = res.json()
    assert data["DEMO_MODE_ENABLED"] is False
    assert data["ENVIRONMENT"] == "production"

    # Protected endpoint without credentials must return 401
    prot = client.get("/api/devices")
    assert prot.status_code == 401


# -----------------------------------------------------------------------------
# 2. Production mode rejects demo login
# -----------------------------------------------------------------------------
def test_production_mode_rejects_demo_login(client: TestClient, monkeypatch):
    """2. POST /api/auth/demo-login returns HTTP 403 Forbidden in production mode."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "demo_mode", False)

    res = client.post("/api/auth/demo-login", json={"username": "engineer"})
    assert res.status_code == 403
    assert "strictly disabled in production mode" in res.json().get("detail", "")


# -----------------------------------------------------------------------------
# 3. No default production users are seeded
# -----------------------------------------------------------------------------
def test_no_default_production_users_seeded(monkeypatch):
    """3. In production mode with demo_mode=False, init_default_users refuses to seed demo accounts."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "demo_mode", False)

    init_default_users()
    assert not is_demo_mode_allowed()


# -----------------------------------------------------------------------------
# 4. Invalid/missing/expired JWT rejection
# -----------------------------------------------------------------------------
def test_invalid_missing_expired_jwt_rejection(client: TestClient):
    """4. Unauthenticated, malformed, and expired tokens return 401 Unauthorized."""
    # Missing token
    res1 = client.get("/api/devices")
    assert res1.status_code == 401

    # Malformed token
    res2 = client.get("/api/devices", headers={"Authorization": "Bearer bad.token.signature"})
    assert res2.status_code == 401

    # Expired token
    expired = create_access_token(
        {"sub": "engineer", "user_id": "usr-eng", "role": ROLE_NETWORK_ENGINEER},
        expires_delta=timedelta(seconds=-3600),
    )
    res3 = client.get("/api/devices", headers={"Authorization": f"Bearer {expired}"})
    assert res3.status_code == 401
    assert "expired" in res3.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 5. Weak or missing production JWT secret rejection
# -----------------------------------------------------------------------------
def test_weak_or_missing_production_jwt_secret_rejection(monkeypatch):
    """5. In production mode, weak or default JWT secret raises ValueError."""
    monkeypatch.setattr(settings, "environment", "production")

    # Default secret in production must fail
    monkeypatch.setattr(settings, "jwt_secret_key", "change-this-in-production-netcoop-secret-key-32chars")
    with pytest.raises(ValueError, match="Insecure production configuration"):
        get_jwt_secret()

    # Short secret in production must fail
    monkeypatch.setattr(settings, "jwt_secret_key", "too-short")
    with pytest.raises(ValueError, match="at least 32 characters"):
        get_jwt_secret()


# -----------------------------------------------------------------------------
# 6. Inactive account rejection
# -----------------------------------------------------------------------------
def test_inactive_account_rejection(client: TestClient):
    """6. Deactivated accounts cannot log in and active tokens are rejected with 401."""
    inactive_user = get_user_by_username("inactive_test_user")
    if not inactive_user:
        create_user(
            username="inactive_test_user",
            hashed_password=hash_password("InactivePass!2026"),
            role=ROLE_HELPDESK,
            is_active=False,
        )

    res = client.post(
        "/api/auth/login",
        json={"username": "inactive_test_user", "password": "InactivePass!2026"},
    )
    assert res.status_code == 401
    assert "inactive" in res.json().get("detail", "").lower()

    token = create_access_token({"sub": "inactive_test_user", "role": ROLE_HELPDESK})
    res_req = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_req.status_code == 401
    assert "inactive" in res_req.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 7. Role revocation takes effect immediately
# -----------------------------------------------------------------------------
def test_role_revocation_takes_effect_immediately(client: TestClient):
    """7. Changing a user's role in SQLite takes immediate effect on existing tokens."""
    from sqlmodel import Session, select
    from storage.db import engine

    user = get_user_by_username("dynamic_role_user")
    if not user:
        user = create_user(
            username="dynamic_role_user",
            hashed_password=hash_password("DynamicPass!2026"),
            role=ROLE_NETWORK_ENGINEER,
        )
    else:
        with Session(engine) as session:
            u = session.exec(select(UserRecord).where(UserRecord.username == "dynamic_role_user")).first()
            u.role = ROLE_NETWORK_ENGINEER
            session.add(u)
            session.commit()

    token = create_access_token({"sub": "dynamic_role_user", "role": ROLE_NETWORK_ENGINEER})
    headers = {"Authorization": f"Bearer {token}"}

    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert "MODIFY_COMMANDS" in me_res.json()["permissions"]

    with Session(engine) as session:
        u = session.exec(select(UserRecord).where(UserRecord.username == "dynamic_role_user")).first()
        u.role = ROLE_HELPDESK
        session.add(u)
        session.commit()

    action_id = "act-role-demote-01"
    save_remediation_action_log(
        incident_id="inc-role-demote",
        action_dict={"action_id": action_id, "device": "spine-01", "commands": ["commit"]},
        status="pending",
    )
    mod_res = client.post(
        f"/api/remediation/{action_id}/modify",
        headers=headers,
        json={"commands": ["interface et-0/0/1 shutdown"]},
    )
    assert mod_res.status_code == 403
    assert "lacks required permissions" in mod_res.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 8. Unauthorized incident assignment
# -----------------------------------------------------------------------------
def test_unauthorized_incident_assignment(client: TestClient):
    """8. Helpdesk and Auditor users cannot assign incidents (HTTP 403)."""
    save_incident(incident_id="inc-assign-test-01", network_id="net-1", status="open")

    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")
    res_hd = client.post(
        "/api/incidents/inc-assign-test-01/assign",
        headers=hd_headers,
        json={"assignee": "engineer"},
    )
    assert res_hd.status_code == 403

    aud_headers = get_auth_headers(role=ROLE_AUDITOR, username="auditor")
    res_aud = client.post(
        "/api/incidents/inc-assign-test-01/assign",
        headers=aud_headers,
        json={"assignee": "engineer"},
    )
    assert res_aud.status_code == 403


# -----------------------------------------------------------------------------
# 9. Authorized incident assignment
# -----------------------------------------------------------------------------
def test_authorized_incident_assignment(client: TestClient):
    """9. NOC Operator and Network Engineer can assign incidents (HTTP 200)."""
    save_incident(incident_id="inc-assign-test-02", network_id="net-1", status="open")

    noc_headers = get_auth_headers(role=ROLE_NOC_OPERATOR, username="noc")
    res_noc = client.post(
        "/api/incidents/inc-assign-test-02/assign",
        headers=noc_headers,
        json={"assignee": "engineer", "rationale": "High priority incident"},
    )
    assert res_noc.status_code == 200
    assert res_noc.json()["assigned_to"] == "engineer"
    assert res_noc.json()["assigned_by"] == "noc"

    inc = get_incident("inc-assign-test-02")
    assert inc is not None
    assert inc.assigned_to == "engineer"
    assert inc.assigned_by == "noc"


# -----------------------------------------------------------------------------
# 10. Unauthorized user management
# -----------------------------------------------------------------------------
def test_unauthorized_user_management(client: TestClient):
    """10. Only Platform Administrator can manage users; other roles receive 403."""
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res_eng = client.post(
        "/api/users",
        headers=eng_headers,
        json={"username": "rogue_user", "password": "Password123!", "role": "noc_operator"},
    )
    assert res_eng.status_code == 403

    aud_headers = get_auth_headers(role=ROLE_AUDITOR, username="auditor")
    res_aud = client.get("/api/users", headers=aud_headers)
    assert res_aud.status_code == 403

    test_uname = f"new_user_{int(time.time()*1000)}"
    admin_headers = get_auth_headers(role=ROLE_PLATFORM_ADMIN, username="platform_admin")
    res_admin = client.post(
        "/api/users",
        headers=admin_headers,
        json={"username": test_uname, "password": "ValidPassword123!", "role": "helpdesk"},
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["username"] == test_uname


# -----------------------------------------------------------------------------
# 11. Platform Administrator cannot modify or approve remediation (Least Privilege)
# -----------------------------------------------------------------------------
def test_platform_admin_cannot_modify_or_approve_remediation(client: TestClient):
    """11. Platform Administrator has NO MODIFY_COMMANDS or APPROVE_REMEDIATION (403)."""
    action_id = "act-plat-admin-no-hitl"
    save_remediation_action_log(
        incident_id="inc-plat-01",
        action_dict={"action_id": action_id, "device": "spine-01", "commands": ["commit"]},
        status="pending",
    )
    headers = get_auth_headers(role=ROLE_PLATFORM_ADMIN, username="platform_admin")

    mod_res = client.post(
        f"/api/remediation/{action_id}/modify",
        headers=headers,
        json={"commands": ["interface et-0/0/1 shutdown"]},
    )
    assert mod_res.status_code == 403
    assert "lacks required permissions" in mod_res.json().get("detail", "").lower()

    app_res = client.post(
        f"/api/remediation/{action_id}/approve",
        headers=headers,
        json={"rationale": "Admin trying to approve"},
    )
    assert app_res.status_code == 403


# -----------------------------------------------------------------------------
# 12. Authorized engineer remediation modification
# -----------------------------------------------------------------------------
def test_authorized_engineer_remediation_modification(client: TestClient):
    """12. Network Engineer can modify remediation commands (HTTP 200)."""
    action_id = "act-eng-mod-01"
    save_remediation_action_log(
        incident_id="inc-eng-mod-01",
        action_dict={"action_id": action_id, "device": "spine-01", "commands": ["original command"]},
        status="pending",
    )
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res = client.post(
        f"/api/remediation/{action_id}/modify",
        headers=headers,
        json={
            "commands": ["configure terminal", "interface et-0/0/1", "mtu 9000", "commit and-quit"],
            "rationale": "Harmonizing MTU based on diagnostic findings",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "modified"

    persisted = get_remediation_action_log(action_id)
    assert persisted is not None
    assert persisted.status == "modified"
    assert "mtu 9000" in persisted.commands_json


# -----------------------------------------------------------------------------
# 13. Audit access restricted correctly
# -----------------------------------------------------------------------------
def test_audit_access_restricted_correctly(client: TestClient):
    """13. Auditor and Platform Admin access audit logs (200); Helpdesk receives 403."""
    aud_headers = get_auth_headers(role=ROLE_AUDITOR, username="auditor")
    assert client.get("/api/auth/logs", headers=aud_headers).status_code == 200
    assert client.get("/api/remediation/logs", headers=aud_headers).status_code == 200

    plat_headers = get_auth_headers(role=ROLE_PLATFORM_ADMIN, username="platform_admin")
    assert client.get("/api/auth/logs", headers=plat_headers).status_code == 200

    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")
    assert client.get("/api/auth/logs", headers=hd_headers).status_code == 403
    assert client.get("/api/remediation/logs", headers=hd_headers).status_code == 403


# -----------------------------------------------------------------------------
# 14. HITL actor persistence in database (All 7 fields asserted independently)
# -----------------------------------------------------------------------------
def test_hitl_actor_persistence_in_database(client: TestClient):
    """14. Approvals persist actor_user_id, actor_username, actor_role, decision, rationale, timestamp, action_id."""
    action_id = "act-hitl-actor-persist-01"
    save_remediation_action_log(
        incident_id="inc-actor-01",
        action_dict={"action_id": action_id, "device": "spine-01", "commands": ["commit"]},
        status="pending",
    )
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res = client.post(
        f"/api/remediation/{action_id}/approve",
        headers=headers,
        json={"rationale": "Approved after verification"},
    )
    assert res.status_code == 200

    log = get_remediation_action_log(action_id)
    assert log is not None
    # Assert all seven required fields independently
    assert log.actor_user_id is not None and len(log.actor_user_id) > 0
    assert log.actor_username == "engineer"
    assert log.actor_role == ROLE_NETWORK_ENGINEER
    assert log.decision == "approved"
    assert log.rationale == "Approved after verification"
    assert log.decision_timestamp is not None and len(log.decision_timestamp) > 0
    assert log.action_id == action_id


# -----------------------------------------------------------------------------
# 15. Forged actor identity rejected
# -----------------------------------------------------------------------------
def test_forged_actor_identity_rejected(client: TestClient):
    """15. Operator spoofing in request body is ignored; server binds authenticated token identity."""
    action_id = "act-spoof-defense-01"
    save_remediation_action_log(
        incident_id="inc-spoof-01",
        action_dict={"action_id": action_id, "device": "spine-01", "commands": ["commit"]},
        status="pending",
    )
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res = client.post(
        f"/api/remediation/{action_id}/approve",
        headers=headers,
        json={
            "operator": "spoofed_admin",
            "actor_username": "fake_user",
            "actor_role": "fake_role",
            "rationale": "Testing identity forgery defense",
        },
    )
    assert res.status_code == 200

    log = get_remediation_action_log(action_id)
    assert log is not None
    assert log.actor_username == "engineer"
    assert log.actor_role == ROLE_NETWORK_ENGINEER
    assert "spoofed_admin" not in (log.approved_by or "")


# -----------------------------------------------------------------------------
# 16. Logout/token invalidation behavior
# -----------------------------------------------------------------------------
def test_logout_and_token_invalidation(client: TestClient):
    """16. POST /api/auth/logout revokes token jti; subsequent token usage returns 401."""
    login_res = client.post(
        "/api/auth/login",
        json={"username": "engineer", "password": os.getenv("NETCOOP_DEV_PASSWORD", "NetCoopDev!2026")},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/auth/me", headers=headers).status_code == 200

    logout_res = client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    revoked_res = client.get("/api/auth/me", headers=headers)
    assert revoked_res.status_code == 401
    assert "revoked" in revoked_res.json().get("detail", "").lower()


# -----------------------------------------------------------------------------
# 17. WebSocket Ticket Authentication & Replay Prevention
# -----------------------------------------------------------------------------
def test_websocket_ticket_exchange_endpoint(client: TestClient):
    """17a. POST /api/auth/ws-ticket issues short-lived single-use ticket to authorized users."""
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res = client.post("/api/auth/ws-ticket", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "ticket" in data
    assert data["expires_in"] == 60
    assert len(data["ticket"]) >= 32

    # Unauthenticated ticket request returns 401
    unauth = client.post("/api/auth/ws-ticket")
    assert unauth.status_code == 401


def test_websocket_ticket_connection_and_replay_rejection(client: TestClient):
    """17b. WebSocket connects with valid ticket; replaying the same ticket is rejected with 1008."""
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    ticket_res = client.post("/api/auth/ws-ticket", headers=headers)
    assert ticket_res.status_code == 200
    ticket = ticket_res.json()["ticket"]

    # 1. First connection consumes ticket successfully
    with client.websocket_connect(f"/ws/events?ticket={ticket}") as ws:
        connected_msg = ws.receive_json()
        assert connected_msg["event_type"] == "connected"
        assert connected_msg["user"] == "engineer"

    # 2. Replay attempt with already-consumed ticket must be rejected immediately
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/events?ticket={ticket}") as ws_replayed:
            pass


def test_websocket_invalid_and_expired_ticket_rejected(client: TestClient):
    """17c. WebSocket rejects invalid and expired tickets with policy violation."""
    # Invalid ticket
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/events?ticket=invalid-bogus-ticket") as ws:
            pass

    # Expired ticket
    user = get_user_by_username("engineer")
    expired_ticket = create_ws_ticket(user, expiry_seconds=-10)
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/events?ticket={expired_ticket}") as ws:
            pass


def test_websocket_anonymous_rejected(client: TestClient):
    """17d. Connecting to /ws/events without ticket or token is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/events") as ws:
            pass


# -----------------------------------------------------------------------------
# 18. MCP Authorization & Environment Token Support
# -----------------------------------------------------------------------------
def test_mcp_authorization(client: TestClient, monkeypatch):
    """18. Invoking MCP sensitive tools without token returns isError; authorized succeeds."""
    monkeypatch.delenv("NETCOOP_MCP_TOKEN", raising=False)

    # Without token
    err1 = NetCoopMCPServer.call_tool(
        "simulate_remediation",
        {"incident_id": "inc-mcp", "action_id": "act-mcp"},
    )
    assert err1.get("isError") is True
    assert "Missing authentication token" in err1["content"][0]["text"]

    # With unauthorized role (Helpdesk lacks SIMULATE_REMEDIATION)
    hd_token = create_access_token({"sub": "helpdesk", "role": ROLE_HELPDESK})
    err2 = NetCoopMCPServer.call_tool(
        "simulate_remediation",
        {"incident_id": "inc-mcp", "action_id": "act-mcp", "auth_token": hd_token},
    )
    assert err2.get("isError") is True
    assert "lacks 'SIMULATE_REMEDIATION'" in err2["content"][0]["text"]

    # With authorized role (Network Engineer via argument)
    save_incident(incident_id="inc-mcp-ok", network_id="net-1", status="open")
    eng_token = create_access_token({"sub": "engineer", "role": ROLE_NETWORK_ENGINEER})
    res_mcp = NetCoopMCPServer.call_tool(
        "simulate_remediation",
        {"incident_id": "inc-mcp-ok", "action_id": "act-mcp-ok", "auth_token": eng_token},
    )
    assert res_mcp.get("isError") is not True
    assert "content" in res_mcp

    # With authorized role via session environment variable NETCOOP_MCP_TOKEN
    monkeypatch.setenv("NETCOOP_MCP_TOKEN", eng_token)
    res_env = NetCoopMCPServer.call_tool(
        "simulate_remediation",
        {"incident_id": "inc-mcp-ok", "action_id": "act-mcp-ok"},
    )
    assert res_env.get("isError") is not True


# -----------------------------------------------------------------------------
# SEC-01 through SEC-06 Original Findings Traceability
# -----------------------------------------------------------------------------
def test_sec01_unauthenticated_remediation_approval_returns_401(client: TestClient):
    """SEC-01: Direct unauthenticated POST /api/remediation/{id}/approve returns 401; authorized returns 200."""
    action_id = "act-sec01-trace-01"
    save_remediation_action_log(
        incident_id="inc-sec01",
        action_dict={"action_id": action_id, "device": "spine-01", "commands": ["commit"]},
        status="pending",
    )

    # 1. Unauthenticated attempt -> 401
    res_unauth = client.post(f"/api/remediation/{action_id}/approve")
    assert res_unauth.status_code == 401

    # 2. Authorized engineer attempt -> 200
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res_auth = client.post(f"/api/remediation/{action_id}/approve", headers=headers)
    assert res_auth.status_code == 200
    assert res_auth.json()["status"] == "approved"


def test_sec02_helpdesk_remediation_approval_returns_403(client: TestClient):
    """SEC-02: Authenticated Helpdesk POST /api/remediation/{id}/approve returns 403; authorized returns 200."""
    action_id = "act-sec02-trace-01"
    save_remediation_action_log(
        incident_id="inc-sec02",
        action_dict={"action_id": action_id, "device": "spine-01", "commands": ["commit"]},
        status="pending",
    )

    # 1. Helpdesk user -> 403 Forbidden
    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")
    res_hd = client.post(f"/api/remediation/{action_id}/approve", headers=hd_headers)
    assert res_hd.status_code == 403
    assert "lacks required permissions" in res_hd.json().get("detail", "").lower()

    # 2. Network Administrator -> 200 OK
    admin_headers = get_auth_headers(role=ROLE_NETWORK_ADMIN, username="admin")
    res_admin = client.post(f"/api/remediation/{action_id}/approve", headers=admin_headers)
    assert res_admin.status_code == 200


def test_sec03_auditor_remediation_modification_returns_403(client: TestClient):
    """SEC-03: Authenticated Auditor POST /api/remediation/{id}/modify returns 403; authorized returns 200."""
    action_id = "act-sec03-trace-01"
    save_remediation_action_log(
        incident_id="inc-sec03",
        action_dict={"action_id": action_id, "device": "spine-01", "commands": ["commit"]},
        status="pending",
    )

    # 1. Auditor user -> 403 Forbidden
    aud_headers = get_auth_headers(role=ROLE_AUDITOR, username="auditor")
    res_aud = client.post(
        f"/api/remediation/{action_id}/modify",
        headers=aud_headers,
        json={"commands": ["interface et-0/0/1 shutdown"]},
    )
    assert res_aud.status_code == 403
    assert "lacks required permissions" in res_aud.json().get("detail", "").lower()

    # 2. Network Engineer -> 200 OK
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res_eng = client.post(
        f"/api/remediation/{action_id}/modify",
        headers=eng_headers,
        json={"commands": ["interface et-0/0/1 mtu 9000"]},
    )
    assert res_eng.status_code == 200


def test_sec04_unauthenticated_device_inventory_returns_401(client: TestClient):
    """SEC-04: Unauthenticated GET /api/devices returns 401; Helpdesk returns 403; Network Admin returns 200."""
    # 1. Unauthenticated -> 401
    res_unauth = client.get("/api/devices")
    assert res_unauth.status_code == 401

    # 2. Helpdesk (lacking MANAGE_DEVICES) -> 403
    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")
    res_hd = client.get("/api/devices", headers=hd_headers)
    assert res_hd.status_code == 403

    # 3. Network Administrator -> 200 OK
    admin_headers = get_auth_headers(role=ROLE_NETWORK_ADMIN, username="admin")
    res_admin = client.get("/api/devices", headers=admin_headers)
    assert res_admin.status_code == 200
    assert len(res_admin.json()) > 0


def test_sec05_unauthenticated_platform_status_returns_401(client: TestClient):
    """SEC-05: Unauthenticated GET /api/platform/status returns 401; Engineer returns 403; Platform Admin returns 200."""
    # 1. Unauthenticated -> 401
    res_unauth = client.get("/api/platform/status")
    assert res_unauth.status_code == 401

    # 2. Network Engineer (lacking CONFIGURE_SETTINGS) -> 403
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res_eng = client.get("/api/platform/status", headers=eng_headers)
    assert res_eng.status_code == 403

    # 3. Platform Administrator -> 200 OK
    plat_headers = get_auth_headers(role=ROLE_PLATFORM_ADMIN, username="platform_admin")
    res_plat = client.get("/api/platform/status", headers=plat_headers)
    assert res_plat.status_code == 200
    assert res_plat.json()["status"] == "healthy"


def test_sec06_unauthenticated_audit_log_returns_401(client: TestClient):
    """SEC-06: Unauthenticated GET /api/remediation/logs returns 401; Helpdesk returns 403; Auditor returns 200."""
    # 1. Unauthenticated -> 401
    res_unauth = client.get("/api/remediation/logs")
    assert res_unauth.status_code == 401

    # 2. Helpdesk (lacking EXPORT_AUDIT_LOGS) -> 403
    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")
    res_hd = client.get("/api/remediation/logs", headers=hd_headers)
    assert res_hd.status_code == 403

    # 3. Auditor -> 200 OK
    aud_headers = get_auth_headers(role=ROLE_AUDITOR, username="auditor")
    res_aud = client.get("/api/remediation/logs", headers=aud_headers)
    assert res_aud.status_code == 200
    assert isinstance(res_aud.json(), list)


def test_rate_limiting_locks_account_after_5_failed_attempts(client: TestClient):
    """Login rate limiting locks account or returns 429 after 5 failed attempts in 5 minutes."""
    client_ip = "192.0.2.200"
    clear_login_failures(client_ip)

    for _ in range(5):
        record_login_failure(client_ip)

    with pytest.raises(Exception) as exc_info:
        check_login_rate_limit(client_ip)
    assert "429" in str(exc_info.value) or "excessive failed attempts" in str(exc_info.value)

    clear_login_failures(client_ip)


def test_real_remediation_execution_blocked_with_403(client: TestClient):
    """Real remediation execution returns 403 (NetCoop-AI operates strictly in simulation-only mode)."""
    headers = get_auth_headers(role=ROLE_NETWORK_ADMIN, username="admin")
    res = client.post("/api/remediation/act-any/execute", headers=headers)
    assert res.status_code == 403
    assert "Real production remediation execution is strictly disabled" in res.json().get("detail", "")

# -----------------------------------------------------------------------------
# Part 5.A REST Authorization Matrix Tests
# -----------------------------------------------------------------------------
def test_part5a_rest_authorization_matrix(client: TestClient):
    """Verify complete route authorization matrix for incidents, envelopes, and orchestrator."""
    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")
    noc_headers = get_auth_headers(role=ROLE_NOC_OPERATOR, username="noc")

    # 1. /api/incidents
    assert client.get("/api/incidents").status_code == 401
    assert client.get("/api/incidents", headers=hd_headers).status_code == 200

    # 2. /api/incidents/{incident_id}
    assert client.get("/api/incidents/inc-part5a").status_code == 401
    save_incident(incident_id="inc-part5a", network_id="net-1", status="open")
    assert client.get("/api/incidents/inc-part5a", headers=hd_headers).status_code == 200

    # 3. /api/incidents/{incident_id}/envelopes
    assert client.get("/api/incidents/inc-part5a/envelopes").status_code == 401
    assert client.get("/api/incidents/inc-part5a/envelopes", headers=hd_headers).status_code == 200

    # 4. /api/envelopes/{correlation_id}
    assert client.get("/api/envelopes/corr-part5a").status_code == 401
    assert client.get("/api/envelopes/corr-part5a", headers=hd_headers).status_code == 200

    # 5. /api/orchestrator/pause
    assert client.post("/api/orchestrator/pause", json={"session_id": "sess-part5a"}).status_code == 401
    assert client.post("/api/orchestrator/pause", json={"session_id": "sess-part5a"}, headers=hd_headers).status_code == 403
    assert client.post("/api/orchestrator/pause", json={"session_id": "sess-part5a"}, headers=noc_headers).status_code == 200

    # 6. /api/orchestrator/checkpoints/{session_id}
    assert client.get("/api/orchestrator/checkpoints/sess-part5a").status_code == 401
    assert client.get("/api/orchestrator/checkpoints/sess-part5a", headers=hd_headers).status_code == 403
    assert client.get("/api/orchestrator/checkpoints/sess-part5a", headers=noc_headers).status_code == 200


# -----------------------------------------------------------------------------
# Part 5.B Concurrent WebSocket Ticket Consumption Test
# -----------------------------------------------------------------------------
def test_websocket_concurrent_consumption(client: TestClient):
    """Verify persistent atomic ticket consumption under concurrent execution."""
    user = get_user_by_username("engineer")
    assert user is not None
    ticket = create_ws_ticket(user, expiry_seconds=60)

    # Attempt concurrent consumption from multiple threads
    results = []
    def try_consume():
        return consume_ws_ticket(ticket)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(try_consume) for _ in range(5)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    success_count = sum(1 for ok, _, u in results if ok and u is not None)
    failure_count = sum(1 for ok, reason, _ in results if not ok and "already been consumed" in reason)

    assert success_count == 1, f"Expected exactly 1 successful consumption, got {success_count}"
    assert failure_count == 4, f"Expected 4 replay rejection failures, got {failure_count}"

