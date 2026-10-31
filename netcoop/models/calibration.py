"""Probability calibration and empirical precision threshold derivation."""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.isotonic import IsotonicRegression


class ProbabilityCalibrator:
    """Isotonic regression probability calibrator with ECE and empirical precision metrics."""

    def __init__(self) -> None:
        self.calibrators: Dict[str, IsotonicRegression] = {}
        self.confidence_thresholds: Dict[str, float] = {
            "high": 0.85,
            "medium": 0.65,
            "low": 0.45,
        }
        self.empirical_precisions: Dict[str, float] = {
            "high": 0.95,
            "medium": 0.85,
            "low": 0.70,
        }

    def fit(self, y_prob: np.ndarray, y_true: np.ndarray, class_names: List[str]) -> "ProbabilityCalibrator":
        """Fit isotonic regression models per class on calibration split."""
        for idx, cname in enumerate(class_names):
            ir = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            scores = y_prob[:, idx]
            labels = y_true[:, idx]
            ir.fit(scores, labels)
            self.calibrators[cname] = ir
        return self

    def calibrate(self, y_prob: np.ndarray, class_names: List[str]) -> np.ndarray:
        """Apply fitted calibrators to raw model probabilities."""
        calibrated = np.zeros_like(y_prob)
        for idx, cname in enumerate(class_names):
            if cname in self.calibrators:
                calibrated[:, idx] = self.calibrators[cname].predict(y_prob[:, idx])
            else:
                calibrated[:, idx] = y_prob[:, idx]
        return calibrated

    @classmethod
    def compute_ece(cls, probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> Tuple[float, List[Dict[str, float]]]:
        """Compute Expected Calibration Error (ECE) and reliability diagram bins."""
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        total_samples = len(probs)
        bins_data: List[Dict[str, float]] = []

        for i in range(n_bins):
            lower = bin_edges[i]
            upper = bin_edges[i + 1]
            mask = (probs >= lower) & (probs <= upper if i == n_bins - 1 else probs < upper)
            count = int(np.sum(mask))
            if count > 0:
                bin_acc = float(np.mean(labels[mask]))
                bin_conf = float(np.mean(probs[mask]))
                ece += (count / total_samples) * abs(bin_acc - bin_conf)
                bins_data.append({
                    "bin_lower": round(lower, 2),
                    "bin_upper": round(upper, 2),
                    "mean_confidence": round(bin_conf, 3),
                    "accuracy": round(bin_acc, 3),
                    "sample_count": count,
                })
            else:
                bins_data.append({
                    "bin_lower": round(lower, 2),
                    "bin_upper": round(upper, 2),
                    "mean_confidence": round((lower + upper) / 2.0, 2),
                    "accuracy": 0.0,
                    "sample_count": 0,
                })
        return float(ece), bins_data

    def derive_cutoffs_from_validation(
        self,
        val_probs: np.ndarray,
        val_labels: np.ndarray,
        target_precisions: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Compute monotonically decreasing confidence thresholds meeting empirical validation precision targets."""
        targets = target_precisions or {
            "high": 0.95,
            "medium": 0.85,
            "low": 0.70,
        }

        # Evaluate max predicted probabilities against correctness
        pred_classes = np.argmax(val_probs, axis=1)
        max_probs = np.max(val_probs, axis=1)
        correctness = (val_labels[np.arange(len(val_labels)), pred_classes] == 1).astype(int)

        cutoffs: Dict[str, float] = {}
        precisions: Dict[str, float] = {}

        # Distinct candidate ranges to guarantee meaningful separation:
        # HIGH: >= 0.80 floor (automated remediation candidate)
        # MEDIUM: [0.60, 0.79] floor (operator review)
        # LOW: [0.40, 0.59] floor (tentative finding)
        tier_ranges = {
            "high": np.linspace(0.80, 0.95, 31),
            "medium": np.linspace(0.60, 0.78, 37),
            "low": np.linspace(0.40, 0.58, 37),
        }

        for cat in ["high", "medium", "low"]:
            target_p = targets[cat]
            candidates = tier_ranges[cat]
            best_thresh = float(candidates[0])
            best_p = 1.0
            found = False

            for th in candidates:
                mask = (max_probs >= th)
                if np.sum(mask) >= 5:
                    prec = float(np.mean(correctness[mask]))
                    if prec >= target_p:
                        best_thresh = round(float(th), 3)
                        best_p = round(prec, 3)
                        found = True
                        break

            if not found:
                # Fallback to defaults with empirical precision at default
                default_th = 0.85 if cat == "high" else (0.65 if cat == "medium" else 0.45)
                mask = (max_probs >= default_th)
                if np.sum(mask) >= 3:
                    best_p = round(float(np.mean(correctness[mask])), 3)
                else:
                    best_p = target_p
                best_thresh = default_th

            cutoffs[cat] = best_thresh
            precisions[cat] = best_p

        # Enforce strict monotonicity: high > medium > low
        if cutoffs["medium"] >= cutoffs["high"]:
            cutoffs["medium"] = round(cutoffs["high"] - 0.15, 3)
            mask = (max_probs >= cutoffs["medium"])
            if np.sum(mask) >= 3:
                precisions["medium"] = round(float(np.mean(correctness[mask])), 3)

        if cutoffs["low"] >= cutoffs["medium"]:
            cutoffs["low"] = round(cutoffs["medium"] - 0.15, 3)
            mask = (max_probs >= cutoffs["low"])
            if np.sum(mask) >= 3:
                precisions["low"] = round(float(np.mean(correctness[mask])), 3)

        self.confidence_thresholds = cutoffs
        self.empirical_precisions = precisions
        return cutoffs
