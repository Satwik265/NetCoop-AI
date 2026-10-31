# NetCoop AI Robustness & Chaos Resilience Specification

This document defines the fault tolerance, chaos resilience, schema adaptation, and degraded-mode operation standards implemented in NetCoop AI for the IIT Bhubaneswar Agentic AI Grand Finale.

---

## 1. Resilience Philosophy

NetCoop AI operates under zero-trust assumptions regarding input telemetry, schema consistency, and agent reliability:
1. **Never Crash**: Incompatible data, malformed payloads, network partitions, or agent crashes must never produce an unhandled exception or abort the diagnostic pipeline.
2. **Never Claim False Certainty**: When evidence is missing, corrupted, or below confidence thresholds, the system explicitly returns `status: "insufficient_evidence"` and withholds an exact root cause.
3. **Graceful Degradation**: If an agent process fails or trips its circuit breaker, or if an optional data feed (e.g., topology) is absent, the orchestrator continues in degraded mode, flagging known limitations in the final diagnostic report.
4. **Data Quality-Aware Confidence**: Confidence scores are dynamically penalized and capped whenever telemetry exhibits data quality degradation, missing fields, or single-snapshot limitation.

---

## 2. Chaos Fuzzer Architecture (`tests/test_chaos.py`)

The chaos testing framework includes `ChaosFuzzer`, a deterministic, seedable fuzzer that injects realistic telemetry anomalies into synthetic and organizer benchmark datasets:

| Corruption Type | Mutation Mechanics | Handled By |
|---|---|---|
| `drop_fields` | Randomly drops essential or auxiliary metrics (`latency_ms`, `queue_drops`, etc.) | Adapter field quarantining and signature missing-evidence penalty |
| `rename_fields` | Maps canonical keys to aliases (`rtt`, `util`, `drops`, `loss`, `cpu_util`) | `OrganizerAdapter.FIELD_ALIASES` and fuzzy `FieldNameMatcher` |
| `change_units` | Scales metrics (e.g., latency from ms to s, throughput from Mbps to kbps) | `UnitInference` heuristic threshold analysis |
| `shuffle_time` | Randomizes timestamp ordering across telemetry samples | Window sorting and temporal realignment |
| `truncate` | Discards up to 66% of telemetry records to simulate stream truncation | `is_snapshot_mode` penalty and data quality scoring |
| `inject_nulls` | Injects `None`, `"null"`, and `"NaN"` into metric fields | Pydantic null-coercion, sanitizer, and typed validation errors |
| `mix_schema_versions`| Injects legacy or unsupported version strings (`1.0.0`, `2.0.0`, `99.0.0`) | Version compatibility handler and `ERR_UNSUPPORTED_SCHEMA_VERSION` |
| `mix_organizer_records`| Interleaves flat v1 records with nested organizer records (`metrics: {...}`) | Recursive unnesting and field merging |

---

## 3. Typed Error Registry

All schema and payload validation anomalies are captured in a structured `TypedValidationError` format rather than throwing unhandled exceptions:

```json
{
  "code": "ERR_MISSING_FIELD",
  "field": "metrics",
  "explanation": "Nested metrics object was null or missing.",
  "suggested_fix": "Supply dictionary under 'metrics' key in organizer format."
}
```

### Registered Error Codes

