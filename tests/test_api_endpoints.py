"""Tests for FastAPI backend REST and WebSocket endpoints."""

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_api_health():
    """Verify backend health endpoint."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_api_ingest():
    """Verify /api/ingest canonicalizes incoming telemetry data."""
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


def test_websocket_events_stream():
    """Verify WebSocket connection and initial handshake event."""
    with client.websocket_connect("/ws/events") as websocket:
        init_event = websocket.receive_json()
        assert init_event["event_type"] == "connected"
        assert "NetCoop WebSocket" in init_event["message"]

        websocket.send_text("ping")
        pong = websocket.receive_text()
        assert pong == "pong"
