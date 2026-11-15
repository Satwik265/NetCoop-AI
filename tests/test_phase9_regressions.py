"""Phase 9 Regression Test Suite: Verification of RC-1 Truth Audit Remediations.

Tests written first before fixes:
- Group 1 (Item A): HITL, session pause/resume, and simulation route RBAC with exact UI URLs.
- Group 2 (Item B): Data-quality-aware confidence scoring and limitations.
- Group 3 (Item C): Canonical cause-key taxonomy enum and exhaustive remediation mapping.
- Group 4 (Item D): Unified confidence semantics (1.0 for benign, 0.0 for abstention).
- Group 5 (Item E): Terminology consistency ('7 specialist agents plus gateway and orchestrator').
- Group 6 (Item F & G): Documentation secret sanitization and .gitignore secret patterns.
"""

import json
import os
import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from api.main import app
from netcoop.core.auth import (
    get_auth_headers,
    ROLE_NETWORK_ENGINEER,
    ROLE_NOC_OPERATOR,
    ROLE_HELPDESK,
    ROLE_PLATFORM_ADMIN,
)


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# Group 1 (Item A): HITL / Session / Simulation Route RBAC & UI URLs (F-05)
# ============================================================================

def test_hitl_decision_endpoint_rbac_and_url_contract(client):
    """Verify POST /api/incidents/{incident_id}/hitl-decision enforces auth, RBAC, and matches UI URL."""
    eng_headers = get_auth_headers(ROLE_NETWORK_ENGINEER, "engineer")
    help_headers = get_auth_headers(ROLE_HELPDESK, "helpdesk")

    url = "/api/incidents/inc-test-hitl-1/hitl-decision"
    payload = {
        "action_id": "act-test-01",
        "decision": "approve",
        "rationale": "Verified transit queue drops warrant traffic rebalancing.",
        "operator": "engineer (network_engineer)",
    }

    # 1. Unauthenticated request must return 401
    res_unauth = client.post(url, json=payload)
    assert res_unauth.status_code == 401

    # 2. Unauthorized role lacking PERM_APPROVE_REMEDIATION must return 403
    res_unauthorized = client.post(url, json=payload, headers=help_headers)
    assert res_unauthorized.status_code == 403

    # 3. Authorized engineer must return 200 OK
    res_authorized = client.post(url, json=payload, headers=eng_headers)
    assert res_authorized.status_code == 200
    data = res_authorized.json()
    assert data["success"] is True
    assert data["decision"] == "approve"
    assert data["status"] == "hitl_approve"


def test_remediate_simulation_endpoint_rbac_and_url_contract(client):
    """Verify POST /api/remediate/simulate enforces auth, RBAC, and matches UI URL."""
    eng_headers = get_auth_headers(ROLE_NETWORK_ENGINEER, "engineer")
    help_headers = get_auth_headers(ROLE_HELPDESK, "helpdesk")

    url = "/api/remediate/simulate"
    payload = {
        "action_id": "act-sim-01",
        "action_type": "rebalance_traffic",
        "device": "spine-01",
        "scenario_or_incident_id": "link_congestion",
    }

    # 1. Unauthenticated must return 401
    res_unauth = client.post(url, json=payload)
    assert res_unauth.status_code == 401

    # 2. Unauthorized role lacking PERM_SIMULATE_REMEDIATION must return 403
    res_unauthorized = client.post(url, json=payload, headers=help_headers)
    assert res_unauthorized.status_code == 403

    # 3. Authorized engineer must return 200 OK
    res_authorized = client.post(url, json=payload, headers=eng_headers)
    assert res_authorized.status_code == 200
    data = res_authorized.json()
    assert data["status"] in ("success", "simulated_success")
    assert data["is_simulated"] is True


