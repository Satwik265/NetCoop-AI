import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
import httpx

base_url = "http://127.0.0.1:8000"
client = httpx.Client(base_url=base_url, timeout=30.0)

# 1. Login
auth_res = client.post("/api/auth/login", json={"username": "engineer", "password": "NetCoopDev!2026"})
assert auth_res.status_code == 200, f"Login failed: {auth_res.text}"
token = auth_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

scenarios = [
    ("A. Normal operation", "data/scenarios/normal_operation.json"),
    ("B. Link congestion", "data/scenarios/link_congestion.json"),
    ("C. Weak Wi-Fi", "data/scenarios/weak_wifi_signal.json"),
    ("D. Ethernet fault", "data/scenarios/ethernet_interface_fault.json"),
    ("E. DNS failure", "data/scenarios/dns_failure.json"),
    ("E2. DHCP failure", "data/scenarios/dhcp_failure.json"),
    ("G. Compound/Conflicting", "data/scenarios/ambiguous_multi_fault.json"),
    ("H. Insufficient evidence", "data/scenarios/05_insufficient_evidence_sparse.json"),
]

results = {}

for label, path_str in scenarios:
    p = Path(path_str)
    content = p.read_bytes()
    h = hashlib.sha256(content).hexdigest()
    data = json.loads(content.decode("utf-8"))
    
    t0 = time.time()
    res = client.post("/api/diagnose", json=data, headers=headers)
    elapsed_ms = round((time.time() - t0) * 1000, 1)
    
    print(f"\n========================================================")
    print(f"=== {label} ===")
    print(f"File: {path_str} (SHA256: {h})")
    print(f"HTTP Status: {res.status_code} in {elapsed_ms}ms")
    
    if res.status_code == 200:
        rep = res.json()
        status = rep.get("status")
        cause = rep.get("probable_cause")
        conf = rep.get("confidence")
        evidence = rep.get("evidence", [])
        actions = rep.get("remediation_actions", [])
        alternatives = rep.get("alternative_causes", [])
        limitations = rep.get("limitations", [])
        
        print(f"Diagnostic Status: {status}")
        print(f"Probable Cause: {cause}")
        print(f"Confidence: {conf}")
        print(f"Evidence Count: {len(evidence)}")
        for i, ev in enumerate(evidence[:3]):
            print(f"  Ev[{i}]: [{ev.get('source_agent')}] {ev.get('metric_name')} -> {ev.get('description')}")
        if len(evidence) > 3:
            print(f"  ... and {len(evidence) - 3} more evidence items")
        print(f"Alternative Causes: {alternatives}")
        print(f"Remediation Actions: {len(actions)}")
        print(f"Limitations Count: {len(limitations)}")
        
        results[label] = {
            "file": path_str,
            "sha256": h,
            "http_status": res.status_code,
            "elapsed_ms": elapsed_ms,
            "status": status,
            "probable_cause": cause,
            "confidence": conf,
            "evidence_count": len(evidence),
            "remediation_actions_count": len(actions),
            "alternatives": alternatives,
            "sample_evidence": evidence[:2] if evidence else [],
        }
    else:
        print(f"Error ({res.status_code}): {res.text[:300]}")
        results[label] = {
            "file": path_str,
            "sha256": h,
            "http_status": res.status_code,
            "elapsed_ms": elapsed_ms,
            "error": res.text[:300],
        }

# ========================================================
# Scenario F: Interoperability and Robustness Tests
# ========================================================
print(f"\n========================================================")
print(f"=== Scenario F: Interoperability Failure & Robustness ===")

interop_scenarios = [
    ("F1. Malformed JSON", "data/scenarios/interop_malformed_json.json", True),
    ("F2. Missing fields", "data/scenarios/interop_missing_fields.json", False),
    ("F3. Renamed fields", "data/scenarios/interop_renamed_fields.json", False),
]

for label, p_str, is_malformed in interop_scenarios:
    p = Path(p_str)
    content = p.read_bytes()
    h = hashlib.sha256(content).hexdigest()
    t0 = time.time()
    
    if is_malformed:
        res = client.post("/api/diagnose", content=content, headers={**headers, "Content-Type": "application/json"})
    else:
        data = json.loads(content.decode("utf-8"))
        res = client.post("/api/diagnose", json=data, headers=headers)
    elapsed_ms = round((time.time() - t0) * 1000, 1)
    
    print(f"\n--- {label} ---")
    print(f"File: {p_str} (SHA256: {h})")
    print(f"HTTP Status: {res.status_code} in {elapsed_ms}ms")
    
    if res.status_code == 200:
        rep = res.json()
        print(f"Status: {rep.get('status')}, Cause: {rep.get('probable_cause')}, Confidence: {rep.get('confidence')}")
        results[label] = {
            "file": p_str,
            "sha256": h,
            "http_status": res.status_code,
            "elapsed_ms": elapsed_ms,
            "status": rep.get("status"),
            "probable_cause": rep.get("probable_cause"),
            "confidence": rep.get("confidence"),
        }
    elif res.status_code == 422:
        print(f"Handled validation error: HTTP 422 Unprocessable Entity (Expected for malformed inputs)")
        results[label] = {
            "file": p_str,
            "sha256": h,
            "http_status": res.status_code,
            "elapsed_ms": elapsed_ms,
            "response": res.json(),
        }
    else:
        print(f"Response ({res.status_code}): {res.text[:200]}")
        results[label] = {
            "file": p_str,
            "sha256": h,
            "http_status": res.status_code,
            "elapsed_ms": elapsed_ms,
            "response": res.text[:200],
        }

