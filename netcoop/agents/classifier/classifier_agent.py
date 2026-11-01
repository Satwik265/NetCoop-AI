"""ClassifierAgent: Learned and statistical multi-label classifier specialist agent."""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional
import warnings
import joblib
import numpy as np

from netcoop.agents.base import BaseAgent
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    Hypothesis,
    MessageType,
    Observation,
    ObservationCategory,
    Severity,
)
from netcoop.models.features import WindowFeatureExtractor
from netcoop.models.calibration import ProbabilityCalibrator
from netcoop.models.conformal import ConformalAbstentionEngine

ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "models" / "artifacts"

FAULT_DESCRIPTIONS = {
    "link_congestion": "Link utilization saturation causing buffer queue drops and latency spikes",
    "weak_wifi_signal": "Hostel access point RF attenuation causing high retransmissions and packet loss",
    "ethernet_interface_fault": "Physical layer Ethernet interface CRC errors and flapping transitions",
    "dns_failure": "DNS resolution service outage with high query timeout failure rate",
    "dhcp_failure": "DHCP scope exhaustion or relay failure preventing lease assignment",
    "device_cpu_overload": "Control-plane CPU exhaustion on core router driving queue drops",
    "upstream_failure_cascade": "Core router failure causing failover saturation on distribution links",
    "normal_operation": "Normal operational state across all zones",
}

CLASSES = [
    "link_congestion",
    "weak_wifi_signal",
    "ethernet_interface_fault",
    "dns_failure",
    "dhcp_failure",
    "device_cpu_overload",
    "upstream_failure_cascade",
    "normal_operation",
]


