"""Split conformal prediction and uncertainty-aware abstention."""

import math
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np


class ConformalAbstentionEngine:
    """Computes conformal prediction sets and governs abstention to 'insufficient_evidence'."""

    def __init__(self, alpha: float = 0.10) -> None:
        self.alpha = alpha  # Target error rate: 10% (90% coverage guarantee)
        self.q_hat: float = 0.85
        self.calibration_size: int = 0

    def fit_calibration(self, calib_probs: np.ndarray, calib_labels: np.ndarray) -> float:
        """Compute conformal nonconformity threshold on held-out calibration split.

        Nonconformity score: s_i = 1 - p(y_true)
        """
        n = len(calib_probs)
        self.calibration_size = n
        if n == 0:
            self.q_hat = 0.85
            return self.q_hat

        # Extract predicted probability assigned to ground truth positive class
        scores: List[float] = []
        for i in range(n):
            pos_indices = np.where(calib_labels[i] == 1)[0]
            if len(pos_indices) > 0:
                # Pick max probability among ground-truth positive classes
                best_prob = float(np.max(calib_probs[i, pos_indices]))
                nonconformity = 1.0 - best_prob
                scores.append(nonconformity)
            else:
                # Normal or no fault class
                scores.append(1.0 - float(calib_probs[i, 0]))

        scores.sort()
        # Quantile index at ceil((n + 1) * (1 - alpha)) / n
        idx = int(math.ceil((n + 1) * (1.0 - self.alpha))) - 1
        idx = max(0, min(n - 1, idx))
        self.q_hat = float(scores[idx])
        return self.q_hat

    def predict_set(
        self,
        class_probs: Dict[str, float],
        top_prob_threshold: float = 0.35,
    ) -> Tuple[str, List[str], float]:
        """Predict conformal set for a single test sample.

        Returns:
            (status, prediction_set, confidence)
            status: 'diagnosed', 'ambiguous', or 'insufficient_evidence'
        """
        # Threshold: classes where 1 - p(c) <= q_hat <=> p(c) >= 1 - q_hat
        min_p = max(0.05, 1.0 - self.q_hat)

        prediction_set: List[str] = [
            c for c, p in class_probs.items() if p >= min_p and c != "normal_operation"
        ]

        top_score = max(class_probs.values()) if class_probs else 0.0

        if top_score < top_prob_threshold or len(prediction_set) == 0:
            return "insufficient_evidence", prediction_set, round(top_score, 3)

        if len(prediction_set) == 1:
            return "diagnosed", prediction_set, round(class_probs[prediction_set[0]], 3)

        # Size > 1 means ambiguous multiple causes
        return "ambiguous", prediction_set, round(top_score, 3)
