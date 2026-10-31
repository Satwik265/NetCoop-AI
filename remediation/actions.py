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
        cls, device: str, interface: str = "et-0/0/1"
    ) -> RemediationActionItem:
        """Generate simulated command to dynamically rebalance traffic across parallel links."""
        return RemediationActionItem(
            action_id=f"act-rebalance-{device}",
            title=f"Rebalance traffic across ECMP next-hops from {device} {interface}",
            description="Re-weight hash buckets to steer egress flows across parallel paths and relieve congestion.",
            device=device,
            commands=[
                f"configure terminal",
                f"interface {interface}",
                f"load-interval 30",
                f"traffic-policy REBALANCE_ECMP",
                f"commit and-quit",
            ],
            rollback_commands=[
                f"configure terminal",
                f"interface {interface}",
                f"no traffic-policy REBALANCE_ECMP",
                f"commit and-quit",
            ],
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_clear_counters_action(
        cls, device: str, interface: str = "et-0/0/1"
    ) -> RemediationActionItem:
        """Generate simulated command to clear interface CRC and drop counters."""
        return RemediationActionItem(
            action_id=f"act-clear-counters-{device}",
            title=f"Clear interface counters and queue drops on {device} {interface}",
            description="Reset transient CRC and buffer overflow metrics to verify remediation efficacy.",
            device=device,
            commands=[
                f"clear counters {interface}",
                f"clear interface {interface} queue-drops",
            ],
            rollback_commands=[],
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_raise_qos_action(
        cls, device: str, interface: str = "et-0/0/1"
    ) -> RemediationActionItem:
        """Generate simulated command to raise QoS priority for latency-sensitive traffic."""
        return RemediationActionItem(
            action_id=f"act-qos-{device}",
            title=f"Raise QoS priority and buffer reserve on {device} {interface}",
            description="Prioritize delay-sensitive flows and allocate strict priority queue bandwidth.",
            device=device,
            commands=[
                f"configure terminal",
                f"interface {interface}",
                f"service-policy type qos output EXPEDITE_VOICE_VIDEO",
                f"commit and-quit",
            ],
            rollback_commands=[
                f"configure terminal",
                f"interface {interface}",
                f"no service-policy type qos output EXPEDITE_VOICE_VIDEO",
                f"commit and-quit",
            ],
            risk_level="low",
            blast_radius_devices=[device],
            is_simulated=True,
            status="pending_approval",
        )

    @classmethod
    def create_failover_link_action(
        cls, device: str, interface: str = "et-0/0/1", peer_device: Optional[str] = None
    ) -> RemediationActionItem:
        """Generate simulated command to administratively fail over a degraded link."""
        blast = [device]
        if peer_device:
            blast.append(peer_device)
        return RemediationActionItem(
            action_id=f"act-failover-{device}",
            title=f"Fail over link {device}:{interface} to redundant secondary circuit",
            description="Isolate degraded link to trigger instantaneous failover to secondary path.",
            device=device,
            commands=[
                f"configure terminal",
                f"interface {interface}",
                f"shutdown",
                f"commit and-quit",
            ],
            rollback_commands=[
                f"configure terminal",
                f"interface {interface}",
                f"no shutdown",
                f"commit and-quit",
            ],
            risk_level="medium",
            blast_radius_devices=blast,
            is_simulated=True,
            status="pending_approval",
        )
