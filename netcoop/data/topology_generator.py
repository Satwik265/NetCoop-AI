"""Topology-randomized network telemetry and topology generator.

Supports device counts from 4 to 16, heterogeneous equipment roles,
variable link capacities (100M - 100G), and multi-topology split manifests.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from netcoop.data.generator import DeviceStatus, DeviceType, NoiseShape, SeverityLevel


class NetworkRole(str, Enum):
    """Network equipment role in topology hierarchy."""
    ROUTER = "router"
    SWITCH = "switch"
    ACCESS_POINT = "access_point"
    HOST = "host"


TOPOLOGY_REGISTRY: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # Training Topologies (Device count 4 to 16)
    # -------------------------------------------------------------------------
    "train_branch_4": {
        "description": "Small branch office: 1 border router, 1 PoE switch, 1 AP, 1 workstation (4 devices)",
        "device_count": 4,
        "nodes": [
            {"id": "br-rtr-01", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 1000.0, "zone": "branch_wan"},
            {"id": "br-sw-01", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 1000.0, "zone": "branch_lan"},
            {"id": "br-ap-01", "type": DeviceType.ACCESS_POINT, "role": "access_point", "bandwidth_mbps": 1000.0, "zone": "branch_wifi"},
            {"id": "br-host-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 300.0, "zone": "branch_wifi"},
        ],
        "links": [
            {"source": "br-rtr-01", "target": "br-sw-01", "bandwidth_mbps": 1000.0, "media_type": "fiber", "source_interface": "ge-0/0/0", "target_interface": "ge-0/0/1"},
            {"source": "br-sw-01", "target": "br-ap-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/2", "target_interface": "eth0"},
            {"source": "br-ap-01", "target": "br-host-01", "bandwidth_mbps": 300.0, "media_type": "wireless", "source_interface": "wlan0", "target_interface": "wlan0"},
        ],
    },
    "train_campus_8": {
        "description": "Mid-sized campus network: 2 core routers, 2 distribution/access switches, 2 APs, 2 hosts (8 devices)",
        "device_count": 8,
        "nodes": [
            {"id": "core-rtr-01", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 10000.0, "zone": "core"},
            {"id": "core-rtr-02", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 10000.0, "zone": "core"},
            {"id": "dist-sw-01", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 10000.0, "zone": "distribution"},
            {"id": "access-sw-01", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 1000.0, "zone": "access"},
            {"id": "ap-zone-a", "type": DeviceType.ACCESS_POINT, "role": "access_point", "bandwidth_mbps": 1000.0, "zone": "wifi_zone_a"},
            {"id": "ap-zone-b", "type": DeviceType.ACCESS_POINT, "role": "access_point", "bandwidth_mbps": 1000.0, "zone": "wifi_zone_b"},
            {"id": "host-work-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 1000.0, "zone": "access"},
            {"id": "host-wifi-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 300.0, "zone": "wifi_zone_a"},
        ],
        "links": [
            {"source": "core-rtr-01", "target": "core-rtr-02", "bandwidth_mbps": 10000.0, "media_type": "fiber", "source_interface": "xe-0/0/0", "target_interface": "xe-0/0/0"},
            {"source": "core-rtr-01", "target": "dist-sw-01", "bandwidth_mbps": 10000.0, "media_type": "fiber", "source_interface": "xe-0/0/1", "target_interface": "xe-0/0/1"},
            {"source": "core-rtr-02", "target": "dist-sw-01", "bandwidth_mbps": 10000.0, "media_type": "fiber", "source_interface": "xe-0/0/1", "target_interface": "xe-0/0/2"},
            {"source": "dist-sw-01", "target": "access-sw-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/1", "target_interface": "ge-0/0/1"},
            {"source": "dist-sw-01", "target": "ap-zone-a", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/2", "target_interface": "eth0"},
            {"source": "access-sw-01", "target": "ap-zone-b", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/2", "target_interface": "eth0"},
            {"source": "access-sw-01", "target": "host-work-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/3", "target_interface": "eth0"},
            {"source": "ap-zone-a", "target": "host-wifi-01", "bandwidth_mbps": 300.0, "media_type": "wireless", "source_interface": "wlan0", "target_interface": "wlan0"},
        ],
    },
    "train_distribution_12": {
        "description": "Multi-tier distribution network: 2 core routers, 4 switches, 2 APs, 4 hosts (12 devices)",
        "device_count": 12,
        "nodes": [
            {"id": "edge-rtr-01", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 40000.0, "zone": "edge"},
            {"id": "edge-rtr-02", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 40000.0, "zone": "edge"},
            {"id": "agg-sw-01", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 40000.0, "zone": "aggregation"},
            {"id": "agg-sw-02", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 40000.0, "zone": "aggregation"},
            {"id": "dept-sw-01", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 10000.0, "zone": "department"},
            {"id": "dept-sw-02", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 10000.0, "zone": "department"},
            {"id": "ap-north-01", "type": DeviceType.ACCESS_POINT, "role": "access_point", "bandwidth_mbps": 1000.0, "zone": "north_wing"},
            {"id": "ap-south-01", "type": DeviceType.ACCESS_POINT, "role": "access_point", "bandwidth_mbps": 1000.0, "zone": "south_wing"},
            {"id": "srv-db-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 10000.0, "zone": "datacenter"},
            {"id": "srv-app-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 10000.0, "zone": "datacenter"},
            {"id": "work-eng-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 1000.0, "zone": "department"},
            {"id": "mob-user-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 300.0, "zone": "north_wing"},
        ],
        "links": [
            {"source": "edge-rtr-01", "target": "agg-sw-01", "bandwidth_mbps": 40000.0, "media_type": "fiber", "source_interface": "xl-0/0/0", "target_interface": "xl-0/0/1"},
            {"source": "edge-rtr-02", "target": "agg-sw-02", "bandwidth_mbps": 40000.0, "media_type": "fiber", "source_interface": "xl-0/0/0", "target_interface": "xl-0/0/1"},
            {"source": "agg-sw-01", "target": "agg-sw-02", "bandwidth_mbps": 40000.0, "media_type": "fiber", "source_interface": "xl-0/0/2", "target_interface": "xl-0/0/2"},
            {"source": "agg-sw-01", "target": "dept-sw-01", "bandwidth_mbps": 10000.0, "media_type": "fiber", "source_interface": "xe-0/0/1", "target_interface": "xe-0/0/1"},
            {"source": "agg-sw-02", "target": "dept-sw-02", "bandwidth_mbps": 10000.0, "media_type": "fiber", "source_interface": "xe-0/0/1", "target_interface": "xe-0/0/1"},
            {"source": "dept-sw-01", "target": "srv-db-01", "bandwidth_mbps": 10000.0, "media_type": "copper", "source_interface": "xe-0/0/2", "target_interface": "eth0"},
            {"source": "dept-sw-01", "target": "srv-app-01", "bandwidth_mbps": 10000.0, "media_type": "copper", "source_interface": "xe-0/0/3", "target_interface": "eth0"},
            {"source": "dept-sw-02", "target": "work-eng-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/1", "target_interface": "eth0"},
            {"source": "dept-sw-02", "target": "ap-north-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/2", "target_interface": "eth0"},
            {"source": "dept-sw-02", "target": "ap-south-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/3", "target_interface": "eth0"},
            {"source": "ap-north-01", "target": "mob-user-01", "bandwidth_mbps": 300.0, "media_type": "wireless", "source_interface": "wlan0", "target_interface": "wlan0"},
        ],
    },
    "train_datacenter_16": {
        "description": "High-density enterprise datacenter: 4 border/spine routers, 6 leaf/TOR switches, 2 APs, 4 hosts (16 devices)",
        "device_count": 16,
        "nodes": [
            {"id": "spine-01", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 100000.0, "zone": "fabric"},
            {"id": "spine-02", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 100000.0, "zone": "fabric"},
            {"id": "border-gw-01", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 100000.0, "zone": "edge"},
            {"id": "border-gw-02", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 100000.0, "zone": "edge"},
            {"id": "leaf-01", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 40000.0, "zone": "fabric"},
            {"id": "leaf-02", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 40000.0, "zone": "fabric"},
            {"id": "leaf-03", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 40000.0, "zone": "fabric"},
            {"id": "leaf-04", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 40000.0, "zone": "fabric"},
            {"id": "tor-sw-01", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 10000.0, "zone": "rack_1"},
            {"id": "tor-sw-02", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 10000.0, "zone": "rack_2"},
            {"id": "mgmt-ap-01", "type": DeviceType.ACCESS_POINT, "role": "access_point", "bandwidth_mbps": 1000.0, "zone": "noc"},
            {"id": "mgmt-ap-02", "type": DeviceType.ACCESS_POINT, "role": "access_point", "bandwidth_mbps": 1000.0, "zone": "dc_floor"},
            {"id": "node-comp-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 25000.0, "zone": "rack_1"},
            {"id": "node-comp-02", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 25000.0, "zone": "rack_1"},
            {"id": "node-stor-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 25000.0, "zone": "rack_2"},
            {"id": "adm-term-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 1000.0, "zone": "noc"},
        ],
        "links": [
            {"source": "border-gw-01", "target": "spine-01", "bandwidth_mbps": 100000.0, "media_type": "fiber", "source_interface": "et-0/0/0", "target_interface": "et-0/0/0"},
            {"source": "border-gw-02", "target": "spine-02", "bandwidth_mbps": 100000.0, "media_type": "fiber", "source_interface": "et-0/0/0", "target_interface": "et-0/0/0"},
            {"source": "spine-01", "target": "leaf-01", "bandwidth_mbps": 40000.0, "media_type": "fiber", "source_interface": "et-0/0/1", "target_interface": "et-0/0/1"},
            {"source": "spine-01", "target": "leaf-02", "bandwidth_mbps": 40000.0, "media_type": "fiber", "source_interface": "et-0/0/2", "target_interface": "et-0/0/1"},
            {"source": "spine-02", "target": "leaf-03", "bandwidth_mbps": 40000.0, "media_type": "fiber", "source_interface": "et-0/0/1", "target_interface": "et-0/0/1"},
            {"source": "spine-02", "target": "leaf-04", "bandwidth_mbps": 40000.0, "media_type": "fiber", "source_interface": "et-0/0/2", "target_interface": "et-0/0/1"},
            {"source": "leaf-01", "target": "tor-sw-01", "bandwidth_mbps": 10000.0, "media_type": "copper", "source_interface": "xe-0/0/1", "target_interface": "xe-0/0/1"},
            {"source": "leaf-03", "target": "tor-sw-02", "bandwidth_mbps": 10000.0, "media_type": "copper", "source_interface": "xe-0/0/1", "target_interface": "xe-0/0/1"},
            {"source": "tor-sw-01", "target": "node-comp-01", "bandwidth_mbps": 25000.0, "media_type": "copper", "source_interface": "xe-0/0/2", "target_interface": "eth0"},
            {"source": "tor-sw-01", "target": "node-comp-02", "bandwidth_mbps": 25000.0, "media_type": "copper", "source_interface": "xe-0/0/3", "target_interface": "eth0"},
            {"source": "tor-sw-02", "target": "node-stor-01", "bandwidth_mbps": 25000.0, "media_type": "copper", "source_interface": "xe-0/0/2", "target_interface": "eth0"},
            {"source": "leaf-02", "target": "mgmt-ap-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/1", "target_interface": "eth0"},
            {"source": "leaf-04", "target": "mgmt-ap-02", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/1", "target_interface": "eth0"},
            {"source": "mgmt-ap-01", "target": "adm-term-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/2", "target_interface": "eth0"},
        ],
    },

    # -------------------------------------------------------------------------
    # Validation Topology (Device count 7)
    # -------------------------------------------------------------------------
    "validation_mesh_7": {
        "description": "Validation multi-switch campus: 1 core router, 3 switches, 1 AP, 2 hosts (7 devices)",
        "device_count": 7,
        "nodes": [
            {"id": "val-rtr-01", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 20000.0, "zone": "val_core"},
            {"id": "val-agg-sw", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 20000.0, "zone": "val_dist"},
            {"id": "val-acc-sw-1", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 10000.0, "zone": "val_access_a"},
            {"id": "val-acc-sw-2", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 10000.0, "zone": "val_access_b"},
            {"id": "val-ap-01", "type": DeviceType.ACCESS_POINT, "role": "access_point", "bandwidth_mbps": 1000.0, "zone": "val_wifi"},
            {"id": "val-srv-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 10000.0, "zone": "val_access_a"},
            {"id": "val-client-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 300.0, "zone": "val_wifi"},
        ],
        "links": [
            {"source": "val-rtr-01", "target": "val-agg-sw", "bandwidth_mbps": 20000.0, "media_type": "fiber", "source_interface": "xe-0/0/0", "target_interface": "xe-0/0/1"},
            {"source": "val-agg-sw", "target": "val-acc-sw-1", "bandwidth_mbps": 10000.0, "media_type": "fiber", "source_interface": "xe-0/0/2", "target_interface": "xe-0/0/1"},
            {"source": "val-agg-sw", "target": "val-acc-sw-2", "bandwidth_mbps": 10000.0, "media_type": "fiber", "source_interface": "xe-0/0/3", "target_interface": "xe-0/0/1"},
            {"source": "val-acc-sw-1", "target": "val-srv-01", "bandwidth_mbps": 10000.0, "media_type": "copper", "source_interface": "xe-0/0/2", "target_interface": "eth0"},
            {"source": "val-acc-sw-2", "target": "val-ap-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/1", "target_interface": "eth0"},
            {"source": "val-ap-01", "target": "val-client-01", "bandwidth_mbps": 300.0, "media_type": "wireless", "source_interface": "wlan0", "target_interface": "wlan0"},
        ],
    },

    # -------------------------------------------------------------------------
    # TWO Unseen Blind Topologies (MUST NEVER BE INSPECTED BEFORE FREEZE)
    # -------------------------------------------------------------------------
    "blind_edge_iot_6": {
        "description": "Blind Topology 1: Industrial IoT Edge site with field bus switches and sensor hubs (6 devices)",
        "device_count": 6,
        "nodes": [
            {"id": "iot-edge-gw-01", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 10000.0, "zone": "edge_wan"},
            {"id": "iot-field-sw-01", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 2500.0, "zone": "plant_floor"},
            {"id": "iot-field-sw-02", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 2500.0, "zone": "assembly_line"},
            {"id": "iot-ap-sensor-01", "type": DeviceType.ACCESS_POINT, "role": "access_point", "bandwidth_mbps": 1000.0, "zone": "sensor_mesh"},
            {"id": "iot-gateway-box-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 1000.0, "zone": "plant_floor"},
            {"id": "sensor-hub-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 300.0, "zone": "sensor_mesh"},
        ],
        "links": [
            {"source": "iot-edge-gw-01", "target": "iot-field-sw-01", "bandwidth_mbps": 2500.0, "media_type": "fiber", "source_interface": "xe-0/0/1", "target_interface": "xe-0/0/1"},
            {"source": "iot-edge-gw-01", "target": "iot-field-sw-02", "bandwidth_mbps": 2500.0, "media_type": "fiber", "source_interface": "xe-0/0/2", "target_interface": "xe-0/0/1"},
            {"source": "iot-field-sw-01", "target": "iot-gateway-box-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/1", "target_interface": "eth0"},
            {"source": "iot-field-sw-02", "target": "iot-ap-sensor-01", "bandwidth_mbps": 1000.0, "media_type": "copper", "source_interface": "ge-0/0/1", "target_interface": "eth0"},
            {"source": "iot-ap-sensor-01", "target": "sensor-hub-01", "bandwidth_mbps": 300.0, "media_type": "wireless", "source_interface": "wlan0", "target_interface": "wlan0"},
        ],
    },
    "blind_spine_leaf_10": {
        "description": "Blind Topology 2: High-speed spine-leaf compute cluster with redundant fabrics (10 devices)",
        "device_count": 10,
        "nodes": [
            {"id": "blind-spine-01", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 100000.0, "zone": "spine_layer"},
            {"id": "blind-spine-02", "type": DeviceType.ROUTER, "role": "router", "bandwidth_mbps": 100000.0, "zone": "spine_layer"},
            {"id": "blind-leaf-01", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 25000.0, "zone": "leaf_layer"},
            {"id": "blind-leaf-02", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 25000.0, "zone": "leaf_layer"},
            {"id": "blind-leaf-03", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 25000.0, "zone": "leaf_layer"},
            {"id": "blind-leaf-04", "type": DeviceType.SWITCH, "role": "switch", "bandwidth_mbps": 25000.0, "zone": "leaf_layer"},
            {"id": "blind-srv-01", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 25000.0, "zone": "compute_cluster"},
            {"id": "blind-srv-02", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 25000.0, "zone": "compute_cluster"},
            {"id": "blind-srv-03", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 25000.0, "zone": "compute_cluster"},
            {"id": "blind-srv-04", "type": DeviceType.HOST, "role": "host", "bandwidth_mbps": 25000.0, "zone": "compute_cluster"},
        ],
        "links": [
            {"source": "blind-spine-01", "target": "blind-leaf-01", "bandwidth_mbps": 25000.0, "media_type": "fiber", "source_interface": "et-0/0/1", "target_interface": "et-0/0/1"},
            {"source": "blind-spine-01", "target": "blind-leaf-02", "bandwidth_mbps": 25000.0, "media_type": "fiber", "source_interface": "et-0/0/2", "target_interface": "et-0/0/1"},
            {"source": "blind-spine-02", "target": "blind-leaf-03", "bandwidth_mbps": 25000.0, "media_type": "fiber", "source_interface": "et-0/0/1", "target_interface": "et-0/0/1"},
            {"source": "blind-spine-02", "target": "blind-leaf-04", "bandwidth_mbps": 25000.0, "media_type": "fiber", "source_interface": "et-0/0/2", "target_interface": "et-0/0/1"},
            {"source": "blind-leaf-01", "target": "blind-srv-01", "bandwidth_mbps": 25000.0, "media_type": "copper", "source_interface": "xe-0/0/1", "target_interface": "eth0"},
            {"source": "blind-leaf-02", "target": "blind-srv-02", "bandwidth_mbps": 25000.0, "media_type": "copper", "source_interface": "xe-0/0/1", "target_interface": "eth0"},
            {"source": "blind-leaf-03", "target": "blind-srv-03", "bandwidth_mbps": 25000.0, "media_type": "copper", "source_interface": "xe-0/0/1", "target_interface": "eth0"},
            {"source": "blind-leaf-04", "target": "blind-srv-04", "bandwidth_mbps": 25000.0, "media_type": "copper", "source_interface": "xe-0/0/1", "target_interface": "eth0"},
        ],
    },
}


class TopologyRandomizedGenerator:
    """Generates synthetic network telemetry and incidents across arbitrary registered topologies."""

    TRAIN_TOPOLOGIES = [
        "train_branch_4",
        "train_campus_8",
        "train_distribution_12",
        "train_datacenter_16",
    ]
    VALIDATION_TOPOLOGY = "validation_mesh_7"
    BLIND_TOPOLOGY_1 = "blind_edge_iot_6"
    BLIND_TOPOLOGY_2 = "blind_spine_leaf_10"

    @classmethod
    def _heavy_tail_noise(cls, rng: random.Random, scale: float = 1.0, shape: float = 3.0) -> float:
        """Heavy-tailed Pareto perturbation."""
        val = (rng.paretovariate(shape) - 1.0) * scale
        sign = 1.0 if rng.random() > 0.4 else -0.5
        return val * sign

    @classmethod
    def generate(
        cls,
        scenario: str = "normal_operation",
        seed: int = 42,
        topology_name: str = "train_campus_8",
        severity: SeverityLevel = SeverityLevel.HIGH,
        noise_level: float = 0.05,
        noise_shape: NoiseShape = NoiseShape.GAUSSIAN,
        missing_sample_rate: float = 0.0,
        base_time: Optional[datetime] = None,
        use_heavy_tail: bool = False,
    ) -> Dict[str, Any]:
        """Generate deterministic incident on a specific topology."""
        if topology_name not in TOPOLOGY_REGISTRY:
            raise ValueError(f"Unknown topology '{topology_name}'. Registered: {list(TOPOLOGY_REGISTRY.keys())}")

        topo = TOPOLOGY_REGISTRY[topology_name]
        nodes = topo["nodes"]
        links = topo["links"]

        rng = random.Random(seed)
        start_dt = base_time or datetime(2026, 11, 16, 10, 0, 0, tzinfo=timezone.utc)
        timestamp_str = start_dt.isoformat()

        # Severity scale
        sev_scale = 1.0
        if severity == SeverityLevel.LOW:
            sev_scale = 0.7
        elif severity == SeverityLevel.MEDIUM:
            sev_scale = 0.85
        elif severity == SeverityLevel.HIGH:
            sev_scale = 1.0
        elif severity == SeverityLevel.CRITICAL:
            sev_scale = 1.25

        # Group nodes by role
        by_role: Dict[str, List[Dict[str, Any]]] = {
            "router": [],
            "switch": [],
            "access_point": [],
            "host": [],
        }
        for n in nodes:
            r = str(getattr(n.get("type"), "value", n.get("type", ""))).lower()
            if r not in by_role:
                r = str(n.get("role", "host")).lower()
            if r in by_role:
                by_role[r].append(n)
            else:
                by_role["host"].append(n)

        # Identify key target devices per role for fault injection
        primary_router = by_role["router"][0] if by_role["router"] else (nodes[0] if nodes else None)
        primary_switch = by_role["switch"][0] if by_role["switch"] else (nodes[1] if len(nodes) > 1 else None)
        primary_ap = by_role["access_point"][0] if by_role["access_point"] else None
        primary_host = by_role["host"][0] if by_role["host"] else (nodes[-1] if nodes else None)

        telemetry: List[Dict[str, Any]] = []

        for node in nodes:
            d_id = node["id"]
            d_type = node["type"]
            role = str(getattr(d_type, "value", d_type)).lower()
            bw = float(node.get("bandwidth_mbps", 1000.0))

            # Base nominal metrics
            if use_heavy_tail:
                ht = cls._heavy_tail_noise(rng, scale=noise_level * 5.0, shape=3.0)
                lat = max(0.5, rng.uniform(1.8, 4.5) + abs(ht * 0.3))
                jit = max(0.2, rng.uniform(0.5, 1.8) + abs(ht * 0.1))
                loss = 0.0
                util = max(5.0, min(80.0, rng.uniform(18.0, 32.0) + ht))
                cpu = max(5.0, min(80.0, rng.uniform(16.0, 28.0) + ht))
                mem = max(10.0, min(80.0, rng.uniform(25.0, 42.0) + ht))
            else:
                lat = rng.uniform(2.0, 5.5)
                jit = rng.uniform(0.5, 1.8)
                loss = rng.uniform(0.0, 0.2)
                util = rng.uniform(18.0, 32.0)
                cpu = rng.uniform(16.0, 28.0)
                mem = rng.uniform(25.0, 42.0)

            drops = 0
            errs = 0
            flaps = 0
            wifi_rssi = rng.uniform(-55.0, -48.0) if role in ("access_point", "host") else None
            wifi_retx = rng.uniform(1.0, 3.5) if role in ("access_point", "host") else None
            dns_res = rng.uniform(14.0, 24.0)
            dns_fail = 0.0
            dhcp_fail = 0.0
            status = DeviceStatus.ONLINE

            # Apply Fault Signatures based on roles
            if scenario == "link_congestion":
                # Congestion on core router / distribution switch
                target_ids = {primary_router["id"]} if primary_router else set()
                if primary_switch:
                    target_ids.add(primary_switch["id"])
                if d_id in target_ids:
                    util = min(100.0, rng.uniform(92.0, 98.5) * sev_scale)
                    lat = rng.uniform(115.0, 165.0) * sev_scale
                    jit = rng.uniform(25.0, 45.0) * sev_scale
                    loss = rng.uniform(4.5, 9.5) * sev_scale
                    drops = int(rng.randint(500, 1900) * sev_scale)
                    status = DeviceStatus.DEGRADED

            elif scenario == "weak_wifi_signal":
                target_ids = set()
                if primary_ap:
                    target_ids.add(primary_ap["id"])
                if primary_host and (role == "host" or "wifi" in str(primary_host.get("zone", ""))):
                    target_ids.add(primary_host["id"])
                if not target_ids and by_role["host"]:
                    target_ids.add(by_role["host"][0]["id"])

                if d_id in target_ids:
                    wifi_rssi = max(-96.0, rng.uniform(-89.0, -82.0) - (sev_scale - 1.0) * 5.0)
                    wifi_retx = min(100.0, rng.uniform(28.0, 48.0) * sev_scale)
                    loss = min(100.0, rng.uniform(8.0, 18.0) * sev_scale)
                    lat = rng.uniform(45.0, 95.0) * sev_scale
                    status = DeviceStatus.DEGRADED

            elif scenario == "ethernet_interface_fault":
                target_id = primary_switch["id"] if primary_switch else d_id
                if d_id == target_id:
                    errs = int(rng.randint(1800, 6500) * sev_scale)
                    flaps = int(rng.randint(5, 14) * sev_scale)
                    loss = min(100.0, rng.uniform(6.0, 15.0) * sev_scale)
                    status = DeviceStatus.DEGRADED

            elif scenario == "dns_failure":
                # DNS failure manifests network-wide on resolution
                dns_res = rng.uniform(2500.0, 4500.0) * sev_scale
                dns_fail = min(100.0, rng.uniform(82.0, 99.0) * sev_scale)
                status = DeviceStatus.DEGRADED

            elif scenario == "dhcp_failure":
                if role == "host":
                    dhcp_fail = min(100.0, rng.uniform(78.0, 96.0) * sev_scale)
                    status = DeviceStatus.DEGRADED

            elif scenario == "device_cpu_overload":
                target_id = primary_router["id"] if primary_router else d_id
                if d_id == target_id:
                    cpu = min(100.0, rng.uniform(96.0, 99.8) * sev_scale)
                    mem = min(100.0, rng.uniform(88.0, 95.0) * sev_scale)
                    lat = rng.uniform(85.0, 135.0) * sev_scale
                    drops = int(rng.randint(300, 900) * sev_scale)
                    status = DeviceStatus.DEGRADED

            elif scenario == "upstream_failure_cascade":
                if primary_router and d_id == primary_router["id"]:
                    status = DeviceStatus.OFFLINE
                    loss = 100.0
                elif primary_switch and d_id == primary_switch["id"]:
                    util = min(100.0, rng.uniform(95.0, 99.9) * sev_scale)
                    drops = int(rng.randint(1200, 3500) * sev_scale)
                    lat = rng.uniform(180.0, 320.0) * sev_scale
                    status = DeviceStatus.DEGRADED

            elif scenario == "ambiguous_multi_fault":
                if primary_ap and d_id == primary_ap["id"]:
                    wifi_rssi = -86.0
                    wifi_retx = 35.0
                    status = DeviceStatus.DEGRADED
                if primary_router and d_id == primary_router["id"]:
                    cpu = 95.0
                    status = DeviceStatus.DEGRADED
                dns_fail = 45.0

            elif scenario == "insufficient_data":
                # Sparse telemetry: single record missing essential indicators
                if primary_router and d_id != primary_router["id"]:
                    continue
                loss = 1.5

            # Apply missing sample rate (random dropouts)
            if missing_sample_rate > 0.0 and rng.random() < missing_sample_rate:
                continue

            rec = {
                "timestamp": timestamp_str,
                "device_id": d_id,
                "device_type": str(getattr(d_type, "value", d_type)),
                "device_status": str(getattr(status, "value", status)),
                "latency_ms": round(lat, 2),
                "jitter_ms": round(jit, 2),
                "packet_loss_pct": round(loss, 2),
                "throughput_mbps": round((util / 100.0) * bw, 2),
                "bandwidth_mbps": bw,
                "link_utilization_pct": round(util, 2),
                "cpu_pct": round(cpu, 1),
                "memory_pct": round(mem, 1),
                "queue_drops": drops,
                "interface_errors": errs,
                "link_flaps": flaps,
                "wifi_rssi_dbm": round(wifi_rssi, 1) if wifi_rssi is not None else None,
                "wifi_retransmission_pct": round(wifi_retx, 1) if wifi_retx is not None else None,
                "dns_resolution_ms": round(dns_res, 1) if dns_res is not None else None,
                "dns_failure_pct": round(dns_fail, 1) if dns_fail is not None else None,
                "dhcp_failure_pct": round(dhcp_fail, 1) if dhcp_fail is not None else None,
            }
            telemetry.append(rec)

        return {
            "incident_id": f"inc-{scenario.replace('_', '-')}-{seed}-{topology_name}",
            "scenario": scenario,
            "seed": seed,
            "topology_name": topology_name,
            "topology": {
                "nodes": [
                    {
                        "id": n["id"],
                        "type": str(getattr(n["type"], "value", n["type"])),
                        "role": n.get("role", "switch"),
                        "bandwidth_mbps": n.get("bandwidth_mbps", 1000.0),
                        "zone": n.get("zone", "default"),
                    }
                    for n in nodes
                ],
                "links": [
                    {
                        "source": l["source"],
                        "target": l["target"],
                        "bandwidth_mbps": l.get("bandwidth_mbps", 1000.0),
                        "speed_bps": int(l.get("bandwidth_mbps", 1000.0) * 1_000_000),
                        "media_type": l.get("media_type", "fiber"),
                        "source_interface": l.get("source_interface", "eth0"),
                        "target_interface": l.get("target_interface", "eth0"),
                    }
                    for l in links
                ],
            },
            "telemetry": telemetry,
            "configurations": [],
            "logs": [],
        }
