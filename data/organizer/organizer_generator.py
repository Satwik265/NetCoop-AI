"""Organizer Colab telemetry generator replicating Mock_data_builder_netScoopAI.

Provides:
- OrganizerTelemetryGenerator class for programmatic batch/window evaluation
- Standalone generation functions (generate_telemetry, generate_series, emit_jsonl_samples)
- CLI entrypoint for generating samples and JSONL files
"""

import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Union


class OrganizerTelemetryGenerator:
    """Generates synthetic telemetry in the exact format produced by the hackathon organizer Colab notebook."""

    FAULT_TYPES = ["normal", "latency_spike", "hardware_failure"]

    @classmethod
    def generate_single_record(
        cls,
        fault_type: str = "normal",
        device_id: Optional[str] = None,
        base_time: Optional[datetime] = None,
        rng: Optional[random.Random] = None,
    ) -> Dict[str, Any]:
        """Generate a single organizer telemetry record."""
        r = rng if rng is not None else random.Random()
        dev = device_id or f"SW_CAMPUS_{r.randint(1, 10)}"
        t = base_time or datetime.now(timezone.utc)
        iso_time = t.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        record: Dict[str, Any] = {
            "timestamp": iso_time,
            "device_id": dev,
            "metrics": {},
        }

        if fault_type == "latency_spike":
            record["metrics"] = {
                "cpu_utilization_pct": round(r.uniform(40.0, 70.0), 2),
                "link_utilization_pct": round(r.uniform(60.0, 85.0), 2),
                "packet_loss_pct": round(r.uniform(0.1, 1.5), 2),
                "latency_ms": round(r.uniform(150.0, 400.0), 2),
                "jitter_ms": round(r.uniform(30.0, 80.0), 2),
                "queue_drops": r.randint(0, 50),
            }
            record["status"] = "Warning"
        elif fault_type == "hardware_failure":
            record["metrics"] = {
                "cpu_utilization_pct": 99.9,
                "link_utilization_pct": 100.0,
                "packet_loss_pct": round(r.uniform(15.0, 30.0), 2),
                "latency_ms": round(r.uniform(500.0, 1000.0), 2),
                "queue_drops": r.randint(5000, 15000),
                "interface_errors": r.randint(100, 500),
            }
            record["status"] = "Critical"
        else:
            record["metrics"] = {
                "cpu_utilization_pct": round(r.uniform(10.0, 35.0), 2),
                "link_utilization_pct": round(r.uniform(20.0, 50.0), 2),
                "packet_loss_pct": 0.0,
                "latency_ms": round(r.uniform(5.0, 20.0), 2),
                "jitter_ms": round(r.uniform(1.0, 5.0), 2),
                "queue_drops": 0,
            }
            record["status"] = "Healthy"

        return record

    @classmethod
    def generate_incident(
        cls,
        fault_type: str = "normal",
        seed: int = 1001,
        is_window: bool = True,
        window_size: int = 5,
    ) -> Dict[str, Any]:
        """Generate an incident payload either as a single snapshot or a multi-point time window."""
        rng = random.Random(seed)
        dev = f"SW_CAMPUS_{rng.randint(1, 10)}"
        start_time = datetime(2026, 10, 14, 7, 5, 0, tzinfo=timezone.utc) + timedelta(minutes=seed % 1000)

        if not is_window or window_size <= 1:
            rec = cls.generate_single_record(fault_type=fault_type, device_id=dev, base_time=start_time, rng=rng)
            return {
                "format": "organizer_single_snapshot",
                "fault_type": fault_type,
                "seed": seed,
                "payload": rec,
            }

        records: List[Dict[str, Any]] = []
        for i in range(window_size):
            t = start_time + timedelta(seconds=i * 10)
            rec = cls.generate_single_record(fault_type=fault_type, device_id=dev, base_time=t, rng=rng)
            records.append(rec)

        return {
            "format": "organizer_windowed",
            "fault_type": fault_type,
            "seed": seed,
            "payload": records,
        }

    @classmethod
    def generate_eval_set(
        cls,
        samples_per_fault: int = 300,
        is_window: bool = True,
        base_seed: int = 5000,
    ) -> List[Dict[str, Any]]:
        """Generate a complete evaluation dataset across all fault types and seeds."""
        dataset: List[Dict[str, Any]] = []
        seed = base_seed
        for fault in cls.FAULT_TYPES:
            for _ in range(samples_per_fault):
                item = cls.generate_incident(fault_type=fault, seed=seed, is_window=is_window)
                dataset.append(item)
                seed += 1
        return dataset


