"""Value-based unit inference using statistical properties and decision trees."""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.tree import DecisionTreeClassifier


class ValueUnitInferencer:
    """Infers whether numeric telemetry fields are in seconds vs ms or kbps vs Mbps based on value distributions."""

    def __init__(self) -> None:
        self.clf = DecisionTreeClassifier(max_depth=4, random_state=42)
        self.is_fitted = False
        self._fit_default_tree()

    def _fit_default_tree(self) -> None:
        """Train decision tree on synthetic value distribution statistics."""
        # Feature vector: [median, p95, max, fraction_in_0_1, fraction_integer, field_group]
        # field_group: 0=time/latency, 1=rate/throughput
        # Labels: 0=ms, 1=seconds, 2=mbps, 3=kbps
        X: List[List[float]] = []
        y: List[int] = []

        np.random.seed(42)

        # 1. Latency in seconds (fractional small numbers <= 1.5)
        for _ in range(60):
            vals = np.random.uniform(0.005, 1.2, 15)
            X.append([float(np.median(vals)), float(np.percentile(vals, 95)), float(np.max(vals)), 1.0, 0.0, 0.0])
            y.append(1)  # seconds

        # 2. Latency in milliseconds (numbers > 2.0 up to 2500)
        for _ in range(60):
            vals = np.random.uniform(5.0, 1500.0, 15)
            X.append([float(np.median(vals)), float(np.percentile(vals, 95)), float(np.max(vals)), 0.0, 0.0, 0.0])
            y.append(0)  # ms

        # 3. Throughput in kbps (large numbers 3,000 to 1,000,000+)
        for low, high in [(3000, 15000), (15000, 60000), (60000, 250000), (250000, 1000000)]:
            for _ in range(20):
                vals = np.random.uniform(low, high, 15)
                X.append([float(np.median(vals)), float(np.percentile(vals, 95)), float(np.max(vals)), 0.0, 0.0, 1.0])
                y.append(3)  # kbps

        # 4. Throughput in Mbps (moderate numbers 0.5 to 2,500)
        for low, high in [(0.5, 50), (50, 300), (300, 1000), (1000, 2500)]:
            for _ in range(20):
                vals = np.random.uniform(low, high, 15)
                X.append([float(np.median(vals)), float(np.percentile(vals, 95)), float(np.max(vals)), 0.0, 0.0, 1.0])
                y.append(2)  # mbps

        self.clf.fit(np.array(X), np.array(y))
        self.is_fitted = True

    @classmethod
    def extract_value_stats(cls, values: List[float], field_group: int) -> np.ndarray:
        """Extract statistical features from a series of values."""
        clean = [float(v) for v in values if v is not None and not (math.isnan(v) or math.isinf(v))]
        if not clean:
            return np.array([0.0, 0.0, 0.0, 0.0, 0.0, float(field_group)])

        arr = np.array(clean)
        med = float(np.median(arr))
        p95 = float(np.percentile(arr, 95))
        max_v = float(np.max(arr))
        frac_0_1 = float(np.mean((arr >= 0.0) & (arr <= 1.0)))
        frac_int = float(np.mean(np.floor(arr) == arr))
        return np.array([med, p95, max_v, frac_0_1, frac_int, float(field_group)])

    def infer_latency_unit(self, values: List[float]) -> Tuple[str, float]:
        """Infer whether latency values are in seconds or milliseconds.

        Returns:
            ('seconds' or 'ms', confidence)
        """
        feats = self.extract_value_stats(values, field_group=0).reshape(1, -1)
        pred = self.clf.predict(feats)[0]
        probs = self.clf.predict_proba(feats)[0]
        conf = float(np.max(probs))
        unit = "seconds" if pred == 1 else "ms"
        return unit, conf

    def infer_throughput_unit(self, values: List[float]) -> Tuple[str, float]:
        """Infer whether throughput values are in kbps or Mbps.

        Returns:
            ('kbps' or 'mbps', confidence)
        """
        feats = self.extract_value_stats(values, field_group=1).reshape(1, -1)
        pred = self.clf.predict(feats)[0]
        probs = self.clf.predict_proba(feats)[0]
        conf = float(np.max(probs))
        unit = "kbps" if pred == 3 else "mbps"
        return unit, conf
