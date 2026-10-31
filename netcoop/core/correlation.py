"""Deterministic offline correlation engine and hypothesis evaluation matrix."""

from typing import Dict, List, Optional, Tuple
from netcoop.core.envelope import Observation
from netcoop.core.evidence import DiagnosticHypothesis, EvidenceItem, UncertaintyEvaluation


class OfflineCorrelationEngine:
    """Evaluates multi-agent empirical observations against deterministic network fault models.

    Strict rule: Never claim an exact root cause when evidence is insufficient.
    """

    # Minimum confidence threshold to accept a diagnosis
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
                    reasons=["No observations reported across any agent domain."],
                    missing_evidence=[
                        "telemetry:interface_counters",
                        "topology:link_state",
                        "config:running_config",
                        "logs:syslog",
                    ],
                ),
            )

        # Build index of observations by entity and category
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

        # Test candidate fault models
        candidate_hypotheses: List[DiagnosticHypothesis] = []

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

        # Sort candidates by final confidence descending
        candidate_hypotheses.sort(key=lambda h: h.final_confidence, reverse=True)

        if not candidate_hypotheses:
            # Anomalies exist but match no conclusive pattern
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
            supporting_evidence=[
                e for e in evidence if e.source_agent in provided_domains
            ],
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

        # Also requires verification that config didn't change
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
