"""Deterministic, seeded synthetic network telemetry and topology generator with split-friendly parameter ranges."""

import json
import math
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


class SeverityLevel(str, Enum):
    """Calibrated severity ratings for scenario faults."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NoiseShape(str, Enum):
    """Stochastic noise distributions."""

    GAUSSIAN = "gaussian"
    UNIFORM = "uniform"
    BURST = "burst"


class TelemetryRecord(BaseModel):
    """Single network device observation record matching specification."""

    timestamp: str
    device_id: str
    device_type: DeviceType
    device_status: DeviceStatus
    latency_ms: Optional[float] = None
    jitter_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    throughput_mbps: Optional[float] = None
    bandwidth_mbps: Optional[float] = None
    link_utilization_pct: Optional[float] = None
    cpu_pct: Optional[float] = None
    memory_pct: Optional[float] = None
    queue_drops: Optional[int] = None
    interface_errors: Optional[int] = None
    link_flaps: Optional[int] = None
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

    # Split-friendly parameter ranges by severity level
    SEVERITY_SCALES = {
        SeverityLevel.LOW: 0.6,
        SeverityLevel.MEDIUM: 0.85,
        SeverityLevel.HIGH: 1.0,
        SeverityLevel.CRITICAL: 1.25,
    }

    @classmethod
    def generate(
        cls,
        scenario: str = "normal_operation",
        seed: int = 42,
        severity: SeverityLevel = SeverityLevel.HIGH,
        noise_level: float = 0.0,
        noise_shape: NoiseShape = NoiseShape.GAUSSIAN,
        missing_sample_rate: float = 0.0,
        staleness_seconds: float = 0.0,
        onset_offset_seconds: float = 0.0,
        base_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate deterministic telemetry and topology dataset for a scenario.

        Split-friendly arguments:
            scenario: Fault pattern or compound fault identifier
            seed: Pseudo-random seed guaranteeing exact reproducibility
            severity: SeverityLevel multiplier (LOW, MEDIUM, HIGH, CRITICAL)
            noise_level: Magnitude of noise perturbation (0.0 to 1.0)
            noise_shape: Noise distribution (GAUSSIAN, UNIFORM, BURST)
            missing_sample_rate: Proportion of optional fields to drop as None (0.0 to 0.8)
            staleness_seconds: Time offset simulating lag/staleness
            onset_offset_seconds: Start offset for fault onset
            base_time: Starting ISO timestamp anchor
        """
        rng = random.Random(seed)
        start_dt = base_time or datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
        effective_dt = start_dt + timedelta(seconds=onset_offset_seconds) - timedelta(seconds=staleness_seconds)
        timestamp_str = effective_dt.isoformat()

        sev_scale = cls.SEVERITY_SCALES.get(severity, 1.0)
        telemetry_records: List[Dict[str, Any]] = []

        for dev in cls.DEFAULT_DEVICES:
            dev_id = dev["id"]
            dev_type = dev["type"]
            zone = dev["zone"]
            bw = dev["bandwidth_mbps"]

            # Baseline nominal parameters
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

            # Apply Scenario Signatures
            if scenario == "link_congestion":
                if dev_id in ("core-rtr-01", "dist-sw-core"):
                    util = min(100.0, rng.uniform(92.0, 98.5) * sev_scale)
                    lat = rng.uniform(110.0, 160.0) * sev_scale
                    jit = rng.uniform(25.0, 45.0) * sev_scale
                    loss = rng.uniform(4.5, 9.0) * sev_scale
                    q_drops = int(rng.randint(450, 1800) * sev_scale)
                    status = DeviceStatus.DEGRADED

            elif scenario == "weak_wifi_signal":
                if dev_id in ("ap-hostel-b1", "host-student-01"):
                    rssi = max(-95.0, rng.uniform(-88.0, -82.0) - (sev_scale - 1.0) * 5.0)
                    wifi_retx = min(100.0, rng.uniform(28.0, 45.0) * sev_scale)
                    loss = min(100.0, rng.uniform(8.0, 18.0) * sev_scale)
                    lat = rng.uniform(45.0, 90.0) * sev_scale
                    status = DeviceStatus.DEGRADED

            elif scenario == "ethernet_interface_fault":
                if dev_id == "dept-sw-cs-01":
                    if_errs = int(rng.randint(1800, 6500) * sev_scale)
                    flaps = int(rng.randint(5, 14) * sev_scale)
                    loss = min(100.0, rng.uniform(6.0, 15.0) * sev_scale)
                    status = DeviceStatus.DEGRADED

            elif scenario == "dns_failure":
                dns_res = rng.uniform(2500.0, 4500.0) * sev_scale
                dns_fail = min(100.0, rng.uniform(82.0, 99.0) * sev_scale)
                status = DeviceStatus.DEGRADED

            elif scenario == "dhcp_failure":
                if dev_type == DeviceType.HOST:
                    dhcp_fail = min(100.0, rng.uniform(78.0, 95.0) * sev_scale)
                    status = DeviceStatus.DEGRADED

            elif scenario == "device_cpu_overload":
                if dev_id == "core-rtr-01":
                    cpu = min(100.0, rng.uniform(96.0, 99.5) * sev_scale)
                    mem = min(100.0, rng.uniform(88.0, 94.0) * sev_scale)
                    lat = rng.uniform(80.0, 130.0) * sev_scale
                    q_drops = int(rng.randint(300, 900) * sev_scale)
                    status = DeviceStatus.DEGRADED

            elif scenario == "upstream_failure_cascade":
                if dev_id == "core-rtr-01":
                    status = DeviceStatus.OFFLINE
                    loss = 100.0
                elif dev_id == "dist-sw-core":
                    util = min(100.0, rng.uniform(95.0, 99.9) * sev_scale)
                    q_drops = int(rng.randint(1200, 3500) * sev_scale)
                    lat = rng.uniform(180.0, 320.0) * sev_scale
                    status = DeviceStatus.DEGRADED

            elif scenario == "ambiguous_multi_fault":
                # Multiple simultaneous conflicting signals
                if dev_id == "ap-hostel-b1":
                    rssi = -85.0
                    wifi_retx = 35.0
                if dev_id == "core-rtr-01":
                    cpu = 95.0
                dns_fail = 45.0

            elif scenario == "insufficient_data":
                # Sparse telemetry: single record missing essential indicators
                if dev_id != "core-rtr-01":
                    continue
                loss = 1.5

            # Compound faults (two simultaneous causes)
            elif scenario in ("compound_cpu_and_link", "compound_faults"):
                # Cause 1: Router CPU Overload
                if dev_id == "core-rtr-01":
                    cpu = min(100.0, rng.uniform(96.0, 99.5) * sev_scale)
                    mem = min(100.0, rng.uniform(88.0, 95.0) * sev_scale)
                    status = DeviceStatus.DEGRADED
                # Cause 2: Link Congestion on core distribution link
                if dev_id in ("core-rtr-01", "dist-sw-core"):
                    util = min(100.0, rng.uniform(93.0, 99.0) * sev_scale)
                    q_drops = int(rng.randint(600, 2200) * sev_scale)
                    lat = rng.uniform(120.0, 200.0) * sev_scale
                    loss = min(100.0, rng.uniform(5.0, 12.0) * sev_scale)
                    status = DeviceStatus.DEGRADED

            elif scenario == "compound_wifi_and_dns":
                # Cause 1: Weak Wi-Fi in hostel
                if dev_id in ("ap-hostel-b1", "host-student-01"):
                    rssi = rng.uniform(-89.0, -84.0)
                    wifi_retx = rng.uniform(30.0, 48.0)
                    loss = rng.uniform(10.0, 20.0)
                    status = DeviceStatus.DEGRADED
                # Cause 2: Campus-wide DNS server resolution failures
                dns_res = rng.uniform(2800.0, 4800.0)
                dns_fail = rng.uniform(85.0, 98.0)

            # Apply Noise Knobs
            if noise_level > 0.0:
                if noise_shape == NoiseShape.GAUSSIAN:
                    noise_factor = rng.gauss(1.0, noise_level * 0.15)
                elif noise_shape == NoiseShape.UNIFORM:
                    noise_factor = rng.uniform(1.0 - noise_level * 0.2, 1.0 + noise_level * 0.2)
                elif noise_shape == NoiseShape.BURST:
                    noise_factor = rng.uniform(1.5, 2.5) if rng.random() < 0.2 else 1.0
                else:
                    noise_factor = 1.0

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

        incident_id = f"inc-{scenario.replace('_', '-')}-{seed}"
        return {
            "incident_id": incident_id,
            "network_id": "iit-bbs-campus-fabric",
            "scenario": scenario,
            "seed": seed,
            "severity": severity.value if isinstance(severity, SeverityLevel) else str(severity),
            "noise_level": noise_level,
            "noise_shape": noise_shape.value if isinstance(noise_shape, NoiseShape) else str(noise_shape),
            "missing_sample_rate": missing_sample_rate,
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

    @classmethod
    def save_scenario_to_disk(
        cls,
        scenario: str,
        output_path: Path,
        seed: int = 42,
        severity: SeverityLevel = SeverityLevel.HIGH,
        noise_level: float = 0.0,
        noise_shape: NoiseShape = NoiseShape.GAUSSIAN,
        missing_sample_rate: float = 0.0,
        staleness_seconds: float = 0.0,
        onset_offset_seconds: float = 0.0,
    ) -> Path:
        """Generate and serialize scenario dataset to file."""
        data = cls.generate(
            scenario=scenario,
            seed=seed,
            severity=severity,
            noise_level=noise_level,
            noise_shape=noise_shape,
            missing_sample_rate=missing_sample_rate,
            staleness_seconds=staleness_seconds,
            onset_offset_seconds=onset_offset_seconds,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return output_path
