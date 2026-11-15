"""Tests for Phase 13B: Genuine, Independent Evidence from Log and Config Agents.

Verifies:
1. Log and config findings carry genuine independent provenance (source_agent, message_id, correlation_id).
2. Missing logs reduce independent evidence count and are listed in report limitations.
3. Conflicting evidence fixture produces a recorded conflict or abstention, never a silent single answer.
4. Leave-one-out behavior on extended fixtures.
5. Baseline 21 scenarios in manifest.json and benchmark populations remain completely unaltered.
"""

import json
from pathlib import Path
import pytest

from netcoop.orchestrator.graph import run_diagnosis, mediator
from netcoop.core.envelope import AgentRole

PROJECT_ROOT = Path(__file__).parent.parent
SCENARIOS_DIR = PROJECT_ROOT / "data" / "scenarios"


@pytest.fixture(autouse=True)
def restore_mediator():
    """Ensure mediator registry and health state are reset after each test."""
    orig_roles = list(mediator.registry.registered_roles)
    mediator.reset_dead_agents()
    mediator.reset_circuit_breaker()
    yield
    mediator.registry.registered_roles = list(orig_roles)
    mediator.reset_dead_agents()
    mediator.reset_circuit_breaker()


def test_log_and_config_provenance_independence():
    """Verify that log and config findings carry independent provenance attributes."""
    mtu_fixture = SCENARIOS_DIR / "mtu_mismatch_with_config.json"
    assert mtu_fixture.exists()

    with open(mtu_fixture, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = run_diagnosis(data)

    assert report.status == "diagnosed"
    assert "log_agent" in report.evidence_sources
    assert "config_agent" in report.evidence_sources
    assert "telemetry_agent" in report.evidence_sources

    log_items = [e for e in report.evidence if (e.get("source_agent") if isinstance(e, dict) else e.source_agent) == "log_agent"]
    config_items = [e for e in report.evidence if (e.get("source_agent") if isinstance(e, dict) else e.source_agent) == "config_agent"]

    assert len(log_items) >= 1
    assert len(config_items) >= 1

    # Check distinct provenance fields
    for item in log_items:
        obs_id = item.get("observation_id") if isinstance(item, dict) else item.observation_id
        msg_id = item.get("message_id") if isinstance(item, dict) else item.message_id
        corr_id = item.get("correlation_id") if isinstance(item, dict) else item.correlation_id
        finding = item.get("finding") if isinstance(item, dict) else item.finding

        assert obs_id.startswith("obs-")
        assert msg_id is not None and len(msg_id) > 0
        assert corr_id == data.get("incident_id")
        assert "mtu" in finding.lower() or "packet" in finding.lower()

    for item in config_items:
        obs_id = item.get("observation_id") if isinstance(item, dict) else item.observation_id
        msg_id = item.get("message_id") if isinstance(item, dict) else item.message_id
        corr_id = item.get("correlation_id") if isinstance(item, dict) else item.correlation_id

        assert obs_id.startswith("obs-")
        assert msg_id is not None and len(msg_id) > 0
        assert corr_id == data.get("incident_id")
        # Ensure log and config message IDs are distinct
        log_msg_ids = [l.get("message_id") if isinstance(l, dict) else l.message_id for l in log_items]
        assert msg_id not in log_msg_ids


def test_missing_logs_reduces_evidence_and_adds_limitation():
    """Verify missing logs produce a clear limitation and exclude log_agent from evidence sources."""
    baseline_fixture = SCENARIOS_DIR / "link_congestion.json"
    assert baseline_fixture.exists()

    with open(baseline_fixture, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = run_diagnosis(data)

    # Baseline link_congestion has no syslog records
    assert "log_agent" not in report.evidence_sources
    expected_limitation = "syslog telemetry unavailable: no log events recorded for device scope"
    assert any(expected_limitation in lim for lim in report.limitations)


def test_conflicting_fixture_produces_recorded_conflict():
    """Verify conflicting evidence fixture records conflict arbitration, never a silent single answer."""
    conflict_fixture = SCENARIOS_DIR / "conflicting_evidence.json"
    assert conflict_fixture.exists()

    with open(conflict_fixture, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = run_diagnosis(data)

    conflicts = report.provenance.get("conflicts_resolved", [])
    assert len(conflicts) >= 1

    conflict_entry = conflicts[0]
    assert "conflict" in conflict_entry
    assert "winner" in conflict_entry
    assert "precedence" in conflict_entry
    assert "rationale" in conflict_entry
    assert len(conflict_entry["rationale"]) > 0


def test_leave_one_out_removes_specific_evidence_domain():
    """Verify removing an agent drops its evidence and triggers abstention when required."""
    mtu_fixture = SCENARIOS_DIR / "mtu_mismatch_with_config.json"
    with open(mtu_fixture, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Full pipeline
    rep_full = run_diagnosis(data)
    assert rep_full.status == "diagnosed"
    assert "config_agent" in rep_full.evidence_sources
    assert "log_agent" in rep_full.evidence_sources

    # 2. Without log_agent: diagnosed, but log_agent excluded
    mediator.registry.registered_roles = [
        r for r in mediator.registry.registered_roles if r != AgentRole.LOG_AGENT
    ]
    rep_no_log = run_diagnosis(data)
    assert rep_no_log.status == "diagnosed"
    assert "log_agent" not in rep_no_log.evidence_sources
    assert len(rep_no_log.evidence) < len(rep_full.evidence)

    # 3. Without config_agent: Path MTU Mismatch strictly requires config diff -> must abstain
    mediator.registry.registered_roles = [
        r for r in mediator.registry.registered_roles if r != AgentRole.CONFIG_AGENT
    ]
    rep_no_cfg = run_diagnosis(data)
    assert rep_no_cfg.status == "insufficient_evidence"
    assert rep_no_cfg.confidence == 0.0


def test_baseline_scenarios_and_benchmark_population_unaltered():
    """Verify that baseline 21 scenarios in manifest.json and benchmark populations remain untouched."""
    manifest_path = SCENARIOS_DIR / "manifest.json"
    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    baseline_entries = manifest.get("scenarios", [])
    assert len(baseline_entries) == 21, f"Expected 21 baseline scenarios, got {len(baseline_entries)}"

    for sc_meta in baseline_entries:
        filename = sc_meta["file"]
        fpath = SCENARIOS_DIR / filename
        assert fpath.exists(), f"Baseline scenario {filename} missing"
        raw_text = fpath.read_text(encoding="utf-8")
        if filename == "interop_malformed_json.json":
            # Must remain invalid JSON by design
            with pytest.raises(json.JSONDecodeError):
                json.loads(raw_text)
        else:
            sc_data = json.loads(raw_text)
            # All valid baseline scenarios must still have empty logs and configurations
            assert sc_data.get("logs") == [], f"Baseline {filename} logs modified"
            assert sc_data.get("configurations") == [], f"Baseline {filename} configs modified"

    # Verify extended section exists
    extended_entries = manifest.get("extended", [])
    assert len(extended_entries) == 4, f"Expected 4 extended scenarios, got {len(extended_entries)}"
