# NetCoop AI: Data Layer and Testing Specification

## 1. Data Layer Overview

NetCoop AI incorporates a dedicated synthetic telemetry generation engine and adapter gateway designed to model campus network environments with precision, reproducibility, and interoperability.

The data layer models the IIT Bhubaneswar campus infrastructure across four topological zones:
1. `hostel_wifi`: High-density residential Wi-Fi access points and student hosts subject to RF attenuation, high retransmission rates, and roaming interference.
2. `department_ethernet`: Gigabit Ethernet access switches connecting academic laboratories and desktop workstations.
3. `lecture_halls`: High-concurrency auditorium wireless access points subject to session bursts and DHCP pool contention.
4. `core_distribution_access`: High-speed 10 Gbps fiber backbones interconnecting distribution switches and core transit routers.

---

## 2. Telemetry Schema Specification

Every generated observation record provides 20 deterministic fields:

| Field Name | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `timestamp` | String | ISO 8601 UTC | UTC observation timestamp (e.g., `2026-10-31T12:00:00Z`). |
| `device_id` | String | Name string | Fully qualified device hostname (e.g., `core-rtr-01`). |
| `device_type` | Enum | Classification | One of: `router`, `switch`, `access_point`, `host`. |
| `device_status` | Enum | State | One of: `online`, `degraded`, `offline`. |
| `latency_ms` | Float | Milliseconds (`ms`) | End-to-end round trip time. |
| `jitter_ms` | Float | Milliseconds (`ms`) | Statistical latency variance between successive packets. |
| `packet_loss_pct` | Float | Percent (`%`) | Packet drop percentage over measurement window. |
| `throughput_mbps` | Float | Megabits/sec (`Mbps`) | Current measured transmission data rate. |
| `bandwidth_mbps` | Float | Megabits/sec (`Mbps`) | Maximum theoretical interface link capacity. |
| `link_utilization_pct` | Float | Percent (`%`) | Ratio of throughput to bandwidth multiplied by 100. |
| `cpu_pct` | Float | Percent (`%`) | Control plane and data plane processor utilization. |
| `memory_pct` | Float | Percent (`%`) | Device system RAM utilization. |
| `queue_drops` | Integer | Packets | Buffer drop count during interface egress congestion. |
| `interface_errors` | Integer | Frames | CRC and Frame Check Sequence (FCS) corrupted frames. |
| `link_flaps` | Integer | Transitions | Physical carrier state down/up flap transitions. |
| `wifi_rssi_dbm` | Float / Null | Decibel-milliwatts (`dBm`) | Received Signal Strength Indicator for wireless devices. |
| `wifi_retransmission_pct` | Float / Null | Percent (`%`) | Proportion of 802.11 frames requiring retransmission. |
| `dns_resolution_ms` | Float / Null | Milliseconds (`ms`) | Time required for recursive DNS resolution. |
| `dns_failure_pct` | Float / Null | Percent (`%`) | Percentage of DNS queries resulting in SERVFAIL or timeout. |
| `dhcp_failure_pct` | Float / Null | Percent (`%`) | Percentage of DHCP discover/request queries failing lease. |

---

## 3. Seeded Determinism and Chaos Knobs

The telemetry generator (`data/generator.py`) guarantees exact mathematical reproducibility through PRNG seeding and provides three tuning knobs:

### 3.1 Reproducibility Guarantee
Running `SyntheticNetworkGenerator.generate(scenario, seed=42)` across independent operating systems, processes, or runs produces identical byte-for-byte telemetry streams.

### 3.2 Tuning Knobs
- **Noise Knob (`noise_level`: 0.0 to 1.0)**: Injects Gaussian perturbations into continuous metrics (latency, jitter, CPU, utilization). Simulates natural empirical sensor variance without altering the macro fault pattern.
- **Missing-Sample Knob (`missing_sample_rate`: 0.0 to 1.0)**: Probabilistically drops metric attributes to `None`. Tests agent resilience against incomplete telemetry collections.
- **Staleness Knob (`staleness_seconds`: float)**: Shifts observation timestamps backward relative to current time. Tests clock skew and timestamp normalization layers.

### 3.3 Command-Line Generation
Generate synthetic scenarios directly via the CLI:
```bash
# Generate baseline link congestion scenario
netcoop gen --scenario link_congestion --seed 42

# Generate with 20% noise and 15% dropped samples saved to file
netcoop gen --scenario weak_wifi_signal --seed 42 --noise 0.2 --drop-rate 0.15 --output custom_scenario.json
```

