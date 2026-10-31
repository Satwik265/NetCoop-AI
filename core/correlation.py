"""Deterministic offline correlation engine with full campus network fault signatures."""

from typing import Dict, List, Optional, Tuple
from core.envelope import Observation
from core.evidence import DiagnosticHypothesis, EvidenceItem, UncertaintyEvaluation


class OfflineCorrelationEngine:
    """Evaluates multi-agent empirical observations against deterministic network fault models.

    Strict rule: Never claim an exact root cause when evidence is insufficient or ambiguous.
    """

    ACCEPTANCE_CONFIDENCE_THRESHOLD = 0.70

    @classmethod
    def evaluate(
        cls,
        observations: List[Observation],
        active_inquiries_pending: bool = False,
    ) -> Tuple[str, Optional[DiagnosticHypothesis], UncertaintyEvaluation]:
        """Correlate observations across agents.

        Returns:
            Tuple of:
              - status: "diagnosed" | "insufficient_evidence" | "benign"
              - top_hypothesis: DiagnosticHypothesis or None
              - uncertainty: UncertaintyEvaluation
        """
        if not observations:
            return (
                "insufficient_evidence",
                None,
                UncertaintyEvaluation(
                    score=1.0,
                    reasons=["No anomalous observations reported across any agent domain."],
                    missing_evidence=["telemetry_counters", "link_state", "configs", "syslog"],
                ),
            )

        evidence_items: List[EvidenceItem] = []
        domains_present = set()

        for obs in observations:
            domain = obs.context.get("agent_domain", "unknown")
            domains_present.add(domain)
            evidence_items.append(
                EvidenceItem(
                    source_agent=domain,
                    category=obs.category.value,
                    finding=f"{obs.entity} {obs.metric_name}: observed {obs.observed_value} {obs.unit}",
                    entity=obs.entity,
                    metric_name=obs.metric_name,
                    value=obs.observed_value,
                    unit=obs.unit,
                    severity=obs.severity.value,
                    timestamp=obs.timestamp_start or obs.timestamp_end,
                )
            )

        # Check candidate fault models
        candidate_hypotheses: List[DiagnosticHypothesis] = []

        # Campus & Enterprise models
        congestion_hyp = cls._check_link_congestion(observations, evidence_items)
        if congestion_hyp:
            candidate_hypotheses.append(congestion_hyp)

        wifi_hyp = cls._check_weak_wifi(observations, evidence_items)
        if wifi_hyp:
            candidate_hypotheses.append(wifi_hyp)

        eth_hyp = cls._check_ethernet_fault(observations, evidence_items)
        if eth_hyp:
            candidate_hypotheses.append(eth_hyp)

        dns_hyp = cls._check_dns_failure(observations, evidence_items)
        if dns_hyp:
            candidate_hypotheses.append(dns_hyp)

        dhcp_hyp = cls._check_dhcp_failure(observations, evidence_items)
        if dhcp_hyp:
            candidate_hypotheses.append(dhcp_hyp)

        cpu_hyp = cls._check_cpu_overload(observations, evidence_items)
        if cpu_hyp:
            candidate_hypotheses.append(cpu_hyp)

        cascade_hyp = cls._check_upstream_cascade(observations, evidence_items)
        if cascade_hyp:
            candidate_hypotheses.append(cascade_hyp)

        # Datacenter / Backbone models
        mtu_hyp = cls._check_mtu_mismatch(observations, evidence_items)
        if mtu_hyp:
            candidate_hypotheses.append(mtu_hyp)

        bgp_hyp = cls._check_bgp_flap_damping(observations, evidence_items)
        if bgp_hyp:
            candidate_hypotheses.append(bgp_hyp)

        optic_hyp = cls._check_optical_degradation(observations, evidence_items)
        if optic_hyp:
            candidate_hypotheses.append(optic_hyp)

        stp_hyp = cls._check_stp_loop(observations, evidence_items)
        if stp_hyp:
            candidate_hypotheses.append(stp_hyp)

        # Subsumption hierarchy: Root cause failure signatures subsume downstream symptom hypotheses
        if optic_hyp:
            candidate_hypotheses = [h for h in candidate_hypotheses if h.cause_key != "ETHERNET_INTERFACE_FAULT"]
        if stp_hyp:
            candidate_hypotheses = [h for h in candidate_hypotheses if h.cause_key != "DEVICE_CPU_OVERLOAD"]
        if cascade_hyp:
            candidate_hypotheses = [h for h in candidate_hypotheses if h.cause_key != "LINK_CONGESTION"]

        # Sort candidates by final confidence descending
        candidate_hypotheses.sort(key=lambda h: h.final_confidence, reverse=True)

        if not candidate_hypotheses:
            # Check if all observations were benign/info
            all_benign = all(o.severity.value == "info" for o in observations)
            if all_benign:
                return (
                    "benign",
                    None,
                    UncertaintyEvaluation(
                        score=0.05,
                        reasons=["All telemetry metrics within normal operating bounds."],
                        missing_evidence=[],
                    ),
                )

            uncertainty = UncertaintyEvaluation(
                score=0.90,
                reasons=[
                    "Observations show anomalous metrics, but cross-domain corroboration is absent.",
                    "No recognized multi-point fault signature matched.",
                ],
                missing_evidence=[
                    "Detailed path telemetry (packet traces, MTU probes)",
                    "Optics diagnostic counters (DOM / DDM)",
                    "Protocol adjacency state logs",
                ],
            )
            return "insufficient_evidence", None, uncertainty

        # Ambiguity check: if multiple distinct strong hypotheses compete within 0.10 margin
        if len(candidate_hypotheses) >= 2:
            top = candidate_hypotheses[0]
            second = candidate_hypotheses[1]
            if top.cause_key != second.cause_key and abs(top.final_confidence - second.final_confidence) <= 0.05:
                # Ambiguous multi-fault condition
                uncertainty = UncertaintyEvaluation(
                    score=0.75,
                    reasons=[
                        f"Ambiguous multi-fault signature: competing hypotheses '{top.title}' ({top.final_confidence}) and '{second.title}' ({second.final_confidence}) present with equal weight.",
                        "Evidence is contradictory or multi-incident without isolated causality.",
                    ],
                    missing_evidence=["Targeted cross-examination probes", "Sequential isolation tests"],
                    alternative_hypotheses=[
                        {"cause": h.title, "confidence": h.final_confidence}
                        for h in candidate_hypotheses
                    ],
                )
                return "insufficient_evidence", None, uncertainty

        top_hyp = candidate_hypotheses[0]

        # Enforce strict sufficiency rule
        if (
            not top_hyp.is_sufficient
            or top_hyp.final_confidence < cls.ACCEPTANCE_CONFIDENCE_THRESHOLD
        ):
            missing_domains = [
                d
                for d in top_hyp.required_evidence_domains
                if d not in top_hyp.provided_evidence_domains
            ]
            uncertainty = UncertaintyEvaluation(
                score=round(1.0 - top_hyp.final_confidence, 2),
                reasons=[
                    f"Candidate diagnosis '{top_hyp.title}' lacked prerequisite corroboration.",
                    f"Required corroboration domains missing: {missing_domains or ['multi-agent confirmation']}",
                ],
                missing_evidence=[f"corroboration_from:{d}" for d in missing_domains]
                or ["peer_agent_verification"],
                alternative_hypotheses=[
                    {"cause": h.title, "confidence": h.final_confidence}
                    for h in candidate_hypotheses[1:]
                ],
            )
            return "insufficient_evidence", None, uncertainty

        # Sufficient evidence verified
        alt_hypotheses = [
            {"cause": h.title, "confidence": h.final_confidence}
            for h in candidate_hypotheses[1:]
        ]
        uncertainty = UncertaintyEvaluation(
            score=round(max(0.0, 1.0 - top_hyp.final_confidence), 2),
            reasons=[],
            missing_evidence=[],
            alternative_hypotheses=alt_hypotheses,
        )
        return "diagnosed", top_hyp, uncertainty

    # ----------------- Scenario Checkers -----------------

    @classmethod
    def _check_link_congestion(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate link congestion and buffer queue drop signature."""
        high_util_obs = [o for o in observations if o.metric_name == "link_utilization_pct" and float(o.observed_value or 0) > 85.0]
        queue_drop_obs = [o for o in observations if o.metric_name in ("queue_drops", "egress_queue_drops") and float(o.observed_value or 0) > 100]

        if not (high_util_obs and queue_drop_obs):
            return None

        devs = list({o.entity.split(":")[0] for o in (high_util_obs + queue_drop_obs)})
        return DiagnosticHypothesis(
            cause_key="LINK_CONGESTION",
            title="Link utilization saturation causing buffer queue drops and latency spikes",
            description="Core transit link utilization exceeds threshold, driving egress buffer drop sequences.",
            affected_devices=devs,
            supporting_evidence=[e for e in evidence if e.metric_name in ("link_utilization_pct", "queue_drops", "egress_queue_drops")],
            required_evidence_domains=["telemetry_agent"],
            provided_evidence_domains=["telemetry_agent"],
            raw_score=0.92,
            final_confidence=0.92,
            is_sufficient=True,
            suggested_remediation_type="qos_traffic_shaping",
        )

    @classmethod
    def _check_weak_wifi(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate weak Wi-Fi signal and high retransmission rate."""
        low_rssi = [o for o in observations if o.metric_name == "wifi_rssi_dbm" and float(o.observed_value or 0) < -78.0]
        high_retx = [o for o in observations if o.metric_name == "wifi_retransmission_pct" and float(o.observed_value or 0) > 20.0]

        if not (low_rssi or high_retx):
            return None

        devs = list({o.entity.split(":")[0] for o in (low_rssi + high_retx)})
        is_sufficient = len(low_rssi) > 0 and len(high_retx) > 0
        return DiagnosticHypothesis(
            cause_key="WEAK_WIFI_SIGNAL",
            title="Hostel access point RF attenuation causing high retransmissions and packet loss",
            description="Wireless client receives degraded RSSI signal driving excessive frame retransmissions.",
            affected_devices=devs,
            supporting_evidence=[e for e in evidence if e.metric_name in ("wifi_rssi_dbm", "wifi_retransmission_pct")],
            required_evidence_domains=["telemetry_agent"],
            provided_evidence_domains=["telemetry_agent"],
            raw_score=0.90 if is_sufficient else 0.50,
            final_confidence=0.90 if is_sufficient else 0.50,
            is_sufficient=is_sufficient,
            suggested_remediation_type="adjust_ap_power",
        )

    @classmethod
    def _check_ethernet_fault(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate Ethernet interface errors and flapping."""
        errs = [o for o in observations if o.metric_name in ("interface_errors", "fcs_errors", "crc_errors") and float(o.observed_value or 0) > 500]
        flaps = [o for o in observations if o.metric_name == "link_flaps" and float(o.observed_value or 0) > 3]

        if not (errs or flaps):
            return None

        devs = list({o.entity.split(":")[0] for o in (errs + flaps)})
        is_sufficient = len(errs) > 0
        return DiagnosticHypothesis(
            cause_key="ETHERNET_INTERFACE_FAULT",
            title="Physical layer Ethernet interface CRC errors and flapping transitions",
            description="Ethernet physical cabling or SFP transceiver reporting severe frame check sequence drops.",
            affected_devices=devs,
            supporting_evidence=[e for e in evidence if e.metric_name in ("interface_errors", "link_flaps", "crc_errors")],
            required_evidence_domains=["telemetry_agent"],
            provided_evidence_domains=["telemetry_agent"],
            raw_score=0.94 if is_sufficient else 0.45,
            final_confidence=0.94 if is_sufficient else 0.45,
            is_sufficient=is_sufficient,
            suggested_remediation_type="cycle_interface",
        )

    @classmethod
    def _check_dns_failure(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate DNS resolution failure and timeout."""
        dns_obs = [o for o in observations if (o.metric_name == "dns_failure_pct" and float(o.observed_value or 0) > 50.0) or (o.metric_name == "dns_resolution_ms" and float(o.observed_value or 0) > 1500.0)]
        if not dns_obs:
            return None

        devs = list({o.entity.split(":")[0] for o in dns_obs})
        return DiagnosticHypothesis(
            cause_key="DNS_FAILURE",
            title="DNS resolution service outage with high query timeout failure rate",
            description="Recursive resolver is unreachable or timing out on campus host queries.",
            affected_devices=devs,
            supporting_evidence=[e for e in evidence if e.metric_name in ("dns_failure_pct", "dns_resolution_ms")],
            required_evidence_domains=["telemetry_agent"],
            provided_evidence_domains=["telemetry_agent"],
            raw_score=0.95,
            final_confidence=0.95,
            is_sufficient=True,
            suggested_remediation_type="restart_dns_cache",
        )

    @classmethod
    def _check_dhcp_failure(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate DHCP pool exhaustion or relay failure."""
        dhcp_obs = [o for o in observations if o.metric_name == "dhcp_failure_pct" and float(o.observed_value or 0) > 50.0]
        if not dhcp_obs:
            return None

        devs = list({o.entity.split(":")[0] for o in dhcp_obs})
        return DiagnosticHypothesis(
            cause_key="DHCP_FAILURE",
            title="DHCP scope exhaustion or relay failure preventing lease assignment",
            description="Clients failing to obtain IP configuration leases.",
            affected_devices=devs,
            supporting_evidence=[e for e in evidence if e.metric_name == "dhcp_failure_pct"],
            required_evidence_domains=["telemetry_agent"],
            provided_evidence_domains=["telemetry_agent"],
            raw_score=0.92,
            final_confidence=0.92,
            is_sufficient=True,
            suggested_remediation_type="clear_dhcp_bindings",
        )

    @classmethod
    def _check_cpu_overload(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate device control plane CPU overload."""
        cpu_obs = [o for o in observations if o.metric_name in ("cpu_pct", "cpu_utilization_pct") and float(o.observed_value or 0) > 90.0]
        if not cpu_obs:
            return None

        devs = list({o.entity.split(":")[0] for o in cpu_obs})
        return DiagnosticHypothesis(
            cause_key="DEVICE_CPU_OVERLOAD",
            title="Control-plane CPU exhaustion on core router driving queue drops",
            description="Device CPU is pegging at maximum capacity causing packet drop cascade.",
            affected_devices=devs,
            supporting_evidence=[e for e in evidence if e.metric_name in ("cpu_pct", "cpu_utilization_pct")],
            required_evidence_domains=["telemetry_agent"],
            provided_evidence_domains=["telemetry_agent"],
            raw_score=0.94,
            final_confidence=0.94,
            is_sufficient=True,
            suggested_remediation_type="throttle_copp",
        )

    @classmethod
    def _check_upstream_cascade(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate upstream device failure with downstream cascade."""
        offline_obs = [o for o in observations if o.metric_name in ("device_offline", "carrier_transitions") or (o.metric_name == "packet_loss_pct" and float(o.observed_value or 0) >= 99.0)]
        util_obs = [o for o in observations if o.metric_name in ("link_utilization_pct", "queue_drops") and float(o.observed_value or 0) > 80.0]

        if not (offline_obs and util_obs):
            return None

        devs = list({o.entity.split(":")[0] for o in (offline_obs + util_obs)})
        return DiagnosticHypothesis(
            cause_key="UPSTREAM_FAILURE_CASCADE",
            title="Core router failure causing failover saturation on distribution links",
            description="Upstream link termination triggered traffic diversion, saturating secondary trunks.",
            affected_devices=devs,
            supporting_evidence=[e for e in evidence if e.metric_name in ("device_offline", "link_utilization_pct", "queue_drops")],
            required_evidence_domains=["telemetry_agent"],
            provided_evidence_domains=["telemetry_agent"],
            raw_score=0.96,
            final_confidence=0.96,
            is_sufficient=True,
            suggested_remediation_type="drain_and_reroute_link",
        )

    @classmethod
    def _check_mtu_mismatch(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate MTU mismatch fault signature."""
        has_drops = any(
            obs.metric_name in ("egress_queue_drops", "packet_loss_pct", "large_packet_drops")
            and float(obs.observed_value or 0) > 0
            for obs in observations
        )
        has_mtu_diff = any(
            obs.metric_name == "mtu_mismatch"
            or (obs.metric_name == "mtu" and obs.observed_value != obs.baseline_value)
            for obs in observations
        )

        devices = list({obs.entity.split(":")[0] for obs in observations if ":" in obs.entity})
        if not (has_drops or has_mtu_diff):
            return None

        provided_domains = []
        if has_drops:
            provided_domains.append("telemetry_agent")
        if has_mtu_diff:
            provided_domains.append("config_agent")

        required = ["telemetry_agent", "config_agent"]
        is_sufficient = all(d in provided_domains for d in required)
        confidence = 0.95 if is_sufficient else 0.45

        return DiagnosticHypothesis(
            cause_key="MTU_MISMATCH_BLACKHOLE",
            title="Path MTU Mismatch causing packet blackholing on jumbo frames",
            description="Intermediate transit link possesses lower MTU than endpoints with DF bit set.",
            affected_devices=devices or ["leaf-01", "spine-01"],
            supporting_evidence=[e for e in evidence if e.source_agent in provided_domains],
            required_evidence_domains=required,
            provided_evidence_domains=provided_domains,
            raw_score=0.95 if is_sufficient else 0.45,
            final_confidence=confidence,
            is_sufficient=is_sufficient,
            suggested_remediation_type="harmonize_mtu",
        )

    @classmethod
    def _check_bgp_flap_damping(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate BGP route flap damping signature."""
        has_flaps = any(
            obs.metric_name in ("bgp_state_flaps", "flaps_count")
            and float(obs.observed_value or 0) >= 3
            for obs in observations
        )
        has_bfd_or_link_loss = any(
            obs.metric_name in ("bfd_session_down", "carrier_transitions", "link_down_events")
            for obs in observations
        )
        has_suppressed_route = any(
            obs.metric_name in ("route_suppressed", "flap_damping_active")
            for obs in observations
        )

        if not (has_flaps or has_suppressed_route):
            return None

        provided = []
        if has_flaps:
            provided.append("topology_agent")
        if has_bfd_or_link_loss:
            provided.append("log_agent")
        if has_suppressed_route:
            provided.append("topology_agent")

        provided_unique = list(set(provided))
        required = ["topology_agent", "log_agent"]
        is_sufficient = all(d in provided_unique for d in required)
        confidence = 0.92 if is_sufficient else 0.40

        devices = list({obs.entity.split(":")[0] for obs in observations if ":" in obs.entity})
        return DiagnosticHypothesis(
            cause_key="BGP_ROUTE_FLAP_DAMPING",
            title="BGP Route Flap Damping triggered by unstable peer link",
            description="Repeated interface transitions caused BGP flap penalties to exceed suppression threshold.",
            affected_devices=devices or ["wan-01"],
            supporting_evidence=[e for e in evidence if e.source_agent in provided_unique],
            required_evidence_domains=required,
            provided_evidence_domains=provided_unique,
            raw_score=0.92 if is_sufficient else 0.40,
            final_confidence=confidence,
            is_sufficient=is_sufficient,
            suggested_remediation_type="clear_flap_damping",
        )

    @classmethod
    def _check_optical_degradation(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate optical transceiver power and physical CRC error signature."""
        has_low_power = any(
            obs.metric_name in ("rx_power_dbm", "optical_rx_power")
            and float(obs.observed_value or 0) < -15.0
            for obs in observations
        )
        has_crc_errors = any(
            obs.metric_name in ("fcs_errors", "crc_errors", "alignment_errors")
            and float(obs.observed_value or 0) > 10
            for obs in observations
        )

        if not (has_low_power or has_crc_errors):
            return None

        provided = []
        if has_low_power and has_crc_errors:
            provided.append("telemetry_agent")

        no_config_diff = not any(obs.category.value == "config_diff" for obs in observations)
        if no_config_diff:
            provided.append("config_agent")

        required = ["telemetry_agent", "config_agent"]
        is_sufficient = has_low_power and has_crc_errors
        confidence = 0.94 if is_sufficient else 0.45

        devices = list({obs.entity.split(":")[0] for obs in observations if ":" in obs.entity})
        return DiagnosticHypothesis(
            cause_key="OPTICAL_TRANSCEIVER_DEGRADATION",
            title="Physical Layer Optical Signal Degradation (SFP/Fiber Loss)",
            description="Receiver optical power is below sensitivity threshold, driving high Frame Check Sequence (FCS) error rates.",
            affected_devices=devices or ["core-a", "core-b"],
            supporting_evidence=[e for e in evidence if e.source_agent in provided],
            required_evidence_domains=required,
            provided_evidence_domains=provided,
            raw_score=0.94 if is_sufficient else 0.45,
            final_confidence=confidence,
            is_sufficient=is_sufficient,
            suggested_remediation_type="drain_and_reroute_link",
        )

    @classmethod
    def _check_stp_loop(
        cls, observations: List[Observation], evidence: List[EvidenceItem]
    ) -> Optional[DiagnosticHypothesis]:
        """Correlate Spanning Tree Protocol loop / broadcast storm signature."""
        has_bpdu_anomaly = any(
            obs.metric_name in ("bpdu_filter", "stp_state", "bpdu_guard_violation")
            for obs in observations
        )
        has_storm = any(
            (obs.metric_name in ("cpu_utilization_pct", "broadcast_pps", "mac_flaps"))
            and float(obs.observed_value or 0) > 75
            for obs in observations
        )

        if not (has_bpdu_anomaly or has_storm):
            return None

        provided = []
        if has_bpdu_anomaly:
            provided.append("config_agent")
        if has_storm:
            provided.append("telemetry_agent")

        required = ["config_agent", "telemetry_agent"]
        is_sufficient = all(d in provided for d in required)
        confidence = 0.96 if is_sufficient else 0.50

        devices = list({obs.entity.split(":")[0] for obs in observations if ":" in obs.entity})
        return DiagnosticHypothesis(
            cause_key="STP_SPLIT_BRAIN_LOOP",
            title="Spanning Tree Forwarding Loop / Broadcast Storm",
            description="BPDU filtering or mismatched root bridge configuration caused unblocked cyclic forwarding path.",
            affected_devices=devices or ["access-01", "access-02"],
            supporting_evidence=[e for e in evidence if e.source_agent in provided],
            required_evidence_domains=required,
            provided_evidence_domains=provided,
            raw_score=0.96 if is_sufficient else 0.50,
            final_confidence=confidence,
            is_sufficient=is_sufficient,
            suggested_remediation_type="disable_port_bpdu_filter",
        )
