"""Integration test for Gateway /ingest and /health microservice endpoints."""

from fastapi.testclient import TestClient
from gateway.api import app

client = TestClient(app)


def test_gateway_health():
    """Verify gateway health endpoint returns ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "gateway"


def test_gateway_ingest_raw_telemetry():
    """Verify gateway transforms raw telemetry with aliases and kbps units."""
    raw_payload = {
        "incident_id": "test-ingest-01",
        "network_id": "lab-net",
        "telemetry": [
            {
                "dev": "rtr-core-01",
                "role": "router",
                "state": "online",
                "rtt": 12.5,
                "loss": 0.0,
                "throughput_kbps": 50000.0,
                "timestamp": "2026-10-31T12:00:00Z",
            }
        ],
    }

    response = client.post("/ingest", json=raw_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == "test-ingest-01"
    assert len(data["telemetry"]) == 1

    record = data["telemetry"][0]
    assert record["device_id"] == "rtr-core-01"
    assert record["device_type"] == "router"
    assert record["device_status"] == "online"
    assert record["latency_ms"] == 12.5
    assert record["packet_loss_pct"] == 0.0
    assert record["throughput_mbps"] == 50.0  # kbps converted to mbps
