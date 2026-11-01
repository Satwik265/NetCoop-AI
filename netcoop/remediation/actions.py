"""Simulated remediation templates and command generators."""

from typing import Dict, List, Optional
from netcoop.core.report import RemediationActionItem


class RemediationCatalog:
    """Pre-defined safe remediation action templates with rollback capabilities."""

    @classmethod
    def create_mtu_harmonization_action(
        cls, device: str, interface: str, target_mtu: int = 9000
    ) -> RemediationActionItem:
        """Generate simulated MTU alignment commands."""
        return RemediationActionItem(
            action_id=f"act-mtu-{device}",
            title=f"Harmonize MTU to {target_mtu} bytes on {device} {interface}",
            description="Align MTU along transit path to prevent Path MTU blackholing on jumbo frames.",
            device=device,
            commands=[
                f"configure terminal",
                f"interface {interface}",
                f"mtu {target_mtu}",
                f"commit and-quit",
            ],
            rollback_commands=[
                f"configure terminal",
                f"interface {interface}",
                f"mtu 1500",
                f"commit and-quit",
            ],
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_clear_flap_damping_action(
        cls, device: str, peer_ip: str
    ) -> RemediationActionItem:
        """Generate simulated command to un-suppress stabilized BGP peer."""
        return RemediationActionItem(
            action_id=f"act-bgp-{device}",
            title=f"Reset BGP Route Flap Damping penalty on {device} for peer {peer_ip}",
            description="Clear route dampening statistics after physical carrier stabilization.",
            device=device,
            commands=[
                f"clear bgp ipv4 unicast dampening {peer_ip}",
                f"clear bgp ipv6 unicast dampening {peer_ip}",
            ],
            rollback_commands=[],
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_drain_optical_link_action(
        cls, device: str, interface: str, peer_device: str
    ) -> RemediationActionItem:
        """Generate simulated command to divert traffic away from degraded optic."""
        return RemediationActionItem(
            action_id=f"act-drain-{device}",
            title=f"Drain and reroute traffic off degraded optical link {device}:{interface}",
            description="Increase IGP metric to max to smoothly reroute traffic to redundant link before transceiver replacement.",
            device=device,
            commands=[
                f"configure terminal",
                f"router isis backbone",
                f"interface {interface}",
                f"metric 16777214",
                f"commit and-quit",
            ],
            rollback_commands=[
                f"configure terminal",
                f"router isis backbone",
                f"interface {interface}",
                f"no metric 16777214",
                f"commit and-quit",
            ],
            risk_level="medium",
            blast_radius_devices=[device, peer_device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_remove_bpdu_filter_action(
        cls, device: str, interface: str
    ) -> RemediationActionItem:
        """Generate simulated command to disable BPDU filter on trunk port."""
        return RemediationActionItem(
            action_id=f"act-stp-{device}",
            title=f"Disable erroneous Spanning Tree BPDU filter on {device} {interface}",
            description="Allow BPDU exchange to resume and block redundant loop paths.",
            device=device,
            commands=[
                f"configure terminal",
                f"interface {interface}",
                f"no spanning-tree bpdufilter enable",
                f"commit and-quit",
            ],
            rollback_commands=[
                f"configure terminal",
                f"interface {interface}",
                f"spanning-tree bpdufilter enable",
                f"commit and-quit",
            ],
            risk_level="high",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_rebalance_traffic_action(
        cls, device: str, interface: Optional[str] = None
    ) -> RemediationActionItem:
        """Generate simulated command to dynamically rebalance traffic across parallel links."""
        iface_str = f" {interface}" if interface else ""
        cmds = ["configure terminal"]
        if interface:
            cmds.append(f"interface {interface}")
        cmds.extend(["load-interval 30", "traffic-policy REBALANCE_ECMP", "commit and-quit"])

        rollback = ["configure terminal"]
        if interface:
            rollback.append(f"interface {interface}")
        rollback.extend(["no traffic-policy REBALANCE_ECMP", "commit and-quit"])

        return RemediationActionItem(
            action_id=f"act-rebalance-{device}",
            title=f"Rebalance traffic across ECMP next-hops from {device}{iface_str}",
            description="Re-weight hash buckets to steer egress flows across parallel paths and relieve congestion.",
            device=device,
            commands=cmds,
            rollback_commands=rollback,
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_clear_counters_action(
        cls, device: str, interface: Optional[str] = None
    ) -> RemediationActionItem:
        """Generate simulated command to clear interface CRC and drop counters."""
        iface_str = f" {interface}" if interface else ""
        if interface:
            cmds = [f"clear counters {interface}", f"clear interface {interface} queue-drops"]
        else:
            cmds = ["clear counters", "clear queue-drops"]

        return RemediationActionItem(
            action_id=f"act-clear-counters-{device}",
            title=f"Clear interface counters and queue drops on {device}{iface_str}",
            description="Reset transient CRC and buffer overflow metrics to verify remediation efficacy.",
            device=device,
            commands=cmds,
            rollback_commands=[],
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_raise_qos_action(
        cls, device: str, interface: Optional[str] = None
    ) -> RemediationActionItem:
        """Generate simulated command to raise QoS priority for latency-sensitive traffic."""
        iface_str = f" {interface}" if interface else ""
        cmds = ["configure terminal"]
        if interface:
            cmds.append(f"interface {interface}")
        cmds.extend(["service-policy type qos output EXPEDITE_VOICE_VIDEO", "commit and-quit"])

        rollback = ["configure terminal"]
        if interface:
            rollback.append(f"interface {interface}")
        rollback.extend(["no service-policy type qos output EXPEDITE_VOICE_VIDEO", "commit and-quit"])

        return RemediationActionItem(
            action_id=f"act-qos-{device}",
            title=f"Raise QoS priority and buffer reserve on {device}{iface_str}",
            description="Prioritize delay-sensitive flows and allocate strict priority queue bandwidth.",
            device=device,
            commands=cmds,
            rollback_commands=rollback,
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_failover_link_action(
        cls, device: str, interface: Optional[str] = None, peer_device: Optional[str] = None
    ) -> RemediationActionItem:
        """Generate simulated command to administratively fail over a degraded link."""
        blast = [device]
        if peer_device:
            blast.append(peer_device)
        if interface:
            title = f"Fail over link {device}:{interface} to redundant secondary circuit"
            cmds = ["configure terminal", f"interface {interface}", "shutdown", "commit and-quit"]
            rollback = ["configure terminal", f"interface {interface}", "no shutdown", "commit and-quit"]
        else:
            title = f"Fail over active transit link on {device} to redundant secondary path"
            cmds = ["configure terminal", "redundancy force-switchover", "commit and-quit"]
            rollback = ["configure terminal", "no redundancy force-switchover", "commit and-quit"]

        return RemediationActionItem(
            action_id=f"act-failover-{device}",
            title=title,
            description="Isolate degraded link to trigger instantaneous failover to secondary path.",
            device=device,
            commands=cmds,
            rollback_commands=rollback,
            risk_level="medium",
            blast_radius_devices=blast,
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_adjust_ap_power_action(
        cls, device: str, target_power_dbm: int = 20
    ) -> RemediationActionItem:
        """Generate simulated command to adjust AP transmit power for weak Wi-Fi coverage."""
        return RemediationActionItem(
            action_id=f"act-wifi-power-{device}",
            title=f"Adjust wireless radio transmit power to {target_power_dbm} dBm on {device}",
            description="Increase access point radio transmit power to mitigate RF path attenuation and packet loss.",
            device=device,
            commands=[
                "configure terminal",
                f"radio 2.4ghz transmit-power {target_power_dbm}",
                f"radio 5ghz transmit-power {target_power_dbm}",
                "commit and-quit",
            ],
            rollback_commands=[
                "configure terminal",
                "radio 2.4ghz transmit-power default",
                "radio 5ghz transmit-power default",
                "commit and-quit",
            ],
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_restart_dns_cache_action(
        cls, device: str
    ) -> RemediationActionItem:
        """Generate simulated command to flush DNS resolver cache and restart daemon."""
        return RemediationActionItem(
            action_id=f"act-dns-restart-{device}",
            title=f"Flush resolver cache and restart recursive DNS forwarder on {device}",
            description="Clear corrupted DNS cache entries and restart local lookup daemon to restore resolution.",
            device=device,
            commands=[
                "systemctl restart named-resolver",
                "rndc flush",
            ],
            rollback_commands=[
                "systemctl restart named-resolver",
            ],
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_clear_dhcp_bindings_action(
        cls, device: str
    ) -> RemediationActionItem:
        """Generate simulated command to clear exhausted DHCP bindings and renew lease pool."""
        return RemediationActionItem(
            action_id=f"act-dhcp-clear-{device}",
            title=f"Clear exhausted DHCP lease bindings and renew relay pool on {device}",
            description="Flush expired and stale DHCP leases to free up pool allocation for requesting campus hosts.",
            device=device,
            commands=[
                "clear ip dhcp binding *",
                "clear ip dhcp server statistics",
            ],
            rollback_commands=[],
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )
