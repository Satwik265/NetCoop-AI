# NetCoop AI Evidence Ledger

This document tracks all evaluation splits, sample partitions, topologies, and seeds utilized throughout the development, calibration, and validation lifecycle of NetCoop AI. Every split is classified into one of three anti-leakage audit categories:

- **`TUNED`**: Data was inspected or used to fit classifier parameters, conformal nonconformity quantiles, dynamic decision weights, or heuristic threshold values.
- **`DEVELOPMENT`**: Data was evaluated during intermediate diagnostic iterations or regression testing; structural or diagnostic engine policies were modified after observing error traces, but parameters were not directly overfitted to these exact samples.
- **`CLEAN`**: Truly unseen holdout partition evaluated strictly **once** under a frozen codebase without subsequent code, parameter, or threshold tuning.

---

## 1. Complete Partition Ledger

| Split Identifier | Generator | Topology | Seeds | Sample Count | Phases Inspected | Code / Threshold Changes Followed | Audit Classification |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- | :---: |
| **`in_distribution_primary_400`** | `SyntheticNetworkGenerator` | IIT BBS Campus Fabric (8 devices) | 101–140 | 400 | Phase 11, 13H, 13K, 13N | Isotonic regression calibrator, split-conformal calibration ($q_{\text{hat}} = 0.6786$), decision weights ($w_{\text{rules}}=0.55$, $w_{\text{model}}=0.45$), data quality penalty coefficients. | **`TUNED`** |
| **`heldout_primary_300`** | `HeldoutNetworkGenerator` | IIT BBS Campus Fabric (8 devices) | 201–215,<br/>301–315 | 300 | Phase 11, 13C | Error analysis on Row 8 cascade misclassification (seed 313); optical vs queue drop precedence hierarchy. | **`TUNED`** |
| **`organizer_suite_900`** | `OrganizerTelemetryGenerator` | Single-switch campus/spine model | 6000–6149 | 900 | Phase 11, 13F, 13I, 13K, 13N | Organizer precedence policy (domain rules override ambiguous conformal sets / classifier vetoes); catastrophic hardware failure signature; dirty string and clock skew adaptation. | **`TUNED`** |
| **`blind_normal_split_701_715`** | `SyntheticNetworkGenerator` | IIT BBS Campus Fabric (8 devices) | 701–715 | 150 | Phase 13H | Diagnosis of 0/15 normal recall failure; implemented noise-robust health score (`healthy_health_score_threshold = 0.85`), sliding window median, and persistent healthy confirmation guard. | **`DEVELOPMENT`** |
| **`topology_train_suite`** | `TopologyRandomizedGenerator` | `train_branch_4`, `train_campus_8`, `train_dist_12`, `train_dc_16` | 801–815 | 600 | Phase 13J | Topology-invariant feature extractor (per-role quantile aggregates); Mahalanobis OOD distance calibration ($d_{\text{thresh}} = 12.20$). | **`DEVELOPMENT`** |
| **`unseen_blind_topologies_300`** | `TopologyRandomizedGenerator` | `blind_edge_iot_6`, `blind_spine_leaf_10` | 801–815 | 300 | Phase 13J, 13K, 13N | Phase 13N multi-domain rule ambiguity detection (`detect_rule_ambiguity()`) enforcing safe abstention for simultaneous multi-faults. | **`DEVELOPMENT`** |
| **`phase13l_emulation_50`** | Linux Network Namespaces (`veth`/`tc`/`FRR`) | Core-Dist-Edge 3-namespace emulated network | 50 episodes | 50 | Phase 13L, 13M | RFC 3164 and RFC 5424 syslog parser; log agent non-dict guard; scope-aware healthy confirmation; data-quality score decoupling from optional domains. | **`DEVELOPMENT`** |
| **`heldout_seeds_901_915`** | `HeldoutNetworkGenerator` | IIT BBS Campus Fabric (8 devices) | 901–915 | 150 | Phase 13N | First look in Phase 13N cross-generator validation. Evaluated once frozen; zero threshold or code changes followed. | **`CLEAN`** |
| **`fresh_unseen_topologies_450`** | `TopologyRandomizedGenerator` | `blind_edge_iot_6`, `blind_spine_leaf_10`, `blind_branch_9` | 1001–1015 | 450 | Phase 13O | Fresh holdout run once under Phase 13O freeze. Zero subsequent changes. | **`CLEAN`** |
| **`fresh_organizer_300`** | `OrganizerTelemetryGenerator` | Single-switch campus/spine model | 7000–7099 | 300 | Phase 13O | Fresh holdout run once under Phase 13O freeze (50 windowed + 50 snapshot per class). Zero subsequent changes. | **`CLEAN`** |
| **`fresh_heldout_1101_1115`** | `HeldoutNetworkGenerator` | IIT BBS Campus Fabric (8 devices) | 1101–1115 | 150 | Phase 13O | Fresh holdout run once under Phase 13O freeze. Zero subsequent changes. | **`CLEAN`** |
| **`fresh_emulation_20001_20050`** | Linux Network Namespaces (`veth`/`tc`/`FRR`) | Core-Dist-Edge 3-namespace emulated network | 20001–20050 | 50 | Phase 13O | Fresh emulation run once under Phase 13O freeze. Zero subsequent changes. | **`CLEAN`** |
| **`borderline_suite_400`** | `SyntheticNetworkGenerator` | IIT BBS Campus Fabric (8 devices) | 1201–1240 | 400 | Phase 13O | 0.3x–0.8x nominal severity with 0%–40% missingness. Evaluated once under Phase 13O freeze. Zero subsequent changes. | **`CLEAN`** |

---

## 2. Anti-Leakage Audit Summary

- **Total Samples Evaluated Across Project History:** `5,715`
- **Samples in `TUNED` Partitions:** `1,600` (28.0%)
- **Samples in `DEVELOPMENT` Partitions:** `1,100` (19.2%)
- **Samples in `CLEAN` Single-Eval Holdout Partitions:** `3,015` (52.8%)

All diagnostic performance metrics reported in Phase 13O for fresh holdout sets reflect **single-run, zero-tuning evaluation**.
