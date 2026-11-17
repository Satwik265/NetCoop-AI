"""Comprehensive evaluation script for Phase 13B live HTTP execution and leave-one-out analysis."""
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
import httpx

PROJECT_ROOT = Path(r"D:\NetCoop-AI\Team_inSANE_MITRA_NetCoop-AI")
SCENARIOS_DIR = PROJECT_ROOT / "data" / "scenarios"

BASE_URL = "http://127.0.0.1:8000"
client = httpx.Client(base_url=BASE_URL, timeout=30.0)

# Authenticate as network engineer
auth_res = client.post("/api/auth/login", json={"username": "engineer", "password": "NetCoopDev!2026"})
assert auth_res.status_code == 200, f"Login failed: {auth_res.text}"
token = auth_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

extended_scenarios = [
    ("link_congestion_with_logs", SCENARIOS_DIR / "link_congestion_with_logs.json"),
    ("ethernet_fault_with_logs", SCENARIOS_DIR / "ethernet_fault_with_logs.json"),
    ("mtu_mismatch_with_config", SCENARIOS_DIR / "mtu_mismatch_with_config.json"),
    ("conflicting_evidence", SCENARIOS_DIR / "conflicting_evidence.json"),
]

print("================================================================================")
print("PHASE 13B: LIVE HTTP SYSTEM EVALUATION")
print("================================================================================")

run_records = {}

for name, path in extended_scenarios:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    content = path.read_bytes()
    sha = hashlib.sha256(content).hexdigest()

    t0 = time.time()
    resp = client.post("/api/diagnose", json=data, headers=headers)
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    assert resp.status_code == 200, f"Failed diagnose on {name}: {resp.status_code} {resp.text}"
    rep = resp.json()
    run_records[name] = rep

    status = rep.get("status")
    cause = rep.get("probable_cause")
    conf = rep.get("confidence")
    ev_sources = rep.get("evidence_sources", [])
    evidence = rep.get("evidence", [])
    alternatives = rep.get("alternative_causes", [])
    limitations = rep.get("limitations", [])
    provenance = rep.get("provenance", {})

    print(f"\n--- Scenario: {name} ---")
    print(f"File: {path.name} (SHA-256: {sha[:16]}...)")
    print(f"HTTP Latency: {elapsed_ms} ms")
    print(f"Status: {status}")
    print(f"Probable Cause: {cause}")
    print(f"Confidence: {conf}")
    print(f"Evidence Sources ({len(ev_sources)}): {ev_sources}")
    print(f"Total Evidence Items: {len(evidence)}")

    log_evidence = [e for e in evidence if e.get("source_agent") == "log_agent"]
    config_evidence = [e for e in evidence if e.get("source_agent") == "config_agent"]

    print(f"\n  [Log Agent Evidence ({len(log_evidence)} items)]:")
    for e in log_evidence:
        print(f"   * Entity: {e.get('entity')}, Metric: {e.get('metric_name') or e.get('metric')}")
        print(f"     Finding: {e.get('finding')}")
        print(f"     Observation ID: {e.get('observation_id')}")
        print(f"     Message ID: {e.get('message_id')}")
        print(f"     Correlation ID: {e.get('correlation_id')}")

    print(f"\n  [Config Agent Evidence ({len(config_evidence)} items)]:")
    for e in config_evidence:
        print(f"   * Entity: {e.get('entity')}, Metric: {e.get('metric_name') or e.get('metric')}")
        print(f"     Finding: {e.get('finding')}")
        print(f"     Observation ID: {e.get('observation_id')}")
        print(f"     Message ID: {e.get('message_id')}")
        print(f"     Correlation ID: {e.get('correlation_id')}")

    print(f"\n  [Alternative Causes ({len(alternatives)})]:")
    for a in alternatives:
        print(f"   * {a}")

    inquiries_count = provenance.get("inquiries_count", 0)
    conflicts_count = provenance.get("conflicts_resolved_count", 0)
    print(f"\n  [Inquiries & Conflicts]:")
    print(f"   * Inquiries Count: {inquiries_count}")
    print(f"   * Conflicts Resolved Count: {conflicts_count}")
    if conflicts_count > 0:
        for c in provenance.get("conflicts_resolved", []):
            print(f"     - Conflict: {c.get('conflict')}, Winner: {c.get('winner')}, Precedence: {c.get('precedence')}")
            print(f"       Rationale: {c.get('rationale')}")

# Save detailed run report to JSON for inspection
out_file = PROJECT_ROOT / "docs" / "phase13b_live_runs.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(run_records, f, indent=2)
print(f"\nSaved live runs to {out_file.name}")
