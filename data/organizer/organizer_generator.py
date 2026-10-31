"""Organizer Colab telemetry generator replicating Mock_data_builder_netScoopAI."""

from datetime import datetime, timezone, timedelta
import random
from typing import Any, Dict, List, Optional


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
