# NetCoop AI Model Card: Learned Multi-Label Diagnostic Classifier

## 1. Model Details
- **Architecture**: Multi-Output Histogram-Based Gradient Boosting Classifier (`HistGradientBoostingClassifier`), with a multi-output `LogisticRegression` baseline.
- **Python / Environment**: Python 3.13 (`.venv`), scikit-learn 1.9.1.
- **Tree Ensemble Rationale**: scikit-learn's `HistGradientBoostingClassifier` was selected as the authoritative tree ensemble to avoid Windows OpenMP runtime DLL initialization barriers on Python 3.13 while providing native missing-value (`NaN`) handling.
- **Input Features**: 148 aggregated incident features derived from 14 physical/logical telemetry metrics (mean, p95, linear slope over time, delta vs nominal baseline, fraction missing) combined with topological upstream link utilization and neighbor error/loss metrics. Single-snapshot inputs have history-dependent features flagged and safely set to `NaN`.
- **Output**: Binary multi-label indicator across 8 canonical classes (allowing multi-cause compound faults and explicit normal operation recognition).

---

## 2. Confidence Architecture: Classifier vs Report Level

NetCoop AI strictly distinguishes between two levels of confidence:
1. **Classifier-Level Confidence**: The calibrated posterior probability $p(c \mid X) \in [0.0, 1.0]$ output by the learned layer (`ClassifierAgent`). It reflects empirical frequency of correctness for individual feature signatures.
2. **Report-Level Confidence**: The composite confidence score rendered in the unified diagnostic report (`run_diagnosis`). It blends domain specialist corroboration (telemetry, topology, config, logs) with the calibrated classifier probability according to verified domain weights (`weights.json`).

---

## 3. Training Data and Split Methodology

- **Data Source**: Seeded synthetic incident telemetry generated via `SyntheticNetworkGenerator` across 12 distinct operational scenarios (nominal, link congestion, weak Wi-Fi, Ethernet interface CRC flaps, DNS service failures, DHCP exhaustion, router CPU overload, upstream cascade failure, ambiguous multi-fault, sparse insufficient data, and two compound fault variants).
- **Zero Training on Organizer Data**: Organizer Colab telemetry is strictly held out as an external test set and never exposed during training or calibration.
- **Statistically Defensible Seed-Disjoint Partitioning** (`netcoop/models/splits.py`):
  - **Train Partition (`TRAIN_SPEC`)**: Seeds 1 to 200 (2,400 runs), low and medium severity ranges, Gaussian and Uniform noise distributions. Fits the base multi-label classifier.
  - **Calibrator-Fit Partition (`CALIBRATOR_FIT_SPEC`)**: Seeds 201 to 225 (300 runs), held out from base training. Fits the production `ProbabilityCalibrator` using fixed classifier predictions.
  - **Conformal Calibration Partition (`CONFORMAL_CALIB_SPEC`)**: Seeds 226 to 250 (300 runs), strictly disjoint from the calibrator fitting split. Computes nonconformity scores and conformal quantile $\hat{q}_\alpha$ using the exact deployed production transformation.
  - **Validation Partition (`VALIDATION_SPEC`)**: Seeds 251 to 300 (600 runs), high severity range, Burst noise distribution. Used for empirical precision cutoff derivation and monotonicity enforcement.
  - **Test Partition (`TEST_SPEC`)**: Seeds 301 to 360 (720 runs), high and critical severity, high missingness (20-60%), unseen parameter ranges. Evaluates test set coverage and ECE.
- **Seed Overlap**: Asserted at zero across all partitions (`len(seed_A ∩ seed_B) == 0`).

---

## 4. Calibration and Conformal Prediction

- **Calibration Engine**: Per-class isotonic regression (`ProbabilityCalibrator` in `netcoop/models/calibration.py`).
- **Conformal Abstention Engine**: Split conformal prediction with significance level $\alpha = 0.10$ guaranteeing $\ge 90\%$ finite-sample marginal coverage under exchangeability.
- **Finite-Sample Order Statistic**:
  $$k = \lceil (n + 1)(1 - \alpha) \rceil, \quad \hat{q} = s_{(k)}$$
  Preserves the actual finite-sample order statistic without arbitrary heuristic quantile clipping. If $k > n$, empirical guarantees cannot be established without extrapolation; the engine flags `is_calibrated = False` and safely abstains.
- **Nonconformity Formulation**:
  $$s_i = 1 - \min_{y \in Y_i} p_i(y)$$
  where $Y_i$ is the true set of active classes, guaranteeing multi-label set coverage $Y_i \subseteq C(X_i)$.
- **Conformal Prediction Set**:
  $$C(X) = \{ c \mid p(c) \ge 1 - \hat{q} \}$$
- **Decision & Abstention Rules**:
  - **$|C(X)| = 1$**: Single decisive fault cause $\to$ Status `diagnosed`.
  - **$|C(X)| > 1$**: Competing hypotheses satisfy confidence $\to$ Status `ambiguous` (reported as competing alternatives).
  - **Normal Operation**: Positive evidence that `normal_operation` satisfies threshold ($p(\text{normal}) \ge 1 - \hat{q}$) with zero active fault predictions $\to$ Status `benign`.
  - **$|C(X)| = 0$ or top score $< 0.35$**: Status `insufficient_evidence` (disciplined abstention).
  - **Uncalibrated or Missing Engine**: Status safely falls back to `insufficient_evidence` with confidence 0.0 and empty prediction set.

---

## 5. Empirically Derived Confidence Categories (`docs/confidence.md`)

Cutoffs are computed by scanning validation holdout precision curves:
- **HIGH**: Precision $\ge 95\% \to \tau = 0.800$ (Observed precision: 98.0%, status: `estimated`)
- **MEDIUM**: Precision $\ge 85\% \to \tau = 0.600$ (Observed precision: 97.0%, status: `estimated`)
- **LOW**: Precision $\ge 70\% \to \tau = 0.400$ (Observed precision: 97.0%, status: `estimated`)

Monotonicity ($\tau_{\text{high}} > \tau_{\text{medium}} > \tau_{\text{low}}$) is strictly enforced, and empirical precisions and sample counts are recomputed on the validation set for the final adjusted thresholds.

---

## 6. Limitations and Out-of-Distribution Behavior
- **Exchangeability Requirement**: Conformal coverage guarantees hold strictly under exchangeability between calibration and production distributions.
- **Distribution Shift**: When presented with unprecedented topologies, alternative edge configurations, or organizer telemetry, the exchangeability assumption does not hold. Under distribution shift, the prediction set collapses to empty or yields diffuse probabilities, causing disciplined fallback to status `insufficient_evidence`, preventing false alarm hallucinations.
- **Remediation Boundary**: Predictions are informational findings feeding into the orchestrator; remediation plans are strictly simulated and real network infrastructure is never modified automatically.
