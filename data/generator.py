"""Deterministic, seeded synthetic network telemetry and topology generator."""

import json
import random
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    """Network equipment device classifications."""

    ROUTER = "router"
    SWITCH = "switch"
    ACCESS_POINT = "access_point"
    HOST = "host"


class DeviceStatus(str, Enum):
    """Operational status of a network device."""

    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class CampusZone(str, Enum):
    """IIT Bhubaneswar campus topological zones."""

    HOSTEL_WIFI = "hostel_wifi"
    DEPARTMENT_ETHERNET = "department_ethernet"
    LECTURE_HALLS = "lecture_halls"
    CORE_DISTRIBUTION_ACCESS = "core_distribution_access"


class TelemetryRecord(BaseModel):
    """Single network device observation record matching specification."""

    timestamp: str
    device_id: str
    device_type: DeviceType
    device_status: DeviceStatus
    latency_ms: float
    jitter_ms: float
    packet_loss_pct: float
    throughput_mbps: float
    bandwidth_mbps: float
    link_utilization_pct: float
    cpu_pct: float
    memory_pct: float
    queue_drops: int
    interface_errors: int
    link_flaps: int
    wifi_rssi_dbm: Optional[float] = None
    wifi_retransmission_pct: Optional[float] = None
    dns_resolution_ms: Optional[float] = None
    dns_failure_pct: Optional[float] = None
    dhcp_failure_pct: Optional[float] = None


