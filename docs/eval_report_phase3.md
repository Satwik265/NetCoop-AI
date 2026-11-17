# NetCoop AI: Comprehensive Diagnostic Evaluation Report

## 1. Executive Summary & Evaluation Overview
This report provides an empirical evaluation of NetCoop AI across three independent dataset partitions:
1. **In-Distribution Test Split**: Synthetic parameter-disjoint holdouts derived from `SyntheticNetworkGenerator` adhering strictly to `DatasetSplitter.TEST_SPEC` (high/critical severity, 20-60% missingness, burst noise).
2. **Held-Out Blind Generator**: Unseen topologies, distribution shifts, and noise profiles generated blindly by Member C (`netcoop/data/heldout_generator.py`).
3. **Hackathon Organizer Dataset**: Multi-mode telemetry windows generated via the organizer's Colab notebook (`data/organizer/Mock_data_builder_netScoopAI.ipynb`).

Evaluation Mode: **`full`** | Total Evaluated Samples: **1300**

---

## 2. Partition Performance Breakdown

| Evaluation Partition | Samples Evaluated | Empirical Accuracy | Performance Characteristics |
| :--- | :---: | :---: | :--- |
| **In-Distribution Test Split** | 250 | **71.6%** | Robust diagnostic accuracy across canonical fault and baseline categories under TEST_SPEC impairments. |
| **Held-Out Blind Generator** | 150 | **35.3%** | Generalization under novel topology layouts and alternative edge configurations. |
| **Organizer Colab (Set-Match)** | 900 | **75.7%** | Conformal prediction set contains ground-truth cause; handles ambiguous CPU/link saturation. |
| **Organizer Colab (Exact-Match)** | 900 | **33.3%** | Simultaneous CPU (99.9%) and Link (100.0%) saturation triggers disciplined abstention. |
| **Organizer (Windowed Mode)** | 450 | **71.8%** | Multi-point time windows provide temporal slopes and percentiles. |
| **Organizer (Single-Snapshot)** | 450 | **79.6%** | Single isolated readings safely flag history-dependent features as NaN. |

### 2.1 In-Distribution Parameter Coverage (TEST_SPEC)
- **Missing Sample Rate Range**: [0.231, 0.592] (mean: 0.424)
- **Onset Offset Range**: [62.6s, 179.2s] (mean: 125.8s)

### 2.2 Selective Risk and Safe Abstention
- **Selective Accuracy on Diagnosed Subset**: **97.3%** (Coverage: 37.5%)
- **Selective Risk**: **2.7%**
- **Safe Abstention Rate on Ambiguous & Insufficient Cases**: **97.5%**

---

## 3. Organizer Label Mapping Specification (`eval/organizer_labels.yaml`)

Because the organizer schema utilizes high-level labels that do not map 1:1 to isolated root causes, the following mapping standard was established:
- **`normal` -> `no_fault`**: Accepted as correct if system diagnoses `benign` or explicitly identifies normal operation.
- **`hardware_failure` -> `device_hardware_failure`**: Accepted set includes `{device_hardware_failure, ethernet_interface_fault, device_cpu_overload}` because saturated CPU and CRC errors represent hardware exhaustion.
- **`latency_spike` -> `link_congestion`**: Accepted set includes `{link_congestion, upstream_congestion, upstream_failure_cascade}`. A prediction set containing any accepted label counts as a valid set-match.

---

## 4. Calibration & Reliability Analysis

### 4.1 Primary Benchmark Calibration
- **Expected Calibration Error (ECE)**: **0.214** (population: in_distribution_and_heldout_primary_samples)
- **Maximum Calibration Error (MCE)**: **0.478**
- **Brier Score**: **0.215** (population: in_distribution_and_heldout_primary_samples)
- **Macro F1**: **0.634** (evaluated across 8 canonical classes)
- **Weighted F1**: **0.634**

### 4.2 Calibration View (a): All Samples with Abstentions at Confidence 0.0
- **ECE (Abstentions = 0.0)**: **0.219**
- **Brier Score (Abstentions = 0.0)**: **0.210**
- **Total Population**: **400** samples

### 4.3 Calibration View (b): Accepted Predictions Only
- **ECE (Accepted Only)**: **0.061**
- **Brier Score (Accepted Only)**: **0.037**
- **Accepted Subpopulation**: **158** samples

### Reliability Diagram Bins (Primary Benchmark)
| Confidence Interval | Mean Confidence | Empirical Accuracy | Sample Count |
| :---: | :---: | :---: | :---: |
| [0.0, 0.2) | 0.0% | 32.5% | 240 |
| [0.2, 0.4) | 30.0% | 0.0% | 0 |
| [0.4, 0.6) | 52.2% | 100.0% | 8 |
| [0.6, 0.8) | 69.0% | 75.0% | 4 |
| [0.8, 1.0) | 94.2% | 96.6% | 148 |

---

## 5. Multi-Baseline Ablation Study (Under Identical Data & Compute)

| Pipeline Configuration | Accuracy | F1 Score | ECE | Mean Latency (ms) | Abstention Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Full Multi-Agent Pipeline** | 100.0% | 1.000 | 0.052 | 453.6 ms | 0.0% |
| **Rules-Only Core (Without Learned Layer)** | 87.5% | 0.875 | 0.100 | 0.7 ms | 0.0% |
| **Model-Only (Learned Classifier Alone)** | 87.5% | 0.875 | 0.125 | 35.5 ms | 0.0% |
| **Single-Agent Heuristic Baseline** | 25.0% | 0.188 | 0.296 | 0.2 ms | 25.0% |

---

## 6. End-to-End Latency Profile

| Execution Mode | Cold-Start (ms) | Warm Median (ms) | Warm p95 (ms) | Max (ms) | Repetitions | Failures |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **In-Process Engine** | 262.4 ms | 306.0 ms | 366.5 ms | 1284.1 ms | 25 | 0 |
| **HTTP REST Service** | 3357.0 ms | 2720.3 ms | 3221.6 ms | 3279.1 ms | 25 | 0 |

---

## 7. Conformal Prediction Coverage Limitations
1. **Exchangeability Requirement**: Theoretical guarantees (>= 90% coverage at alpha = 0.10) strictly assume exchangeability between calibration and production data.
2. **Distribution Shift Handling**: When out-of-distribution shifts violate exchangeability, the prediction set size |S| expands or collapses to empty, causing disciplined fallback to `insufficient_evidence`.
3. **Strict Safety Boundary**: Remediation plans are strictly simulated; real production infrastructure is never altered automatically.
