"""Tests for Phase 13J topology-randomized generator, invariant features, and OOD gate."""

import pytest
import numpy as np
from netcoop.data.topology_generator import TopologyRandomizedGenerator, TOPOLOGY_REGISTRY
from netcoop.models.features import WindowFeatureExtractor
from netcoop.models.ood_gate import OODGate


def test_topology_generator_all_topologies():
    """Verify that all registered topologies generate valid incident data."""
    for name in TOPOLOGY_REGISTRY:
        inc = TopologyRandomizedGenerator.generate(
            scenario="normal_operation",
            seed=42,
            topology_name=name,
        )
        assert inc is not None
        assert "incident_id" in inc
        assert "telemetry" in inc
        assert "topology" in inc
        assert len(inc["telemetry"]) > 0
        assert len(inc["topology"]["nodes"]) == TOPOLOGY_REGISTRY[name]["device_count"]


def test_topology_generator_fault_scenarios():
    """Verify fault generation across distinct equipment roles."""
    scenarios = [
        "link_congestion",
        "weak_wifi_signal",
        "ethernet_interface_fault",
        "dns_failure",
        "dhcp_failure",
        "device_cpu_overload",
        "upstream_failure_cascade",
    ]
    for sc in scenarios:
        inc = TopologyRandomizedGenerator.generate(
            scenario=sc,
            seed=42,
            topology_name="train_campus_8",
        )
        assert inc["scenario"] == sc
        assert len(inc["telemetry"]) > 0


def test_topology_invariant_features():
    """Verify invariant feature extraction yields fixed-dimension vectors across varying topologies."""
    names = WindowFeatureExtractor.get_topology_invariant_feature_names()
    assert len(names) == 358

    topos = ["train_branch_4", "train_campus_8", "train_datacenter_16", "validation_mesh_7"]
    for t in topos:
        inc = TopologyRandomizedGenerator.generate("normal_operation", seed=42, topology_name=t)
        vec, f_names = WindowFeatureExtractor.extract_topology_invariant_features(inc)
        assert len(vec) == 358
        assert f_names == names
        assert not np.isnan(vec).any()


def test_ood_gate_fit_and_predict():
    """Verify OOD gate fitting and distance evaluation."""
    rng = np.random.RandomState(42)
    X_train = rng.randn(100, 358).astype(np.float32)
    names = [f"f_{i}" for i in range(358)]

    gate = OODGate(range_margin=0.25, pca_components=10)
    gate.fit(X_train, names)

    # In-distribution sample
    x_in = np.mean(X_train, axis=0, keepdims=True)
    is_ood_in, reasons_in, score_in = gate.predict(x_in)
    assert not is_ood_in

    # Severe OOD sample
    x_out = (np.max(X_train, axis=0, keepdims=True) * 5.0) + 10.0
    is_ood_out, reasons_out, score_out = gate.predict(x_out)
    assert is_ood_out
    assert len(reasons_out) > 0
    assert score_out > score_in