class ClassifierAgent(BaseAgent):
    """Learned classifier evaluating multi-device telemetry windows with conformal sets."""

    def __init__(
        self,
        name: str = "classifier_agent",
        model_path: Optional[Path] = None,
        calibrator_path: Optional[Path] = None,
        quantile_path: Optional[Path] = None,
        weights_path: Optional[Path] = None,
    ) -> None:
        super().__init__(role=AgentRole.CLASSIFIER_AGENT, name=name)
        self.model = None
        self.calibrator = None
        self.conformal_engine = ConformalAbstentionEngine(alpha=0.10)
        self.weights: Dict[str, float] = {}

        # 1. Load trained MultiOutput Classifier
        m_path = model_path or (ARTIFACTS_DIR / "classifier_model.joblib")
        if m_path.exists():
            try:
                self.model = joblib.load(m_path)
            except Exception:
                pass

        # 2. Load Probability Calibrator
        c_path = calibrator_path or (ARTIFACTS_DIR / "calibrator.joblib")
        if c_path.exists():
            try:
                self.calibrator = joblib.load(c_path)
            except Exception:
                pass

        # 3. Load Conformal Quantile
        q_path = quantile_path or (ARTIFACTS_DIR / "conformal_quantile.json")
        if q_path.exists():
            try:
                with open(q_path, "r", encoding="utf-8") as f:
                    q_data = json.load(f)
                    if "q_hat" in q_data and q_data["q_hat"] is not None:
                        self.conformal_engine.q_hat = float(q_data["q_hat"])
                        self.conformal_engine.is_calibrated = bool(q_data.get("is_calibrated", True))
                    else:
                        self.conformal_engine.q_hat = None
                        self.conformal_engine.is_calibrated = False
            except Exception:
                self.conformal_engine.q_hat = None
                self.conformal_engine.is_calibrated = False
        else:
            self.conformal_engine.q_hat = None
            self.conformal_engine.is_calibrated = False

        # 4. Load Ensembling Weights
        w_path = weights_path or (ARTIFACTS_DIR / "weights.json")
        if w_path.exists():
            try:
                with open(w_path, "r", encoding="utf-8") as f:
                    self.weights = json.load(f)
            except Exception:
                pass

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Process incoming raw telemetry, run inference, and return observations and hypotheses."""
        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)
        raw_data = envelope.payload.raw_data or {}

        # 1. Extract incident features
        matrix, dev_ids, metas = WindowFeatureExtractor.extract_incident_features(raw_data)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            feat_max = np.nanmax(matrix, axis=0)
            feat_mean = np.nanmean(matrix, axis=0)
            feat_max = np.nan_to_num(feat_max, nan=0.0)
            feat_mean = np.nan_to_num(feat_mean, nan=0.0)
        x = np.hstack([feat_max, feat_mean]).reshape(1, -1)

        # 2. Model prediction
        raw_probs: Dict[str, float] = {}
        if self.model is not None:
            try:
                prob_list = self.model.predict_proba(x)
                for c_idx, cname in enumerate(CLASSES):
                    c_probs = prob_list[c_idx]
                    p = float(c_probs[0, 1]) if c_probs.shape[1] == 2 else float(c_probs[0, 0])
                    raw_probs[cname] = p
            except Exception:
                raw_probs = {c: 0.1 for c in CLASSES}
        else:
            raw_probs = {c: 0.1 for c in CLASSES}

        # 3. Probability Calibration
        calib_probs = dict(raw_probs)
        if self.calibrator is not None:
            p_arr = np.array([[raw_probs[c] for c in CLASSES]], dtype=np.float32)
            cal_arr = self.calibrator.calibrate(p_arr, CLASSES)
            for c_idx, cname in enumerate(CLASSES):
                calib_probs[cname] = round(float(cal_arr[0, c_idx]), 3)

        # 4. Conformal Prediction Set & Abstention
        conformal_status, prediction_set, top_conf = self.conformal_engine.predict_set(calib_probs)

        # 5. Generate Observations (Feature Attribution Evidence)
        observations: List[Observation] = []
        feat_names = WindowFeatureExtractor.get_feature_names()

        # Find abnormal metrics across devices
        for d_idx, d_id in enumerate(dev_ids):
            d_vec = matrix[d_idx]
            for f_idx, f_name in enumerate(feat_names):
                val = d_vec[f_idx]
                if not math.isnan(val) and ("mean" in f_name or "p95" in f_name or "slope" in f_name):
                    # Flag notable anomalies
                    if (
                        ("loss" in f_name and val > 2.0)
                        or ("util" in f_name and val > 85.0)
                        or ("cpu" in f_name and val > 90.0)
                        or ("error" in f_name and val > 500)
                        or ("dns_fail" in f_name and val > 50.0)
                        or ("dhcp_fail" in f_name and val > 50.0)
                        or ("rssi" in f_name and val < -78.0)
                    ):
                        obs = Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=d_id,
                            metric_name=f_name,
                            observed_value=round(val, 2),
                            unit="percent" if "pct" in f_name or "frac" in f_name else "count",
                            severity=Severity.CRITICAL
                            if ("cpu" in f_name and val > 95.0) or ("util" in f_name and val > 95.0)
                            else Severity.WARNING,
                            confidence=round(top_conf, 2),
                            provenance={
                                "agent": "classifier_agent",
                                "model": "HistGradientBoosting",
                                "feature": f_name,
                            },
                        )
                        observations.append(obs)

        # 6. Generate Hypotheses: only if positive evidence exists (never emit exact fault diagnoses on empty/insufficient evidence)
        hypotheses: List[Hypothesis] = []
        if conformal_status != "insufficient_evidence" or len(prediction_set) > 0:
            active_classes = prediction_set if prediction_set else [max(calib_probs, key=calib_probs.get)]

            for cname in active_classes:
                prob = calib_probs.get(cname, 0.0)
                if prob >= 0.15:
                    hyp = Hypothesis(
                        probable_cause=FAULT_DESCRIPTIONS.get(cname, cname),
                        confidence=prob,
                        supporting_observation_ids=[o.observation_id for o in observations[:4]],
                        provenance={
                            "agent": "classifier_agent",
                            "conformal_status": conformal_status,
                            "calibrated": True,
                        },
                    )
                    hypotheses.append(hyp)

        response.payload.observations = observations
        response.payload.hypotheses = hypotheses
        response.payload.data_quality = {
            "calibrated_probabilities": calib_probs,
            "conformal_prediction_set": prediction_set,
            "conformal_status": conformal_status,
        }
        response.context["classifier_conformal_set"] = prediction_set
        return response
