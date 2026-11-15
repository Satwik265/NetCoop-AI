"""Generate Phase 13B extended scenario fixtures and register in manifest.json."""
import copy
import json
from pathlib import Path

PROJECT_ROOT = Path(r"D:\NetCoop-AI\Team_inSANE_MITRA_NetCoop-AI")
SCENARIOS_DIR = PROJECT_ROOT / "data" / "scenarios"

from netcoop.data.generator import SyntheticNetworkGenerator

gen = SyntheticNetworkGenerator()

# -----------------------------------------------------------------------------
# 1. link_congestion_with_logs.json
# -----------------------------------------------------------------------------
base_lc = gen.generate("link_congestion", seed=42)
lc_data = copy.deepcopy(base_lc)
lc_data["incident_id"] = "inc-ext-congestion-logs"
lc_data["description"] = "Core link congestion accompanied by queue tail-drop syslogs and QoS shaper config diff."
lc_data["logs"] = [
    {
        "device": "core-rtr-01",
        "timestamp_utc": "2026-11-15T10:14:22Z",
        "severity": 4,
        "facility": "QOS",
        "message": "%QOS-4-QUEUE_DROP: Interface GigabitEthernet0/0/0/1 egress queue 2 tail drop count 740 packets",
    },
    {
        "device": "dist-sw-core",
        "timestamp_utc": "2026-11-15T10:14:25Z",
        "severity": 4,
        "facility": "QOS",
        "message": "%QOS-4-BUFFER_SATURATION: Core trunk port buffer occupancy at 98% capacity, active tail-drop initiated",
    },
]
lc_data["configurations"] = [
    {
        "device": "core-rtr-01",
        "timestamp_utc": "2026-11-15T09:45:00Z",
        "running_config": {
            "interfaces": {
                "GigabitEthernet0/0/0/1": {
                    "description": "Trunk to dist-sw-core",
                    "service_policy_output": "RESTRICTED_EGRESS_SHAPER",
                    "mtu": 1500,
                }
            }
        },
        "candidate_diff": "--- running\n+++ candidate\n@@ -12,3 +12,3 @@\n interface GigabitEthernet0/0/0/1\n- service-policy output ENTERPRISE_DEFAULT\n+ service-policy output RESTRICTED_EGRESS_SHAPER",
    }
]

file_lc = SCENARIOS_DIR / "link_congestion_with_logs.json"
with open(file_lc, "w", encoding="utf-8") as f:
    json.dump(lc_data, f, indent=2)
print(f"Created {file_lc.name}")

# -----------------------------------------------------------------------------
# 2. ethernet_fault_with_logs.json
# -----------------------------------------------------------------------------
base_ef = gen.generate("ethernet_interface_fault", seed=42)
ef_data = copy.deepcopy(base_ef)
ef_data["incident_id"] = "inc-ext-eth-logs"
ef_data["description"] = "Physical Ethernet corruption with CRC error increments and link-flap syslog state transitions."
ef_data["logs"] = [
    {
        "device": "dept-sw-cs-01",
        "timestamp_utc": "2026-11-15T11:02:14Z",
        "severity": 3,
        "facility": "ETH",
        "message": "%ETH-4-CRC_ERR: Interface FastEthernet0/1 input CRC errors exceeded threshold (count: 2450)",
    },
    {
        "device": "dept-sw-cs-01",
        "timestamp_utc": "2026-11-15T11:02:20Z",
        "severity": 3,
        "facility": "LINK",
        "message": "%LINK-3-UPDOWN: Interface FastEthernet0/1, changed state to down",
    },
    {
        "device": "dept-sw-cs-01",
        "timestamp_utc": "2026-11-15T11:02:23Z",
        "severity": 5,
        "facility": "LINEPROTO",
        "message": "%LINEPROTO-5-UPDOWN: Line protocol on Interface FastEthernet0/1, changed state to up",
    },
    {
        "device": "dept-sw-cs-01",
        "timestamp_utc": "2026-11-15T11:02:40Z",
        "severity": 3,
        "facility": "LINK",
        "message": "%LINK-3-UPDOWN: Interface FastEthernet0/1, changed state to down",
    },
]
ef_data["configurations"] = []

file_ef = SCENARIOS_DIR / "ethernet_fault_with_logs.json"
with open(file_ef, "w", encoding="utf-8") as f:
    json.dump(ef_data, f, indent=2)
print(f"Created {file_ef.name}")

# -----------------------------------------------------------------------------
# 3. mtu_mismatch_with_config.json
# -----------------------------------------------------------------------------
mtu_data = copy.deepcopy(base_lc)
mtu_data["incident_id"] = "inc-ext-mtu-config"
mtu_data["description"] = "Path MTU size disparity between core-rtr-01 and dist-sw-core causing packet loss on large frames."

for rec in mtu_data.get("telemetry", []):
    rec["link_utilization_pct"] = 28.5
    rec["queue_drops"] = 0
    rec["latency_ms"] = 14.2
    rec["packet_loss_pct"] = 18.5

