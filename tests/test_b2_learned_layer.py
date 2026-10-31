"""Unit and property tests for B2 learned layer:
- Dataset splitting and seed disjointness
- Window feature extraction (windowed vs single-snapshot)
- Isotonic calibration and ECE
- Split conformal prediction set and abstention
- Value-based unit inference decision tree
- Character n-gram field-name matching generalization (cpu_utilization_pct -> cpu_pct)
- ClassifierAgent HTTP envelope processing
"""

import math
import numpy as np
import pytest

from netcoop.models.splits import DatasetSplitter
from netcoop.models.features import WindowFeatureExtractor
from netcoop.models.calibration import ProbabilityCalibrator
from netcoop.models.conformal import ConformalAbstentionEngine
from gateway.adapters.unit_inference import ValueUnitInferencer
from gateway.adapters.field_matcher import FieldNameMatcher
from netcoop.agents.classifier.classifier_agent import ClassifierAgent
from netcoop.core.envelope import AgentEnvelope, AgentRole, EnvelopePayload, MessageType, NetworkScope, ProtocolHeader


# -----------------------------------------------------------------------------
# 1. Dataset Splitting & Seed Disjointness
# -----------------------------------------------------------------------------

def test_splits_seed_disjointness() -> None:
    """Verify that train, calibration, validation, and test splits share zero seeds."""
    DatasetSplitter.verify_no_seed_overlap()

    train_s = DatasetSplitter.TRAIN_SPEC.seeds
    calib_s = DatasetSplitter.CALIBRATION_SPEC.seeds
    val_s = DatasetSplitter.VALIDATION_SPEC.seeds
    test_s = DatasetSplitter.TEST_SPEC.seeds

    assert len(train_s) >= 200
    assert len(calib_s) >= 50
    assert len(val_s) >= 50
    assert len(test_s) >= 50

    # Strict pairwise disjointness
    assert len(train_s.intersection(calib_s)) == 0
    assert len(train_s.intersection(val_s)) == 0
    assert len(train_s.intersection(test_s)) == 0
    assert len(calib_s.intersection(val_s)) == 0
    assert len(calib_s.intersection(test_s)) == 0
    assert len(val_s.intersection(test_s)) == 0


# -----------------------------------------------------------------------------
# 2. Feature Extraction (Single Snapshot vs Multi-Point Window)
# -----------------------------------------------------------------------------

def test_feature_extraction_single_snapshot() -> None:
    """Single-snapshot input sets history-dependent features to NaN and flags is_single_snapshot."""
    single_record = [
        {
            "timestamp": "2026-10-31T12:00:00Z",
            "device_id": "sw-1",
            "latency_ms": 25.0,
            "packet_loss_pct": 0.5,
            "link_utilization_pct": 60.0,
        }
    ]
    vec, meta = WindowFeatureExtractor.extract_device_features("sw-1", single_record)
    assert meta["is_single_snapshot"] is True
    assert meta["record_count"] == 1

    names = WindowFeatureExtractor.get_feature_names()
    slope_idx = names.index("latency_ms_slope")
    assert math.isnan(vec[slope_idx])

    single_flag_idx = names.index("is_single_snapshot")
    assert vec[single_flag_idx] == 1.0


def test_feature_extraction_window_with_slope() -> None:
    """Multi-point window calculates valid linear slopes and percentiles."""
    records = [
        {"device_id": "sw-1", "latency_ms": 10.0, "link_utilization_pct": 50.0},
        {"device_id": "sw-1", "latency_ms": 20.0, "link_utilization_pct": 70.0},
        {"device_id": "sw-1", "latency_ms": 30.0, "link_utilization_pct": 90.0},
    ]
    vec, meta = WindowFeatureExtractor.extract_device_features("sw-1", records)
    assert meta["is_single_snapshot"] is False
    assert meta["record_count"] == 3

    names = WindowFeatureExtractor.get_feature_names()
    lat_mean_idx = names.index("latency_ms_mean")
    assert vec[lat_mean_idx] == 20.0

    lat_slope_idx = names.index("latency_ms_slope")
    assert not math.isnan(vec[lat_slope_idx])
    assert vec[lat_slope_idx] > 0.0  # strictly increasing


# -----------------------------------------------------------------------------
# 3. Calibration & ECE
# -----------------------------------------------------------------------------

def test_calibration_isotonic_and_ece() -> None:
    """Verify Isotonic calibration outputs bounded probabilities and valid ECE."""
    np.random.seed(42)
    # Synthetic uncalibrated overconfident probabilities
    y_true = np.random.binomial(1, 0.7, size=(100, 2))
    raw_probs = np.clip(y_true * 0.8 + np.random.uniform(-0.1, 0.1, size=(100, 2)), 0.0, 1.0)

    calibrator = ProbabilityCalibrator()
    calibrator.fit(raw_probs, y_true, ["class_a", "class_b"])
    calibrated = calibrator.calibrate(raw_probs, ["class_a", "class_b"])

    assert calibrated.shape == raw_probs.shape
    assert np.all(calibrated >= 0.0)
    assert np.all(calibrated <= 1.0)

    ece, bins = ProbabilityCalibrator.compute_ece(calibrated[:, 0], y_true[:, 0], n_bins=5)
    assert 0.0 <= ece <= 1.0
    assert len(bins) == 5


