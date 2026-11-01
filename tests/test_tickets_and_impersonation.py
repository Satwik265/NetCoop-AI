"""Tests for ticket management workflow, RBAC access boundaries, and audited impersonation."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.auth import (
    ROLE_PLATFORM_ADMIN,
    ROLE_NETWORK_ADMIN,
    ROLE_NETWORK_ENGINEER,
    ROLE_HELPDESK,
    ROLE_AUDITOR,
    create_test_token,
    get_auth_headers,
)
from storage.db import (
    init_db,
    save_incident,
    get_user_by_username,
    list_tickets,
    get_auth_audit_logs,
)


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as test_client:
        yield test_client


# -----------------------------------------------------------------------------
# Ticket Management Workflow & RBAC Tests
# -----------------------------------------------------------------------------

def test_ticket_creation_and_persistence(client: TestClient):
    """Helpdesk can create a support ticket with automatic unique ID and validation."""
    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")

    # 1. Validation failure on missing fields
    res_invalid = client.post(
        "/api/tickets",
        headers=hd_headers,
        json={"title": "", "category": "wifi", "location": "", "affected_service": "", "description": ""},
    )
    assert res_invalid.status_code == 400

    # 2. Valid ticket creation
    res_valid = client.post(
        "/api/tickets",
        headers=hd_headers,
        json={
            "title": "Intermittent packet loss in Hostel Block A",
            "category": "wifi",
            "location": "Hostel Block A",
            "affected_service": "Campus WiFi",
            "description": "Students experiencing severe dropouts on zoom calls.",
            "priority": "high",
            "contact_info": "hostel-a@iitbbsr.ac.in",
        },
    )
    assert res_valid.status_code == 201
    ticket = res_valid.json()
    assert ticket["ticket_id"].startswith("TICK-2026-")
    assert ticket["status"] == "New"
    assert ticket["created_by"] == "helpdesk"
    assert ticket["priority"] == "high"


def test_ticket_list_and_role_access(client: TestClient):
    """Operational roles view tickets; non-operational roles only see their authored tickets."""
    # Create ticket as helpdesk
    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")
    res_create = client.post(
        "/api/tickets",
        headers=hd_headers,
        json={
            "title": "Library printer offline",
            "category": "hardware",
            "location": "Central Library",
            "affected_service": "Printing",
            "description": "Network printer not responding to ping.",
            "priority": "low",
        },
    )
    assert res_create.status_code == 201
    ticket_id = res_create.json()["ticket_id"]

    # 1. Platform Admin can list and retrieve
    admin_headers = get_auth_headers(role=ROLE_PLATFORM_ADMIN, username="platform_admin")
    res_list = client.get("/api/tickets", headers=admin_headers)
    assert res_list.status_code == 200
    ticket_ids = [t["ticket_id"] for t in res_list.json()]
    assert ticket_id in ticket_ids

    # 2. Network Engineer can view ticket details
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res_get = client.get(f"/api/tickets/{ticket_id}", headers=eng_headers)
    assert res_get.status_code == 200
    assert res_get.json()["ticket_id"] == ticket_id

    # 3. Auditor cannot view another user's unauthored ticket
    aud_headers = get_auth_headers(role=ROLE_AUDITOR, username="auditor")
    res_aud_get = client.get(f"/api/tickets/{ticket_id}", headers=aud_headers)
    assert res_aud_get.status_code == 403


def test_ticket_lifecycle_transitions(client: TestClient):
    """Valid transitions succeed; invalid transitions and unauthorized state changes fail."""
    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")

    # Create ticket
    res_create = client.post(
        "/api/tickets",
        headers=hd_headers,
        json={
            "title": "Router port flapping in Admin building",
            "category": "hardware",
            "location": "Admin Complex",
            "affected_service": "VoIP",
            "description": "VoIP phones rebooting intermittently.",
            "priority": "high",
        },
    )
    assert res_create.status_code == 201
    ticket_id = res_create.json()["ticket_id"]

    # 1. Invalid transition New -> Resolved returns 400
    res_inv = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=eng_headers,
        json={"status": "Resolved"},
    )
    assert res_inv.status_code == 400

    # 2. Helpdesk opens ticket (New -> Open) -> 200
    res_open = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=hd_headers,
        json={"status": "Open", "notes": "Ticket reviewed by helpdesk."},
    )
    assert res_open.status_code == 200
    assert res_open.json()["status"] == "Open"

    # 3. Helpdesk cannot resolve ticket directly -> 403
    res_hd_res = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=hd_headers,
        json={"status": "Resolved"},
    )
    assert res_hd_res.status_code == 403

    # 3b. Helpdesk cannot assign ticket to operational personnel -> 403
    res_hd_assign = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=hd_headers,
        json={"assigned_to": "engineer"},
    )
    assert res_hd_assign.status_code == 403

    # 4. Engineer assigns and investigates (Open -> Assigned -> Investigating -> Resolved)
    res_assign = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=eng_headers,
        json={"status": "Assigned", "assigned_to": "engineer"},
    )
    assert res_assign.status_code == 200
    assert res_assign.json()["status"] == "Assigned"
    assert res_assign.json()["assigned_to"] == "engineer"

    res_inv2 = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=eng_headers,
        json={"status": "Investigating", "notes": "Analyzing port packet drop counters."},
    )
    assert res_inv2.status_code == 200
    assert res_inv2.json()["status"] == "Investigating"

    res_res = client.patch(
        f"/api/tickets/{ticket_id}",
        headers=eng_headers,
        json={
            "status": "Resolved",
            "notes": "Replaced faulty SFP+ optical module.",
            "user_summary": "VoIP services fully restored across Admin Complex.",
        },
    )
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "Resolved"
    assert res_res.json()["user_facing_summary"] is not None


def test_ticket_to_incident_relationship(client: TestClient):
    """Authorized operators can link support tickets to diagnosed network incidents."""
    inc_id = "inc-ticket-link-01"
    save_incident(incident_id=inc_id, network_id="iitbbsr-campus", status="diagnosed")

    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")

    # Create ticket
    res_create = client.post(
        "/api/tickets",
        headers=hd_headers,
        json={
            "title": "Slow campus intranet",
            "category": "connectivity",
            "location": "Academic Complex",
            "affected_service": "Internet Gateway",
            "description": "High latency observed campus-wide.",
            "priority": "critical",
        },
    )
    ticket_id = res_create.json()["ticket_id"]

    # 1. Helpdesk cannot link to incident -> 403
    res_hd_link = client.post(
        f"/api/tickets/{ticket_id}/link-incident",
        headers=hd_headers,
        json={"incident_id": inc_id},
    )
    assert res_hd_link.status_code == 403

    # 2. Engineer links to incident -> 200
    res_eng_link = client.post(
        f"/api/tickets/{ticket_id}/link-incident",
        headers=eng_headers,
        json={"incident_id": inc_id},
    )
    assert res_eng_link.status_code == 200
    assert res_eng_link.json()["linked_incident_id"] == inc_id


# -----------------------------------------------------------------------------
# Impersonation and User Account Management Tests
# -----------------------------------------------------------------------------

def test_impersonation_security_boundaries(client: TestClient):
    """Only Platform Admin may impersonate; impersonation is audited; sessions can exit safely."""
    admin_headers = get_auth_headers(role=ROLE_PLATFORM_ADMIN, username="platform_admin")
    eng_headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    hd_headers = get_auth_headers(role=ROLE_HELPDESK, username="helpdesk")

    # 1. Non-Platform Admin cannot initiate impersonation -> 403
    res_eng = client.post(
        "/api/auth/impersonate",
        headers=eng_headers,
        json={"username": "helpdesk"},
    )
    assert res_eng.status_code == 403

    # 2. Platform Admin cannot impersonate own account -> 400
    res_self = client.post(
        "/api/auth/impersonate",
        headers=admin_headers,
        json={"username": "platform_admin"},
    )
    assert res_self.status_code == 400

    # 3. Platform Admin impersonates helpdesk -> 200 with impersonation claims
    res_imp = client.post(
        "/api/auth/impersonate",
        headers=admin_headers,
        json={"username": "helpdesk"},
    )
    assert res_imp.status_code == 200
    imp_data = res_imp.json()
    assert imp_data["role"] == ROLE_HELPDESK
    assert imp_data["username"] == "helpdesk"
    assert imp_data["impersonated_by"] == "platform_admin"

    imp_token = imp_data["access_token"]
    imp_headers = {"Authorization": f"Bearer {imp_token}"}

    # 4. Calling /api/auth/me with impersonation token returns helpdesk profile and impersonated_by metadata
    res_me = client.get("/api/auth/me", headers=imp_headers)
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["role"] == ROLE_HELPDESK
    assert me_data["impersonated_by"] == "platform_admin"

    # 5. Impersonated user cannot perform admin actions (e.g. create users)
    res_unauth = client.post(
        "/api/users",
        headers=imp_headers,
        json={"username": "rogue", "password": "Password123!", "role": "network_engineer"},
    )
    assert res_unauth.status_code == 403

    # 6. Exit impersonation endpoint succeeds
    res_exit = client.post("/api/auth/exit-impersonation", headers=imp_headers)
    assert res_exit.status_code == 200

    # 7. Audit log contains IMPERSONATION_START and IMPERSONATION_END
    audit_logs = get_auth_audit_logs(limit=20)
    event_types = [l.event_type for l in audit_logs]
    assert "IMPERSONATION_START" in event_types
    assert "IMPERSONATION_END" in event_types


def test_user_status_deactivation(client: TestClient):
    """Platform Admin can enable/disable users; deactivated users cannot authenticate."""
    admin_headers = get_auth_headers(role=ROLE_PLATFORM_ADMIN, username="platform_admin")
    target_user = get_user_by_username("engineer")
    assert target_user is not None

    # 1. Admin disables user
    res_disable = client.patch(
        f"/api/users/{target_user.user_id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert res_disable.status_code == 200
    assert res_disable.json()["is_active"] is False

    # 2. Disabled user cannot call authenticated APIs
    eng_token = create_test_token(role=ROLE_NETWORK_ENGINEER, username="engineer")
    res_call = client.get("/api/auth/me", headers={"Authorization": f"Bearer {eng_token}"})
    assert res_call.status_code == 401

    # 3. Admin re-enables user
    res_enable = client.patch(
        f"/api/users/{target_user.user_id}/status",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert res_enable.status_code == 200
    assert res_enable.json()["is_active"] is True

