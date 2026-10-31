# NetCoop AI: Held-Out Generator Differences & Evaluation Notes

This document describes the design, statistical distributions, and deliberate parameter shifts of the held-out evaluation dataset generator (`netcoop/data/heldout_generator.py`).

---

## 1. Clean-Room Architectural Independence

The held-out generator was developed independently from all detector implementations, specialist agent rules, and baseline generator code:
- **Reference Specifications Only**: Built exclusively from [`schemas/telemetry.json`](../schemas/telemetry.json) and [`docs/contract.md`](contract.md).
- **Zero Detector Tuning**: Developed without viewing internal threshold constants, heuristic signature patterns, or agent correlation weights.
- **Strict Canonical Compatibility**: Produces 100% schema-compliant datasets ready for ingestion via the Gateway or `/api/diagnose`.

---

## 2. Key Differences from the Baseline Generator

| Evaluation Dimension | Baseline Generator | Held-Out Evaluation Generator | Evaluation Purpose |
| :--- | :--- | :--- | :--- |
| **Noise Distribution** | Gaussian / Normal ($\mu, \sigma$) | **Heavy-Tailed Pareto & Log-Normal** | Evaluates detector resilience to asymmetric shocks, long-tail outliers, and non-linear baseline drift. |
| **Severity Range** | Narrow, fixed thresholds | **Wide continuous multiplier ($0.75\times$ to $1.65\times$)** | Tests performance on both subtle borderline anomalies and extreme saturations. |
| **Fault Onset Timing** | Fixed onset step ($t \approx 30\%$) | **Dynamic onset ($10\%$ early to $85\%$ late) + oscillation** | Tests whether agents detect early-onset faults, withstand late-onset faults, and track intermittent flaps. |
| **Telemetry Continuity** | Continuous uniform interval sampling | **Bursty dropouts & missing intervals** | Tests system robustness to missing data, packet loss in telemetry streams, and asynchronous reporting. |
| **Compound Faults** | Predominantly single-domain | **Multi-domain compound mixes** | Evaluates mediator conflict arbitration (e.g. CPU + link congestion, Wi-Fi + DNS, optics + BGP flaps). |

---

## 3. Detailed Parameter Shifts

### 3.1 Heavy-Tailed and Bursty Noise
Instead of symmetric bell-curve perturbations, the held-out generator utilizes:
- **Pareto-Derived Outliers**: Scaled Pareto distribution ($P(X > x) \sim x^{-\alpha}$, $\alpha \in [2.5, 4.0]$) producing sporadic, asymmetric high-magnitude metric spikes.
- **Log-Normal Multipliers**: Used for egress queue drop bursts and CRC error accumulations where values cluster near baseline but exhibit exponential positive excursions.

### 3.2 Dynamic Severity Ranges
- A seeded severity multiplier $\lambda \in [0.75, 1.65]$ scales fault magnitudes across runs.
- **Milder Faults** ($\lambda < 0.85$): Packet loss between $2.5\%$ and $4.5\%$, link utilization near $88\%$, and borderline optical attenuation. Evaluates whether detectors avoid false negatives on mild degradation.
- **Extreme Faults** ($\lambda > 1.40$): Packet loss $> 85\%$, CPU $> 98\%$, and multi-thousand queue drop bursts. Evaluates whether detectors avoid numeric overflow or clipping anomalies.

### 3.3 Variable Onset Timing and Intermittent Bursts
- Fault activation step is parameterized with scenario-specific offsets and random jitter:
  - Early onset: Link congestion and MTU mismatch ($10-20\%$ into trace).
  - Mid onset: Ethernet interface and DNS faults ($40-50\%$).
  - Late onset: Upstream transit cascades and DHCP pool depletion ($60-75\%$).
  - Intermittent oscillation: Routing flaps and ambiguous faults cycle on/off in 3-step burst cycles.

### 3.4 Bursty Telemetry Dropouts
- Simulates realistic in-band network degradation where the telemetry transport itself suffers packet loss:
  - Contiguous drop gaps (2–4 consecutive timestamps) are randomly omitted on selected devices.
  - In `insufficient_data` and `insufficient_evidence_sparse` scenarios, $60-80\%$ of telemetry records are dropped across nodes to verify that agents refuse to guess and return `insufficient_evidence`.

### 3.5 Compound Fault Scenarios
- `compound_cpu_and_link`: Core spine switch exhibits concurrent $96\%$ CPU exhaustion and egress queue tail-drops.
- `compound_wifi_and_dns`: Wireless access point suffers severe retry rate while upstream DNS resolution fails.
- `compound_optics_and_flaps`: Optical interface degradation on leaf switches triggers cascading BGP session flap damping.

---

## 4. CLI Execution

The held-out generator supports direct command-line execution:

```powershell
# Generate held-out dataset to file
python -m netcoop.data.heldout_generator --scenario link_congestion --seed 7 --out data/heldout_link_congestion.json

# List all supported held-out scenario identifiers
python -m netcoop.data.heldout_generator --list-scenarios

# Stream generated canonical JSON to stdout
python -m netcoop.data.heldout_generator --scenario weak_wifi_signal --seed 42
```

---

## 5. Verification and Test Coverage

All generator behaviors are validated in [`tests/test_heldout_generator.py`](../tests/test_heldout_generator.py):
1. **Schema Compliance**: Every generated dataset validates against [`schemas/telemetry.json`](../schemas/telemetry.json).
2. **Strict Determinism**: Re-running with the identical seed produces identical JSON; changing seed produces variance.
3. **Complete Scenario Coverage**: All 23 supported scenarios produce populated topology, telemetry, routing state, configs, and syslogs.
4. **CLI Contract**: Verified via end-to-end subprocess execution.

