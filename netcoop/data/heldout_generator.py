"""Held-out synthetic network scenario generator with non-overlapping parameters and topologies."""

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from netcoop.data.generator import (
    DeviceStatus,
    DeviceType,
    NoiseShape,
    SeverityLevel,
)


class HeldoutNetworkGenerator:
    """Produces unseen topologies (e.g. Research Satellite Campus) and shifted parameter distributions."""

    HELDOUT_DEVICES = [
        {"id": "sat-rtr-01", "type": DeviceType.ROUTER, "zone": "satellite_core", "bandwidth_mbps": 40000.0},
        {"id": "sat-agg-sw-01", "type": DeviceType.SWITCH, "zone": "satellite_distribution", "bandwidth_mbps": 20000.0},
        {"id": "med-res-sw-01", "type": DeviceType.SWITCH, "zone": "medical_research", "bandwidth_mbps": 10000.0},
        {"id": "bio-sequencer-01", "type": DeviceType.HOST, "zone": "medical_research", "bandwidth_mbps": 10000.0},
        {"id": "sat-ap-clinic-01", "type": DeviceType.ACCESS_POINT, "zone": "health_center_wifi", "bandwidth_mbps": 1000.0},
        {"id": "telemed-tablet-01", "type": DeviceType.HOST, "zone": "health_center_wifi", "bandwidth_mbps": 300.0},
    ]

    HELDOUT_EDGES = [
        {"source": "sat-rtr-01", "target": "sat-agg-sw-01", "bandwidth_mbps": 40000.0, "media_type": "fiber"},
        {"source": "sat-agg-sw-01", "target": "med-res-sw-01", "bandwidth_mbps": 10000.0, "media_type": "fiber"},
        {"source": "med-res-sw-01", "target": "bio-sequencer-01", "bandwidth_mbps": 10000.0, "media_type": "copper"},
        {"source": "sat-agg-sw-01", "target": "sat-ap-clinic-01", "bandwidth_mbps": 1000.0, "media_type": "copper"},
        {"source": "sat-ap-clinic-01", "target": "telemed-tablet-01", "bandwidth_mbps": 300.0, "media_type": "wireless"},
    ]

    @classmethod
    def generate(
        cls,
        scenario: str = "link_congestion",
        seed: int = 1042,
        severity: SeverityLevel = SeverityLevel.HIGH,
        noise_level: float = 0.1,
    ) -> Dict[str, Any]:
        """Generate held-out dataset."""
        rng = random.Random(seed)
        start_dt = datetime(2026, 11, 15, 8, 30, 0, tzinfo=timezone.utc)
        timestamp_str = start_dt.isoformat()

        telemetry: List[Dict[str, Any]] = []
        for dev in cls.HELDOUT_DEVICES:
            d_id = dev["id"]
            d_type = dev["type"]
            bw = dev["bandwidth_mbps"]

            util = rng.uniform(20.0, 40.0)
            lat = rng.uniform(1.5, 4.5)
            loss = 0.0
            drops = 0
            errs = 0
            cpu = rng.uniform(20.0, 35.0)
            mem = rng.uniform(30.0, 50.0)
            status = DeviceStatus.ONLINE

            if scenario == "link_congestion" and d_id in ("sat-rtr-01", "sat-agg-sw-01"):
                util = rng.uniform(94.0, 99.5)
                drops = rng.randint(800, 3200)
                lat = rng.uniform(140.0, 220.0)
                loss = rng.uniform(5.0, 10.0)
                status = DeviceStatus.DEGRADED
            elif scenario == "weak_wifi_signal" and d_id in ("sat-ap-clinic-01", "telemed-tablet-01"):
                loss = rng.uniform(12.0, 24.0)
                lat = rng.uniform(60.0, 120.0)
                status = DeviceStatus.DEGRADED
            elif scenario == "device_cpu_overload" and d_id == "sat-rtr-01":
                cpu = rng.uniform(97.0, 99.9)
                mem = rng.uniform(92.0, 96.0)
                status = DeviceStatus.DEGRADED

            telemetry.append({
                "timestamp": timestamp_str,
                "device_id": d_id,
                "device_type": d_type.value,
                "device_status": status.value,
                "latency_ms": round(lat, 2),
                "jitter_ms": 1.2,
                "packet_loss_pct": round(loss, 2),
                "throughput_mbps": round((util / 100.0) * bw, 2),
                "bandwidth_mbps": bw,
                "link_utilization_pct": round(util, 2),
                "cpu_pct": round(cpu, 1),
                "memory_pct": round(mem, 1),
                "queue_drops": drops,
                "interface_errors": errs,
                "link_flaps": 0,
            })

        return {
            "incident_id": f"inc-heldout-{scenario}-{seed}",
            "network_id": "iit-bbs-satellite-medical-campus",
            "scenario": scenario,
            "seed": seed,
            "telemetry": telemetry,
            "topology": {
                "nodes": [{"id": d["id"], "role": d["type"].value} for d in cls.HELDOUT_DEVICES],
                "links": cls.HELDOUT_EDGES,
            },
        }
