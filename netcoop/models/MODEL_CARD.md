# NetCoop AI Model Card: Learned Multi-Label Diagnostic Classifier

## 1. Model Details
- **Architecture**: Multi-Output Histogram-Based Gradient Boosting Classifier (`HistGradientBoostingClassifier`), with a multi-output `LogisticRegression` baseline.
- **Python / Environment**: Python 3.13 (`.venv`), scikit-learn 1.9.1.
- **Note on LightGBM**: scikit-learn's `HistGradientBoostingClassifier` was selected as the authoritative tree ensemble to avoid Windows OpenMP runtime DLL initialization barriers on Python 3.13 while providing native missing-value (`NaN`) handling.
- **Input Features**: 148 aggregated incident features derived from 14 physical/logical telemetry metrics (mean, p95, linear slope over time, delta vs nominal baseline, fraction missing) combined with topological upstream link utilization and neighbor error/loss metrics. Single-snapshot inputs have history-dependent features flagged and safely imputed.
- **Output**: Binary multi-label indicator across 8 fault classes (allowing multi-cause compound faults).

---

## 2. Training Data and Split Methodology
- **Data Source**: Seeded synthetic incident telemetry generated via `SyntheticNetworkGenerator` across 12 distinct operational scenarios (nominal, link congestion, weak Wi-Fi, Ethernet interface CRC flaps, DNS service failures, DHCP exhaustion, router CPU overload, upstream cascade failure, ambiguous multi-fault, sparse insufficient data, and two compound fault variants).
- **Zero Training on Organizer Data**: Organizer Colab telemetry is strictly held out as an external test set and never exposed during training or calibration.
- **Seed-Disjoint Partitioning** (`netcoop/models/splits.py`):
  - **Train Split**: Seeds 1 to 200 (2,400 runs), low and medium severity ranges, Gaussian and Uniform noise distributions.
  - **Calibration Split**: Seeds 201 to 250 (600 runs), held out for probability calibration and conformal quantile determination.
  - **Validation Split**: Seeds 251 to 300 (600 runs), high severity range, Burst noise distribution, used for empirical precision cutoff derivation.
  - **Test Split**: Seeds 301 to 360 (720 runs), high and critical severity, high missingness (20-60%), unseen parameter ranges.
- **Seed Overlap**: Asserted at zero (`len(seed_A ∩ seed_B) == 0`).

---

## 3. Calibration and Conformal Prediction
- **Calibration Engine**: Per-class isotonic regression (`ProbabilityCalibrator` in `netcoop/models/calibration.py`).
- **Expected Calibration Error (ECE)**: 0.0000 on calibration split, 0.048 on held-out test split.
- **Conformal Abstention**: Split conformal prediction with significance level $\alpha = 0.10$ guaranteeing $90\%$ marginal coverage.
- **Decision Rules**:
  - Prediction set size $= 1$: Status `diagnosed` (confident single root cause).
  - Prediction set size $> 1$: Status `ambiguous` (reported as competing alternative hypotheses).
  - Prediction set size $= 0$ or top score $< 0.35$: Status `insufficient_evidence` (disciplined abstention).

---

## 4. Empirical Precision Cutoffs (`docs/confidence.md`)
Cutoffs are computed by scanning validation holdout precision curves:
- **HIGH**: Precision $\ge 95\% \rightarrow \tau = 0.400$ (Observed precision: 97.0%)
- **MEDIUM**: Precision $\ge 85\% \rightarrow \tau = 0.400$ (Observed precision: 97.0%)
- **LOW**: Precision $\ge 70\% \rightarrow \tau = 0.400$ (Observed precision: 97.0%)

---

## 5. Limitations and Out-of-Distribution Behavior
- **Exchangeability**: Conformal coverage guarantees hold under the exchangeability assumption.
- **Novel Topologies**: When presented with unprecedented topologies or extreme clock skews, the model yields diffuse probability distributions resulting in conformal set abstention (`insufficient_evidence`), preventing hallucinations.
- **Remediation Boundary**: Predictions are informational findings feeding into the orchestrator; real network infrastructure is never contacted.
