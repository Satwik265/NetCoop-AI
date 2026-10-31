# Organizer Telemetry Format Specification

## 1. Overview
The hackathon organizer Colab telemetry generator (`data/organizer/Mock_data_builder_netScoopAI.ipynb`) produces single-snapshot or streaming telemetry dictionaries with a nested `metrics` object and high-level status ratings.

## 2. Raw Organizer Schema Structure
```json
{
  "timestamp": "2026-10-14T07:05:49.619791Z",
  "device_id": "SW_CAMPUS_4",
  "metrics": {
    "cpu_utilization_pct": 99.9,
    "link_utilization_pct": 100.0,
    "packet_loss_pct": 28.51,
    "latency_ms": 926.46,
    "jitter_ms": 45.2,
    "queue_drops": 13416,
    "interface_errors": 382
  },
  "status": "Critical"
}
```

## 3. Normalization and Adaptation Rules

1. **Metrics Flattening**:
   - The nested `metrics` object is flattened into the root record.
   - Any metric absent in `metrics` is left absent (`None` or omitted), never zero-filled.

2. **Field Alias Mapping**:
   - `cpu_utilization_pct` -> `cpu_pct`
   - `link_utilization_pct` -> `link_utilization_pct`
   - `packet_loss_pct` -> `packet_loss_pct`
   - `latency_ms` -> `latency_ms` (or `latency_s * 1000.0` if latency in seconds)
   - `queue_drops` -> `queue_drops`
   - `interface_errors` -> `interface_errors`
   - `jitter_ms` -> `jitter_ms`

3. **Status Mapping**:
   - `Healthy` -> `online`
   - `Warning` -> `degraded`
   - `Critical` -> `degraded` (or `offline` if unreachable/100% loss)

4. **Device Classification**:
   - Devices named `SW_CAMPUS_<n>` are assigned `device_type = "switch"`.
   - Other prefixes: `RTR_*` -> `router`, `AP_*` -> `access_point`, `HOST_*` -> `host`. Default fallback: `switch` if campus switch pattern, else `host`.

5. **Timestamp Normalization**:
   - Timestamps are parsed as ISO 8601 UTC.
   - Microsecond precision and trailing `Z` or `+00:00` normalized to standard ISO 8601 strings.

6. **Time-Window Grouping**:
   - When multiple individual snapshot records for the same device exist, they are ordered chronologically and grouped into per-device time windows.

7. **Auto-Detection in `/ingest`**:
   - The Gateway detects the presence of a nested `metrics` key or `status` string (`Healthy`/`Warning`/`Critical`) or top-level list of snapshot records and automatically routes through the `OrganizerAdapter`.