---

## 4. External Ingestion: Organizer Adapter

The gateway adapter (`gateway/adapters/organizer_adapter.py`) enables zero-recode compatibility with external hackathon organizer data and Google Colab generator outputs.

### Key Capabilities
1. **Field Alias Translation**: Automatically maps variant keys (`dev`, `dev_id`, `node`, `hostname` -> `device_id`; `delay`, `rtt` -> `latency_ms`; `util`, `utilization` -> `link_utilization_pct`; `tput` -> `throughput_mbps`).
2. **Unit Conversion**: Translates fractional seconds (`latency_s`) to milliseconds (`ms`) and rate units (`throughput_kbps`) to megabits per second (`Mbps`).
3. **Data Sanitization**: Strips string representations of `NaN`, `null`, `None`, and `undefined`, converting them into valid JSON `null` values.
4. **Chronological Sorting and Deduplication**: Prunes duplicate records sharing identical device and timestamp tuples and sorts entries chronologically.
5. **Clock Skew Detection**: Identifies cross-device clock drift exceeding 10 minutes and flags `clock_skew_detected`.
6. **Malformed JSON Recovery**: Recovers single-quoted or unquoted JSON payloads safely without runtime crashes.

---

## 5. Scenario Library and Ground-Truth Manifest

The repository provides a library of scenarios in `data/scenarios/` accompanied by `manifest.json`:

### 5.1 Core Fault Scenarios
- `normal_operation.json`: Nominal metrics; all devices online; expected status: `benign`.
- `link_congestion.json`: Utilization > 92%, queue drops > 500; expected status: `diagnosed`.
- `weak_wifi_signal.json`: RSSI < -82 dBm, Wi-Fi retransmissions > 25%; expected status: `diagnosed`.
- `ethernet_interface_fault.json`: Interface errors > 2000, link flaps > 5; expected status: `diagnosed`.
- `dns_failure.json`: DNS resolution latency > 2500ms, failure rate > 80%; expected status: `diagnosed`.
- `dhcp_failure.json`: DHCP failure rate > 75%, host degraded; expected status: `diagnosed`.
- `device_cpu_overload.json`: CPU > 95%, memory > 85%, queue drops; expected status: `diagnosed`.
- `upstream_failure_cascade.json`: Upstream core router link down, secondary trunks saturated; expected status: `diagnosed`.
- `ambiguous_multi_fault.json`: Simultaneous conflicting faults; expected status: `insufficient_evidence`.
- `insufficient_data.json`: Sparse single record with missing fields; expected status: `insufficient_evidence`.

### 5.2 Interoperability Failure Variants
- `interop_renamed_fields.json`: Evaluates field alias adaptation.
- `interop_seconds_vs_ms.json`: Evaluates time unit conversions.
- `interop_kbps_vs_mbps.json`: Evaluates bandwidth rate conversions.
- `interop_schema_v1_vs_v2.json`: Evaluates schema version tag divergence.
- `interop_missing_fields.json`: Evaluates graceful degradation with missing metrics.
- `interop_null_nan.json`: Evaluates string null and NaN sanitization.
- `interop_duplicate_out_of_order.json`: Evaluates timestamp deduplication and reordering.
- `interop_clock_skew.json`: Evaluates clock drift resilience.
- `interop_malformed_json.json`: Evaluates tolerant JSON parsing.

---

## 6. Testing Strategy and Execution

### 6.1 Test Suites
- `tests/test_generator.py`: Verifies mathematical determinism across seeds, scenario signatures, and chaos knobs.
- `tests/test_organizer_adapter.py`: Verifies adapter mapping across all interoperability edge cases.
- `tests/test_robustness_hypothesis.py`: Property-based fuzz testing using Hypothesis.
- `tests/test_protocol_envelope.py`: Validates Pydantic v2 envelope models and SI units against `schemas/envelope.json`.
- `tests/test_conflict_resolution.py`: Tests deterministic arbitration and tie handling.
- `tests/test_remediation_safety.py`: Verifies blast-radius constraints and simulation invariants.
- `tests/test_scenarios.py`: End-to-end integration across benchmark scenarios.

### 6.2 Ground-Truth Benchmark
Run the automated benchmark across all 19 scenarios:
```bash
python scripts/eval_benchmark.py
# or
make eval
```
Benchmark asserts:
- Diagnosed status and confidence >= target threshold for all fault scenarios.
- Insufficient evidence status and confidence == 0 for ambiguous and sparse scenarios.
- 100% pass rate across all interoperability failure variants.
