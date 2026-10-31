"""Split conformal prediction and uncertainty-aware abstention."""

import math
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np


class ConformalAbstentionEngine:
    """Computes conformal prediction sets and governs disciplined abstention."""

    def __init__(self, alpha: float = 0.10) -> None:
        self.alpha = alpha  # Target error rate: 10% (90% coverage guarantee)
        self.q_hat: Optional[float] = None
        self.calibration_size: int = 0
        self._is_calibrated: bool = False

    @property
    def is_calibrated(self) -> bool:
        """Indicate whether the conformal engine has been calibrated with valid guarantees."""
        if self._is_calibrated:
            return True
        return self.q_hat is not None and 0.0 <= self.q_hat <= 1.0

    @is_calibrated.setter
    def is_calibrated(self, value: bool) -> None:
        self._is_calibrated = bool(value)

    def fit_calibration(
        self,
        calib_probs: np.ndarray,
        calib_labels: np.ndarray,
        class_names: Optional[List[str]] = None,
    ) -> float:
        """Compute conformal nonconformity threshold on held-out calibration split.

        To guarantee exact multi-label set coverage Y subseteq C(X) with probability >= 1 - alpha
        under exchangeability, the nonconformity score is:
            s_i = 1 - min_{y in Y_i} p_i(y)
        so that every ground-truth label satisfies p_i(y) >= 1 - q_hat.
        """
        n = len(calib_probs)
        self.calibration_size = n
        if n == 0:
            self._is_calibrated = False
            self.q_hat = None
            return 1.0

        normal_idx = None
        if class_names and "normal_operation" in class_names:
            normal_idx = class_names.index("normal_operation")

        fault_indices = (
            [c for c in range(len(class_names)) if class_names[c] != "normal_operation"]
            if class_names
            else list(range(calib_probs.shape[1]))
        )

        # Extract nonconformity score per sample
        scores: List[float] = []
        for i in range(n):
            pos_indices = np.where(calib_labels[i] == 1)[0]
            if len(pos_indices) > 0:
                # Set-coverage nonconformity score: 1 - min probability among true classes
                min_prob = float(np.min(calib_probs[i, pos_indices]))
                scores.append(1.0 - min_prob)
            else:
                # Empty true positive fault set (insufficient data / no-fault case)
                # Nonconformity is highest false alarm probability assigned to any fault
                max_fault_p = float(np.max(calib_probs[i, fault_indices])) if fault_indices else 0.0
                scores.append(max_fault_p)

        scores.sort()
        # Finite-sample quantile order statistic index k = ceil((n + 1) * (1 - alpha))
        k = int(math.ceil((n + 1) * (1.0 - self.alpha)))

        # Finite-sample validity check: if k > n, empirical guarantee cannot be established
        if k > n:
            self._is_calibrated = False
            self.q_hat = None
            return 1.0

        raw_q = float(scores[k - 1])
        # Preserve actual finite-sample order statistic without arbitrary heuristic clipping
        self.q_hat = round(raw_q, 4)
        self._is_calibrated = True
        return self.q_hat

    def predict_set(
        self,
        class_probs: Dict[str, float],
        top_prob_threshold: float = 0.35,
    ) -> Tuple[str, List[str], float]:
        """Predict conformal prediction set for a single test sample.

        Returns:
            (status, prediction_set, confidence)
            status: 'diagnosed', 'ambiguous', 'benign', or 'insufficient_evidence'
        """
        # If uncalibrated or missing quantile, safely abstain
        if not self.is_calibrated or self.q_hat is None:
            return "insufficient_evidence", [], 0.0

        # Conformal inclusion threshold: classes where p(c) >= 1 - q_hat
        min_p = max(0.0, 1.0 - self.q_hat)

        prediction_set: List[str] = [
            c for c, p in class_probs.items() if p >= min_p and c != "normal_operation"
        ]

        top_score = max(class_probs.values()) if class_probs else 0.0

        # Normal operation: positive evidence that normal_operation meets threshold with no active fault hypotheses
        normal_prob = class_probs.get("normal_operation", 0.0)
        if normal_prob >= min_p and len(prediction_set) == 0:
            return "benign", ["normal_operation"], round(normal_prob, 3)

        # Insufficient data: low top probability or prediction set contains no supported causes
        if top_score < top_prob_threshold or len(prediction_set) == 0:
            return "insufficient_evidence", prediction_set, round(top_score, 3)

        if len(prediction_set) == 1:
            return "diagnosed", prediction_set, round(class_probs[prediction_set[0]], 3)

        # Size > 1 means ambiguous multiple causes
        return "ambiguous", prediction_set, round(top_score, 3)
