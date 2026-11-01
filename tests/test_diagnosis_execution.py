"""Test suite validating diagnosis execution flow, repeated runs, and run comparison."""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from core.auth import ROLE_NETWORK_ENGINEER, get_auth_headers
from storage.db import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def _get_auth_header():
    return get_auth_headers(role=ROLE_NETWORK_ENGINEER, username="engineer")


def test_scenario_validation_endpoint(client: TestClient):
    """Verify live schema and input quality audit returns real metrics."""
    headers = _get_auth_header()
    res = client.get("/api/scenarios/link_congestion.json/validate", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["scenario_filename"] == "link_congestion.json"
    assert data["is_validated"] is True
    assert "quality_score" in data
    assert "detected_format" in data
    assert "transformations_count" in data
    assert "validation_errors" in data


def test_fresh_diagnosis_execution_and_repeated_runs(client: TestClient):
    """Verify Run Diagnosis executes a new run with unique execution ID, and repeated run generates new ID."""
    headers = _get_auth_header()

    # Run 1
    res1 = client.post("/api/scenarios/link_congestion.json/run", headers=headers)
    assert res1.status_code == 200, f"Run 1 failed: {res1.text}"
    data1 = res1.json()
    assert "run_id" in data1
    assert "execution_id" in data1
    assert data1["status"] == "completed"
    assert "report" in data1
    assert data1["report"]["status"] in ("diagnosed", "benign", "ambiguous", "insufficient_evidence")
    assert "envelopes" in data1
    run1_id = data1["run_id"]

    # Run 2 on same scenario (repeated execution)
    res2 = client.post("/api/scenarios/link_congestion.json/run", headers=headers)
    assert res2.status_code == 200, f"Run 2 failed: {res2.text}"
    data2 = res2.json()
    run2_id = data2["run_id"]

    # Must generate distinct execution identifiers
    assert run1_id != run2_id
    assert data2["previous_run_id"] == run1_id
    assert data2["previous_report"] is not None

    # Test run history list
    res_history = client.get("/api/scenarios/link_congestion.json/runs", headers=headers)
    assert res_history.status_code == 200
    runs = res_history.json()
    assert len(runs) >= 2
    run_ids = [r["run_id"] for r in runs]
    assert run2_id in run_ids
    assert run1_id in run_ids

    # Test comparison endpoint
    res_comp = client.get(f"/api/runs/{run2_id}/compare/{run1_id}", headers=headers)
    assert res_comp.status_code == 200
    comp = res_comp.json()
    assert comp["current_run_id"] == run2_id
    assert comp["previous_run_id"] == run1_id
    assert "probable_cause" in comp
    assert "confidence" in comp
    assert "uncertainty" in comp
    assert "affected_devices" in comp
    assert "classification_probabilities" in comp
    assert "remediation_actions" in comp
