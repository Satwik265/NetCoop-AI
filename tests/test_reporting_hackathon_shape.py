"""Test asserting exact key set for hackathon-required report JSON shape."""

from __future__ import annotations

import os
import pytest

from netcoop.config import settings
from netcoop.data.generator import SyntheticNetworkGenerator
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.reporting.builder import export_hackathon_report_json


@pytest.fixture(autouse=True)
def setup_in_process_mode() -> None:
    os.environ["AGENTS_MODE"] = "in_process"
    os.environ["IN_PROCESS_FALLBACK"] = "true"
    os.environ["ALLOW_DEV_IN_PROCESS_FALLBACK"] = "true"
    settings.agents_mode = "in_process"
    settings.in_process_fallback = True
    settings.allow_dev_in_process_fallback = True


def test_hackathon_required_report_json_exact_key_set() -> None:
    """Verify export_hackathon_report_json produces the exact required 10-key contract."""
    gen = SyntheticNetworkGenerator()
    inc = gen.generate(scenario="link_congestion", seed=42)
    unified_report = run_diagnosis(inc)

    result = export_hackathon_report_json(unified_report)

    # 1. Exact top-level key set
    expected_keys = {
        "incident_id",
        "status",
        "suspected_root_cause",
        "confidence",
        "affected_devices",
        "supporting_evidence",
        "alternative_causes",
        "recommended_actions",
        "evidence_sources",
        "limitations",
    }
    assert set(result.keys()) == expected_keys, f"Key mismatch. Got: {set(result.keys())}, expected: {expected_keys}"

    # 2. Field types and structure
    assert isinstance(result["incident_id"], str)
    assert isinstance(result["status"], str)
    assert isinstance(result["suspected_root_cause"], (str, type(None)))
    assert isinstance(result["confidence"], (float, int))
    assert isinstance(result["affected_devices"], list)
    assert isinstance(result["supporting_evidence"], list)
    assert isinstance(result["alternative_causes"], list)
    assert isinstance(result["recommended_actions"], list)
    assert isinstance(result["evidence_sources"], list)
    assert isinstance(result["limitations"], list)

    # 3. supporting_evidence items exact keys: {metric, value, interpretation}
    evidence_expected_keys = {"metric", "value", "interpretation"}
    assert len(result["supporting_evidence"]) > 0
    for item in result["supporting_evidence"]:
        assert isinstance(item, dict)
        assert set(item.keys()) == evidence_expected_keys, f"Evidence item key mismatch: {set(item.keys())}"

    # 4. recommended_actions must be list of strings
    for act in result["recommended_actions"]:
        assert isinstance(act, str)