mtu_data["configurations"] = [
    {
        "device": "core-rtr-01",
        "timestamp_utc": "2026-11-15T08:30:00Z",
        "running_config": {
            "interfaces": {
                "eth0": {"mtu": 9000, "ip": "10.0.1.1/30"}
            }
        },
        "candidate_diff": "--- running\n+++ candidate\n@@ -5,2 +5,2 @@\n interface eth0\n+ mtu 9000",
    },
    {
        "device": "dist-sw-core",
        "timestamp_utc": "2026-11-15T08:00:00Z",
        "running_config": {
            "interfaces": {
                "eth0": {"mtu": 1500, "ip": "10.0.1.2/30"}
            }
        },
        "candidate_diff": "",
    },
]
mtu_data["logs"] = [
    {
        "device": "core-rtr-01",
        "timestamp_utc": "2026-11-15T08:35:10Z",
        "severity": 4,
        "facility": "SYS",
        "message": "%IP-4-PACKET_TOO_BIG: Packet size 9000 bytes exceeds peer MTU (1500) on eth0",
    }
]

file_mtu = SCENARIOS_DIR / "mtu_mismatch_with_config.json"
with open(file_mtu, "w", encoding="utf-8") as f:
    json.dump(mtu_data, f, indent=2)
print(f"Created {file_mtu.name}")

# -----------------------------------------------------------------------------
# 4. conflicting_evidence.json
# -----------------------------------------------------------------------------
conf_data = copy.deepcopy(base_lc)
conf_data["incident_id"] = "inc-ext-conflicting"
conf_data["description"] = "Conflicting evidence: Telemetry indicates link congestion while configuration introduces BPDU filter loop."
conf_data["configurations"] = [
    {
        "device": "core-rtr-01",
        "timestamp_utc": "2026-11-15T09:00:00Z",
        "running_config": {
            "interfaces": {
                "eth0": {
                    "mtu": 1500,
                    "spanning-tree": {"bpdufilter": "enable"},
                }
            }
        },
        "candidate_diff": "--- running\n+++ candidate\n@@ -10,2 +10,2 @@\n interface eth0\n+ spanning-tree bpdufilter enable",
    }
]
conf_data["logs"] = [
    {
        "device": "core-rtr-01",
        "timestamp_utc": "2026-11-15T09:12:00Z",
        "severity": 2,
        "facility": "OPTICS",
        "message": "Optics DOM alarm: rx power -24.8 dBm critical below receiver sensitivity threshold",
    }
]

file_conf = SCENARIOS_DIR / "conflicting_evidence.json"
with open(file_conf, "w", encoding="utf-8") as f:
    json.dump(conf_data, f, indent=2)
print(f"Created {file_conf.name}")

# -----------------------------------------------------------------------------
# 5. Register in manifest.json under 'extended' section
# -----------------------------------------------------------------------------
manifest_path = SCENARIOS_DIR / "manifest.json"
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

# Ensure existing 21 scenarios are preserved untouched
assert len(manifest.get("scenarios", [])) == 21, "Baseline 21 scenarios must remain intact!"

manifest["extended"] = [
    {
        "name": "link_congestion_with_logs",
        "file": "link_congestion_with_logs.json",
        "category": "multi_domain",
        "ground_truth": "Link utilization saturation causing buffer queue drops and latency spikes corroborated by queue-drop syslogs and QoS candidate diff",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "expected_evidence_sources": ["config_agent", "log_agent", "telemetry_agent", "topology_agent"],
        "target_confidence_min": 0.85,
        "description": "Core transit trunk saturation with multi-domain corroboration from syslog tail-drops and QoS shaper config diff.",
    },
    {
        "name": "ethernet_fault_with_logs",
        "file": "ethernet_fault_with_logs.json",
        "category": "multi_domain",
        "ground_truth": "Physical layer Ethernet interface CRC errors and flapping transitions corroborated by link-flap and CRC error syslog events",
        "expected_status": "diagnosed",
        "expected_devices": ["dept-sw-cs-01"],
        "expected_evidence_sources": ["log_agent", "telemetry_agent"],
        "target_confidence_min": 0.85,
        "description": "Physical Ethernet corruption with CRC error increments and link-flap syslog state transitions.",
    },
    {
        "name": "mtu_mismatch_with_config",
        "file": "mtu_mismatch_with_config.json",
        "category": "multi_domain",
        "ground_truth": "Path MTU size disparity between interconnected network endpoints corroborated by config diff and packet drop telemetry",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "expected_evidence_sources": ["config_agent", "log_agent", "telemetry_agent"],
        "target_confidence_min": 0.85,
        "description": "Path MTU disparity (9000 vs 1500) producing packet loss on large frames with config diff and packet-too-big syslog.",
    },
    {
        "name": "conflicting_evidence",
        "file": "conflicting_evidence.json",
        "category": "conflict",
        "ground_truth": "Contradictory fault indicators across telemetry, configuration, and syslog domains producing recorded conflict or abstention",
        "expected_status": "diagnosed",
        "expected_devices": ["core-rtr-01", "dist-sw-core"],
        "expected_evidence_sources": ["config_agent", "telemetry_agent", "topology_agent"],
        "target_confidence_min": 0.0,
        "description": "Telemetry indicates link congestion while configuration diff introduces BPDU filter loop, triggering recorded conflict resolution.",
    },
]

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Updated {manifest_path.name} with {len(manifest['extended'])} extended scenarios.")
