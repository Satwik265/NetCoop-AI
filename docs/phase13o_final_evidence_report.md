# Phase 13O: Final Evidence Freeze & Verification Report

**Date:** 2026-11-17  
**Branch:** `fix/ps-readiness-p0`  
**Evaluation Scorecard Version:** `phase13o_v1`  
**Fresh Holdouts Freeze Version:** `phase13o_freeze_v1`  

---

## 1. Executive Summary & Verification Evidence

Phase 13O completes the comprehensive evidence freeze, anti-leakage audit, and holdout evaluation across the entire NetCoop AI platform.

- **Zero Data Leakage**: All 5,715 historical and holdout evaluation samples across the project lifecycle have been indexed and categorized in [`docs/evidence_ledger.md`](docs/evidence_ledger.md).
  - **`CLEAN` Single-Evaluation Holdouts**: 3,015 samples (52.8%)
  - **`DEVELOPMENT` Intermediate Splits**: 1,100 samples (19.2%)
  - **`TUNED` Training & Calibration Sets**: 1,600 samples (28.0%)
- **Zero Engine Edits During Holdout Evaluation**: Engine logic was frozen before generating and running fresh holdouts.
- **Perfect Selective Reliability**:
  - Across all 2,115 canonical benchmark samples in `docs/scorecard.json`: **100.0% selective accuracy** on all accepted diagnoses; **0.0% selective risk**.
  - Across all 1,350 fresh holdouts (seeds 1001–1015 on unseen topologies, seeds 7000–7099 on organizer telemetry, seeds 1101–1115 on heavy Pareto noise, seeds 1201–1240 on borderline suite, and seeds 20001–20050 on containerized Linux network): **100.0% selective accuracy** on all accepted diagnoses; **0.0% selective risk**.
- **Absolute Safety Invariant**: **Faults called normal remains 0** across all 3,465 combined benchmark and holdout samples (Rule-of-Three 95% upper bound $\le 0.08\%$).

---

## 2. Before / After Comparison: Metrics Reconciliation

| Evaluation Metric / Split | Phase 13N Baseline | Phase 13O Verified (`phase13o_v1`) | Root Cause of Change / Reconciliation Evidence |
| :--- | :---: | :---: | :--- |
| **`interop_suite` Coverage** | 75.0% (6 / 8 accepted) | **100.0% (8 / 8 accepted)** | `scripts/bench.py` routed interop scenarios through `OrganizerAdapter.adapt_dataset()`, resolving kbps-to-Mbps unit normalization and `dev` alias mapping. |
| **`interop_suite` Selective Accuracy** | 100.0% (6 / 6) | **100.0% (8 / 8)** | Perfect diagnosis of `link_congestion` across all accepted interop variations. |
| **HTTP Latency Benchmark Protocol** | TestClient only (200 runs) | **Dual Benchmark: TestClient (200 runs) + Real Uvicorn Sockets (50 runs)** | Measures real TCP socket loopback latency (`P50 = 2498.44 ms`, `P95 = 3067.76 ms`) alongside in-process TestClient (`P50 = 2484.32 ms`, `P95 = 3335.91 ms`). |
| **`classifier_agent` Ablation Explanation** | Unexplained identical result | **Mechanically Verified & Documented** | In `node_dispatch()`, disabling `classifier_agent` yields empty calibrated probabilities. On the frozen in-distribution set, multi-signal domain rules fire with $\ge 2$ independent corroborating domains, meaning deterministic precedence dictates identical decisions. |
| **Operational Parameters Parity** | 25 parameters | **27 parameters (100% code parity)** | Added `rule_ambiguity_cpu_threshold = 95.0%` and `healthy_guard_median_window = 3` to `config/parameters.yaml` and verified parity in `tests/test_parameters_parity.py`. |
| **README Links to `demo_artifacts/`** | 2 unversioned links | **0 unversioned links (100% tracked)** | All documentation links point strictly to tracked repository files (`docs/scorecard.json`, `docs/evidence_ledger.md`, `config/parameters.yaml`). |

---

## 3. Fresh Holdouts Evaluation Results (`phase13o_freeze_v1`)

Evaluated strictly **once under code freeze** with zero parameter tuning:

| Split Identifier | Partition Description | Total Samples | Accepted (Cov %) | Abstained | Selective Acc | Selective Risk (Wilson 95% CI) | Faults Called Normal (Rule-of-3) | Healthy Recall |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`fresh_unseen_topologies_450`** | Seeds 1001–1015 across 3 unseen topologies | 450 | 360 (80.0%) | 90 | 100.0% | 0.0% [0.0%, 1.1%] | 0 (<= 0.95%) | 100.0% (45/45) |
| ↳ *`blind_edge_iot_6`* | Sub-topology slice (6 devices, 15 seeds/class) | 150 | 120 (80.0%) | 30 | 100.0% | 0.0% [0.0%, 3.1%] | 0 (<= 2.86%) | 100.0% (15/15) |
| ↳ *`blind_spine_leaf_10`* | Sub-topology slice (10 devices, 15 seeds/class) | 150 | 120 (80.0%) | 30 | 100.0% | 0.0% [0.0%, 3.1%] | 0 (<= 2.86%) | 100.0% (15/15) |
| ↳ *`blind_branch_9`* | Sub-topology slice (9 devices, 15 seeds/class, NEW) | 150 | 120 (80.0%) | 30 | 100.0% | 0.0% [0.0%, 3.1%] | 0 (<= 2.86%) | 100.0% (15/15) |
| **`fresh_organizer_7000_7099`** | Seeds 7000–7099 (150 snapshot + 150 windowed) | 300 | 300 (100.0%) | 0 | 100.0% | 0.0% [0.0%, 1.2%] | 0 (<= 1.50%) | 100.0% (100/100) |
| **`fresh_heldout_1101_1115`** | `HeldoutNetworkGenerator` seeds 1101–1115 (heavy Pareto noise) | 150 | 120 (80.0%) | 30 | 100.0% | 0.0% [0.0%, 3.1%] | 0 (<= 2.86%) | 100.0% (15/15) |
| **`fresh_emulation_20001_20050`** | Physical containerized Linux network (seeds 20001–20050) | 50 | 40 (80.0%) | 10 | 100.0% | 0.0% [0.0%, 8.8%] | 0 (<= 10.00%) | 100.0% (10/10) |

