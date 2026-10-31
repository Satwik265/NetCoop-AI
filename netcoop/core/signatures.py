"""Deterministic fault signatures, causal chains, and discriminating tests.

Covers all 10 standard network hypothesis models:
1. link_congestion
2. upstream_congestion
3. weak_wifi_signal
4. interface_or_cable_fault
5. device_cpu_overload
6. dns_failure
7. dhcp_failure
8. device_hardware_failure
9. no_fault
10. unknown
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from netcoop.core.thresholds import DynamicThresholds, OrganizerSnapshotThresholds, is_snapshot_mode


class EvidencePrecedence(int, Enum):
    """Tie-break hierarchy for deterministic arbitration.

    Rule: direct evidence > correlated evidence > topology inference.
    """
    DIRECT = 3           # Hardware down, optical DOM attenuation, physical FCS error, DNS timeout
    CORRELATED = 2       # Queue drops, link utilization, CPU utilization, latency
    TOPOLOGY_INFERENCE = 1  # Upstream path assumption, downstream cascade inference


class HypothesisKey(str, Enum):
    """Canonical hypothesis keys."""
    LINK_CONGESTION = "link_congestion"
    UPSTREAM_CONGESTION = "upstream_congestion"
    WEAK_WIFI_SIGNAL = "weak_wifi_signal"
    INTERFACE_OR_CABLE_FAULT = "interface_or_cable_fault"
    DEVICE_CPU_OVERLOAD = "device_cpu_overload"
    DNS_FAILURE = "dns_failure"
    DHCP_FAILURE = "dhcp_failure"
    DEVICE_HARDWARE_FAILURE = "device_hardware_failure"
    NO_FAULT = "no_fault"
    UNKNOWN = "unknown"


@dataclass
class SignatureDefinition:
    """Formal definition of a fault signature."""
    key: HypothesisKey
    title: str
    description: str
    causal_chain: List[str]
    discriminating_test: str
    precedence: EvidencePrecedence
    required_corroboration: List[str]


SIGNATURE_REGISTRY: Dict[HypothesisKey, SignatureDefinition] = {
    HypothesisKey.LINK_CONGESTION: SignatureDefinition(
        key=HypothesisKey.LINK_CONGESTION,
        title="Link utilization saturation causing buffer queue drops and latency spikes",
        description="Local interface traffic volume exceeds link capacity, filling egress buffers and triggering drops.",
        causal_chain=[
            "High egress traffic volume approaches interface bandwidth limit",
            "Egress queue buffer fills to maximum allocation limit",
            "Tail drops occur as incoming frames exceed buffer capacity",
            "Packet serialization delays induce latency and jitter spikes",
            "TCP endpoints detect loss and trigger congestion window backoff",
        ],
        discriminating_test="Audit egress queue drops and interface utilization on the specific local interface vs upstream transit hops.",
        precedence=EvidencePrecedence.CORRELATED,
        required_corroboration=["telemetry_agent"],
    ),
    HypothesisKey.UPSTREAM_CONGESTION: SignatureDefinition(
        key=HypothesisKey.UPSTREAM_CONGESTION,
        title="Upstream provider or transit link congestion inducing downstream delay",
        description="High latency and packet loss observed locally while local link utilization and queue drops remain nominal.",
        causal_chain=[
            "Upstream core router or ISP transit link experiences traffic overload",
            "Upstream network egress buffers accumulate queue drops and transit delays",
            "Downstream campus packets experience delayed acknowledgment and packet loss",
            "Local interface utilization remains low while end-to-end RTT spikes",
        ],
        discriminating_test="Query upstream transit link utilization and queue drops via topology path traversal.",
        precedence=EvidencePrecedence.TOPOLOGY_INFERENCE,
        required_corroboration=["topology_agent", "telemetry_agent"],
    ),
    HypothesisKey.WEAK_WIFI_SIGNAL: SignatureDefinition(
        key=HypothesisKey.WEAK_WIFI_SIGNAL,
        title="Weak Wi-Fi signal and RF attenuation causing frame retransmissions",
        description="Low RSSI, poor SNR, and elevated 802.11 MAC frame retransmissions on wireless access points.",
        causal_chain=[
            "Physical RF distance or building material attenuation degrades received signal",
            "RSSI drops below -75 dBm with SNR falling below 20 dB",
            "Access point drops PHY modulation to lower MCS index",
            "802.11 frame check sequence errors trigger MAC layer retransmissions",
            "Channel airtime contention spikes, causing client packet loss and jitter",
        ],
        discriminating_test="Measure wireless client RSSI/SNR and 802.11 retries vs wired AP uplink port error counters.",
        precedence=EvidencePrecedence.DIRECT,
        required_corroboration=["wifi_services_agent"],
    ),
    HypothesisKey.INTERFACE_OR_CABLE_FAULT: SignatureDefinition(
        key=HypothesisKey.INTERFACE_OR_CABLE_FAULT,
        title="Physical layer Ethernet interface degradation and packet corruption",
        description="CRC/FCS checksum errors and link state flaps caused by physical cable fault or optical degradation.",
        causal_chain=[
            "Damaged patch cable, bent fiber, or failing transceiver PHY",
            "Electrical noise or optical power attenuation corrupts frame bits in transit",
            "Ethernet receiver MAC rejects malformed frames with CRC/FCS checksum errors",
            "PHY auto-negotiation or loss of sync triggers physical link flaps",
            "Higher-layer protocols experience intermittent connectivity loss",
        ],
        discriminating_test="Inspect optical transceiver DOM Rx/Tx power levels and physical CRC error registers without queue drops.",
        precedence=EvidencePrecedence.DIRECT,
        required_corroboration=["telemetry_agent", "log_agent"],
    ),
    HypothesisKey.DEVICE_CPU_OVERLOAD: SignatureDefinition(
        key=HypothesisKey.DEVICE_CPU_OVERLOAD,
        title="Control-plane CPU exhaustion degrading packet processing and forwarding",
        description="Device CPU utilization exceeds 90%, causing process scheduling delay and buffer starvation.",
        causal_chain=[
            "High control plane workload, protocol storm, or routing churn",
            "Routing engine CPU utilization saturates above 90%",
            "Kernel process scheduler starves packet forwarding and timer threads",
            "Buffer management starvation leads to packet drops across multiple interfaces",
            "Control plane protocol keepalives (BGP/OSPF/BFD) miss deadlines",
        ],
        discriminating_test="Inspect per-process CPU breakdown (routing daemon vs kernel forwarding) and memory usage.",
        precedence=EvidencePrecedence.CORRELATED,
        required_corroboration=["telemetry_agent"],
    ),
    HypothesisKey.DNS_FAILURE: SignatureDefinition(
        key=HypothesisKey.DNS_FAILURE,
        title="DNS resolution service outage with high query timeout failure rate",
        description="DNS resolution latency exceeds 150ms or failure percentage exceeds 20% while IP transport is healthy.",
        causal_chain=[
            "Recursive DNS daemon unreachable, overloaded, or upstream resolver failure",
            "UDP port 53 queries time out or return SERVFAIL/NXDOMAIN",
            "Host operating system DNS client retries expire",
            "Application connection initiation stalls despite healthy IP layer reachability",
        ],
        discriminating_test="Perform UDP port 53 dig/nslookup query vs ICMP ping to DNS server IP address.",
        precedence=EvidencePrecedence.DIRECT,
        required_corroboration=["wifi_services_agent"],
    ),
    HypothesisKey.DHCP_FAILURE: SignatureDefinition(
        key=HypothesisKey.DHCP_FAILURE,
        title="DHCP scope exhaustion or relay failure preventing lease assignment",
        description="DHCP failure percentage exceeds 10%, causing client address allocation failures.",
        causal_chain=[
            "DHCP IP address pool fully allocated or DHCP relay agent drops requests",
            "DHCP DISCOVER packets from connecting clients receive no DHCPOFFER response",
            "Client DHCP state machine times out and assigns APIPA (169.254.0.0/16) address",
            "Clients fail to establish default gateway route or campus network access",
        ],
        discriminating_test="Audit DHCP server active lease pool utilization and relay agent forwarded packet counters.",
        precedence=EvidencePrecedence.DIRECT,
        required_corroboration=["wifi_services_agent"],
    ),
    HypothesisKey.DEVICE_HARDWARE_FAILURE: SignatureDefinition(
        key=HypothesisKey.DEVICE_HARDWARE_FAILURE,
        title="Device hardware failure or catastrophic control plane crash",
        description="Critical hardware malfunction, ASIC/PSU failure, status down/critical with extreme packet loss or unreachability.",
        causal_chain=[
            "Internal hardware component failure (power supply, ASIC, memory bank, or fabric)",
            "System state transitions to Critical or Unreachable",
            "Forwarding plane halts or enters catastrophic drop loop (CPU 99%+, queue drops spike)",
            "Traffic transiting device is blackholed with near 100% loss or extreme latency",
        ],
        discriminating_test="Check out-of-band IPMI / console heartbeat and device status sensors.",
        precedence=EvidencePrecedence.DIRECT,
        required_corroboration=["telemetry_agent", "log_agent"],
    ),
    HypothesisKey.NO_FAULT: SignatureDefinition(
        key=HypothesisKey.NO_FAULT,
        title="Normal network operation within nominal operational boundaries",
        description="All telemetry metrics, queue depths, error counters, and services are healthy.",
        causal_chain=[
            "Steady-state network operation",
            "Interface utilization and CPU load remain within normal baseline",
            "Zero queue drops and packet loss observed",
            "System operates without anomalous state transitions",
        ],
        discriminating_test="Compare all metrics against nominal baselines.",
        precedence=EvidencePrecedence.DIRECT,
        required_corroboration=["telemetry_agent"],
    ),
    HypothesisKey.UNKNOWN: SignatureDefinition(
        key=HypothesisKey.UNKNOWN,
        title="Insufficient or ambiguous evidence to isolate root cause",
        description="Reported anomalies lack cross-domain corroboration or represent competing unresolvable hypotheses.",
        causal_chain=[
            "Multiple disparate or incomplete observations detected",
            "Observations fail cross-domain corroboration sufficiency thresholds",
            "Diagnostic engine declines to speculate root cause without targeted probe data",
        ],
        discriminating_test="Execute active diagnostic probes and path-level telemetry collection.",
        precedence=EvidencePrecedence.TOPOLOGY_INFERENCE,
        required_corroboration=[],
    ),
}


class SignatureMatcher:
    """Matches raw telemetry and multi-agent observations against the 10 canonical fault signatures."""

    @classmethod
    def evaluate_telemetry(
        cls,
        telemetry_records: List[Dict[str, Any]],
        topology_available: bool = True,
    ) -> Tuple[HypothesisKey, float, List[str], List[Dict[str, Any]], List[str]]:
        """Evaluate raw telemetry records against fault signatures.

        Returns:
            Tuple of:
              - primary_key: HypothesisKey
              - confidence: float (0.0 to 1.0)
              - affected_devices: List[str]
              - alternative_hypotheses: List[Dict[str, Any]] (ranked with scores & discriminating tests)
              - limitations: List[str]
        """
        limitations: List[str] = []
        is_snapshot = is_snapshot_mode(telemetry_records)

        if is_snapshot:
            limitations.append("single snapshot, no temporal context")

        if not topology_available:
            limitations.append("topology data unavailable; upstream transit inference uncorroborated")

        # Track missing metric categories across the dataset
        if telemetry_records:
            first = telemetry_records[0]
            metrics = first.get("metrics", first)
            for m in ["wifi_rssi_dbm", "wifi_retransmission_pct"]:
                if m not in metrics and metrics.get(m) is None:
                    limitations.append("wifi metrics missing (rssi, retransmission)")
                    break
            for m in ["dns_failure_pct", "dhcp_failure_pct"]:
                if m not in metrics and metrics.get(m) is None:
                    limitations.append("service metrics missing (dns, dhcp)")
                    break

        if not telemetry_records:
            return (
                HypothesisKey.UNKNOWN,
                0.0,
                [],
                [],
                ["empty telemetry payload", *limitations],
            )

        # 1. Check for Hardware Failure pattern (e.g. Organizer hardware_failure sample)
        # Signature: status == "Critical" or "Down", or CPU 99%+, or loss > 15% with massive queue drops
        hw_devices = []
        for rec in telemetry_records:
            dev = rec.get("device_id") or rec.get("device") or "unknown"
            status = str(rec.get("status") or rec.get("device_status") or "").lower()
            metrics = rec.get("metrics", rec)
            cpu = float(metrics.get("cpu_utilization_pct") or metrics.get("cpu_pct") or 0.0)
            loss = float(metrics.get("packet_loss_pct") or 0.0)
            drops = int(metrics.get("queue_drops") or 0)
            lat = float(metrics.get("latency_ms") or 0.0)

            if status in OrganizerSnapshotThresholds.STATUS_DOWN_VALUES or status == "critical":
                if cpu >= 95.0 or loss >= 15.0 or drops >= 5000:
                    hw_devices.append(dev)
            elif cpu >= 99.0 and loss >= 15.0 and drops >= 5000:
                hw_devices.append(dev)

        if hw_devices:
            conf = 0.95 if not is_snapshot else 0.88
            return (
                HypothesisKey.DEVICE_HARDWARE_FAILURE,
                conf,
                list(set(hw_devices)),
                [
                    {
                        "cause": SIGNATURE_REGISTRY[HypothesisKey.LINK_CONGESTION].title,
                        "confidence": 0.40,
                        "discriminating_test": "Check IPMI hardware watchdog logs vs egress buffer drop counters.",
                    }
                ],
                limitations,
            )

        # 2. Check for DNS Failure
        dns_devices = []
        for rec in telemetry_records:
            dev = rec.get("device_id") or rec.get("device") or "unknown"
            metrics = rec.get("metrics", rec)
            dns_fail = float(metrics.get("dns_failure_pct") or 0.0)
            dns_lat = float(metrics.get("dns_resolution_ms") or 0.0)
            if dns_fail >= DynamicThresholds.DNS_FAILURE_CRIT_PCT or dns_lat >= DynamicThresholds.DNS_RESOLUTION_CRIT_MS:
                dns_devices.append(dev)
        if dns_devices:
            conf = 0.94 if not is_snapshot else 0.82
            return (
                HypothesisKey.DNS_FAILURE,
                conf,
                list(set(dns_devices)),
                [],
                limitations,
            )

        # 3. Check for DHCP Failure
        dhcp_devices = []
        for rec in telemetry_records:
            dev = rec.get("device_id") or rec.get("device") or "unknown"
            metrics = rec.get("metrics", rec)
            dhcp_fail = float(metrics.get("dhcp_failure_pct") or 0.0)
            if dhcp_fail >= DynamicThresholds.DHCP_FAILURE_CRIT_PCT:
                dhcp_devices.append(dev)
        if dhcp_devices:
            conf = 0.92 if not is_snapshot else 0.80
            return (
                HypothesisKey.DHCP_FAILURE,
                conf,
                list(set(dhcp_devices)),
                [],
                limitations,
            )

        # 4. Check for Weak Wi-Fi Signal
        wifi_devices = []
        for rec in telemetry_records:
            dev = rec.get("device_id") or rec.get("device") or "unknown"
            metrics = rec.get("metrics", rec)
            rssi = metrics.get("wifi_rssi_dbm")
            retx = metrics.get("wifi_retransmission_pct")
            if rssi is not None and float(rssi) <= DynamicThresholds.WIFI_RSSI_WARN_DBM:
                wifi_devices.append(dev)
            elif retx is not None and float(retx) >= DynamicThresholds.WIFI_RETX_WARN_PCT:
                wifi_devices.append(dev)
        if wifi_devices:
            conf = 0.90 if not is_snapshot else 0.78
            return (
                HypothesisKey.WEAK_WIFI_SIGNAL,
                conf,
                list(set(wifi_devices)),
                [],
                limitations,
            )

        # 5. Check for Physical Interface / Cable Fault
        eth_devices = []
        for rec in telemetry_records:
            dev = rec.get("device_id") or rec.get("device") or "unknown"
            metrics = rec.get("metrics", rec)
            errs = int(metrics.get("interface_errors") or metrics.get("fcs_errors") or metrics.get("crc_errors") or 0)
            flaps = int(metrics.get("link_flaps") or 0)
            drops = int(metrics.get("queue_drops") or 0)
            if errs >= 100 and drops < 20:
                eth_devices.append(dev)
            elif flaps >= 2 and errs >= 50:
                eth_devices.append(dev)
        if eth_devices:
            conf = 0.92 if not is_snapshot else 0.82
            return (
                HypothesisKey.INTERFACE_OR_CABLE_FAULT,
                conf,
                list(set(eth_devices)),
                [],
                limitations,
            )

        # 6. Check for Device CPU Overload
        cpu_devices = []
        for rec in telemetry_records:
            dev = rec.get("device_id") or rec.get("device") or "unknown"
            metrics = rec.get("metrics", rec)
            cpu = float(metrics.get("cpu_utilization_pct") or metrics.get("cpu_pct") or 0.0)
            util = float(metrics.get("link_utilization_pct") or 0.0)
            if cpu >= DynamicThresholds.CPU_CRIT_PCT and util < 70.0:
                cpu_devices.append(dev)
        if cpu_devices:
            conf = 0.90 if not is_snapshot else 0.78
            return (
                HypothesisKey.DEVICE_CPU_OVERLOAD,
                conf,
                list(set(cpu_devices)),
                [],
                limitations,
            )

        # 7. Check for Latency Spike / Link Congestion / Upstream Congestion
        # (e.g. Organizer latency_spike sample: latency 150-300ms, jitter 30-70ms, util 60-75%, drops 10-50)
        spike_devices = []
        for rec in telemetry_records:
            dev = rec.get("device_id") or rec.get("device") or "unknown"
            metrics = rec.get("metrics", rec)
            lat = float(metrics.get("latency_ms") or 0.0)
            jit = float(metrics.get("jitter_ms") or 0.0)
            util = float(metrics.get("link_utilization_pct") or 0.0)
            drops = int(metrics.get("queue_drops") or 0)

            lat_trip = lat >= (OrganizerSnapshotThresholds.LATENCY_CRIT_MS if is_snapshot else DynamicThresholds.LATENCY_WARN_MS)
            jit_trip = jit >= (OrganizerSnapshotThresholds.JITTER_CRIT_MS if is_snapshot else DynamicThresholds.JITTER_WARN_MS)
            util_trip = util >= (OrganizerSnapshotThresholds.LINK_UTILIZATION_CRIT_PCT if is_snapshot else DynamicThresholds.LINK_UTILIZATION_WARN_PCT)
            drops_trip = drops >= (OrganizerSnapshotThresholds.QUEUE_DROPS_CRIT if is_snapshot else DynamicThresholds.QUEUE_DROPS_WARN)

            if lat_trip or (util_trip and drops_trip) or jit_trip:
                spike_devices.append(dev)

        if spike_devices:
            # Latency spike scenario:
            # Must yield link_congestion and upstream_congestion as ranked ambiguous alternatives with stated discriminating test!
            aff_devs = list(set(spike_devices))

            base_conf_link = 0.82 if not is_snapshot else 0.72
            base_conf_upstream = 0.76 if not is_snapshot else 0.65

            if not topology_available:
                base_conf_upstream = 0.40  # Marked unverifiable

            alt_upstream = {
                "cause": SIGNATURE_REGISTRY[HypothesisKey.UPSTREAM_CONGESTION].title,
                "confidence": round(base_conf_upstream, 2),
                "discriminating_test": "Query egress queue drops and interface utilization on upstream transit hops vs local interface counters.",
            }
            if not topology_available:
                alt_upstream["status"] = "unverifiable"

            return (
                HypothesisKey.LINK_CONGESTION,
                round(base_conf_link, 2),
                aff_devs,
                [alt_upstream],
                limitations,
            )

        # 8. Check for Normal / Benign operation
        is_normal = True
        for rec in telemetry_records:
            metrics = rec.get("metrics", rec)
            lat = float(metrics.get("latency_ms") or 0.0)
            loss = float(metrics.get("packet_loss_pct") or 0.0)
            cpu = float(metrics.get("cpu_utilization_pct") or metrics.get("cpu_pct") or 0.0)
            util = float(metrics.get("link_utilization_pct") or 0.0)
            drops = int(metrics.get("queue_drops") or 0)

            if lat > 30.0 or loss > 0.05 or cpu > 50.0 or util > 60.0 or drops > 0:
                is_normal = False
                break

        if is_normal:
            return (
                HypothesisKey.NO_FAULT,
                0.95 if not is_snapshot else 0.88,
                [],
                [],
                limitations,
            )

        # 9. Fallback Unknown / Insufficient Evidence
        return (
            HypothesisKey.UNKNOWN,
            0.0,
            [],
            [],
            ["observed metrics ambiguous or lack multi-point corroboration", *limitations],
        )
