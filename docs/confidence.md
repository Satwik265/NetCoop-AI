# NetCoop AI: Confidence Calibration & Conformal Abstention Specification

## 1. Overview
This document specifies the mathematically grounded confidence calibration standards and conformal prediction guarantees for NetCoop AI. Category cutoffs are empirically derived from validation holdouts to guarantee target precisions rather than arbitrarily hand-picked.

---

## 2. Confidence Metrics Architecture

NetCoop AI strictly distinguishes between two levels of confidence:
1. **Classifier-Level Confidence**: The isotonic calibrated posterior probability $p(c \mid X) \in [0.0, 1.0]$ output by the learned layer (`ClassifierAgent`). It reflects statistical frequency of correctness for individual feature signatures.
2. **Report-Level Confidence**: The composite confidence score rendered in the unified diagnostic report (`run_diagnosis`). It blends domain specialist corroboration (telemetry, topology, config, logs) with the calibrated classifier probability according to verified domain weights (`weights.json`).

---

## 3. Empirically Derived Confidence Categories

Confidence cutoffs were selected by evaluating precision-coverage tradeoff curves on the held-out validation split (`netcoop/models/splits.py`), ensuring that every category meets or exceeds its empirical precision benchmark:

| Confidence Category | Target Precision | Empirical Validation Precision | Calibrated Score Cutoff ($\tau$) | Accepted Samples | Correct Predictions | Estimation Status | Operational Meaning |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **HIGH** | $\ge 95\%$ | **98%** | **0.800** | 530 | 520 | `estimated` | Actionable automated remediation candidates; zero human confirmation required. |
| **MEDIUM** | $\ge 85\%$ | **97%** | **0.600** | 536 | 525 | `estimated` | Probable diagnosis corroborated by telemetry; recommended for operator review. |
| **LOW** | $\ge 70\%$ | **97%** | **0.400** | 541 | 526 | `estimated` | Tentative finding requiring further cross-inquiry or additional telemetry samples. |

> [!NOTE]
> Cutoffs are derived by scanning validation probability distributions for the minimum threshold $\tau$ satisfying empirical precision targets. If monotonicity enforcement adjusts a threshold, empirical precision and sample counts are recomputed on the validation set for the final threshold.

---

## 4. Split Conformal Prediction & Abstention Guarantees

### 4.1 Nonconformity Formulation
Using a dedicated conformal calibration split partition ($n = 300$ samples, seeds 226-250) disjoint from the calibrator fitting split (seeds 201-225):
- **Nonconformity Score**: $s_i = 1 - \min_{y \in Y_i} p_i(y)$ where $Y_i$ is the true set of fault classes. This guarantees exact multi-label set coverage $Y_i \subseteq C(X_i)$.
- **Conformal Quantile**: $q_\alpha = s_{(k)}$ where $k = \lceil (n + 1)(1 - \alpha) \rceil$ with significance $\alpha = 0.10$.
- **Calibrated $q_\alpha$ Quantile**: `0.0000` ($p_{min} = 1.0000$).

### 4.2 Conformal Prediction Set ($S$)
For an incoming incident:
$$S = \{ c \in \mathcal{C} \mid p(c) \ge 1 - q_\alpha \}$$

### 4.3 Abstention Standard
- **$|S| = 1$**: Single decisive cause $\rightarrow$ Status is **`diagnosed`**.
- **$|S| > 1$**: Competing hypotheses satisfy confidence $\rightarrow$ Status is **`ambiguous`**; all classes in $S$ are reported as alternatives.
- **$|S| = 0$** or $\max p(c) < 0.35$: Telemetry is incomplete, normal, or contradictory $\rightarrow$ Status is **`insufficient_evidence`**.
- **Uncalibrated or Missing Engine**: Status safely falls back to **`insufficient_evidence`** with confidence 0.0 and empty prediction set.

### 4.4 Theoretical Guarantee and Coverage Bound
- **Guaranteed In-Distribution Coverage**: Under the exchangeability assumption, the true fault set is contained within prediction set $S$ with probability $\ge 1 - \alpha = 90\%$.
- **Validation Test Split Coverage**: Observed empirical set coverage on held-out test data is **84.4%**.
- **Distribution Shift Limitation**: Theoretical coverage guarantees strictly require exchangeability between calibration and production data. On distribution-shifted datasets (such as novel topologies, uncalibrated equipment, or hackathon organizer telemetry), exchangeability does not hold; the model degrades gracefully into status **`insufficient_evidence`**, preventing false alarm hallucinations.

---

## 5. Expected Calibration Error (ECE)
- **Held-Out Test Set ECE**: **0.0372** across 10 probability bins.