class SyntheticNetworkGenerator:
    """Seeded generator producing deterministic telemetry and topology graphs."""

    DEFAULT_DEVICES = [
        # Core & Distribution
        {"id": "core-rtr-01", "type": DeviceType.ROUTER, "zone": CampusZone.CORE_DISTRIBUTION_ACCESS, "bandwidth_mbps": 10000.0},
        {"id": "dist-sw-core", "type": DeviceType.SWITCH, "zone": CampusZone.CORE_DISTRIBUTION_ACCESS, "bandwidth_mbps": 10000.0},
        # Department Ethernet
        {"id": "dept-sw-cs-01", "type": DeviceType.SWITCH, "zone": CampusZone.DEPARTMENT_ETHERNET, "bandwidth_mbps": 1000.0},
        {"id": "host-cs-lab-01", "type": DeviceType.HOST, "zone": CampusZone.DEPARTMENT_ETHERNET, "bandwidth_mbps": 1000.0},
        # Hostel Wi-Fi
        {"id": "dist-sw-hostel", "type": DeviceType.SWITCH, "zone": CampusZone.CORE_DISTRIBUTION_ACCESS, "bandwidth_mbps": 10000.0},
        {"id": "ap-hostel-b1", "type": DeviceType.ACCESS_POINT, "zone": CampusZone.HOSTEL_WIFI, "bandwidth_mbps": 1000.0},
        {"id": "host-student-01", "type": DeviceType.HOST, "zone": CampusZone.HOSTEL_WIFI, "bandwidth_mbps": 300.0},
        # Lecture Halls
        {"id": "ap-lecture-lh1", "type": DeviceType.ACCESS_POINT, "zone": CampusZone.LECTURE_HALLS, "bandwidth_mbps": 1000.0},
    ]

    DEFAULT_EDGES = [
        {"source": "core-rtr-01", "target": "dist-sw-core", "bandwidth_mbps": 10000.0, "media_type": "fiber", "zone": CampusZone.CORE_DISTRIBUTION_ACCESS},
        {"source": "dist-sw-core", "target": "dept-sw-cs-01", "bandwidth_mbps": 1000.0, "media_type": "fiber", "zone": CampusZone.DEPARTMENT_ETHERNET},
        {"source": "dept-sw-cs-01", "target": "host-cs-lab-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "zone": CampusZone.DEPARTMENT_ETHERNET},
        {"source": "dist-sw-core", "target": "dist-sw-hostel", "bandwidth_mbps": 10000.0, "media_type": "fiber", "zone": CampusZone.CORE_DISTRIBUTION_ACCESS},
        {"source": "dist-sw-hostel", "target": "ap-hostel-b1", "bandwidth_mbps": 1000.0, "media_type": "copper", "zone": CampusZone.HOSTEL_WIFI},
        {"source": "ap-hostel-b1", "target": "host-student-01", "bandwidth_mbps": 300.0, "media_type": "wireless", "zone": CampusZone.HOSTEL_WIFI},
        {"source": "dist-sw-core", "target": "ap-lecture-lh1", "bandwidth_mbps": 1000.0, "media_type": "copper", "zone": CampusZone.LECTURE_HALLS},
    ]

    @classmethod
    def generate(
        cls,
        scenario: str = "normal_operation",
        seed: int = 42,
        noise_level: float = 0.0,
        missing_sample_rate: float = 0.0,
        staleness_seconds: float = 0.0,
        base_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate deterministic telemetry and topology dataset for a scenario.

        Args:
            scenario: Fault pattern identifier
            seed: Pseudo-random seed guaranteeing exact reproducibility
            noise_level: Standard deviation scale (0.0 to 1.0) for Gaussian noise
            missing_sample_rate: Proportion of fields to drop as None (0.0 to 1.0)
            staleness_seconds: Time offset to simulate stale/lagging telemetry
            base_time: Fixed start timestamp, defaults to 2026-10-31T12:00:00Z
        """
        rng = random.Random(seed)
        start_dt = base_time or datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
        effective_dt = start_dt - timedelta(seconds=staleness_seconds)
        timestamp_str = effective_dt.isoformat()

        telemetry_records: List[Dict[str, Any]] = []

        # Generate per-device telemetry
        for dev in cls.DEFAULT_DEVICES:
            dev_id = dev["id"]
            dev_type = dev["type"]
            zone = dev["zone"]
            bw = dev["bandwidth_mbps"]

            # Baseline nominal metrics
            lat = rng.uniform(2.0, 6.0)
            jit = rng.uniform(0.5, 2.0)
            loss = rng.uniform(0.0, 0.2)
            util = rng.uniform(15.0, 35.0)
            cpu = rng.uniform(15.0, 30.0)
            mem = rng.uniform(25.0, 45.0)
            q_drops = 0
            if_errs = 0
            flaps = 0
            rssi = rng.uniform(-55.0, -45.0) if dev_type in (DeviceType.ACCESS_POINT, DeviceType.HOST) else None
            wifi_retx = rng.uniform(1.0, 4.0) if dev_type in (DeviceType.ACCESS_POINT, DeviceType.HOST) else None
            dns_res = rng.uniform(12.0, 25.0)
            dns_fail = 0.0
            dhcp_fail = 0.0
            status = DeviceStatus.ONLINE

            # Apply scenario-specific signatures
            if scenario == "link_congestion":
                if dev_id in ("core-rtr-01", "dist-sw-core"):
                    util = rng.uniform(92.0, 98.5)
                    lat = rng.uniform(110.0, 160.0)
                    jit = rng.uniform(25.0, 45.0)
                    loss = rng.uniform(4.5, 9.0)
                    q_drops = rng.randint(450, 1800)
                    status = DeviceStatus.DEGRADED

            elif scenario == "weak_wifi_signal":
                if dev_id in ("ap-hostel-b1", "host-student-01"):
                    rssi = rng.uniform(-88.0, -82.0)
                    wifi_retx = rng.uniform(28.0, 45.0)
                    loss = rng.uniform(8.0, 18.0)
                    lat = rng.uniform(45.0, 90.0)
                    status = DeviceStatus.DEGRADED

            elif scenario == "ethernet_interface_fault":
                if dev_id == "dept-sw-cs-01":
                    if_errs = rng.randint(1800, 6500)
                    flaps = rng.randint(5, 14)
                    loss = rng.uniform(6.0, 15.0)
                    status = DeviceStatus.DEGRADED

            elif scenario == "dns_failure":
                dns_res = rng.uniform(2500.0, 4500.0)
                dns_fail = rng.uniform(82.0, 99.0)
                status = DeviceStatus.DEGRADED

            elif scenario == "dhcp_failure":
                if dev_type == DeviceType.HOST:
                    dhcp_fail = rng.uniform(78.0, 95.0)
                    status = DeviceStatus.DEGRADED

            elif scenario == "device_cpu_overload":
                if dev_id == "core-rtr-01":
                    cpu = rng.uniform(96.0, 99.5)
                    mem = rng.uniform(88.0, 94.0)
                    lat = rng.uniform(80.0, 130.0)
                    q_drops = rng.randint(300, 900)
                    status = DeviceStatus.DEGRADED

            elif scenario == "upstream_failure_cascade":
                if dev_id == "core-rtr-01":
                    status = DeviceStatus.OFFLINE
                    loss = 100.0
                elif dev_id == "dist-sw-core":
                    util = rng.uniform(95.0, 99.9)
                    q_drops = rng.randint(1200, 3500)
                    lat = rng.uniform(180.0, 320.0)
                    status = DeviceStatus.DEGRADED

            elif scenario == "ambiguous_multi_fault":
                # Multiple simultaneous faults pointing in contradictory directions
                if dev_id == "ap-hostel-b1":
                    rssi = -85.0
                    wifi_retx = 35.0
                if dev_id == "core-rtr-01":
                    cpu = 95.0
                dns_fail = 45.0

            elif scenario == "insufficient_data":
                # Only produce 1 device record and drop almost all signals
                if dev_id != "core-rtr-01":
                    continue
                loss = 1.5

            # Apply Noise Knob (Gaussian perturbation)
            if noise_level > 0.0:
                noise_factor = rng.gauss(1.0, noise_level * 0.15)
                lat = max(0.1, lat * noise_factor)
                jit = max(0.01, jit * noise_factor)
                cpu = max(0.0, min(100.0, cpu * noise_factor))
                util = max(0.0, min(100.0, util * noise_factor))

            throughput = round((util / 100.0) * bw, 2)

            rec_dict: Dict[str, Any] = {
                "timestamp": timestamp_str,
                "device_id": dev_id,
                "device_type": dev_type.value,
                "device_status": status.value,
                "latency_ms": round(lat, 2),
                "jitter_ms": round(jit, 2),
                "packet_loss_pct": round(loss, 2),
                "throughput_mbps": throughput,
                "bandwidth_mbps": bw,
                "link_utilization_pct": round(util, 2),
                "cpu_pct": round(cpu, 1),
                "memory_pct": round(mem, 1),
                "queue_drops": q_drops,
                "interface_errors": if_errs,
                "link_flaps": flaps,
                "wifi_rssi_dbm": round(rssi, 1) if rssi is not None else None,
                "wifi_retransmission_pct": round(wifi_retx, 1) if wifi_retx is not None else None,
                "dns_resolution_ms": round(dns_res, 1) if dns_res is not None else None,
                "dns_failure_pct": round(dns_fail, 1) if dns_fail is not None else None,
                "dhcp_failure_pct": round(dhcp_fail, 1) if dhcp_fail is not None else None,
            }

            # Apply Missing-Sample Knob
            if missing_sample_rate > 0.0:
                for k in list(rec_dict.keys()):
                    if k not in ("timestamp", "device_id", "device_type"):
                        if rng.random() < missing_sample_rate:
                            rec_dict[k] = None

            telemetry_records.append(rec_dict)

        # Assemble full incident schema conforming dataset
        incident_id = f"inc-{scenario.replace('_', '-')}-{seed}"
        result_dataset = {
            "incident_id": incident_id,
            "network_id": "iit-bbs-campus-fabric",
            "scenario": scenario,
            "seed": seed,
            "generated_at": timestamp_str,
            "description": f"Synthetic incident telemetry for scenario '{scenario}' (seed={seed})",
            "topology": {
                "nodes": [
                    {
                        "id": d["id"],
                        "role": d["type"].value,
                        "zone": d["zone"].value,
                        "bandwidth_mbps": d["bandwidth_mbps"],
                    }
                    for d in cls.DEFAULT_DEVICES
                ],
                "links": [
                    {
                        "source": e["source"],
                        "source_interface": "eth0",
                        "target": e["target"],
                        "target_interface": "eth0",
                        "speed_bps": int(e["bandwidth_mbps"] * 1_000_000),
                        "media_type": e["media_type"],
                        "zone": e["zone"].value,
                    }
                    for e in cls.DEFAULT_EDGES
                ],
            },
            "telemetry": telemetry_records,
            "configurations": [],
            "logs": [],
        }

        return result_dataset

    @classmethod
    def save_scenario_to_disk(
        cls,
        scenario: str,
        output_path: Path,
        seed: int = 42,
        noise_level: float = 0.0,
        missing_sample_rate: float = 0.0,
        staleness_seconds: float = 0.0,
    ) -> Path:
        """Generate and serialize scenario dataset to file."""
        data = cls.generate(
            scenario=scenario,
            seed=seed,
            noise_level=noise_level,
            missing_sample_rate=missing_sample_rate,
            staleness_seconds=staleness_seconds,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return output_path

