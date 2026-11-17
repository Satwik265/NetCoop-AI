"""Tests verifying that every fault scenario in HeldoutNetworkGenerator is distinguishable from normal_operation."""

import numpy as np
import pytest
from netcoop.data.heldout_generator import HeldoutNetworkGenerator

SEEDS = list(range(601, 616))
CANONICAL_CLASSES = [
    "normal_operation",
    "link_congestion",
    "weak_wifi_signal",
    "ethernet_interface_fault",
    "dns_failure",
    "dhcp_failure",
    "device_cpu_overload",
    "upstream_failure_cascade",
]


def test_every_fault_class_is_distinguishable_from_normal():
    """Verify that each of the 7 fault classes has statistically distinguishable signature metrics from normal_operation."""
    normal_data = [HeldoutNetworkGenerator.generate("normal_operation", seed=s) for s in SEEDS]
    normal_records = [r for d in normal_data for r in d["telemetry"]]

    norm_util = np.mean([r["link_utilization_pct"] for r in normal_records])
    norm_drops = np.mean([r["queue_drops"] for r in normal_records])
    norm_errs = np.mean([r["interface_errors"] for r in normal_records])
    norm_flaps = np.mean([r["link_flaps"] for r in normal_records])
    norm_cpu = np.mean([r["cpu_pct"] for r in normal_records])
    norm_loss = np.mean([r["packet_loss_pct"] for r in normal_records])

    # 1. link_congestion: utilization and drops must be significantly higher
    lc_data = [HeldoutNetworkGenerator.generate("link_congestion", seed=s) for s in SEEDS]
    lc_records = [r for d in lc_data for r in d["telemetry"]]
    lc_util = np.mean([r["link_utilization_pct"] for r in lc_records])
    lc_drops = np.mean([r["queue_drops"] for r in lc_records])
    assert lc_util > norm_util + 10.0, f"link_congestion util {lc_util} must exceed normal {norm_util}"
    assert lc_drops > 200, f"link_congestion drops {lc_drops} must exceed 200"

    # 2. weak_wifi_signal: wifi_rssi_dbm and wifi_retransmission_pct must be present and degraded
    wifi_data = [HeldoutNetworkGenerator.generate("weak_wifi_signal", seed=s) for s in SEEDS]
    wifi_records = [r for d in wifi_data for r in d["telemetry"]]
    wifi_rssi_vals = [r.get("wifi_rssi_dbm") for r in wifi_records if r.get("wifi_rssi_dbm") is not None]
    wifi_retx_vals = [r.get("wifi_retransmission_pct") for r in wifi_records if r.get("wifi_retransmission_pct") is not None]
    assert len(wifi_rssi_vals) > 0, "weak_wifi_signal must contain wifi_rssi_dbm records"
    assert np.mean(wifi_rssi_vals) < -75.0, f"weak_wifi_signal mean RSSI {np.mean(wifi_rssi_vals)} must be < -75.0 dBm"
    assert np.mean(wifi_retx_vals) > 20.0, f"weak_wifi_signal mean retx {np.mean(wifi_retx_vals)} must be > 20%"

    # 3. ethernet_interface_fault: interface_errors and link_flaps must be elevated
    eth_data = [HeldoutNetworkGenerator.generate("ethernet_interface_fault", seed=s) for s in SEEDS]
    eth_records = [r for d in eth_data for r in d["telemetry"]]
    eth_errs = np.mean([r["interface_errors"] for r in eth_records])
    eth_flaps = np.mean([r["link_flaps"] for r in eth_records])
    assert eth_errs > 500, f"ethernet_interface_fault errors {eth_errs} must exceed 500 (normal: {norm_errs})"
    assert eth_flaps >= 2, f"ethernet_interface_fault flaps {eth_flaps} must be >= 2 (normal: {norm_flaps})"

    # 4. dns_failure: dns_failure_pct and dns_resolution_ms must be elevated
    dns_data = [HeldoutNetworkGenerator.generate("dns_failure", seed=s) for s in SEEDS]
    dns_records = [r for d in dns_data for r in d["telemetry"]]
    dns_fails = [r.get("dns_failure_pct") for r in dns_records if r.get("dns_failure_pct") is not None]
    dns_lat = [r.get("dns_resolution_ms") for r in dns_records if r.get("dns_resolution_ms") is not None]
    assert len(dns_fails) > 0, "dns_failure must emit dns_failure_pct"
    assert np.mean(dns_fails) > 60.0, f"dns_failure pct {np.mean(dns_fails)} must exceed 60%"
    assert np.mean(dns_lat) > 1500.0, f"dns resolution ms {np.mean(dns_lat)} must exceed 1500ms"

    # 5. dhcp_failure: dhcp_failure_pct must be elevated
    dhcp_data = [HeldoutNetworkGenerator.generate("dhcp_failure", seed=s) for s in SEEDS]
    dhcp_records = [r for d in dhcp_data for r in d["telemetry"]]
    dhcp_fails = [r.get("dhcp_failure_pct") for r in dhcp_records if r.get("dhcp_failure_pct") is not None]
    assert len(dhcp_fails) > 0, "dhcp_failure must emit dhcp_failure_pct"
    assert np.mean(dhcp_fails) > 60.0, f"dhcp_failure pct {np.mean(dhcp_fails)} must exceed 60%"

    # 6. device_cpu_overload: cpu_pct must be elevated
    cpu_data = [HeldoutNetworkGenerator.generate("device_cpu_overload", seed=s) for s in SEEDS]
    cpu_records = [r for d in cpu_data for r in d["telemetry"]]
    cpu_mean = np.mean([r["cpu_pct"] for r in cpu_records])
    assert cpu_mean > norm_cpu + 8.0, f"device_cpu_overload cpu {cpu_mean} must exceed normal {norm_cpu} + 8"

    # 7. upstream_failure_cascade: router must be offline with 100% loss, switch must show drops/util
    up_data = [HeldoutNetworkGenerator.generate("upstream_failure_cascade", seed=s) for s in SEEDS]
    up_records = [r for d in up_data for r in d["telemetry"]]
    router_recs = [r for r in up_records if r["device_id"] == "sat-rtr-01"]
    switch_recs = [r for r in up_records if r["device_id"] == "sat-agg-sw-01"]
    assert all(r["device_status"] == "offline" for r in router_recs), "sat-rtr-01 must be offline in upstream_failure_cascade"
    assert all(r["packet_loss_pct"] >= 99.0 for r in router_recs), "sat-rtr-01 must have 100% packet loss"
    assert np.mean([r["queue_drops"] for r in switch_recs]) > 500, "sat-agg-sw-01 must experience queue drops in upstream cascade"