# -----------------------------------------------------------------------------
# 4. Conformal Prediction Set & Abstention
# -----------------------------------------------------------------------------

def test_conformal_prediction_set_and_abstention() -> None:
    """Verify conformal set prediction: diagnosed, ambiguous, and insufficient_evidence."""
    engine = ConformalAbstentionEngine(alpha=0.10)
    engine.q_hat = 0.20  # min threshold = 1 - 0.20 = 0.80

    # Case 1: Decisive single root cause
    probs_single = {"link_congestion": 0.94, "weak_wifi_signal": 0.05, "normal_operation": 0.01}
    status, p_set, conf = engine.predict_set(probs_single)
    assert status == "diagnosed"
    assert p_set == ["link_congestion"]
    assert conf == 0.94

    # Case 2: Ambiguous multiple competing causes
    probs_multi = {"device_cpu_overload": 0.88, "link_congestion": 0.85, "weak_wifi_signal": 0.10}
    status_multi, p_set_multi, _ = engine.predict_set(probs_multi)
    assert status_multi == "ambiguous"
    assert "device_cpu_overload" in p_set_multi
    assert "link_congestion" in p_set_multi

    # Case 3: Incomplete/low-score telemetry -> insufficient_evidence
    probs_sparse = {"device_cpu_overload": 0.20, "link_congestion": 0.15}
    status_sparse, p_set_sparse, _ = engine.predict_set(probs_sparse, top_prob_threshold=0.35)
    assert status_sparse == "insufficient_evidence"


# -----------------------------------------------------------------------------
# 5. Value-Based Unit Inference Decision Tree
# -----------------------------------------------------------------------------

def test_unit_inference_decision_tree() -> None:
    """Value-based inferencer identifies seconds vs ms and kbps vs Mbps from distributions."""
    inferencer = ValueUnitInferencer()

    # Fractional small latency (seconds)
    sec_vals = [0.015, 0.045, 0.082, 0.120]
    unit_s, conf_s = inferencer.infer_latency_unit(sec_vals)
    assert unit_s == "seconds"
    assert conf_s >= 0.80

    # Standard ms latency
    ms_vals = [12.5, 45.0, 120.0, 250.0]
    unit_ms, conf_ms = inferencer.infer_latency_unit(ms_vals)
    assert unit_ms == "ms"
    assert conf_ms >= 0.80

    # Large rate (kbps)
    kbps_vals = [50000.0, 85000.0, 100000.0]
    unit_k, conf_k = inferencer.infer_throughput_unit(kbps_vals)
    assert unit_k == "kbps"
    assert conf_k >= 0.80

    # Moderate rate (Mbps)
    mbps_vals = [50.0, 100.0, 450.0]
    unit_m, conf_m = inferencer.infer_throughput_unit(mbps_vals)
    assert unit_m == "mbps"
    assert conf_m >= 0.80


# -----------------------------------------------------------------------------
# 6. Generalization Check: Character n-gram Field Matching
# -----------------------------------------------------------------------------

def test_field_matcher_generalization_without_explicit_alias() -> None:
    """Generalization check: matcher alone maps cpu_utilization_pct to cpu_pct."""
    matcher = FieldNameMatcher(threshold=0.50)
    matched, score, is_conf = matcher.match_field("cpu_utilization_pct")
    assert matched == "cpu_pct"
    assert is_conf is True
    assert score >= 0.50


# -----------------------------------------------------------------------------
# 7. ClassifierAgent Envelope Processing
# -----------------------------------------------------------------------------

def test_classifier_agent_envelope_processing() -> None:
    """Verify ClassifierAgent receives envelope and returns findings with attribution."""
    agent = ClassifierAgent()
    header = ProtocolHeader(
        correlation_id="inc-test-b2-01",
        sender=AgentRole.ORCHESTRATOR,
        recipient=AgentRole.CLASSIFIER_AGENT,
        message_type=MessageType.TELEMETRY_DISPATCH,
    )
    payload = EnvelopePayload(
        scope=NetworkScope(network_id="lab-net", devices=["core-rtr-01"]),
        raw_data={
            "telemetry": [
                {
                    "device_id": "core-rtr-01",
                    "cpu_pct": 98.5,
                    "memory_pct": 92.0,
                    "latency_ms": 110.0,
                    "queue_drops": 600,
                }
            ]
        },
    )
    envelope = AgentEnvelope(header=header, payload=payload)

    response = agent.handle_envelope(envelope)
    assert response.header.sender == AgentRole.CLASSIFIER_AGENT
    assert response.header.recipient == AgentRole.ORCHESTRATOR
    assert response.header.message_type == MessageType.FINDING_SUBMISSION

    # Verify hypotheses emitted with calibrated confidence
    assert len(response.payload.hypotheses) > 0
    top_hyp = response.payload.hypotheses[0]
    assert 0.0 <= top_hyp.confidence <= 1.0

    # Verify conformal set in data_quality
    dq = response.payload.data_quality
    assert "conformal_prediction_set" in dq
    assert "calibrated_probabilities" in dq
    assert "conformal_status" in dq
