"""tests/test_parameters_parity.py: Verify catalog parity and parameter consistency."""

from pathlib import Path
import pytest
import yaml

from netcoop.config import settings
from netcoop.core.thresholds import DynamicThresholds, OrganizerSnapshotThresholds


def test_parameters_yaml_exists_and_valid():
    """Verify config/parameters.yaml exists and contains valid structure."""
    param_path = Path("config/parameters.yaml")
    assert param_path.exists(), "config/parameters.yaml must exist"
    
    with open(param_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    assert "version" in data
    assert "parameters" in data
    assert isinstance(data["parameters"], dict)
    assert len(data["parameters"]) >= 20


def test_parameter_fields_and_evidence():
    """Verify every parameter has value, valid type, category, and evidence."""
    param_path = Path("config/parameters.yaml")
    with open(param_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    valid_types = {"hard safety", "fitted", "heuristic"}
    
    for name, spec in data["parameters"].items():
        assert "value" in spec, f"Parameter {name} missing value"
        assert "type" in spec, f"Parameter {name} missing type"
        assert spec["type"] in valid_types, f"Parameter {name} has invalid type {spec['type']}"
        assert "category" in spec, f"Parameter {name} missing category"
        assert "evidence" in spec, f"Parameter {name} missing evidence"
        assert len(str(spec["evidence"]).strip()) >= 10, f"Parameter {name} has insufficient evidence rationale"


def test_parameters_code_parity():
    """Verify parameter values in parameters.yaml match runtime code constants."""
    param_path = Path("config/parameters.yaml")
    with open(param_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)["parameters"]

    # Conformal and decision gating
    assert data["conformal_alpha"]["value"] == 0.10
    assert data["conformal_q_hat"]["value"] == 0.6786
    assert data["acceptance_confidence_threshold"]["value"] == 0.70
    assert data["high_confidence_threshold"]["value"] == 0.85
    assert data["medium_confidence_threshold"]["value"] == 0.70

    # Data quality
    assert data["dq_threshold"]["value"] == 0.70
    assert data["dq_floor"]["value"] == 0.40

    # Orchestrator parameters
    assert data["max_inquiry_iterations"]["value"] == 3
    assert data["agent_timeout_seconds"]["value"] == float(settings.agent_timeout_seconds)
    assert data["circuit_breaker_failure_threshold"]["value"] == int(settings.circuit_breaker_failure_threshold)
    assert data["circuit_breaker_recovery_timeout_s"]["value"] == float(settings.circuit_breaker_recovery_timeout_s)

    # Dynamic and domain thresholds
    assert data["link_utilization_critical_pct"]["value"] == DynamicThresholds.LINK_UTILIZATION_CRIT_PCT
    assert data["optical_rx_power_warn_dbm"]["value"] == DynamicThresholds.OPTICAL_RX_POWER_WARN_DBM
    assert data["optical_rx_power_crit_dbm"]["value"] == DynamicThresholds.OPTICAL_RX_POWER_CRIT_DBM
    assert data["ethernet_flap_threshold"]["value"] == DynamicThresholds.LINK_FLAPS_CRIT