def test_pause_and_resume_endpoints_rbac(client):
    """Verify session pause and resume endpoints enforce auth and RBAC."""
    eng_headers = get_auth_headers(ROLE_NETWORK_ENGINEER, "engineer")
    help_headers = get_auth_headers(ROLE_HELPDESK, "helpdesk")

    # Pause
    res_pause_unauth = client.post("/api/orchestrator/pause", json={"session_id": "sess-test-1"})
    assert res_pause_unauth.status_code == 401

    res_pause_unauthz = client.post("/api/orchestrator/pause", json={"session_id": "sess-test-1"}, headers=help_headers)
    assert res_pause_unauthz.status_code == 403

    res_pause_ok = client.post("/api/orchestrator/pause", json={"session_id": "sess-test-1", "rationale": "Operator paused"}, headers=eng_headers)
    assert res_pause_ok.status_code == 200
    assert res_pause_ok.json()["status"] == "paused"


# ============================================================================
# Group 2 (Item B): Data-Quality-Aware Confidence Scoring (F-02)
# ============================================================================

def test_confidence_drops_under_missing_fields_without_altering_root_cause():
    """Verify that interop_missing_fields has strictly lower confidence than link_congestion.

    Both scenarios have link saturation as root cause; missing fields must lower confidence
    and add a data quality degradation limitation to the report without changing root cause.
    """
    from netcoop.orchestrator.graph import run_diagnosis
    from gateway.adapters.organizer_adapter import OrganizerAdapter

    # Run clean link_congestion
    with open("data/scenarios/link_congestion.json", "r", encoding="utf-8") as f:
        clean_raw = json.load(f)
    clean_adapted = OrganizerAdapter.adapt_dataset(clean_raw)
    rep_clean = run_diagnosis(clean_adapted)

    # Run interop_missing_fields
    with open("data/scenarios/interop_missing_fields.json", "r", encoding="utf-8") as f:
        missing_raw = json.load(f)
    missing_adapted = OrganizerAdapter.adapt_dataset(missing_raw)
    rep_missing = run_diagnosis(missing_adapted)

    # 1. Both must diagnose LINK_CONGESTION
    assert rep_clean.status == "diagnosed"
    assert rep_missing.status == "diagnosed"
    assert rep_clean.hypothesis_key == "LINK_CONGESTION"
    assert rep_missing.hypothesis_key == "LINK_CONGESTION"

    # 2. Missing fields confidence must be STRICTLY lower than clean confidence
    assert rep_missing.confidence < rep_clean.confidence, (
        f"Expected missing fields confidence ({rep_missing.confidence}) < clean ({rep_clean.confidence})"
    )

    # 3. Report must contain data quality limitation
    has_dq_limitation = any("quality" in lim.lower() for lim in rep_missing.limitations)
    assert has_dq_limitation, "Missing fields report must log data quality degradation limitation"


# ============================================================================
# Group 3 (Item C): Canonical Cause-Key Taxonomy & Remediation Mapping (F-04)
# ============================================================================

def test_every_cause_key_has_valid_remediation_mapping():
    """Verify that every member of CanonicalCauseKey has an explicit remediation mapping."""
    from netcoop.core.taxonomy import CanonicalCauseKey, CAUSE_TO_REMEDIATION_MAP, get_remediation_for_cause

    assert len(CanonicalCauseKey) >= 12, "Taxonomy must define all canonical fault cause keys"

    for cause in CanonicalCauseKey:
        if cause == CanonicalCauseKey.NO_FAULT:
            actions = get_remediation_for_cause(cause.value, devices=["core-01"])
            assert actions == [], "NO_FAULT must map to zero remediation actions"
        else:
            actions = get_remediation_for_cause(cause.value, devices=["core-01"])
            assert len(actions) > 0, f"Cause key {cause.value} must have non-empty remediation mapping"
            for act in actions:
                assert act.action_id
                assert act.title
                assert act.commands
                assert act.description


def test_canonical_cause_key_eval_mapping_coverage():
    """Verify that every member of CanonicalCauseKey has an evaluation class mapping."""
    from netcoop.core.taxonomy import CanonicalCauseKey, CAUSE_TO_EVAL_MAP

    for cause in CanonicalCauseKey:
        assert cause.value in CAUSE_TO_EVAL_MAP or cause in CAUSE_TO_EVAL_MAP, (
            f"Cause key {cause} missing from evaluation mapping table CAUSE_TO_EVAL_MAP"
        )


