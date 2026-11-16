"""Out-of-Distribution (OOD) Gate fitted on training feature representations.

Combines feature-range bounds and regularized Mahalanobis distance to detect
distribution shift, unseen topology scales, or novel metric patterns.
"""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np


class OODGate:
    """Out-of-distribution detector using feature-range bounds and PCA-regularized Mahalanobis distance."""

    def __init__(
        self,
        range_margin: float = 0.25,
        pca_components: int = 15,
        distance_quantile: float = 99.0,
        distance_multiplier: float = 1.35,
    ):
        self.range_margin = range_margin
        self.pca_components = pca_components
        self.distance_quantile = distance_quantile
        self.distance_multiplier = distance_multiplier

        # Fitted parameters
        self.feature_names: List[str] = []
        self.min_bounds: Optional[np.ndarray] = None
        self.max_bounds: Optional[np.ndarray] = None
        self.mean_vector: Optional[np.ndarray] = None
        self.pca_components_matrix: Optional[np.ndarray] = None
        self.pca_inv_cov: Optional[np.ndarray] = None
        self.threshold: float = float("inf")
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> "OODGate":
        """Fit feature ranges, centroid, and regularized covariance on training data."""
        X_clean = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)
        n_samples, n_features = X_clean.shape

        if feature_names is not None:
            self.feature_names = list(feature_names)
        else:
            self.feature_names = [f"feat_{i}" for i in range(n_features)]

        # 1. Feature ranges with margin
        mins = np.min(X_clean, axis=0)
        maxs = np.max(X_clean, axis=0)
        ranges = np.maximum(maxs - mins, 1.0)
        self.min_bounds = mins - self.range_margin * ranges
        self.max_bounds = maxs + self.range_margin * ranges

        # 2. PCA + Mahalanobis projection for high-dimensional stability
        self.mean_vector = np.mean(X_clean, axis=0)
        X_centered = X_clean - self.mean_vector

        # Truncated SVD / PCA
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        k = min(self.pca_components, len(S), n_features)
        self.pca_components_matrix = Vt[:k, :]  # shape: (k, n_features)

        # Projected features: shape (n_samples, k)
        X_proj = X_centered @ self.pca_components_matrix.T

        # Covariance in PCA subspace with ridge regularization
        cov_proj = np.cov(X_proj, rowvar=False)
        if cov_proj.ndim == 0:
            cov_proj = np.array([[cov_proj]])
        reg_eye = np.eye(k) * 1e-2 * float(np.trace(cov_proj) / max(1, k))
        self.pca_inv_cov = np.linalg.pinv(cov_proj + reg_eye)

        # 3. Fit distance threshold on training samples
        train_distances = [self._compute_distance(x) for x in X_clean]
        base_thresh = float(np.percentile(train_distances, self.distance_quantile))
        self.threshold = base_thresh * self.distance_multiplier
        self.is_fitted = True
        return self

    def _compute_distance(self, x: np.ndarray) -> float:
        """Compute regularized Mahalanobis distance in PCA subspace."""
        x_clean = np.nan_to_num(x, nan=0.0, posinf=1e6, neginf=-1e6)
        diff = (x_clean - self.mean_vector).reshape(1, -1)
        diff_proj = diff @ self.pca_components_matrix.T  # (1, k)
        d_sq = diff_proj @ self.pca_inv_cov @ diff_proj.T
        return float(math.sqrt(max(0.0, float(d_sq[0, 0]))))

    def predict(self, x: np.ndarray) -> Tuple[bool, List[str], float]:
        """Evaluate if sample x is out of distribution.

        Returns:
            (is_ood, reasons, distance_score)
        """
        if not self.is_fitted:
            return False, [], 0.0

        x_1d = np.nan_to_num(x.flatten(), nan=0.0, posinf=1e6, neginf=-1e6)
        reasons: List[str] = []

        # 1. Mahalanobis distance check
        dist = self._compute_distance(x_1d)
        if dist > self.threshold:
            reasons.append(f"Mahalanobis distance {dist:.2f} exceeds threshold {self.threshold:.2f}")

        # 2. Extreme range violations on key topological features
        extreme_violations = 0
        for i, val in enumerate(x_1d):
            if val < self.min_bounds[i] or val > self.max_bounds[i]:
                fname = self.feature_names[i] if i < len(self.feature_names) else f"feat_{i}"
                if any(k in fname for k in ("devices", "count", "latency", "loss", "cpu")):
                    extreme_violations += 1
                    if len(reasons) < 3:
                        reasons.append(f"Feature '{fname}' value {val:.2f} outside [{self.min_bounds[i]:.2f}, {self.max_bounds[i]:.2f}]")

        if extreme_violations >= 3 and dist > self.threshold * 0.8:
            is_ood = True
        elif dist > self.threshold:
            is_ood = True
        else:
            is_ood = False

        return is_ood, reasons, dist

    def save(self, filepath: Path) -> None:
        """Save fitted OOD gate to disk."""
        joblib.dump(self, filepath)

    @classmethod
    def load(cls, filepath: Path) -> Optional["OODGate"]:
        """Load fitted OOD gate from disk."""
        if not filepath.exists():
            return None
        try:
            gate = joblib.load(filepath)
            return gate
        except Exception:
            return None