# ========================================================
# Scenario Export Run: POST /api/diagnose/export
# ========================================================
print(f"\n========================================================")
print(f"=== API Export Run: POST /api/diagnose/export ===")
with open("data/scenarios/link_congestion.json", "r", encoding="utf-8") as f:
    scen_data = json.load(f)

res_exp = client.post("/api/diagnose/export", json=scen_data, headers=headers)
print(f"Export HTTP Status: {res_exp.status_code}")
assert res_exp.status_code == 200, f"Export failed: {res_exp.text}"
exp_data = res_exp.json()
print(f"Export Keys: {list(exp_data.keys())}")
print(f"Incident ID: {exp_data.get('incident_id')}")
print(f"Export Report Status: {exp_data.get('status')}")
print(f"Export Has Traceable Supporting Evidence: {len(exp_data.get('supporting_evidence', [])) > 0}")
results["API Export Run"] = {
    "http_status": res_exp.status_code,
    "incident_id": exp_data.get("incident_id"),
    "status": exp_data.get("status"),
    "supporting_evidence_count": len(exp_data.get("supporting_evidence", [])),
    "recommended_actions_count": len(exp_data.get("recommended_actions", [])),
}

# ========================================================
# Simulated Remediation Flow
# ========================================================
print(f"\n========================================================")
print(f"=== Simulated Remediation Flow (HITL Safety Invariant) ===")
# 1. Fetch pending remediation actions
res_pend = client.get("/api/remediation/pending", headers=headers)
print(f"GET /api/remediation/pending Status: {res_pend.status_code}")
assert res_pend.status_code == 200
pending_actions = res_pend.json()
print(f"Pending actions count: {len(pending_actions)}")

if pending_actions:
    action = pending_actions[0]
    action_id = action["action_id"]
    print(f"Testing action: {action_id}")
    
    # 2. Approve action
    res_appr = client.post(
        f"/api/remediation/{action_id}/approve",
        headers=headers,
        json={"rationale": "Verified safe under congestion policy during Phase 7 E2E"},
    )
    print(f"Approve Status: {res_appr.status_code} -> {res_appr.json()}")
    assert res_appr.status_code == 200
    
    # 3. Test Hard Invariant: POST /api/remediation/{action_id}/execute MUST return 403 Forbidden
    res_exec = client.post(f"/api/remediation/{action_id}/execute", headers=headers)
    print(f"Execute Status (Invariant Check): {res_exec.status_code} (Expected 403 Forbidden)")
    assert res_exec.status_code == 403, f"CRITICAL INVARIANT VIOLATION: Expected 403, got {res_exec.status_code}"
    print(f"Execute Detail: {res_exec.json().get('detail')}")
    results["Simulated Remediation Flow"] = {
        "action_id": action_id,
        "approve_status": res_appr.status_code,
        "execute_status": res_exec.status_code,
        "safety_invariant_verified": True,
        "detail": res_exec.json().get("detail"),
    }

# ========================================================
# CLI Diagnosis Run: netcoop diagnose
# ========================================================
print(f"\n========================================================")
print(f"=== Reproducible CLI Run: netcoop diagnose ===")
py_exec = str(Path(".venv/Scripts/python.exe").resolve())
cli_cmd = [
    py_exec,
    "-m",
    "netcoop.cli",
    "diagnose",
    "--file",
    "data/scenarios/link_congestion.json",
]
cli_run = subprocess.run(cli_cmd, capture_output=True, text=True, check=False)
print(f"CLI Exit Code: {cli_run.returncode}")
print(f"CLI Output Snippet:\n{cli_run.stdout[:400]}")
assert cli_run.returncode == 0, f"CLI diagnose failed: {cli_run.stderr}"
results["CLI Run"] = {
    "command": "python -m netcoop.cli diagnose data/scenarios/link_congestion.json",
    "exit_code": cli_run.returncode,
    "output_snippet": cli_run.stdout[:400],
}

# Save detailed output for report
Path("scripts/live_e2e_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print("\nAll End-to-End verification workflows completed and saved to scripts/live_e2e_results.json")