def generate_telemetry(
    fault_type: str = "normal",
    seed: Optional[int] = None,
    device_id: Optional[str] = None,
    timestamp: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """Generate a single snapshot of organizer-format synthetic telemetry."""
    if seed is not None:
        random.seed(seed)

    if timestamp is None:
        ts_str = datetime.now(timezone.utc).isoformat()
    elif isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            ts_str = timestamp.replace(tzinfo=timezone.utc).isoformat()
        else:
            ts_str = timestamp.isoformat()
    else:
        ts_str = str(timestamp)

    target_device = device_id or f"SW_CAMPUS_{random.randint(1, 10)}"

    data: Dict[str, Any] = {
        "timestamp": ts_str,
        "device_id": target_device,
        "metrics": {},
    }

    if fault_type == "latency_spike":
        data["metrics"] = {
            "cpu_utilization_pct": round(random.uniform(40, 70), 2),
            "link_utilization_pct": round(random.uniform(60, 85), 2),
            "packet_loss_pct": round(random.uniform(0.1, 1.5), 2),
            "latency_ms": round(random.uniform(150, 400), 2),  # Spike
            "jitter_ms": round(random.uniform(30, 80), 2),
            "queue_drops": random.randint(0, 50),
        }
        data["status"] = "Warning"
    elif fault_type == "hardware_failure":
        data["metrics"] = {
            "cpu_utilization_pct": 99.9,
            "link_utilization_pct": 100.0,
            "packet_loss_pct": round(random.uniform(15, 30), 2),
            "latency_ms": round(random.uniform(500, 1000), 2),
            "queue_drops": random.randint(5000, 15000),
            "interface_errors": random.randint(100, 500),
        }
        data["status"] = "Critical"
    else:
        data["metrics"] = {
            "cpu_utilization_pct": round(random.uniform(10, 35), 2),
            "link_utilization_pct": round(random.uniform(20, 50), 2),
            "packet_loss_pct": 0.0,
            "latency_ms": round(random.uniform(5, 20), 2),
            "jitter_ms": round(random.uniform(1, 5), 2),
            "queue_drops": 0,
        }
        data["status"] = "Healthy"

    return data


def generate_series(
    fault_type: str,
    device_count: int = 10,
    snapshots_per_device: int = 30,
    spacing_seconds: int = 10,
    base_time: Optional[datetime] = None,
    seed: Optional[int] = 42,
) -> List[Dict[str, Any]]:
    """Generate sequential time-series snapshots across devices."""
    if seed is not None:
        random.seed(seed)

    t0 = base_time or datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
    records: List[Dict[str, Any]] = []

    devices = [f"SW_CAMPUS_{i}" for i in range(1, device_count + 1)]

    for step in range(snapshots_per_device):
        current_time = t0 + timedelta(seconds=step * spacing_seconds)
        for dev in devices:
            record = generate_telemetry(
                fault_type=fault_type,
                device_id=dev,
                timestamp=current_time,
            )
            records.append(record)

    return records


def emit_jsonl_samples(output_dir: Path) -> None:
    """Emit normal, latency_spike, and hardware_failure JSONL sample files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fault_types = ["normal", "latency_spike", "hardware_failure"]

    for ft in fault_types:
        out_path = output_dir / f"{ft}.jsonl"
        records = generate_series(
            fault_type=ft,
            device_count=10,
            snapshots_per_device=30,
            spacing_seconds=10,
            seed=42,
        )
        with open(out_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"Generated {len(records)} records for '{ft}' -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="NetCoop AI Organizer Telemetry Generator")
    parser.add_argument(
        "--fault-type",
        choices=["normal", "latency_spike", "hardware_failure"],
        default="normal",
        help="Fault type scenario",
    )
    parser.add_argument("--devices", type=int, default=10, help="Number of campus switches")
    parser.add_argument("--snapshots", type=int, default=30, help="Snapshots per device")
    parser.add_argument("--spacing", type=int, default=10, help="Seconds between snapshots")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output destination path (JSON or JSONL)",
    )
    parser.add_argument(
        "--emit-all-samples",
        action="store_true",
        help="Generate all standard sample files to data/organizer/samples/",
    )

    args = parser.parse_args()

    if args.emit_all_samples:
        default_dir = Path(__file__).parent / "samples"
        emit_jsonl_samples(default_dir)
        return

    records = generate_series(
        fault_type=args.fault_type,
        device_count=args.devices,
        snapshots_per_device=args.snapshots,
        spacing_seconds=args.spacing,
        seed=args.seed,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"Wrote {len(records)} records to {args.output}")
    else:
        # Print first snapshot as pretty JSON
        print(json.dumps(records[0], indent=2))


if __name__ == "__main__":
    main()