| Code | Trigger Condition | System Action |
|---|---|---|
| `ERR_MISSING_FIELD` | Mandatory schema field (e.g., `device_status`, `timestamp`, `metrics`) is absent or null | Imputes sensible fallback, logs limitation, degrades quality score |
| `ERR_UNSUPPORTED_SCHEMA_VERSION` | Payload version header does not match supported major versions (`>= 3.0.0`) | Logs warning, attempts permissive fallback parse |
| `ERR_UNKNOWN_DEVICE` | `device_id` is missing, blank, or null | Assigns `"unknown_device"` tag, flags quarantine |
| `ERR_WRONG_TYPE` | Non-parseable timestamp or uncoercible data type | Quarantines value, logs validation error |
| `ERR_NAN_INF` | `NaN`, `Infinity`, or `-Infinity` encountered in numeric metrics | Replaces with `None`, flags data quality penalty |
| `ERR_NEGATIVE_VALUE` | Negative value in strictly non-negative counter (e.g., `queue_drops < 0`) | Clamps to `0` or flags as anomalous |
| `ERR_OUT_OF_RANGE_PERCENT` | Percentage field outside `[0.0, 100.0]` (e.g., `cpu_pct = 125.0`) | Clamps to boundary, flags warning |
| `ERR_OUT_OF_ORDER_TIMESTAMP` | Timestamps do not advance monotonically | Sorts records chronologically before analysis |
| `ERR_DUPLICATE_TIMESTAMP` | Identical timestamps from the same device | Deduplicates or averages metric windows |
| `ERR_STALE_TIMESTAMP` | Telemetry older than maximum evaluation window | Applies staleness penalty to confidence |
| `ERR_EMPTY_FILE` | Telemetry stream or payload contains zero records | Returns `status: "insufficient_evidence"` immediately |
| `ERR_MALFORMED_JSON` | Non-JSON text or unparseable syntax in stream | Rejects record safely, preserves remaining stream |

---

## 4. End-to-End Robustness Matrix

The following table documents verification results for end-to-end corruption scenarios verified in `tests/test_chaos.py`:

| Scenario / Corruption | Input State | Adapter / Pipeline Behaviour | Output State & Error Code | Verification Test |
|---|---|---|---|---|
| **Renamed Fields** | Records using `rtt`, `util`, `drops`, `loss` | Maps aliases via `FIELD_ALIASES` table | Correctly maps to `latency_ms`, `link_utilization_pct`, `queue_drops`, `packet_loss_pct`; diagnosis completes | `test_end_to_end_renamed_fields` |
| **Seconds vs Milliseconds** | Latency supplied as `0.195` (seconds) | `UnitInference` detects max latency $< 10.0$ and scales $\times 1000$ | Normalized to `195.0 ms`; accurate congestion diagnosis | `test_end_to_end_seconds_vs_ms_latency` |
| **kbps vs Mbps** | Throughput `950000.0 kbps`, Bandwidth `1000000.0 kbps` | `UnitInference` detects throughput $> 10000.0$ and divides by 1000 | Normalized to `950.0 Mbps`, `1000.0 Mbps`; link utilization calculated correctly | `test_end_to_end_kbps_vs_mbps` |
| **Mixed Schema Versions (v1 & v2)** | Interleaved flat records and nested organizer `{"metrics": {...}}` | Flattens nested dictionary and merges with outer metadata | Both records unified into standard schema; full temporal context preserved | `test_end_to_end_v1_vs_v2_schema` |
| **Missing Message Envelope Fields** | Envelope missing `hypotheses`, `inquiries`, `observations`, `error` | Pydantic defaults initialize empty lists and `error = None` | Envelope validates cleanly; orchestrator processes without attribute errors | `test_end_to_end_missing_message_fields` |
| **Missing Metrics Object** | Organizer record with `"metrics": None` or omitted | Flags `ERR_MISSING_FIELD` on metrics; preserves outer metadata | Returns `status: "insufficient_evidence"`; no false positive cause claimed | `test_end_to_end_organizer_missing_metrics_object` |
| **Unsupported Schema Version** | Payload with `schema_version: "99.0.0"` | Generates `ERR_UNSUPPORTED_SCHEMA_VERSION`; activates permissive parser | Pipeline continues in degraded mode without crashing | `test_end_to_end_unsupported_schema_version` |
| **Missing Topology Data** | Telemetry supplied with no network topology graph | Upstream root-cause signatures disabled; alternative hypotheses marked `"unverifiable"` | Diagnosis completes for local link congestion; report explicitly documents missing topology caveat | `test_missing_topology_handling` |
| **Single-Snapshot Telemetry** | Single point in time per device (no temporal series) | `is_snapshot_mode` triggers 15% confidence penalty | Confidence capped; caveat added to report limitations | `test_snapshot_mode_detection_and_penalty` |
| **Agent Microservice Failure** | Specialist process fails, crashes, or times out | `CircuitBreaker` trips to OPEN state after 2 consecutive failures; fast-fails on subsequent calls | Mediator records dead agent in limitations; diagnostic graph proceeds with remaining agents | `test_circuit_breaker_trips_and_fast_fails`, `test_mediator_degraded_mode_continuation` |
| **Conformal Model Abstention** | ML model prediction set is empty ($|S| = 0$) or flags abstain | Hybrid orchestrator enforces conformal abstention guarantee | Returns `status: "insufficient_evidence"`, `confidence_category: "abstain"`, `probable_cause: None` | `test_hybrid_conformal_abstention_guarantee` |
| **Severe Data Quality Degradation** | Data quality score $DQ < 0.60$ under heavy chaos | Dynamic confidence cap enforced ($C \le 0.88$) | Prevents overconfident diagnosis on corrupt or sparse telemetry | `test_chaos_fuzzer_resilience_and_confidence_capping` |

