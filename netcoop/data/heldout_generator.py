from netcoop.data.generator import (
    DeviceStatus,
    DeviceType,
    NoiseShape,
    SeverityLevel,
)
"""Held-out synthetic telemetry generator with heavy-tailed, bursty noise profiles.

This generator is independently designed against schemas/telemetry.json and docs/contract.md.
It produces the same canonical schema as the production generator, but with deliberately
distinct statistical properties:
- Heavy-tailed noise (Pareto and Log-Normal instead of standard Gaussian)
- Variable fault onset timing (early, mid, late, intermittent)
- Wide severity ranges (milder borderline cases and extreme saturations)
- Bursty missing-data intervals (temporal outages and asynchronous telemetry drops)
- Unique compound fault combinations
"""

import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class HeldoutTelemetryGenerator:
    """Seeded held-out telemetry generator with non-Gaussian statistical distributions."""

    SUPPORTED_SCENARIOS = [
        "normal_operation",
        "link_congestion",
        "ethernet_interface_fault",
        "weak_wifi_signal",
        "dns_failure",
        "dhcp_failure",
        "device_cpu_overload",
        "upstream_failure_cascade",
        "ambiguous_multi_fault",
        "insufficient_data",
        "mtu_mismatch_blackhole",
        "01_mtu_mismatch_blackhole",
        "bgp_route_flap_damping",
        "02_bgp_route_flap_damping",
        "optical_crc_degradation",
        "03_optical_crc_degradation",
        "stp_split_brain_loop",
        "04_stp_split_brain_loop",
        "insufficient_evidence_sparse",
        "05_insufficient_evidence_sparse",
        "compound_cpu_and_link",
        "compound_wifi_and_dns",
        "compound_optics_and_flaps",
    ]

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def _heavy_tail_noise(self, scale: float = 1.0, shape: float = 3.0) -> float:
        """Generate heavy-tailed asymmetric noise using a centered Pareto-derived distribution."""
        # Pareto distribution has heavy polynomial decay tail: P(X > x) ~ x^(-shape)
        val = (self.rng.paretovariate(shape) - 1.0) * scale
        # Randomly assign sign for bidirectional noise spikes
        sign = 1.0 if self.rng.random() > 0.4 else -0.5
        return val * sign

    def _lognormal_value(self, mean: float, sigma: float = 0.4) -> float:
        """Sample from Log-Normal distribution for bursty positive metric variations."""
        mu = math.log(max(mean, 0.001))
        return self.rng.lognormvariate(mu, sigma)

    def _build_topology(self) -> Dict[str, Any]:
        """Construct canonical campus topology with spine, leaf, and edge access devices."""
        nodes = [
            {"id": "spine-01", "role": "spine", "management_ip": "10.0.0.1", "vendor": "arista", "os_version": "eos-4.28"},
            {"id": "spine-02", "role": "spine", "management_ip": "10.0.0.2", "vendor": "arista", "os_version": "eos-4.28"},
            {"id": "leaf-01", "role": "leaf", "management_ip": "10.0.1.1", "vendor": "cisco", "os_version": "nxos-9.3"},
            {"id": "leaf-02", "role": "leaf", "management_ip": "10.0.1.2", "vendor": "cisco", "os_version": "nxos-9.3"},
            {"id": "access-01", "role": "access", "management_ip": "10.0.2.1", "vendor": "juniper", "os_version": "junos-21.4"},
            {"id": "access-02", "role": "access", "management_ip": "10.0.2.2", "vendor": "juniper", "os_version": "junos-21.4"},
            {"id": "core-gw-01", "role": "gateway", "management_ip": "10.0.254.1", "vendor": "cisco", "os_version": "iosxe-17.6"},
            {"id": "ap-cs-01", "role": "wireless_ap", "management_ip": "10.0.10.1", "vendor": "aruba", "os_version": "aos-8.10"},
        ]

        links = [
            {"source": "spine-01", "source_interface": "et-0/0/1", "target": "leaf-01", "target_interface": "et-0/0/1", "speed_bps": 100_000_000_000, "media_type": "fiber"},
            {"source": "spine-01", "source_interface": "et-0/0/2", "target": "leaf-02", "target_interface": "et-0/0/1", "speed_bps": 100_000_000_000, "media_type": "fiber"},
            {"source": "spine-02", "source_interface": "et-0/0/1", "target": "leaf-01", "target_interface": "et-0/0/2", "speed_bps": 100_000_000_000, "media_type": "fiber"},
            {"source": "spine-02", "source_interface": "et-0/0/2", "target": "leaf-02", "target_interface": "et-0/0/2", "speed_bps": 100_000_000_000, "media_type": "fiber"},
            {"source": "leaf-01", "source_interface": "GigabitEthernet0/1", "target": "access-01", "target_interface": "GigabitEthernet0/1", "speed_bps": 10_000_000_000, "media_type": "copper"},
            {"source": "leaf-02", "source_interface": "GigabitEthernet0/1", "target": "access-02", "target_interface": "GigabitEthernet0/1", "speed_bps": 10_000_000_000, "media_type": "copper"},
            {"source": "spine-01", "source_interface": "et-0/0/0", "target": "core-gw-01", "target_interface": "TenGigabitEthernet0/0/0", "speed_bps": 100_000_000_000, "media_type": "fiber"},
            {"source": "access-01", "source_interface": "GigabitEthernet0/2", "target": "ap-cs-01", "target_interface": "eth0", "speed_bps": 1_000_000_000, "media_type": "copper"},
        ]

        return {"nodes": nodes, "links": links}

    def generate_scenario(
        self,
        scenario: str,
        duration_seconds: int = 300,
        step_seconds: int = 15,
        base_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate full canonical dataset for the specified scenario with held-out parameters."""
        normalized_scenario = scenario.lower().strip()
        # Handle prefix aliases
        for prefix in ["01_", "02_", "03_", "04_", "05_"]:
            if normalized_scenario.startswith(prefix):
                normalized_scenario = normalized_scenario[len(prefix):]

        if base_time is None:
            base_time = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)

        topology = self._build_topology()
        telemetry_records: List[Dict[str, Any]] = []
        routing_state: Dict[str, Any] = {"bgp_sessions": [], "stp_state": []}
        configurations: List[Dict[str, Any]] = []
        logs: List[Dict[str, Any]] = []

        total_steps = max(1, duration_seconds // step_seconds)

        # Fault onset and severity configuration with held-out statistical parameters
        # Onset can be early (15%), mid (45%), late (75%), or intermittent
        onset_step = self._determine_onset_step(normalized_scenario, total_steps)
        severity_mult = self._determine_severity_multiplier(normalized_scenario)

        # Missing data bursts: simulate network dropouts on specific devices
        drop_gaps = self._generate_bursty_gaps(total_steps, normalized_scenario)

        # Generate telemetry series step by step
        for step in range(total_steps):
            current_time = base_time + timedelta(seconds=step * step_seconds)
            time_str = current_time.isoformat()
            is_fault_active = self._is_fault_active_at_step(normalized_scenario, step, onset_step)

            for node in topology["nodes"]:
                dev_id = node["id"]
                # Skip emitting telemetry if inside a bursty drop gap
                if (dev_id, step) in drop_gaps:
                    continue

                records = self._generate_device_telemetry(
                    dev_id=dev_id,
                    scenario=normalized_scenario,
                    is_fault_active=is_fault_active,
                    severity_mult=severity_mult,
                    timestamp_utc=time_str,
                )
                telemetry_records.extend(records)

        # Populate scenario-specific routing state, configs, and syslogs
        routing_state = self._generate_routing_state(normalized_scenario, severity_mult)
        configurations = self._generate_configurations(normalized_scenario, base_time)
        logs = self._generate_syslogs(normalized_scenario, base_time, onset_step, step_seconds, severity_mult)

        incident_id = f"inc-{scenario.replace('_', '-')}-{self.seed}"

        return {
            "incident_id": incident_id,
            "network_id": "iit-bbs-campus-fabric",
            "timestamp_utc": base_time.isoformat(),
            "description": f"Held-out benchmark evaluation dataset for scenario '{scenario}' (seed={self.seed})",
            "topology": topology,
            "telemetry": telemetry_records,
            "routing_state": routing_state,
            "configurations": configurations,
            "logs": logs,
        }

    def _determine_onset_step(self, scenario: str, total_steps: int) -> int:
        """Determine variable fault onset timing (early, mid, late) with seed variance."""
        if scenario in ["normal_operation", "insufficient_data", "insufficient_evidence_sparse"]:
            return total_steps + 1  # Never occurs

        onset_profiles = {
            "link_congestion": 0.20,             # Early burst
            "ethernet_interface_fault": 0.50,     # Mid onset
            "weak_wifi_signal": 0.15,             # Early onset
            "dns_failure": 0.40,                 # Mid onset
            "dhcp_failure": 0.60,                # Late onset
            "device_cpu_overload": 0.30,         # Early-mid
            "upstream_failure_cascade": 0.65,    # Late onset
            "mtu_mismatch_blackhole": 0.10,      # Immediately misconfigured
            "bgp_route_flap_damping": 0.35,      # Mid onset
            "optical_crc_degradation": 0.25,     # Early-mid
            "stp_split_brain_loop": 0.55,        # Mid-late loop closure
            "compound_cpu_and_link": 0.25,
            "compound_wifi_and_dns": 0.20,
            "compound_optics_and_flaps": 0.30,
        }
        base_fraction = onset_profiles.get(scenario, 0.40)
        # Add random jitter between -0.08 and +0.08
        jitter = (self.rng.random() - 0.5) * 0.16
        final_fraction = max(0.05, min(0.85, base_fraction + jitter))
        return int(total_steps * final_fraction)

    def _is_fault_active_at_step(self, scenario: str, step: int, onset_step: int) -> bool:
        """Evaluate if fault conditions are active at step, including oscillating bursts."""
        if step < onset_step:
            return False

        # For intermittent scenarios, toggle on/off in bursts
        if "flap" in scenario or scenario == "ambiguous_multi_fault":
            # Oscillate every 3 steps
            cycle = (step - onset_step) % 6
            return cycle < 4

        return True

    def _determine_severity_multiplier(self, scenario: str) -> float:
        """Draw severity multiplier from wide bounded range (milder and extreme faults)."""
        # Seeded draw from beta-like or skewed uniform distribution
        # Multiplier ranges from 0.75 (mild/borderline) to 1.65 (extreme saturation)
        return round(self.rng.uniform(0.75, 1.65), 3)

    def _generate_bursty_gaps(self, total_steps: int, scenario: str) -> set:
        """Generate bursty drop gaps where contiguous telemetry records are dropped."""
        drop_gaps = set()
        if scenario in ["insufficient_data", "insufficient_evidence_sparse"]:
            # Drop 60-80% of telemetry data points
            for s in range(total_steps):
                for dev in ["spine-01", "spine-02", "leaf-01", "leaf-02", "access-01", "access-02", "core-gw-01", "ap-cs-01"]:
                    if self.rng.random() < 0.70:
                        drop_gaps.add((dev, s))
            return drop_gaps

        # Standard scenarios: introduce 1 or 2 burst drop windows per device (2-4 consecutive steps)
        for dev in ["leaf-01", "access-02", "ap-cs-01"]:
            if self.rng.random() < 0.45:
                burst_start = self.rng.randint(2, max(3, total_steps - 5))
                burst_len = self.rng.randint(2, 4)
                for b in range(burst_start, min(total_steps, burst_start + burst_len)):
                    drop_gaps.add((dev, b))

        return drop_gaps

    def _generate_device_telemetry(
        self,
        dev_id: str,
        scenario: str,
        is_fault_active: bool,
        severity_mult: float,
        timestamp_utc: str,
    ) -> List[Dict[str, Any]]:
        """Generate canonical metric measurements for a single device with heavy-tailed noise."""
        records: List[Dict[str, Any]] = []

        # Baseline metrics with heavy-tailed noise
        cpu_baseline = 18.0 + self._heavy_tail_noise(scale=2.5, shape=2.5)
        mem_baseline = 38.0 + self._heavy_tail_noise(scale=1.5, shape=3.0)
        loss_baseline = max(0.0, self._heavy_tail_noise(scale=0.04, shape=4.0))
        lat_baseline = 2.2 + max(0.0, self._heavy_tail_noise(scale=0.8, shape=2.2))
        util_baseline = 24.0 + self._heavy_tail_noise(scale=4.0, shape=2.8)

        # Baseline device metrics
        cpu_val = max(1.0, min(100.0, cpu_baseline))
        mem_val = max(5.0, min(100.0, mem_baseline))

        # Scenario-specific fault injections on target devices
        if is_fault_active:
            if scenario in ["link_congestion", "compound_cpu_and_link"] and dev_id in ["spine-01", "leaf-02"]:
                util_val = max(88.0, min(100.0, 92.0 * severity_mult + self._heavy_tail_noise(scale=3.0)))
                loss_val = max(2.5, min(95.0, 12.0 * severity_mult + self._heavy_tail_noise(scale=2.0)))
                queue_drops = int(max(450, 1800 * severity_mult + self._lognormal_value(250, 0.6)))

                records.append(self._metric(dev_id, "et-0/0/1", "link_utilization_pct", util_val, "percent", timestamp_utc))
                records.append(self._metric(dev_id, "et-0/0/1", "packet_loss_pct", loss_val, "percent", timestamp_utc))
                records.append(self._metric(dev_id, "et-0/0/1", "queue_drops", queue_drops, "count", timestamp_utc))

            if scenario in ["device_cpu_overload", "compound_cpu_and_link"] and dev_id == "spine-01":
                cpu_val = max(88.0, min(100.0, 96.0 * severity_mult + self._heavy_tail_noise(scale=1.8)))

            if scenario in ["ethernet_interface_fault", "optical_crc_degradation", "compound_optics_and_flaps"] and dev_id == "leaf-01":
                crc_errors = int(max(15, 120 * severity_mult + self._lognormal_value(40, 0.5)))
                flaps = max(1, int(4 * severity_mult + max(0, self._heavy_tail_noise(scale=1.5))))
                records.append(self._metric(dev_id, "et-0/0/1", "interface_errors", crc_errors, "count", timestamp_utc))
                records.append(self._metric(dev_id, "et-0/0/1", "link_flaps", flaps, "flaps_per_minute", timestamp_utc))

            if scenario in ["weak_wifi_signal", "compound_wifi_and_dns"] and dev_id == "ap-cs-01":
                rssi = max(-95.0, min(-78.0, -82.0 * severity_mult - abs(self._heavy_tail_noise(scale=2.5))))
                retries = max(25.0, min(90.0, 48.0 * severity_mult + self._heavy_tail_noise(scale=4.0)))
                records.append(self._metric(dev_id, "wlan0", "wifi_rssi_dbm", rssi, "dbm", timestamp_utc))
                records.append(self._metric(dev_id, "wlan0", "wifi_retransmission_pct", retries, "percent", timestamp_utc))

            if scenario in ["dns_failure", "compound_wifi_and_dns"] and dev_id == "core-gw-01":
                dns_lat = max(150.0, 850.0 * severity_mult + self._lognormal_value(200, 0.6))
                dns_fail = max(18.0, min(100.0, 42.0 * severity_mult + self._heavy_tail_noise(scale=5.0)))
                records.append(self._metric(dev_id, "management", "dns_resolution_ms", dns_lat, "ms", timestamp_utc))
                records.append(self._metric(dev_id, "management", "dns_failure_pct", dns_fail, "percent", timestamp_utc))

            if scenario == "dhcp_failure" and dev_id == "core-gw-01":
                dhcp_fail = max(30.0, min(100.0, 65.0 * severity_mult + self._heavy_tail_noise(scale=6.0)))
                records.append(self._metric(dev_id, "management", "dhcp_failure_pct", dhcp_fail, "percent", timestamp_utc))

            if scenario == "upstream_failure_cascade" and dev_id == "core-gw-01":
                loss_val = max(75.0, min(100.0, 95.0 * severity_mult))
                lat_val = max(500.0, 1850.0 * severity_mult)
                records.append(self._metric(dev_id, "TenGigabitEthernet0/0/0", "packet_loss_pct", loss_val, "percent", timestamp_utc))
                records.append(self._metric(dev_id, "TenGigabitEthernet0/0/0", "latency_ms", lat_val, "ms", timestamp_utc))

            if scenario in ["mtu_mismatch_blackhole", "01_mtu_mismatch_blackhole"] and dev_id == "spine-01":
                loss_val = max(15.0, min(80.0, 35.0 * severity_mult + self._heavy_tail_noise(scale=3.0)))
                records.append(self._metric(dev_id, "et-0/0/1", "packet_loss_pct", loss_val, "percent", timestamp_utc))

        # Always emit base CPU and memory
        records.append(self._metric(dev_id, "system", "cpu_pct", round(cpu_val, 2), "percent", timestamp_utc))
        records.append(self._metric(dev_id, "system", "memory_pct", round(mem_val, 2), "percent", timestamp_utc))

        return records

    def _metric(self, device: str, interface: str, metric: str, value: Any, unit: str, timestamp_utc: str) -> Dict[str, Any]:
        """Construct validated canonical telemetry item."""
        if isinstance(value, float):
            value = round(value, 2)
        return {
            "device": device,
            "interface": interface,
            "metric": metric,
            "value": value,
            "unit": unit,
            "timestamp_utc": timestamp_utc,
        }

    def _generate_routing_state(self, scenario: str, severity_mult: float) -> Dict[str, Any]:
        """Generate BGP and STP routing states matching scenario conditions."""
        bgp_sessions = [
            {"device": "spine-01", "peer_ip": "10.0.0.2", "peer_as": 65001, "state": "established", "flaps_count": 0, "prefixes_received": 180},
            {"device": "spine-02", "peer_ip": "10.0.0.1", "peer_as": 65001, "state": "established", "flaps_count": 0, "prefixes_received": 180},
            {"device": "core-gw-01", "peer_ip": "198.51.100.1", "peer_as": 64512, "state": "established", "flaps_count": 0, "prefixes_received": 3400},
        ]

        stp_state = [
            {"device": "leaf-01", "root_bridge": "spine-01", "blocked_ports": ["et-0/0/2"], "bpdu_filter_enabled": False},
            {"device": "leaf-02", "root_bridge": "spine-01", "blocked_ports": ["et-0/0/2"], "bpdu_filter_enabled": False},
        ]

        if scenario in ["bgp_route_flap_damping", "02_bgp_route_flap_damping", "compound_optics_and_flaps"]:
            flaps = int(max(6, 18 * severity_mult))
            bgp_sessions[0]["state"] = "active"
            bgp_sessions[0]["flaps_count"] = flaps
            bgp_sessions[0]["prefixes_received"] = 42

        if scenario in ["stp_split_brain_loop", "04_stp_split_brain_loop"]:
            stp_state[0]["blocked_ports"] = []
            stp_state[0]["bpdu_filter_enabled"] = True
            stp_state[1]["blocked_ports"] = []

        return {"bgp_sessions": bgp_sessions, "stp_state": stp_state}

    def _generate_configurations(self, scenario: str, base_time: datetime) -> List[Dict[str, Any]]:
        """Generate device running configurations and candidate diffs."""
        time_str = base_time.isoformat()
        configs: List[Dict[str, Any]] = []

        if scenario in ["mtu_mismatch_blackhole", "01_mtu_mismatch_blackhole"]:
            configs.append({
                "device": "spine-01",
                "timestamp_utc": time_str,
                "running_config": {
                    "interfaces": {
                        "et-0/0/1": {"mtu": 1500, "description": "Link to leaf-02"},
                        "et-0/0/2": {"mtu": 9000, "description": "Link to leaf-01"},
                    }
                },
                "candidate_diff": "+ interface et-0/0/1\\n- mtu 9000\\n+ mtu 1500",
            })
            configs.append({
                "device": "leaf-02",
                "timestamp_utc": time_str,
                "running_config": {
                    "interfaces": {
                        "et-0/0/1": {"mtu": 9000, "description": "Link to spine-01"},
                    }
                },
                "candidate_diff": "",
            })
        else:
            configs.append({
                "device": "spine-01",
                "timestamp_utc": time_str,
                "running_config": {
                    "interfaces": {
                        "et-0/0/1": {"mtu": 9000, "description": "Link to leaf-02"},
                        "et-0/0/2": {"mtu": 9000, "description": "Link to leaf-01"},
                    }
                },
                "candidate_diff": "",
            })

        return configs

    def _generate_syslogs(
        self,
        scenario: str,
        base_time: datetime,
        onset_step: int,
        step_seconds: int,
        severity_mult: float,
    ) -> List[Dict[str, Any]]:
        """Generate syslog event sequence corresponding to fault signatures."""
        logs: List[Dict[str, Any]] = []
        fault_time = base_time + timedelta(seconds=onset_step * step_seconds)

        if scenario in ["link_congestion", "compound_cpu_and_link"]:
            logs.append({
                "device": "spine-01",
                "timestamp_utc": (fault_time + timedelta(seconds=5)).isoformat(),
                "severity": 3,
                "facility": "QUEUE",
                "message": f"%ETH-QUEUE-3-DROP_BURST: Interface et-0/0/1 egress tail-drop burst {int(1200 * severity_mult)} packets",
            })
        elif scenario in ["ethernet_interface_fault", "optical_crc_degradation", "compound_optics_and_flaps"]:
            logs.append({
                "device": "leaf-01",
                "timestamp_utc": (fault_time + timedelta(seconds=12)).isoformat(),
                "severity": 4,
                "facility": "LINK",
                "message": "%ETH-4-CRC_WARN: Interface et-0/0/1 RX frame check sequence CRC errors accumulating",
            })
            logs.append({
                "device": "leaf-01",
                "timestamp_utc": (fault_time + timedelta(seconds=30)).isoformat(),
                "severity": 2,
                "facility": "LINK",
                "message": "%ETH-2-FLAP: Interface et-0/0/1 carrier state transition down-up detected",
            })
        elif scenario in ["bgp_route_flap_damping", "02_bgp_route_flap_damping"]:
            logs.append({
                "device": "spine-01",
                "timestamp_utc": (fault_time + timedelta(seconds=15)).isoformat(),
                "severity": 3,
                "facility": "BGP",
                "message": "%BGP-3-DAMPENING: Peer 10.0.0.2 route flap penalty exceeded threshold; suppressing prefixes",
            })
        elif scenario in ["device_cpu_overload"]:
            logs.append({
                "device": "spine-01",
                "timestamp_utc": (fault_time + timedelta(seconds=10)).isoformat(),
                "severity": 2,
                "facility": "SYS",
                "message": f"%SYS-2-CPU_HIGH: Control plane CPU threshold exceeded: {min(100.0, 96.0 * severity_mult):.1f}%",
            })

        return logs




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



def main() -> None:
    """CLI entry point for held-out telemetry generator."""
    parser = argparse.ArgumentParser(
        description="NetCoop Held-Out Telemetry Dataset Generator with Non-Gaussian Noise Shapes"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="link_congestion",
        help="Scenario identifier (e.g., link_congestion, weak_wifi_signal, normal_operation)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for strict reproducible generation",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Observation duration in seconds (default: 300)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=15,
        help="Sampling step interval in seconds (default: 15)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Target output file path (e.g. data/heldout_sample.json); stdout if omitted",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="Print list of all supported scenarios and exit",
    )

    args = parser.parse_args()

    if args.list_scenarios:
        print("Supported Held-Out Scenarios:")
        for sc in HeldoutTelemetryGenerator.SUPPORTED_SCENARIOS:
            print(f"  - {sc}")
        return

    generator = HeldoutTelemetryGenerator(seed=args.seed)
    dataset = generator.generate_scenario(
        scenario=args.scenario,
        duration_seconds=args.duration,
        step_seconds=args.step,
    )

    json_str = json.dumps(dataset, indent=2)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_str, encoding="utf-8")
        print(f"Held-out scenario '{args.scenario}' (seed={args.seed}) written to: {out_path}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