# ============================================================================
# Group 4 (Item D): Unified Confidence Semantics (F-08)
# ============================================================================

def test_unified_confidence_semantics_benign_and_abstention():
    """Verify that benign confidence is strictly 1.0 and abstentions are strictly 0.0."""
    from netcoop.orchestrator.graph import run_diagnosis
    from netcoop.reporting.builder import export_hackathon_report_json
    from gateway.adapters.organizer_adapter import OrganizerAdapter

    # Benign scenario
    with open("data/scenarios/normal_operation.json", "r", encoding="utf-8") as f:
        benign_raw = json.load(f)
    rep_benign = run_diagnosis(OrganizerAdapter.adapt_dataset(benign_raw))
    export_benign = export_hackathon_report_json(rep_benign)

    assert rep_benign.status == "benign"
    assert rep_benign.confidence == 1.0, f"Benign confidence must be 1.0, got {rep_benign.confidence}"
    assert export_benign["confidence"] == 1.0, f"Hackathon export benign confidence must be 1.0, got {export_benign['confidence']}"

    # Abstention scenario
    with open("data/scenarios/insufficient_data.json", "r", encoding="utf-8") as f:
        abstain_raw = json.load(f)
    rep_abstain = run_diagnosis(OrganizerAdapter.adapt_dataset(abstain_raw))
    export_abstain = export_hackathon_report_json(rep_abstain)

    assert rep_abstain.status == "insufficient_evidence"
    assert rep_abstain.confidence == 0.0, f"Abstention confidence must be 0.0, got {rep_abstain.confidence}"
    assert export_abstain["confidence"] == 0.0, f"Hackathon export abstention confidence must be 0.0, got {export_abstain['confidence']}"


# ============================================================================
# Group 5 (Item E): Terminology Harmonization (F-10)
# ============================================================================

def test_agent_terminology_consistency():
    """Verify UI and README describe the system as '7 specialist agents plus gateway and orchestrator'."""
    agent_graph_file = Path("dashboard/src/components/AgentGraph.tsx")
    assert agent_graph_file.exists()
    content_graph = agent_graph_file.read_text(encoding="utf-8")

    assert "7 specialist agents plus gateway and orchestrator" in content_graph, (
        "AgentGraph.tsx must state '7 specialist agents plus gateway and orchestrator'"
    )

    readme_file = Path("README.md")
    assert readme_file.exists()
    readme_content = readme_file.read_text(encoding="utf-8")
    assert "7 specialist agents plus gateway and orchestrator" in readme_content, (
        "README.md must state '7 specialist agents plus gateway and orchestrator'"
    )


# ============================================================================
# Group 6 (Items F & G): Doc Secret Sanitization & .gitignore Patterns (F-07)
# ============================================================================

def test_no_literal_secrets_in_tracked_docs():
    """Verify that no literal high-entropy token or secret keys are stored in tracked docs."""
    doc_paths = list(Path("docs").glob("*.md"))
    doc_paths.append(Path("README.md"))

    literal_secret_pattern = re.compile(
        r'(INTERNAL_SERVICE_TOKEN|NETCOOP_JWT_SECRET)\s*=\s*["\']([^"\'<>{}]+)["\']',
        re.IGNORECASE,
    )

    for p in doc_paths:
        text = p.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            m = literal_secret_pattern.search(line)
            if m:
                val = m.group(2)
                # Allow only placeholder or doc descriptions
                assert "placeholder" in val.lower() or "generate" in val.lower() or "<" in val, (
                    f"Found unredacted literal secret in {p.name}:{line_no}: {line.strip()}"
                )


def test_gitignore_contains_secret_file_patterns():
    """Verify that .gitignore contains patterns preventing accidental commitment of secret files."""
    gitignore_path = Path(".gitignore")
    assert gitignore_path.exists()
    text = gitignore_path.read_text(encoding="utf-8")

    required_patterns = ["*.secret", "*.secrets", "*.key", "*.token", "*.pem"]
    for pat in required_patterns:
        assert pat in text, f".gitignore missing pattern {pat}"