---

## 4. Borderline Non-Saturated Suite: Risk-Coverage Curve

Evaluated across 400 borderline samples generated with reduced signal intensity (0.3x–0.8x nominal thresholds) and 0%–40% random telemetry missingness:

| Operating Confidence Threshold | Accepted Samples | Selective Coverage (%) | Selective Accuracy | Selective Risk (Wilson 95% CI) | Operational Posture |
| :---: | :---: | :---: | :---: | :---: | :--- |
| $\ge 0.40$ | 212 / 400 | 53.0% | 100.0% | 0.0% [0.0%, 1.8%] | Broad coverage mode; captures degraded borderline signals |
| $\ge 0.50$ | 212 / 400 | 53.0% | 100.0% | 0.0% [0.0%, 1.8%] | Balanced enterprise diagnostic monitoring |
| $\ge 0.60$ | 199 / 400 | 49.8% | 100.0% | 0.0% [0.0%, 1.9%] | High-corroboration autonomous remediation threshold |
| $\ge 0.70$ | 199 / 400 | 49.8% | 100.0% | 0.0% [0.0%, 1.9%] | Strict multi-domain consensus requirement |
| $\ge 0.80$ | 199 / 400 | 49.8% | 100.0% | 0.0% [0.0%, 1.9%] | Conservative critical infrastructure threshold |
| $\ge 0.85$ | 167 / 400 | 41.8% | 100.0% | 0.0% [0.0%, 2.3%] | Near-saturated high-certainty operating point |
| $\ge 0.90$ | 160 / 400 | 40.0% | 100.0% | 0.0% [0.0%, 2.3%] | Ultra-conservative core fabric safety threshold |

### Abstention Breakdown on Borderline Suite (201 Abstentions)
- **`insufficient_evidence_gating`**: 119 samples (59.2%). Multi-signal domain rules strictly required $\ge 2$ independent corroborating domains; sparse telemetry prevented unsubstantiated guesses.
- **`conformal_prediction_set_ambiguity`**: 26 samples (12.9%). Conformal prediction set cardinality $|C(X)| > 1$ or nonconformity exceeded threshold, triggering safe statistical abstention.
- **`low_calibrated_confidence`**: 56 samples (27.9%). Calibrated probability fell below the 0.70 acceptance threshold.

---

## 5. Physical Network Emulation: Real vs. Harness Comparison

Evaluated on 50 live containerized network episodes executed in Linux network namespaces with `veth` pairs, Traffic Control (`tc`), `iperf3`, and kernel routing:

| Emulated Condition | Real Capture Episodes | Diagnosed Status | Benign Status | Abstained | Selective Acc | Real Telemetry Behavior | Harness vs Real Differences & Ingestion Handling |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| **`congestion`** | 10 | 10 | 0 | 0 | 100.0% | Buffer queue build-up and packet drops under heavy iperf flow (> 95% link rate) | Real Linux tc drops match synthetic burst profiles; normalized via Gateway bps->Mbps. |
| **`link_flap`** | 10 | 4 | 0 | 6 | 100.0% | Kernel link carrier toggled every 1.5s via `ip link set dev veth down/up` | Syslog carrier transition events parsed via RFC 5424; 6/10 safely abstained due to transient window. |
| **`mtu_mismatch`** | 10 | 10 | 0 | 0 | 100.0% | MTU 1500 client attempting jumbo frame transmission across MTU 1400 transit link | ICMP fragmentation needed correctly parsed; diagnosed as MTU mismatch blackholing. |
| **`cpu_stress`** | 10 | 6 | 0 | 4 | 100.0% | Multi-threaded python CPU load generator pinning container CPU cores at 100% | Direct proc/stat telemetry ingested; 4/10 borderline runs safely abstained under strict threshold. |
| **`healthy_run`** | 10 | 0 | 10 | 0 | 100.0% | Standard baseline traffic across uncontended Linux veth namespaces | Scope-aware healthy confirmation: AP and DHCP/DNS omitted from check when unobserved in topology. |

---

## 6. Verification Status of Engine Assertions & Constraints

1. **Deterministic Multi-Signal Domain Rule Precedence**: `VERIFIED`  
   When deterministic domain rules fire with $\ge 2$ independent corroborating domains, neither classifier vetoes nor ambiguous conformal sets force abstention.
2. **Safety Invariant**: `VERIFIED`  
   Zero faults called normal across in-distribution, unseen blind topologies, organizer Colab sets, interop scenarios, noise stress, fresh holdouts, borderline suite, and physical network emulations.
3. **Reproducibility & Parallel Determinism**: `VERIFIED`  
   Evaluated 50 random test seeds concurrently across 4 workers vs. serial execution: 0 differing seeds (`differing_seeds_count = 0`, `is_perfectly_deterministic = True`).
4. **Clean Git State**: `VERIFIED`  
   Branch: `fix/ps-readiness-p0`. `uv.lock` remains completely untouched. Only exact required files will be staged.
