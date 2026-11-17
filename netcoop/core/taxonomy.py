"""Canonical Cause-Key Taxonomy, Remediation Catalog Mapping, and Evaluation Alignment.

Single source of truth for:
1. Canonical Cause Keys emitted across the diagnostic pipeline.
2. Exhaustive remediation catalog mapping ensuring every cause key has valid actions.
3. Evaluation scenario class remapping.
4. Legacy alias resolution for backwards compatibility.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from netcoop.core.report import RemediationActionItem
from netcoop.remediation.actions import RemediationCatalog


class CanonicalCauseKey(str, Enum):
    """Canonical cause keys emitted by correlation engines and diagnostic pipelines."""
    LINK_CONGESTION = "LINK_CONGESTION"
    WEAK_WIFI_SIGNAL = "WEAK_WIFI_SIGNAL"
    ETHERNET_INTERFACE_FAULT = "ETHERNET_INTERFACE_FAULT"
    DEVICE_CPU_OVERLOAD = "DEVICE_CPU_OVERLOAD"
    DNS_FAILURE = "DNS_FAILURE"
    DHCP_FAILURE = "DHCP_FAILURE"
    UPSTREAM_FAILURE_CASCADE = "UPSTREAM_FAILURE_CASCADE"
    DEVICE_HARDWARE_FAILURE = "DEVICE_HARDWARE_FAILURE"
    MTU_MISMATCH_BLACKHOLE = "MTU_MISMATCH_BLACKHOLE"
    BGP_ROUTE_FLAP_DAMPING = "BGP_ROUTE_FLAP_DAMPING"
    OPTICAL_TRANSCEIVER_DEGRADATION = "OPTICAL_TRANSCEIVER_DEGRADATION"
    STP_SPLIT_BRAIN_LOOP = "STP_SPLIT_BRAIN_LOOP"
    NO_FAULT = "NO_FAULT"


# Legacy and heuristic aliases mapped to canonical keys
LEGACY_CAUSE_ALIASES: Dict[str, CanonicalCauseKey] = {
    "INTERFACE_SATURATION_QUEUE_OVERFLOW": CanonicalCauseKey.LINK_CONGESTION,
    "PHYSICAL_LAYER_CRC_DEGRADATION": CanonicalCauseKey.ETHERNET_INTERFACE_FAULT,
    "HARDWARE_FAILURE": CanonicalCauseKey.DEVICE_HARDWARE_FAILURE,
    "UPSTREAM_CONGESTION": CanonicalCauseKey.UPSTREAM_FAILURE_CASCADE,
    "LATENCY_SPIKE": CanonicalCauseKey.LINK_CONGESTION,
    "INTERFACE_DROP_SPIKE": CanonicalCauseKey.ETHERNET_INTERFACE_FAULT,
}


# Mapping to canonical scenario evaluation classes (eval/run_eval.py)
CAUSE_TO_EVAL_MAP: Dict[CanonicalCauseKey, str] = {
    CanonicalCauseKey.LINK_CONGESTION: "link_congestion",
    CanonicalCauseKey.WEAK_WIFI_SIGNAL: "weak_wifi_signal",
    CanonicalCauseKey.ETHERNET_INTERFACE_FAULT: "ethernet_interface_fault",
    CanonicalCauseKey.DEVICE_CPU_OVERLOAD: "device_cpu_overload",
    CanonicalCauseKey.DNS_FAILURE: "dns_failure",
    CanonicalCauseKey.DHCP_FAILURE: "dhcp_failure",
    CanonicalCauseKey.UPSTREAM_FAILURE_CASCADE: "upstream_failure_cascade",
    CanonicalCauseKey.DEVICE_HARDWARE_FAILURE: "device_hardware_failure",
    CanonicalCauseKey.MTU_MISMATCH_BLACKHOLE: "mtu_mismatch",
    CanonicalCauseKey.BGP_ROUTE_FLAP_DAMPING: "bgp_damping",
    CanonicalCauseKey.OPTICAL_TRANSCEIVER_DEGRADATION: "optical_degradation",
    CanonicalCauseKey.STP_SPLIT_BRAIN_LOOP: "stp_loop",
    CanonicalCauseKey.NO_FAULT: "normal_operation",
}


def resolve_canonical_cause(cause_key: Optional[str]) -> Optional[CanonicalCauseKey]:
    """Resolve an arbitrary string or legacy key into a CanonicalCauseKey."""
    if not cause_key:
        return None
    raw = str(cause_key).strip().upper()
    if raw in LEGACY_CAUSE_ALIASES:
        return LEGACY_CAUSE_ALIASES[raw]
    try:
        return CanonicalCauseKey(raw)
    except ValueError:
        return None


def get_remediation_for_cause(
    cause_key: str,
    devices: Optional[List[str]] = None,
    interfaces: Optional[List[str]] = None,
) -> List[RemediationActionItem]:
    """Exhaustively generate validated remediation actions for any canonical cause key.

    Guarantees every cause key maps to concrete, simulated remediation actions,
    while NO_FAULT maps strictly to empty list.
    """
    canonical = resolve_canonical_cause(cause_key)
    if not canonical or canonical == CanonicalCauseKey.NO_FAULT:
        return []

    dev = (devices[0] if devices else "spine-01")
    peer = (devices[1] if devices and len(devices) > 1 else "spine-02")
    iface = (interfaces[0] if interfaces else "et-0/0/1")

    actions: List[RemediationActionItem] = []

    if canonical == CanonicalCauseKey.LINK_CONGESTION:
        actions.append(RemediationCatalog.create_rebalance_traffic_action(device=dev, interface=iface))
        actions.append(RemediationCatalog.create_raise_qos_action(device=dev, interface=iface))

    elif canonical == CanonicalCauseKey.WEAK_WIFI_SIGNAL:
        actions.append(RemediationCatalog.create_adjust_ap_power_action(device=dev, target_power_dbm=20))

    elif canonical == CanonicalCauseKey.ETHERNET_INTERFACE_FAULT:
        actions.append(RemediationCatalog.create_clear_counters_action(device=dev, interface=iface))
        actions.append(RemediationCatalog.create_failover_link_action(device=dev, interface=iface, peer_device=peer))

    elif canonical == CanonicalCauseKey.DEVICE_CPU_OVERLOAD:
        actions.append(RemediationCatalog.create_raise_qos_action(device=dev, interface=iface))
        actions.append(RemediationCatalog.create_rebalance_traffic_action(device=dev, interface=iface))

    elif canonical == CanonicalCauseKey.DNS_FAILURE:
        actions.append(RemediationCatalog.create_restart_dns_cache_action(device=dev))

    elif canonical == CanonicalCauseKey.DHCP_FAILURE:
        actions.append(RemediationCatalog.create_clear_dhcp_bindings_action(device=dev))

    elif canonical == CanonicalCauseKey.UPSTREAM_FAILURE_CASCADE:
        actions.append(RemediationCatalog.create_rebalance_traffic_action(device=dev, interface=iface))
        actions.append(RemediationCatalog.create_raise_qos_action(device=dev, interface=iface))

    elif canonical == CanonicalCauseKey.DEVICE_HARDWARE_FAILURE:
        actions.append(RemediationCatalog.create_clear_counters_action(device=dev, interface=iface))
        actions.append(RemediationCatalog.create_failover_link_action(device=dev, interface=iface, peer_device=peer))

    elif canonical == CanonicalCauseKey.MTU_MISMATCH_BLACKHOLE:
        actions.append(RemediationCatalog.create_mtu_harmonization_action(device=dev, interface=iface, target_mtu=9000))

    elif canonical == CanonicalCauseKey.BGP_ROUTE_FLAP_DAMPING:
        actions.append(RemediationCatalog.create_clear_flap_damping_action(device=dev, peer_ip="198.51.100.1"))

    elif canonical == CanonicalCauseKey.OPTICAL_TRANSCEIVER_DEGRADATION:
        actions.append(RemediationCatalog.create_drain_optical_link_action(device=dev, interface=iface, peer_device=peer))

    elif canonical == CanonicalCauseKey.STP_SPLIT_BRAIN_LOOP:
        actions.append(RemediationCatalog.create_remove_bpdu_filter_action(device=dev, interface=iface))

    return actions


# Global dictionary confirming exhaustive remediation coverage
CAUSE_TO_REMEDIATION_MAP: Dict[CanonicalCauseKey, Any] = {
    k: (get_remediation_for_cause(k.value, ["spine-01"], ["et-0/0/1"]) if k != CanonicalCauseKey.NO_FAULT else [])
    for k in CanonicalCauseKey
}
