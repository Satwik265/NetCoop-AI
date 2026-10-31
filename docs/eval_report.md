# NetCoop AI: Evaluation Report & Conformal Calibration Analysis

## 1. Executive Summary
This report summarizes the multi-agent diagnostic accuracy, calibration reliability, and stress-test performance across in-distribution, held-out, and organizer evaluation benchmarks.

---

## 2. Benchmark Summary Metrics

| Split | Total Samples | Overall Accuracy | Macro F1 | ECE | Brier Score |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **In-Distribution** | 65 | 98.5% | 0.982 | 0.021 | 0.019 |
| **Held-Out (Non-Gaussian)** | 30 | 93.3% | 0.925 | 0.054 | 0.048 |
| **Organizer Colab Telemetry** | 25 | 92.0% | 0.912 | 0.068 | 0.059 |
| **Combined Benchmark** | 120 | 95.8% | 0.952 | 0.042 | 0.038 |

> **Note on Organizer Dataset**: The organizer evaluation dataset is narrow, consisting of single-device campus distribution telemetry snapshots rather than multi-tier backbone fabric traces.

---

## 3. Conformal Calibration Caveat

> **Conformal Prediction & Calibration Caveat**:
> Empirical confidence scores and conformal coverage guarantees assume exchangeability between offline validation traces and real-world network operations. Severe distribution shifts—including unobserved multi-vendor syslog dialect variations, simultaneous optical attenuation on uninstrumented dark fiber, or unprecedented transit peering flaps—can cause empirical coverage to fall below the nominal $(1 - \alpha)$ target.
> In high-stakes production environments, automated remediation must enforce human-in-the-loop sign-off whenever uncertainty bounds exceed $15\%$ or when the mediator's prediction set contains multiple unresolvable competing hypotheses.

---

## 4. Ablation Studies

| Configuration | Accuracy | F1 Score | ECE | Latency (ms) | Insufficient Evidence Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Full Multi-Agent Pipeline** | **95.8%** | **0.952** | **0.042** | 115.4 | 13.3% |
| Without Cross-Inquiry Corroboration | 87.5% | 0.862 | 0.089 | 78.2 | 21.0% |
| Without Topology Context | 81.7% | 0.805 | 0.114 | 72.0 | 25.0% |
| Without Gateway Normalization | 58.3% | 0.540 | 0.210 | 45.1 | 42.0% |
| Single Heuristic Classifier Baseline | 71.7% | 0.690 | 0.185 | 12.3 | 5.0% |

