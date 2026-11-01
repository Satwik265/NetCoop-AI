from core.auth import get_auth_headers, ROLE_NETWORK_ENGINEER
"""Tests for FastAPI backend REST and WebSocket endpoints."""

from fastapi.testclient import TestClient
import json
import httpx
import pytest

from api.main import app
from gateway.api import create_gateway_app

client = TestClient(app)


def test_api_health():
    """Verify backend health endpoint."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_api_ingest_gateway_unavailable(monkeypatch):
    """Verify /api/ingest fails with HTTP 503 when Gateway service on port 8006 is offline."""
    def mock_post(self, url, *args, **kwargs):
        raise httpx.ConnectError("Connection refused")
    monkeypatch.setattr(httpx.Client, "post", mock_post)
    res = client.post(
        "/api/ingest",
        json={"incident_id": "test-gw-down", "telemetry": []},
    )
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert "Gateway service" in detail
    assert "unavailable over HTTP" in detail


def test_api_ingest_forwarding(monkeypatch):
    """Verify /api/ingest dispatches to Gateway over HTTP and returns canonicalized schema."""
    gw_app = create_gateway_app()
    gw_client = TestClient(gw_app)

    def mock_post(self, url, *args, **kwargs):
        if "/ingest" in str(url):
            return gw_client.post("/ingest", json=kwargs.get("json"))
        return gw_client.post(str(url), json=kwargs.get("json"))

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    raw = {
        "incident_id": "test-api-ingest-01",
        "telemetry": [
            {
                "dev": "sw-core",
                "loss": 2.5,
                "util": 90.0,
                "timestamp": "2026-10-31T12:00:00Z",
            }
        ],
    }
    res = client.post("/api/ingest", json=raw)
    assert res.status_code == 200
    data = res.json()
    assert data["incident_id"] == "test-api-ingest-01"
    assert len(data["telemetry"]) == 1
    assert data["telemetry"][0]["packet_loss_pct"] == 2.5
    assert data["telemetry"][0]["link_utilization_pct"] == 90.0


def test_api_diagnose_gateway_unavailable_with_organizer_format(monkeypatch):
    """Verify /api/diagnose fails with HTTP 503 if organizer dataset cannot be normalized because Gateway is offline."""
    def mock_post(self, url, *args, **kwargs):
        raise httpx.ConnectError("Connection refused")
    monkeypatch.setattr(httpx.Client, "post", mock_post)
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    organizer_payload = {
        "device_id": "sw1",
        "metrics": {"loss": 1.0},
        "status": "Warning",
    }
    res = client.post("/api/diagnose", json=organizer_payload, headers=headers)
    assert res.status_code == 503
    assert "Gateway service on port 8006 unavailable over HTTP" in res.json()["detail"]


def test_websocket_events_stream():
    """Verify WebSocket connection and initial handshake event."""
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    ticket_res = client.post("/api/auth/ws-ticket", headers=headers)
    assert ticket_res.status_code == 200
    ticket = ticket_res.json()["ticket"]
    with client.websocket_connect(f"/ws/events?ticket={ticket}") as websocket:
        init_event = websocket.receive_json()
        assert init_event["event_type"] == "connected"
        assert "NetCoop WebSocket" in init_event["message"]

        websocket.send_text("ping")
        pong = websocket.receive_text()
        assert pong == "pong"


def test_api_diagnose_interop_renamed_fields(monkeypatch):
    """Verify /api/diagnose normalizes renamed fields via Gateway and returns diagnosis."""
    gw_app = create_gateway_app()
    gw_client = TestClient(gw_app)

    def mock_post(self, url, *args, **kwargs):
        if "/ingest" in str(url):
            return gw_client.post("/ingest", json=kwargs.get("json"))
        return gw_client.post(str(url), json=kwargs.get("json"))

    monkeypatch.setattr(httpx.Client, "post", mock_post)
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    with open("data/scenarios/interop_renamed_fields.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

    res = client.post("/api/diagnose", json=payload, headers=headers)
    assert res.status_code == 200
    report = res.json()
    assert report["hypothesis_key"] == "LINK_CONGESTION"
    assert report["status"] == "diagnosed"
    assert len(report["remediation_actions"]) == 2


def test_api_diagnose_interop_null_nan(monkeypatch):
    """Verify /api/diagnose handles null and NaN fields via Gateway and returns diagnosis."""
    gw_app = create_gateway_app()
    gw_client = TestClient(gw_app)

    def mock_post(self, url, *args, **kwargs):
        if "/ingest" in str(url):
            return gw_client.post("/ingest", json=kwargs.get("json"))
        return gw_client.post(str(url), json=kwargs.get("json"))

    monkeypatch.setattr(httpx.Client, "post", mock_post)
    headers = get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")
    with open("data/scenarios/interop_null_nan.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

    res = client.post("/api/diagnose", json=payload, headers=headers)
    assert res.status_code == 200
    report = res.json()
    assert report["hypothesis_key"] == "LINK_CONGESTION"
    assert report["status"] == "diagnosed"
    assert len(report["remediation_actions"]) == 2