---

## 5. Confidence Blending & Guarantee Mathematical Formulation

### Hybrid Score Blending
The orchestrator combines expert rule-based signature scores ($S_{rules}$) with calibrated model scores ($S_{model}$) according to weights defined in `netcoop/models/artifacts/weights.json`:

$$S_{blended} = 0.55 \cdot S_{rules} + 0.45 \cdot S_{model}$$

A blind 50/50 average is strictly prohibited. If the classifier agent or model layer is unavailable, the system smoothly falls back to $S_{rules}$ while noting model layer absence in report limitations.

### Conformal Prediction Sets & Abstention
Calibrated probabilities $P(y = c \mid x)$ are converted to conformal prediction sets $S(x)$ at confidence level $1 - \alpha = 0.90$ using empirical conformity thresholds $\hat{q}$:

$$S(x) = \{ c \in \mathcal{C} : P(y = c \mid x) \ge 1 - \hat{q} \}$$

- **High Confidence**: $|S(x)| = 1$ and $S_{blended} \ge 0.85$
- **Medium Confidence**: $|S(x)| = 1$ and $0.70 \le S_{blended} < 0.85$, or $|S(x)| = 2$
- **Low Confidence**: $|S(x)| \ge 3$ or $S_{blended} < 0.70$
- **Abstain**: $|S(x)| = 0$ or model layer flags anomaly. Status is forced to `"insufficient_evidence"`, and no exact root cause is returned.

---

## 6. Verification Summary

```
============================= 17 passed in 24.97s =============================
tests/test_chaos.py::test_circuit_breaker_trips_and_fast_fails PASSED
tests/test_chaos.py::test_mediator_degraded_mode_continuation PASSED
tests/test_chaos.py::test_missing_topology_handling PASSED
tests/test_chaos.py::test_snapshot_mode_detection_and_penalty PASSED
tests/test_chaos.py::test_report_to_markdown_rendering PASSED
tests/test_chaos.py::test_report_schema_json_validation PASSED
tests/test_chaos.py::test_chaos_fuzzer_resilience_and_confidence_capping PASSED
tests/test_chaos.py::test_chaos_fuzzer_on_organizer_samples PASSED
tests/test_chaos.py::test_end_to_end_renamed_fields PASSED
tests/test_chaos.py::test_end_to_end_seconds_vs_ms_latency PASSED
tests/test_chaos.py::test_end_to_end_kbps_vs_mbps PASSED
tests/test_chaos.py::test_end_to_end_v1_vs_v2_schema PASSED
tests/test_chaos.py::test_end_to_end_missing_message_fields PASSED
tests/test_chaos.py::test_end_to_end_organizer_missing_metrics_object PASSED
tests/test_chaos.py::test_end_to_end_unsupported_schema_version PASSED
tests/test_chaos.py::test_hybrid_confidence_breakdown_and_weights PASSED
tests/test_chaos.py::test_hybrid_conformal_abstention_guarantee PASSED
tests/test_chaos.py::test_hybrid_classifier_disagreement_conflict_flow PASSED
```
Full repository regression test: **116 passed** in 37.63s.
